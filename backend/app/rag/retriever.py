"""Question -> top-k chunks of the current student's material, as citations."""
from sqlalchemy.orm import Session

from app.rag.embeddings import embed_query
from app.rag.vector_store import SearchHit, search
from app.schemas.chat import Citation


def label_for(file_type: str, number: int) -> str:
    return f"Slide {number}" if file_type == "pptx" else f"Page {number}"


def strip_prefix(content: str) -> str:
    # chunks are stored as "[filename]\ntext"
    return content.split("\n", 1)[1] if content.startswith("[") and "\n" in content else content


def retrieve(
    db: Session, *, owner_id: str, subject_id: str, question: str, doc_ids: list[str] | None = None
) -> list[SearchHit]:
    return search(
        db,
        owner_id=owner_id,
        subject_id=subject_id,
        query_embedding=embed_query(question),
        doc_ids=doc_ids,
    )


def to_citation(hit: SearchHit) -> Citation:
    text = " ".join(strip_prefix(hit.content).split())
    return Citation(
        doc_id=hit.doc_id,
        filename=hit.filename,
        file_type=hit.file_type,
        page_or_slide=hit.page_or_slide,
        label=label_for(hit.file_type, hit.page_or_slide),
        snippet=text[:280] + ("…" if len(text) > 280 else ""),
        score=hit.score,
    )
