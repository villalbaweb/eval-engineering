from __future__ import annotations

import json
import re

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader


@register_grader("json_schema")
class JsonSchemaGrader(Grader):
    """Final answer must be valid JSON (optionally inside a ```json fence) with the required keys.

    args: required_keys: list[str]
    """

    description = "Final answer is valid JSON containing args.required_keys."

    def grade(self, ctx: GradeContext) -> GradeResult:
        text = ctx.transcript.final_answer.strip()
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if m:
            text = m.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return self.passed(False, f"not valid JSON: {e.msg}")
        keys = self.args.get("required_keys", [])
        missing = [k for k in keys if not isinstance(data, dict) or k not in data]
        return self.passed(not missing, f"missing keys: {missing}" if missing else "valid JSON", missing=missing)
