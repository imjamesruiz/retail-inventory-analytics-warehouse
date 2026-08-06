"""Exponential-backoff retry helper.

Ported from the original inventory-monitor bot's src/utils/retry.ts: same
default backoff schedule, same short-circuit on client errors that will
never succeed on retry (401/403/404).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from inventory_pipeline.logging_config import get_logger

logger = get_logger()

_NON_RETRYABLE_STATUSES = {401, 403, 404}


@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 5.0


def with_retry[T](fn: Callable[[], T], config: RetryConfig | None = None) -> T:
    config = config or RetryConfig()
    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(config.max_retries + 1):
        try:
            return fn()
        except Exception as err:  # noqa: BLE001 - deliberately broad, re-raised below
            last_error = err
            status = err.response.status_code if isinstance(err, httpx.HTTPStatusError) else None

            if status in _NON_RETRYABLE_STATUSES:
                raise

            if attempt == config.max_retries:
                break

            delay = min(config.base_delay_seconds * (2**attempt), config.max_delay_seconds)
            logger.warning(
                "retry_attempt",
                attempt=attempt + 1,
                max_retries=config.max_retries,
                delay_seconds=delay,
                error=str(last_error),
            )
            time.sleep(delay)

    raise last_error
