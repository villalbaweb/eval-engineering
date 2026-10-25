"""Profiles and variants: which agent is under test, and how to run or read it.

A **profile** is one agent: its inventory (tools, skills), its conventions (how to read its
transcripts and traces), where its traces live, and its own datasets/suites/rubrics (folder layout).
A **variant** is one way to run or read that agent; it names the target that executes it.
See ``.agents/AGENT_PROFILES_PLAN.md``. Pure pydantic: no I/O.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class SkillRule(BaseModel):
    """How a tool call reveals a loaded skill. Either ``tool_pattern`` (regex over the tool name, the
    ``skill`` group or the first group is the skill) or ``tool`` + ``arg`` (skill name in an argument)."""

    tool_pattern: str | None = None
    tool: str | None = None
    arg: str | None = None
    normalize: Literal["none", "snake_to_kebab"] = "none"

    @model_validator(mode="after")
    def _one_kind(self) -> SkillRule:
        if bool(self.tool_pattern) == bool(self.tool):
            raise ValueError("a skill rule needs exactly one of tool_pattern or tool (+ arg)")
        if self.tool and not self.arg:
            raise ValueError("a 'tool' skill rule needs 'arg' (the argument holding the skill name)")
        return self


class ToolErrorRule(BaseModel):
    """A tool call failed when ANY rule matches. Set exactly one condition per rule."""

    result_prefix: str | None = None  # result text starts with this
    result_regex: str | None = None  # regex search over the result text
    result_json_key: str | None = None  # result is a JSON object with this key present and non-empty
    message_status: str | None = None  # the tool message's status field equals this (e.g. "error")

    @model_validator(mode="after")
    def _one_condition(self) -> ToolErrorRule:
        n = sum(x is not None for x in (self.result_prefix, self.result_regex, self.result_json_key,
                                        self.message_status))
        if n != 1:
            raise ValueError("a tool_error rule needs exactly one condition")
        return self


LAB_CITATION_REGEX = r"\[([a-z0-9][a-z0-9\-_]*)\]"


class CitationRule(BaseModel):
    regex: str = LAB_CITATION_REGEX  # over the final answer; group 1 = the cited source id
    in_results: str = "[{id}]"  # how a cited id must appear in tool results to count as grounded


def _lab_skill_rules() -> list[SkillRule]:
    return [SkillRule(tool_pattern=r"^load_skill_(?P<skill>.+)$", normalize="snake_to_kebab"),
            SkillRule(tool="load_skill", arg="name")]


def _lab_error_rules() -> list[ToolErrorRule]:
    # exactly the pre-profiles import rule; agents that flag failures by status add {message_status: error}
    return [ToolErrorRule(result_prefix="ERROR")]


class Conventions(BaseModel):
    """How to read this agent's transcripts (imported traces AND live runs).

    The defaults are the lab's own rules (the ``copilot`` agent): a profile that declares nothing behaves
    exactly like the lab did before profiles existed."""

    skills: list[SkillRule] = Field(default_factory=_lab_skill_rules)
    tool_error: list[ToolErrorRule] = Field(default_factory=_lab_error_rules)
    citations: CitationRule | None = Field(default_factory=CitationRule)  # null: citation_grounding skips
    hook: str | None = None  # optional registered Python conventions hook (for what rules cannot express)


class InventoryItem(BaseModel):
    name: str
    description: str = ""
    side_effects: bool = False


class Inventory(BaseModel):
    """What the agent has. Metadata only: the lab never executes a profile's tools."""

    from_registry: bool = False  # the built-in copilot: introspect the lab's tool/skill registries
    tools: list[InventoryItem] = Field(default_factory=list)
    skills: list[InventoryItem] = Field(default_factory=list)


class TraceSource(BaseModel):
    """Where this agent's traces live (defaults for imports)."""

    adapter: str | None = None  # langsmith | jsonl | ... (None: langsmith when enabled, else jsonl)
    project: str | None = None  # LangSmith project (None: LANGSMITH_PROJECT)
    path: str | None = None  # JSONL file or folder, relative to the profile folder
    filters: dict[str, Any] = Field(default_factory=dict)  # e.g. {source: playground}
    window_hours: int = 72


class ProfileDefaults(BaseModel):
    quick_suite: str = "smoke"  # suggested for tasks with expectations
    trace_suite: str = "traces"  # suggested for imported traces (grades logged transcripts)
    trace_group: str = "traces"  # default accept group for logged traces
    langsmith_prefix: str | None = None  # LangSmith dataset names: <prefix>/<suite> (None: legacy 'eval-eng')


class Variant(BaseModel):
    name: str
    description: str = ""
    target: str = "local_agent"  # target that executes this variant
    config: dict[str, Any] = Field(default_factory=dict)  # passed to the target
    aliases: list[str] = Field(default_factory=list)  # older names that still resolve to this variant


class Profile(BaseModel):
    name: str
    description: str = ""
    default_variant: str | None = None
    inventory: Inventory = Field(default_factory=Inventory)
    conventions: Conventions = Field(default_factory=Conventions)
    traces: TraceSource = Field(default_factory=TraceSource)
    defaults: ProfileDefaults = Field(default_factory=ProfileDefaults)
    legacy: bool = False  # loaded from the flat pre-profiles layout (set by the loader, not by files)


Capability = Literal["chat", "rerun", "fault_injection", "record_replay", "model_override", "traffic_sim"]
