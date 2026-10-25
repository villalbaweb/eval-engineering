"""Apply a profile's conventions: which tool calls are skill loads, which tool calls failed, which
answer spans are citations. Data rules first (``Conventions``); a registered hook handles the rest.

    @register_conventions_hook("my_agent")
    class MyAgentRules(ConventionsHook):
        def skill(self, name, args):  # return a skill name, or None to fall back to the rules
            ...
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, ClassVar

from eval_harness.core.registry import Registry
from eval_harness.evals.domain.profile import Conventions, SkillRule, ToolErrorRule


class ConventionsHook:
    type: ClassVar[str] = ""

    def skill(self, tool_name: str, args: dict[str, Any]) -> str | None:
        return None

    def tool_failed(self, result: str, status: str | None) -> bool | None:
        return None


conventions_hook_registry: Registry[type[ConventionsHook]] = Registry(
    "conventions hook", package="eval_harness.profiles.hooks", entry_point_group="eval_harness.conventions_hooks")


def register_conventions_hook(type_: str):
    def deco(cls: type[ConventionsHook]) -> type[ConventionsHook]:
        cls.type = type_
        conventions_hook_registry.register(type_)(cls)
        return cls

    return deco


@lru_cache(maxsize=256)
def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def _hook(conv: Conventions) -> ConventionsHook | None:
    return conventions_hook_registry.get(conv.hook)() if conv.hook else None


def _skill_by_rule(rule: SkillRule, name: str, args: dict[str, Any]) -> str | None:
    if rule.tool_pattern:
        m = _rx(rule.tool_pattern).search(name)
        if not m:
            return None
        raw = m.groupdict().get("skill") or (m.group(1) if m.groups() else None)
    else:
        if name != rule.tool:
            return None
        raw = args.get(rule.arg or "")
    if not raw or not isinstance(raw, str):
        return None
    return raw.replace("_", "-") if rule.normalize == "snake_to_kebab" else raw


def skill_from_call(conv: Conventions, name: str, args: dict[str, Any]) -> str | None:
    """The skill this tool call loads, or None. First matching rule wins."""
    hook = _hook(conv)
    if hook is not None and (s := hook.skill(name, args)):
        return s
    for rule in conv.skills:
        if (s := _skill_by_rule(rule, name, args)) is not None:
            return s
    return None


def _error_by_rule(rule: ToolErrorRule, result: str, status: str | None) -> bool:
    if rule.result_prefix is not None:
        return result.startswith(rule.result_prefix)
    if rule.result_regex is not None:
        return bool(_rx(rule.result_regex).search(result))
    if rule.message_status is not None:
        return status == rule.message_status
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(data, dict) and bool(data.get(rule.result_json_key or ""))


def tool_failed(conv: Conventions, result: str, status: str | None = None) -> bool:
    """Did this tool call fail? Any matching rule says yes."""
    hook = _hook(conv)
    if hook is not None and (r := hook.tool_failed(result, status)) is not None:
        return r
    return any(_error_by_rule(rule, result, status) for rule in conv.tool_error)


def cited_ids(conv: Conventions, answer: str) -> list[str] | None:
    """Source ids cited in an answer; None when this agent has no citation convention."""
    if conv.citations is None:
        return None
    return _rx(conv.citations.regex).findall(answer)


def grounded_in(conv: Conventions, source_id: str, tool_results: str) -> bool:
    assert conv.citations is not None
    return conv.citations.in_results.format(id=source_id) in tool_results
