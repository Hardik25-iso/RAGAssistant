"""Rate limiting with slowapi.

Authenticated requests are limited per user, anonymous ones per client IP.
Behind Nginx/ALB the real client IP is taken from X-Forwarded-For (first hop),
which Nginx sets from the ALB header.
Note: the counter store is in-memory per worker, so the effective limit is
per instance and worker. Moving storage to Redis (ElastiCache) would make it global.
"""
import jwt
from fastapi import Request
from slowapi import Limiter

from app.config import get_settings
from app.security.jwt_handler import decode_token

settings = get_settings()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            return "user:" + decode_token(auth[7:], "access")["sub"]
        except jwt.PyJWTError:
            pass
    return "ip:" + client_ip(request)


limiter = Limiter(
    key_func=rate_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=False,
)
