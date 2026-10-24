from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from eval_harness.tools.base import register_tool


@register_tool(replayable=False, tags=("utility",))
@tool
def current_datetime(timezone: str = "UTC") -> str:
    """Return the current date and time in an IANA timezone such as 'UTC' or 'America/Mexico_City'."""
    try:
        if timezone.upper() == "UTC":  # works even where the tz database (tzdata) is missing
            return datetime.now(UTC).isoformat(timespec="seconds")
        return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")
    except Exception:
        return f"ERROR: unknown timezone '{timezone}'. Use an IANA name such as 'UTC'."
