"""Quality gates for candidate tasks: PII scrub, near-duplicate removal, label-leak check."""

from __future__ import annotations

import re

from eval_harness.evals.domain.task import Task

PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<EMAIL>"),
    (re.compile(r"\b(?:sk|lsv\d?|tvly|pk|ghp|xox[abp])[-_][A-Za-z0-9_\-]{12,}\b"), "<API_KEY>"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "<CARD_NUMBER>"),
    (re.compile(r"\b\+?\d{1,2}[ .-]?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b"), "<PHONE>"),
]


def scrub_pii(text: str) -> str:
    for rx, repl in PII:
        text = rx.sub(repl, text)
    return text


def scrub_task(task: Task) -> Task:
    msgs = [{**m, "content": scrub_pii(m["content"]) if isinstance(m.get("content"), str) else m.get("content")}
            for m in task.input.get("messages", [])]
    return task.model_copy(update={"input": {**task.input, "messages": msgs}})


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def dedupe(new: list[Task], existing: list[Task] | None = None, threshold: float = 0.8) -> tuple[list[Task], list[str]]:
    """Drop tasks whose user text is a near-duplicate of an earlier/existing one."""
    kept: list[Task] = []
    dropped: list[str] = []
    pool = [t.user_text for t in (existing or [])]
    for t in new:
        text = t.user_text
        if any(jaccard(text, p) >= threshold for p in pool):
            dropped.append(t.id)
            continue
        kept.append(t)
        pool.append(text)
    return kept, dropped


def leaks(task: Task) -> list[str]:
    """Expected strings that already appear in the input (the task would be trivially solvable)."""
    e, text = task.expected, task.user_text.lower()
    secrets = [*e.answer_contains, *(e.reference_answer.split(". ") if e.reference_answer else [])]
    return [s for s in secrets if len(s) > 12 and s.lower() in text]


def diversity(tasks: list[Task], dims: list[str]) -> dict[str, dict[str, int]]:
    """Counts per dimension value (stored in task.metadata['dims'] by the generators)."""
    out: dict[str, dict[str, int]] = {d: {} for d in dims}
    for t in tasks:
        for d in dims:
            v = str(t.metadata.get("dims", {}).get(d, "?"))
            out[d][v] = out[d].get(v, 0) + 1
    return out
