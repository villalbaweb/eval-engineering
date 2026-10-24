from __future__ import annotations

import uuid
from datetime import UTC, datetime


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)
