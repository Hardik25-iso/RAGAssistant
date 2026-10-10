from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.database import Base
from app.models.base import IdMixin

EMBED_DIM = get_settings().EMBED_DIM


class Chunk(IdMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (Index("ix_chunks_owner_subject", "owner_id", "subject_id"),)

    doc_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    # owner_id and subject_id are copied onto every chunk so the vector search
    # can always be filtered by owner (student data isolation)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    page_or_slide: Mapped[int] = mapped_column(Integer)
    # pgvector on PostgreSQL; plain JSON list on SQLite (local tests)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM).with_variant(JSON(), "sqlite"))
