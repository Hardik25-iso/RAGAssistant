"""Application settings.

Values come from environment variables (or a local .env file in development).
In production on EC2, secrets are pulled from AWS SSM Parameter Store at
startup (see app/aws/ssm_config.py) so nothing secret lives in Git or on disk.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- general ---
    APP_NAME: str = "StudyRAG"
    ENVIRONMENT: str = "development"  # development | production | test
    LOG_LEVEL: str = "INFO"

    # --- database ---
    DATABASE_URL: str = "sqlite:///./studyrag.db"

    # --- auth ---
    JWT_SECRET: str = "change-me-in-production-please-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 7
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None

    # --- AWS ---
    AWS_REGION: str = "ap-south-1"
    USE_SSM: bool = False
    SSM_PREFIX: str = "/studyrag/"
    STORAGE_BACKEND: str = "local"  # local | s3
    S3_BUCKET: str | None = None
    LOCAL_STORAGE_DIR: str = "./data/uploads"
    PRESIGNED_URL_SECONDS: int = 300

    # --- AI providers ---
    EMBEDDINGS_PROVIDER: str = "gemini"  # gemini | fake
    GEMINI_API_KEY: str | None = None
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"
    EMBED_DIM: int = 768
    # Gemini's free tier counts every text in a batch as one request (~100/min),
    # so ingestion sends small batches and waits out 429s instead of failing.
    EMBED_BATCH_SIZE: int = 20
    EMBED_INGEST_BUDGET_SECONDS: float = 600.0

    LLM_PROVIDER: str = "groq"  # groq | gemini | fake
    LLM_FALLBACK_PROVIDER: str | None = "gemini"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"
    LLM_TIMEOUT_SECONDS: float = 15.0
    LLM_MAX_TOKENS: int = 1024

    # --- resilience (toggle for the before/after experiment) ---
    ENABLE_RESILIENCE: bool = True
    RETRY_ATTEMPTS: int = 3
    PROVIDER_BUDGET_SECONDS: float = 20.0
    # Fault injection for the error-handling experiment: primary LLM always returns 503
    CHAOS_FAIL_PRIMARY_LLM: bool = False

    # --- RAG ---
    CHUNK_TOKENS: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5

    # --- limits / abuse control ---
    MAX_UPLOAD_MB: int = 20
    MAX_DOCS_PER_USER: int = 50
    MAX_STORAGE_MB_PER_USER: int = 300
    MAX_QUERIES_PER_DAY: int = 200
    MAX_QUESTION_CHARS: int = 1000
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"
    RATE_LIMIT_CHAT: str = "20/minute"
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_ENABLED: bool = True

    # --- web ---
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.USE_SSM:
        from app.aws.ssm_config import load_ssm_overrides

        overrides = load_ssm_overrides(settings.SSM_PREFIX, settings.AWS_REGION)
        settings = Settings(**{**settings.model_dump(), **overrides})
    if settings.ENVIRONMENT == "production" and settings.JWT_SECRET.startswith("change-me"):
        raise RuntimeError("JWT_SECRET must be set in production")
    return settings
