import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import QuotaExceededError
from app.models.chat import ChatSession, Message
from app.models.document import Document
from app.models.user import User
from app.rag.pipeline import answer_question
from app.rag.prompt_guard import BLOCKED_REPLY, check_prompt
from app.rag.retriever import retrieve, to_citation
from app.routers.subjects import get_owned_subject
from app.schemas.chat import AskIn, AskOut, Citation, MessageOut, SearchIn, SessionOut
from app.security.audit import audit
from app.security.rate_limiter import limiter
from app.security.rbac import require_student

router = APIRouter(prefix="/api/chat", tags=["chat"])
settings = get_settings()


def _owned_session(db: Session, session_id: str, user: User) -> ChatSession:
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.owner_id == user.id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return s


def _check_doc_ids(db: Session, doc_ids: list[str] | None, user: User, subject_id: str) -> None:
    if not doc_ids:
        return
    owned = (
        db.query(Document.id)
        .filter(Document.id.in_(doc_ids), Document.owner_id == user.id, Document.subject_id == subject_id)
        .count()
    )
    if owned != len(set(doc_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")


def _check_daily_quota(db: Session, user: User) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    used = (
        db.query(Message)
        .join(ChatSession, ChatSession.id == Message.session_id)
        .filter(ChatSession.owner_id == user.id, Message.role == "user", Message.created_at >= since)
        .count()
    )
    if used >= settings.MAX_QUERIES_PER_DAY:
        raise QuotaExceededError(f"Daily question limit reached ({settings.MAX_QUERIES_PER_DAY}). Try again tomorrow.")


@router.post("/ask", response_model=AskOut)
@limiter.limit(settings.RATE_LIMIT_CHAT)
def ask(request: Request, body: AskIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    start = time.perf_counter()
    subject = get_owned_subject(db, body.subject_id, user)
    _check_doc_ids(db, body.doc_ids, user, subject.id)
    _check_daily_quota(db, user)

    if body.session_id:
        session = _owned_session(db, body.session_id, user)
        if session.subject_id != subject.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Chat belongs to a different subject")
    else:
        title = " ".join(body.question.split())[:60]
        session = ChatSession(owner_id=user.id, subject_id=subject.id, title=title or "New chat")
        db.add(session)
        db.flush()

    question = body.question.strip()
    guard = check_prompt(question)
    history = [
        (m.role, m.content)
        for m in db.query(Message).filter(Message.session_id == session.id).order_by(Message.created_at).all()
    ]
    db.add(Message(session_id=session.id, role="user", content=question))

    if guard.blocked:
        answer_text, citations, provider = BLOCKED_REPLY, [], None
        audit(db, "prompt_blocked", user_id=user.id, resource=session.id, request=request,
              details={"reason": guard.reason})
    else:
        result = answer_question(
            db, owner_id=user.id, subject_id=subject.id, question=question,
            doc_ids=body.doc_ids, history=history,
        )
        answer_text, citations, provider = result.text, result.citations, result.provider

    db.add(
        Message(
            session_id=session.id,
            role="assistant",
            content=answer_text,
            citations=[c.model_dump() for c in citations],
        )
    )
    session.updated_at = datetime.now(timezone.utc)
    db.commit()

    latency = int((time.perf_counter() - start) * 1000)
    if not guard.blocked:
        audit(db, "chat_query", user_id=user.id, resource=session.id, request=request,
              details={"latency_ms": latency, "sources": len(citations), "provider": provider})
    return AskOut(session_id=session.id, answer=answer_text, citations=citations,
                  blocked=guard.blocked, latency_ms=latency)


@router.post("/search", response_model=list[Citation])
@limiter.limit("60/minute")
def search_notes(request: Request, body: SearchIn, user: User = Depends(require_student),
                 db: Session = Depends(get_db)):
    """Retrieval only (no LLM): find the slides/pages most related to a query."""
    subject = get_owned_subject(db, body.subject_id, user)
    _check_doc_ids(db, body.doc_ids, user, subject.id)
    hits = retrieve(db, owner_id=user.id, subject_id=subject.id, question=body.query, doc_ids=body.doc_ids)
    return [to_citation(h) for h in hits]


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(subject_id: str, user: User = Depends(require_student), db: Session = Depends(get_db)):
    get_owned_subject(db, subject_id, user)
    return (
        db.query(ChatSession)
        .filter(ChatSession.owner_id == user.id, ChatSession.subject_id == subject_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(100)
        .all()
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def session_messages(session_id: str, user: User = Depends(require_student), db: Session = Depends(get_db)):
    session = _owned_session(db, session_id, user)
    return db.query(Message).filter(Message.session_id == session.id).order_by(Message.created_at).all()


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, user: User = Depends(require_student), db: Session = Depends(get_db)):
    session = _owned_session(db, session_id, user)
    db.delete(session)
    db.commit()
