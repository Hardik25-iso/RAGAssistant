import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.errors import register_error_handlers
from app.routers import admin, auth, chat, documents, subjects
from app.security.headers import INSTANCE_ID, SecurityHeadersMiddleware
from app.security.rate_limiter import limiter

settings = get_settings()
logging.basicConfig(
    stream=sys.stdout,
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s [" + INSTANCE_ID + "] %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # idempotent; guarded by a Postgres advisory lock across instances
    yield


app = FastAPI(
    title="StudyRAG — Secure Study Assistant API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
register_error_handlers(app)

# Order: last added runs first. Security headers wrap everything.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # JWT travels in the Authorization header, not cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Instance-ID"],
    max_age=600,
)
app.add_middleware(SecurityHeadersMiddleware)

for r in (auth.router, subjects.router, documents.router, chat.router, admin.router):
    app.include_router(r)


@app.get("/api/health", tags=["health"])
@limiter.exempt
def health():
    """Used by the ALB target-group health check. Returns 503 if the DB is unreachable,
    so the load balancer stops sending traffic to this instance."""
    from fastapi.responses import JSONResponse

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    body = {"status": "ok" if db_ok else "degraded", "db": db_ok, "instance": INSTANCE_ID,
            "resilience": settings.ENABLE_RESILIENCE}
    return JSONResponse(body, status_code=200 if db_ok else 503)
