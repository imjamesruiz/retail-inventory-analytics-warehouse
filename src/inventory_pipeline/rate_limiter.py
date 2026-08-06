"""Simple call-spacing rate limiter.

Ported from src/utils/rateLimiter.ts. The Node original tracked concurrency
because the bot polled many products in parallel; this pipeline extracts
sequentially, so this keeps only the piece that matters here: a minimum
delay enforced between consecutive calls to a given source.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RateLimiter:
    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds
        self._last_call: float | None = None

    def run(self, fn: Callable[[], T]) -> T:
        if self._last_call is not None:
            elapsed = time.monotonic() - self._last_call
            wait = self._delay_seconds - elapsed
            if wait > 0:
                time.sleep(wait)
        try:
            return fn()
        finally:
            self._last_call = time.monotonic()
