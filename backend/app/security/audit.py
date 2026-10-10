"""Audit logging: one row in audit_logs + one structured log line (shipped to CloudWatch)."""
import logging

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.security.rate_limiter import client_ip

log = logging.getLogger("audit")


def audit(
    db: Session,
    action: str,
    *,
    user_id: str | None = None,
    resource: str | None = None,
    request: Request | None = None,
    details: dict | None = None,
) -> None:
    ip = client_ip(request) if request else None
    try:
        db.add(AuditLog(user_id=user_id, action=action, resource=resource, ip=ip, details=details))
        db.commit()
    except Exception:  # audit must never break the request
        db.rollback()
        log.exception("failed to write audit row")
    log.info("audit action=%s user=%s resource=%s ip=%s", action, user_id, resource, ip)
