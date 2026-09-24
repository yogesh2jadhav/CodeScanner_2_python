"""Timing helpers: every major operation logs component, operation, duration, status."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator


class Timings(dict):
    """Collects named durations (ms) for a single request/operation."""

    def total_ms(self) -> float:
        return round(sum(self.values()), 2)


@contextmanager
def timed(logger: logging.Logger, operation: str, timings: Timings | None = None) -> Iterator[None]:
    start = time.perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        ms = round((time.perf_counter() - start) * 1000, 2)
        if timings is not None:
            timings[operation] = ms
        level = logging.INFO if status == "ok" else logging.ERROR
        logger.log(level, "operation=%s duration_ms=%s status=%s", operation, ms, status)
