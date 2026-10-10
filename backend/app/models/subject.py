from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import CreatedMixin, IdMixin


class Subject(IdMixin, CreatedMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_subject_owner_name"),)

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
