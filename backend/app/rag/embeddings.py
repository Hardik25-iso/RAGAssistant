"""Text embeddings.

gemini: gemini-embedding-001 via REST, truncated to EMBED_DIM (768) dimensions,
        batched EMBED_BATCH_SIZE texts per request. Document ingestion runs in the
        background, so on a 429 it waits for the delay Gemini asks for and retries
        (free-tier rate limit); query embeddings use the normal fast-fail policy.
fake:   deterministic hashed bag-of-words vectors, for tests and load tests
        (no API calls, no cost).
"""
import hashlib
import logging
import math
import re
import time

import httpx

from app.config import get_settings
from app.errors import ProviderUnavailableError
from app.rag.resilience import call_provider, http_timeout

log = logging.getLogger(__name__)
settings = get_settings()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
DEFAULT_RATE_LIMIT_WAIT = 30.0


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _fake_embed(text: str) -> list[float]:
    vec = [0.0] * settings.EMBED_DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16)
        vec[h % settings.EMBED_DIM] += 1.0 if (h >> 12) % 2 else -1.0
    return _normalize(vec)


def _retry_delay(resp: httpx.Response) -> float:
    """Seconds Gemini asks us to wait (google.rpc.RetryInfo, e.g. "37s")."""
    try:
        for d in resp.json()["error"].get("details", []):
            if d.get("@type", "").endswith("RetryInfo"):
                return float(d["retryDelay"].rstrip("s")) + 1.0
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return DEFAULT_RATE_LIMIT_WAIT


def _gemini_batch(texts: list[str], task_type: str) -> list[list[float]]:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    model = settings.GEMINI_EMBED_MODEL
    body = {
        "requests": [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": t[:8000]}]},
                "taskType": task_type,
                "outputDimensionality": settings.EMBED_DIM,
            }
            for t in texts
        ]
    }

    def do() -> list[list[float]]:
        with httpx.Client(timeout=http_timeout()) as client:
            r = client.post(
                GEMINI_URL.format(model=model),
                json=body,
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            )
            r.raise_for_status()
            return [_normalize(e["values"]) for e in r.json()["embeddings"]]

    if task_type != "RETRIEVAL_DOCUMENT" or not settings.ENABLE_RESILIENCE:
        return call_provider("gemini-embeddings", do)

    deadline = time.monotonic() + settings.EMBED_INGEST_BUDGET_SECONDS
    while True:
        try:
            return call_provider("gemini-embeddings", do)
        except ProviderUnavailableError as exc:
            cause = exc.__cause__
            if not (isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code == 429):
                raise
            wait = _retry_delay(cause.response)
            if time.monotonic() + wait > deadline:
                raise
            log.warning("gemini embeddings rate-limited, waiting %.0fs", wait)
            time.sleep(wait)


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if settings.EMBEDDINGS_PROVIDER == "fake":
        return [_fake_embed(t) for t in texts]
    out: list[list[float]] = []
    size = settings.EMBED_BATCH_SIZE
    for i in range(0, len(texts), size):
        out.extend(_gemini_batch(texts[i:i + size], task_type))
    return out


def embed_query(text: str) -> list[float]:
    return embed_texts([text], task_type="RETRIEVAL_QUERY")[0]
