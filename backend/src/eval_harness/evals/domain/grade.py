from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GradeResult(BaseModel):
    grader: str
    layer: int = 1  # 1 code, 2 trajectory, 3 model
    score: float | None = None  # 0..1, None when skipped
    passed: bool | None = None
    skipped: bool = False
    label: str | None = None
    rationale: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float | None = None

    @classmethod
    def skip(cls, grader: str, why: str, layer: int = 1) -> GradeResult:
        return cls(grader=grader, layer=layer, skipped=True, rationale=why)

    @classmethod
    def of(cls, grader: str, passed: bool, rationale: str = "", *, layer: int = 1,
           score: float | None = None, **details: Any) -> GradeResult:
        return cls(grader=grader, layer=layer, passed=passed,
                   score=score if score is not None else (1.0 if passed else 0.0),
                   rationale=rationale, details=details)
