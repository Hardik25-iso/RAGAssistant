"""Central error handling.

Every error leaves the API as JSON {"detail": ..., "request_id": ...}.
Internal details (stack traces, SQL, provider responses) are logged, never
returned to the client.
"""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import OperationalError

log = logging.getLogger("errors")


class ProviderUnavailableError(Exception):
    """An external AI provider (LLM / embeddings) failed after retries."""


class QuotaExceededError(Exception):
    pass


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": _rid(request)},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid request", "errors": errors, "request_id": _rid(request)},
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": f"Too many requests ({exc.detail}). Slow down.", "request_id": _rid(request)},
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(QuotaExceededError)
    async def quota(request: Request, exc: QuotaExceededError):
        return JSONResponse(status_code=429, content={"detail": str(exc), "request_id": _rid(request)})

    @app.exception_handler(ProviderUnavailableError)
    async def provider_down(request: Request, exc: ProviderUnavailableError):
        log.warning("provider unavailable rid=%s: %s", _rid(request), exc)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "The AI service is busy right now. Please try again in a few seconds.",
                "request_id": _rid(request),
            },
            headers={"Retry-After": "10"},
        )

    @app.exception_handler(OperationalError)
    async def db_down(request: Request, exc: OperationalError):
        log.error("database error rid=%s: %s", _rid(request), exc.orig)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database temporarily unavailable", "request_id": _rid(request)},
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error rid=%s path=%s", _rid(request), request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": _rid(request)},
        )
