from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.aws.s3_storage import get_storage
from app.database import get_db
from app.models.document import Document
from app.models.subject import Subject
from app.models.user import User
from app.schemas.subject import SubjectIn, SubjectOut
from app.security.audit import audit
from app.security.rbac import require_student

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


def get_owned_subject(db: Session, subject_id: str, user: User) -> Subject:
    """Ownership check: another student's subject is reported as 404, not 403,
    so its existence is not revealed."""
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.owner_id == user.id).first()
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    return subject


def _out(subject: Subject, count: int) -> SubjectOut:
    out = SubjectOut.model_validate(subject)
    out.document_count = count
    return out


@router.get("", response_model=list[SubjectOut])
def list_subjects(user: User = Depends(require_student), db: Session = Depends(get_db)):
    rows = (
        db.query(Subject, func.count(Document.id))
        .outerjoin(Document, Document.subject_id == Subject.id)
        .filter(Subject.owner_id == user.id)
        .group_by(Subject.id)
        .order_by(Subject.created_at)
        .all()
    )
    return [_out(s, c) for s, c in rows]


def _ensure_unique(db: Session, user: User, name: str, exclude_id: str | None = None) -> None:
    q = db.query(Subject).filter(Subject.owner_id == user.id, func.lower(Subject.name) == name.lower())
    if exclude_id:
        q = q.filter(Subject.id != exclude_id)
    if q.first():
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a subject with this name")


@router.post("", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    if db.query(Subject).filter(Subject.owner_id == user.id).count() >= 30:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Subject limit reached (30)")
    _ensure_unique(db, user, body.name)
    subject = Subject(owner_id=user.id, name=body.name)
    db.add(subject)
    db.commit()
    return _out(subject, 0)


@router.patch("/{subject_id}", response_model=SubjectOut)
def rename_subject(
    subject_id: str, body: SubjectIn, user: User = Depends(require_student), db: Session = Depends(get_db)
):
    subject = get_owned_subject(db, subject_id, user)
    _ensure_unique(db, user, body.name, exclude_id=subject.id)
    subject.name = body.name
    db.commit()
    count = db.query(Document).filter(Document.subject_id == subject.id).count()
    return _out(subject, count)


@router.delete("/{subject_id}", status_code=204)
def delete_subject(
    subject_id: str, request: Request, user: User = Depends(require_student), db: Session = Depends(get_db)
):
    subject = get_owned_subject(db, subject_id, user)
    storage = get_storage()
    for doc in db.query(Document).filter(Document.subject_id == subject.id).all():
        storage.delete(doc.s3_key)
        db.delete(doc)
    db.delete(subject)
    db.commit()
    audit(db, "delete_subject", user_id=user.id, resource=subject_id, request=request)
