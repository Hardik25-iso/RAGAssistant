from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import CreatedMixin, IdMixin


class DocStatus:
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(IdMixin, CreatedMixin, Base):
    __tablename__ = "documents"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    s3_key: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(10))  # pdf | pptx
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=DocStatus.processing)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
