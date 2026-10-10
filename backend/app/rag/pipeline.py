"""Ingestion (file -> chunks -> embeddings) and answering (question -> answer + citations)."""
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.aws.s3_storage import get_storage
from app.database import SessionLocal
from app.models.document import DocStatus, Document
from app.rag.chunker import chunk_pages
from app.rag.embeddings import embed_texts
from app.rag.llm import generate
from app.rag.pdf_loader import load_pdf
from app.rag.pptx_loader import load_pptx
from app.rag.prompts import build_messages
from app.rag.retriever import retrieve, to_citation
from app.rag.vector_store import save_chunks
from app.schemas.chat import Citation

log = logging.getLogger(__name__)
MAX_CHUNKS_PER_DOC = 1500


def ingest_document(doc_id: str) -> None:
    """Runs as a FastAPI BackgroundTask after upload. Always ends in ready or failed."""
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        try:
            data = get_storage().get(doc.s3_key)
            pages = load_pdf(data) if doc.file_type == "pdf" else load_pptx(data)
            chunks = chunk_pages(pages, doc.filename)[:MAX_CHUNKS_PER_DOC]
            vectors = embed_texts([c.content for c in chunks])
            save_chunks(db, doc, [(c.page_or_slide, c.content, v) for c, v in zip(chunks, vectors, strict=False)])
            doc.pages = max(p for p, _ in pages)
            doc.status, doc.error = DocStatus.ready, None
            db.commit()
            log.info("ingested doc=%s pages=%d chunks=%d", doc.id, doc.pages, len(chunks))
        except Exception as exc:
            db.rollback()
            doc = db.get(Document, doc_id)
            if doc is not None:
                doc.status = DocStatus.failed
                # user-facing message only; full trace goes to the logs
                doc.error = str(exc)[:300] if isinstance(exc, ValueError) else "Processing failed. Try again later."
                db.commit()
            log.exception("ingestion failed doc=%s", doc_id)
    finally:
        db.close()


@dataclass
class Answer:
    text: str
    citations: list[Citation]
    provider: str | None


NO_MATERIAL = (
    "I couldn't find anything about this in the documents you selected. "
    "Check that your files have finished processing, or try different keywords."
)


def _cited_only(answer: str, citations: list[Citation]) -> list[Citation]:
    """Keep the sources the model actually cited; fall back to all retrieved ones."""
    refs = {m.strip().lower() for m in re.findall(r"\[([^\[\]]+?)\]", answer)}
    used = [c for c in citations if f"{c.filename}, {c.label}".lower() in refs]
    seen, unique = set(), []
    for c in used or citations:
        key = (c.doc_id, c.page_or_slide)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def answer_question(
    db: Session,
    *,
    owner_id: str,
    subject_id: str,
    question: str,
    doc_ids: list[str] | None,
    history: list[tuple[str, str]],
) -> Answer:
    hits = retrieve(db, owner_id=owner_id, subject_id=subject_id, question=question, doc_ids=doc_ids)
    if not hits:
        return Answer(NO_MATERIAL, [], None)
    text, provider = generate(build_messages(question, hits, history))
    citations = [to_citation(h) for h in hits]
    return Answer(text or NO_MATERIAL, _cited_only(text, citations), provider)
