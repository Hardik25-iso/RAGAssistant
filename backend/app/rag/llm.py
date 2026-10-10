"""LLM providers: Groq (primary, OpenAI-compatible API) and Gemini (backup).

With ENABLE_RESILIENCE=true a failed primary call (after retries) fails over
to the backup provider before the user sees an error.
"""
import logging

import httpx

from app.config import get_settings
from app.errors import ProviderUnavailableError
from app.rag.resilience import call_provider, http_timeout

log = logging.getLogger(__name__)
settings = get_settings()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _groq(messages: list[dict]) -> str:
    if not settings.GROQ_API_KEY:
        raise ProviderUnavailableError("GROQ_API_KEY is not configured")
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_completion_tokens": settings.LLM_MAX_TOKENS,
    }
    if settings.GROQ_MODEL.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"

    def do() -> str:
        if settings.CHAOS_FAIL_PRIMARY_LLM:  # simulated outage (experiment only)
            req = httpx.Request("POST", GROQ_URL)
            raise httpx.HTTPStatusError("chaos", request=req, response=httpx.Response(503, request=req))
        with httpx.Client(timeout=http_timeout()) as client:
            r = client.post(GROQ_URL, json=payload, headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""

    return call_provider("groq", do)


def _gemini(messages: list[dict]) -> str:
    if not settings.GEMINI_API_KEY:
        raise ProviderUnavailableError("GEMINI_API_KEY is not configured")
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": settings.LLM_MAX_TOKENS},
    }

    def do() -> str:
        with httpx.Client(timeout=http_timeout()) as client:
            r = client.post(
                GEMINI_URL.format(model=settings.GEMINI_CHAT_MODEL),
                json=payload,
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            )
            r.raise_for_status()
            parts = r.json()["candidates"][0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)

    return call_provider("gemini", do)


def _fake(messages: list[dict]) -> str:
    """Offline provider for tests / load tests: echoes the first source."""
    user = messages[-1]["content"]
    if "<source" not in user:
        return "Your uploaded material doesn't cover this."
    first = user.split("<source", 1)[1]
    ref = first.split('ref="', 1)[1].split('"', 1)[0]
    body = first.split(">", 1)[1].split("</source>", 1)[0].strip()
    return f"Based on your notes: {body[:300]} {ref}"


PROVIDERS = {"groq": _groq, "gemini": _gemini, "fake": _fake}


def generate(messages: list[dict]) -> tuple[str, str]:
    """Returns (answer, provider_used)."""
    primary = settings.LLM_PROVIDER
    try:
        return PROVIDERS[primary](messages).strip(), primary
    except ProviderUnavailableError as exc:
        backup = settings.LLM_FALLBACK_PROVIDER
        if not settings.ENABLE_RESILIENCE or not backup or backup == primary:
            raise
        log.warning("LLM %s failed (%s); failing over to %s", primary, exc, backup)
        return PROVIDERS[backup](messages).strip(), backup
