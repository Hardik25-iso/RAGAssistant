"""Text embeddings.

gemini: gemini-embedding-001 via REST, truncated to EMBED_DIM (768) dimensions,
        batched 100 texts per request.
fake:   deterministic hashed bag-of-words vectors, for tests and load tests
        (no API calls, no cost).
"""
import hashlib
import math
import re

import httpx

from app.config import get_settings
from app.rag.resilience import call_provider, http_timeout

settings = get_settings()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
BATCH = 100


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _fake_embed(text: str) -> list[float]:
    vec = [0.0] * settings.EMBED_DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16)
        vec[h % settings.EMBED_DIM] += 1.0 if (h >> 12) % 2 else -1.0
    return _normalize(vec)


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

    return call_provider("gemini-embeddings", do)


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if settings.EMBEDDINGS_PROVIDER == "fake":
        return [_fake_embed(t) for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        out.extend(_gemini_batch(texts[i:i + BATCH], task_type))
    return out


def embed_query(text: str) -> list[float]:
    return embed_texts([text], task_type="RETRIEVAL_QUERY")[0]
