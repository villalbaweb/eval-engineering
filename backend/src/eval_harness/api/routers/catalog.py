from __future__ import annotations

from fastapi import APIRouter

from eval_harness.agent.config import list_agent_configs
from eval_harness.agent.middleware.registry import middleware_registry
from eval_harness.api.routers.profiles import MODES, inventory_view, profile_view
from eval_harness.core.settings import get_settings
from eval_harness.evals.data_sources.synthesis.base import generator_registry
from eval_harness.evals.data_sources.traces.base import trace_adapter_registry
from eval_harness.evals.datasets.loader import dataset_groups, list_suites
from eval_harness.evals.graders.base import grader_registry
from eval_harness.evals.metrics.registry import metric_registry
from eval_harness.evals.targets.base import target_registry
from eval_harness.integrations.langsmith.client import enabled as langsmith_enabled
from eval_harness.llm.settings import is_self_judged, judge_configured, resolve_role
from eval_harness.profiles import active_profile
from eval_harness.skills.loader import load_library
from eval_harness.tools.base import TOOL_SPECS, tool_registry

router = APIRouter(tags=["catalog"])


@router.get("/catalog")
def catalog() -> dict:
    """Everything pluggable in one call (drives the Catalog and Launch views)."""
    tool_registry.discover()
    s = get_settings()
    prof = active_profile()
    return {
        "models": {r: resolve_role(r).model_dump() for r in ("agent", "judge", "simulator", "synthesizer")},
        "judge_configured": judge_configured(), "self_judged": is_self_judged(),
        "langsmith": {"enabled": langsmith_enabled(), "project": s.langsmith_project},
        "tools": [{"name": n, "description": (tool_registry.get(n).description or "").strip(),
                   **{k: v for k, v in spec.__dict__.items() if k not in ("name", "description")}}
                  for n, spec in sorted(TOOL_SPECS.items())],
        "skills": [{"name": k.name, "description": k.description, "version": k.version, "tokens": k.tokens,
                    "assets": k.assets, "tool": k.tool_name, "body": k.body} for k in load_library().values()],
        "graders": [{"type": n, "layer": c.layer, "description": c.description} for n, c in grader_registry.items()],
        "targets": target_registry.names(),
        "metrics": metric_registry.names(),
        "middleware": middleware_registry.names(),
        "generators": [{"type": n, "description": c.description} for n, c in generator_registry.items()],
        "agents": [a.model_dump(mode="json") for a in list_agent_configs()],
        "suites": [{"name": x.name, "description": x.description, "agent": x.agent, "target": x.target,
                    "k": x.run.k, "graders": [g.key for g in x.graders], "datasets": x.datasets,
                    "variant": x.variant, "mode": x.mode} for x in list_suites()],
        "datasets": dataset_groups(),
        # the active agent profile: inventory (its tools/skills), variants + capabilities, conventions
        "profile": {**profile_view(prof, prof.name), "inventory": inventory_view(prof)},
        "modes": MODES,
        "trace_adapters": trace_adapter_registry.names(),
    }
