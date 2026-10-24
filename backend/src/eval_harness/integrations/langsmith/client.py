from __future__ import annotations

import logging
from functools import lru_cache

from langsmith import Client

from eval_harness.core.settings import get_settings

log = logging.getLogger(__name__)


def enabled() -> bool:
    """LangSmith features are active only with an API key and tracing switched on."""
    return get_settings().langsmith_enabled


@lru_cache
def get_client() -> Client:
    return Client()


def safe(fn):
    """Decorator: LangSmith problems must never break an experiment."""

    def wrapper(*a, **kw):
        if not enabled():
            return None
        try:
            return fn(*a, **kw)
        except Exception as e:  # noqa: BLE001
            log.warning("LangSmith %s failed: %s: %s", fn.__name__, type(e).__name__, e)
            return None

    wrapper.__name__ = fn.__name__
    return wrapper
