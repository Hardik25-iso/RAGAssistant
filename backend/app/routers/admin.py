"""Admin APIs: statistics and audit logs only. No endpoint here returns
document content, chunks or chat messages."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.chat import Message
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.subject import Subject
from app.models.user import Role, User
from app.security.audit import audit
from app.security.rbac import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    by_status = dict(db.query(Document.status, func.count(Document.id)).group_by(Document.status).all())
    audit(db, "admin_view_stats", user_id=admin.id, request=request)
    return {
        "users": db.query(User).filter(User.role == Role.student).count(),
        "admins": db.query(User).filter(User.role == Role.admin).count(),
        "subjects": db.query(Subject).count(),
        "documents": db.query(Document).count(),
        "documents_by_status": by_status,
        "chunks": db.query(Chunk).count(),
        "storage_bytes": int(db.query(func.coalesce(func.sum(Document.size_bytes), 0)).scalar()),
        "questions_24h": db.query(Message).filter(Message.role == "user", Message.created_at >= since).count(),
        "failed_logins_24h": db.query(AuditLog)
        .filter(AuditLog.action == "login_failed", AuditLog.timestamp >= since)
        .count(),
        "blocked_prompts_24h": db.query(AuditLog)
        .filter(AuditLog.action == "prompt_blocked", AuditLog.timestamp >= since)
        .count(),
    }


@router.get("/users")
def users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(
            User,
            func.count(Document.id),
            func.coalesce(func.sum(Document.size_bytes), 0),
        )
        .outerjoin(Document, Document.owner_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at)
        .all()
    )
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role.value,
            "created_at": u.created_at,
            "documents": n,
            "storage_bytes": int(size),
        }
        for u, n, size in rows
    ]


@router.get("/audit-logs")
def audit_logs(
    action: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    rows = q.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "timestamp": a.timestamp,
                "user_email": email,
                "action": a.action,
                "resource": a.resource,
                "ip": a.ip,
            }
            for a, email in rows
        ],
    }
