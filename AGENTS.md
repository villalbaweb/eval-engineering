# AGENTS.md - conventions for AI coding agents

Eval-engineering lab: a toy `create_agent` agent + a pluggable eval engine. Read `README.md` first (map of "where do I work").

## Layout rules
- **One concept per package, one component per file.** Never add a component by editing a registry; add a file and decorate it.
- `evals/domain/` is pure pydantic (no I/O, no LangChain). Graders, metrics and the runner depend on it, never the reverse.
- Experiment *content* (tasks, suites, agents, rubrics, fault profiles, synthesis configs) is YAML/markdown in `evals/`. Prefer data over code.
- **Agent-specific content lives under its profile** (`evals/profiles/<name>/`; the built-in copilot may stay in the flat `evals/` layout). Never hard-code an agent's tool names, skill naming or error format in engine code: read them from the profile's `conventions` (`profiles/conventions.py`, or `GradeContext.conventions` in graders). Content paths come from `get_settings()` (`datasets_dir`, `suites_dir`...), which already resolve to the active profile.
- New targets declare `capabilities` (see `evals/targets/base.py`); runs, the Playground and traffic simulation are gated on them. Undeclared (`None`) = not gated.
- All chat models are built in `llm/factory.py::make_chat_model(role)`. Never call `init_chat_model`/`ChatOpenRouter` elsewhere. Roles: agent, judge, simulator, synthesizer.
- DB access only through `storage/repositories.py`. Registries live next to their ABC (`graders/base.py`, `targets/base.py`, ...).
- Frontend: feature-sliced. `features/<name>/` owns its page and is registered in `app/routes.tsx`; shared primitives in `shared/`, reusable domain views in `entities/`.

## Commands
```bash
cd backend && uv sync && uv run pytest -q && uv run ruff check src tests
uv run evalh list graders ; uv run evalh run smoke ; uv run evalh scaffold grader <name>
cd frontend && npm run typecheck && npm test && npm run build
```

## Rules that matter
- **Tests never use the network or real models, and never read `.env`** (`EVAL_HARNESS_NO_DOTENV=1`): `tests/conftest.py` forces `LLM_PROVIDER=fake`, tmp DB/data, a private copy of `evals/`. Keep it that way.
- A grader with nothing to check returns `self.skip(...)`, never a fake pass. A broken grader must not crash a run (pipeline catches it).
- Tool functions return failures as text starting with `ERROR` (the agent must be able to recover); they never raise.
- Judge model must differ from the agent model; model graders skip when `JUDGE_MODEL` is unset.
- Never commit `.env`, `data/`, `evals/candidates/*` or generated dataset folders (see `.gitignore`).
- Registries are shared across threads (trials run in `asyncio.to_thread`); discovery is lock-protected. Keep module import side effects idempotent.
- Windows is a supported dev platform: avoid `ZoneInfo` without a fallback (needs `tzdata`), use `pathlib`.
- **No silent behaviour changes**: `tests/golden/test_golden.py` compares the whole lab's offline behaviour with `tests/golden/baseline.json` (both evals layouts). If it fails, you changed results; fix the code, or regenerate the baseline (`uv run python tests/golden/capture.py --update`) only for an intended, explained change.
- The active profile is a context variable (request header `X-Eval-Profile`, `evalh --profile`, `EVAL_PROFILE`); it is inherited by `asyncio` tasks and `to_thread` workers. Code that starts other threads must pass it on (`profiles.use_profile`).
