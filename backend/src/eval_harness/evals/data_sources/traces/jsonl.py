from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval_harness.core.settings import get_settings
from eval_harness.evals.data_sources.traces.base import TraceAdapter, TraceRecord, register_adapter


def traffic_dir() -> Path:
    """Where simulated traffic of the active profile is written: ``data/traffic`` for the built-in
    copilot (unchanged), ``data/traffic/<profile>`` for any other agent."""
    from eval_harness.profiles import DEFAULT_PROFILE, active_profile_name

    name = active_profile_name()
    d = get_settings().data_dir / "traffic" / ("" if name == DEFAULT_PROFILE else name)
    d.mkdir(parents=True, exist_ok=True)
    return d


@register_adapter("jsonl")
class JsonlAdapter(TraceAdapter):
    """Reads TraceRecord JSON lines (what the traffic simulator writes) from a file or a folder
    (default: data/traffic). Works fully offline."""

    def fetch(self, *, limit: int = 50, source: str | None = None, errors_only: bool = False,
              path: str | None = None, **opts: Any) -> list[TraceRecord]:
        p = Path(path) if path else traffic_dir()
        files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
        out: list[TraceRecord] = []
        for f in reversed(files):
            for line in reversed(f.read_text(encoding="utf-8").splitlines()):
                if not line.strip():
                    continue
                rec = TraceRecord.model_validate(json.loads(line))
                if source and rec.source != source:
                    continue
                if errors_only and rec.status == "ok" and rec.feedback.get("thumbs") != 0:
                    continue
                out.append(rec)
                if len(out) >= limit:
                    return out
        return out
