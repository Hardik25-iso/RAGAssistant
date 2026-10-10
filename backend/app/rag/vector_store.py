"""Chunk storage and cosine-similarity search.

SECURITY: every search is filtered by owner_id (and subject_id) inside the SQL
WHERE clause, before ranking. A student's question can never retrieve another
student's chunks, whatever the prompt says.
"""
import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.chunk import Chunk
from app.models.document import DocStatus, Document

settings = get_settings()


@dataclass
class SearchHit:
    chunk_id: str
    doc_id: str
    filename: str
    file_type: str
    page_or_slide: int
    content: str
    score: float  # cosine similarity, 1.0 = identical


def save_chunks(db: Session, doc: Document, items: list[tuple[int, str, list[float]]]) -> None:
    db.query(Chunk).filter(Chunk.doc_id == doc.id).delete()
    db.add_all(
        Chunk(
            doc_id=doc.id,
            owner_id=doc.owner_id,
            subject_id=doc.subject_id,
            page_or_slide=page,
            content=content,
            embedding=emb,
        )
        for page, content, emb in items
    )


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def search(
    db: Session,
    *,
    owner_id: str,
    subject_id: str,
    query_embedding: list[float],
    doc_ids: list[str] | None = None,
    k: int | None = None,
) -> list[SearchHit]:
    k = k or settings.TOP_K
    base = (
        db.query(Chunk, Document.filename, Document.file_type)
        .join(Document, Document.id == Chunk.doc_id)
        .filter(
            Chunk.owner_id == owner_id,  # data isolation between students
            Chunk.subject_id == subject_id,
            Document.owner_id == owner_id,
            Document.status == DocStatus.ready,
        )
    )
    if doc_ids:
        base = base.filter(Chunk.doc_id.in_(doc_ids))

    if settings.is_postgres:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        rows = base.add_columns(distance.label("distance")).order_by(distance).limit(k).all()
        scored = [(c, fn, ft, 1.0 - float(d)) for c, fn, ft, d in rows]
    else:  # SQLite (tests): rank in Python
        scored = [(c, fn, ft, _cosine(c.embedding, query_embedding)) for c, fn, ft in base.all()]
        scored.sort(key=lambda r: r[3], reverse=True)
        scored = scored[:k]

    return [
        SearchHit(c.id, c.doc_id, fn, ft, c.page_or_slide, c.content, round(score, 4))
        for c, fn, ft, score in scored
    ]
