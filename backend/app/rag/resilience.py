"""Retry/timeout policy for calls to external AI providers.

ENABLE_RESILIENCE=true  -> short timeouts, exponential backoff retries on
                           timeouts / 429 / 5xx, then a clean ProviderUnavailableError
                           (and the LLM layer fails over to the backup provider).
ENABLE_RESILIENCE=false -> one attempt with a long timeout; failures bubble up
                           as raw 500s. Used only for the "before" measurements.
"""
import logging
from collections.abc import Callable
from typing import TypeVar

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

from app.config import get_settings
from app.errors import ProviderUnavailableError

log = logging.getLogger(__name__)
settings = get_settings()
T = TypeVar("T")


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def http_timeout() -> httpx.Timeout:
    if settings.ENABLE_RESILIENCE:
        return httpx.Timeout(settings.LLM_TIMEOUT_SECONDS, connect=5.0)
    return httpx.Timeout(120.0)


def call_provider(name: str, fn: Callable[[], T]) -> T:
    if not settings.ENABLE_RESILIENCE:
        return fn()

    wrapped = retry(
        retry=retry_if_exception(_retryable),
        # give up after N attempts OR once the time budget is spent (keeps us under
        # CloudFront's 60s origin timeout even when the backup provider is also tried)
        stop=stop_after_attempt(settings.RETRY_ATTEMPTS) | stop_after_delay(settings.PROVIDER_BUDGET_SECONDS),
        wait=wait_exponential_jitter(initial=0.5, max=6),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )(fn)
    try:
        return wrapped()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:300]
        raise ProviderUnavailableError(f"{name} returned {exc.response.status_code}: {body}") from exc
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderUnavailableError(f"{name} unreachable: {exc!r}") from exc
