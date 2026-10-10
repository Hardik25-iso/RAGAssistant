"""Database engine, session and schema initialisation."""
import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(pool_size=5, max_overflow=5, pool_recycle=1800)

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # SQLite ignores ON DELETE CASCADE unless enabled
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


INIT_LOCK_ID = 727274  # arbitrary advisory-lock id so two instances don't race


def init_db() -> None:
    """Create extension, tables and indexes. Safe to run on every start."""
    from app import models  # noqa: F401  (registers tables)

    if settings.is_postgres:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": INIT_LOCK_ID})
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                # No HNSW index on purpose: searches are always filtered to one
                # student's subject (a few thousand chunks at most), so the btree
                # index on (owner_id, subject_id) + exact cosine scan is fast and
                # never drops results the way a post-filtered ANN index can.
                Base.metadata.create_all(bind=conn)
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": INIT_LOCK_ID})
    else:
        Base.metadata.create_all(bind=engine)
    _seed_admin()


def _seed_admin() -> None:
    if not (settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD):
        return
    from app.models.user import Role, User
    from app.security.password import hash_password

    with SessionLocal() as db:
        if db.query(User).filter(User.email == settings.ADMIN_EMAIL.lower()).first():
            return
        db.add(
            User(
                name="Administrator",
                email=settings.ADMIN_EMAIL.lower(),
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role=Role.admin,
            )
        )
        db.commit()
        log.info("Seeded admin account %s", settings.ADMIN_EMAIL)
