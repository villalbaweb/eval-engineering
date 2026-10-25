# Eval Engineering Lab

A place to **learn and practise evaluation engineering**. A toy [LangChain `create_agent`](https://docs.langchain.com/oss/python/langchain/agents) agent (7 tools, 7 on-demand skills) is the system under test; the real product is the **pluggable evaluation engine** around it: graders, metrics, datasets, synthetic data, trace import, human calibration, LangSmith integration and a React UI.

```
 YAML tasks ──► Runner ──► Target (create_agent) ──► Transcript ──► Graders (code → trajectory → LLM judge)
 synthetic ─┘      │                                                      │
 traces ────┘      └── k trials, concurrency, record/replay tools         ▼
                                                          metrics: pass@k · pass^k · CI · flakiness · cost
                                                          ► SQLite · LangSmith · UI · human labels → calibration
```

## Quickstart

```bash
cp .env.example .env            # optional: without keys the offline "scripted" model is used
cd backend && uv sync
uv run evalh run smoke          # first experiment, no API key needed
uv run evalh serve              # API on :8000        (new terminal)
cd ../frontend && npm install && npm run dev   # UI on :5173
```

Or with Docker: `docker compose up --build` → UI on <http://localhost:5173> (dev override, hot reload).
Production-style (nginx, no reload): `docker compose -f docker-compose.yml up --build` → <http://localhost:8080>.

### Using real models
`.env` (see `.env.example`): `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` for the **agent**, and a separate **`JUDGE_MODEL`** (a stronger model, never the agent's). Without `JUDGE_MODEL`, LLM-judge graders are *skipped* (code graders still run); if it equals the agent model the run is flagged *self-judged*. `LANGSMITH_*` turns on tracing, dataset sync and experiment mirroring; `TAVILY_API_KEY` enables real web search.

## Map: where do I work?

| I'm working on… | Folder | Registered by |
|---|---|---|
| the agent (model, prompt, tools, skills, middleware) | `backend/src/eval_harness/agent/` | `evals/agents/*.yaml` |
| a general tool | `backend/src/eval_harness/tools/` | `@register_tool` |
| a skill | `backend/src/eval_harness/skills/library/<name>/SKILL.md` | the folder itself |
| a grader (code / model / human) | `backend/src/eval_harness/evals/graders/` | `@register_grader` |
| a metric | `.../evals/metrics/` | `@metric_registry.register` |
| what is evaluated (target) | `.../evals/targets/` | `@register_target` |
| synthetic data | `.../evals/data_sources/synthesis/` | `@register_generator` |
| imported traces | `.../evals/data_sources/traces/` | `@register_adapter` |
| LangSmith | `.../integrations/langsmith/` | `RunnerHook` |
| model providers | `.../llm/providers/` | `LLM_PROVIDER` |
| tasks, suites, rubrics, fault profiles | `evals/{datasets,suites,rubrics,faults}/` | *(data only)* |
| **another agent** (its inventory, trace conventions, variants, datasets, suites) | `evals/profiles/<name>/` (start from `demo-external/`) | *(data only)*; `evalh profiles` |
| how a transcript is read (skills, tool errors, citations) | `.../profiles/conventions.py` (+ `profiles/hooks/`) | `@register_conventions_hook` |
| a UI page | `frontend/src/features/<name>/` | `app/routes.tsx` |

## Adding things

```bash
uv run evalh scaffold grader my_check       # grader + unit test      (also: tool, metric, target, generator, skill)
```
- **Test case / suite / agent variant / rubric / fault profile**: add a YAML or markdown file under `evals/`. No code.
- **Skill**: `evalh scaffold skill my-skill` → edit `SKILL.md`. Its loader tool (`load_skill_my_skill`) is generated automatically.
- **Out-of-tree plugin**: expose an entry point in group `eval_harness.graders` / `.tools` / `.targets` / `.metrics` / `.middleware` / `.generators`.

`evalh list graders|tools|skills|suites|datasets|agents|targets|metrics|generators|experiments` shows everything available.

## Experiments to run (the curriculum)

| # | Experiment | How | You learn |
|---|---|---|---|
| E1 | Smoke / regression | `evalh run smoke`, `evalh run regression` | regression evals, code graders |
| E2 | **Per-skill vs generic loader** | `evalh run skill-selection --agent copilot-baseline` vs `--agent copilot-generic-loader`, then `evalh compare A B` | A/B with significance |
| E3 | pass@k vs pass^k | `evalh run capability --k 5` | non-determinism, flaky vs systematic |
| E4 | Trajectory match modes | edit a task's `trajectory_mode` (strict/unordered/subset/superset) | how the grader changes the verdict |
| E5 | Grounded answers | `evalh run capability` (citation_grounding + groundedness judge) | outcome vs trajectory, faithfulness |
| E6 | **Judge calibration** | `evalh run calibration`, label trials in *Annotate*, `evalh calibrate` | coverage, FFR, kappa, criteria drift |
| E7 | Judge position bias | `pairwise_judge` with `swap: true` vs `false` | LLM-judge biases |
| E8 | Fault injection | `evalh run robustness` | recovery & honesty |
| E9 | Multi-turn | `evalh run multi-turn` | conversation-level evals |
| E10 | **Trace flywheel** | `evalh traffic --n 30 --fault-rate 0.3` → `evalh import-traces` → review → `evalh run traces` | online → offline loop |
| E11 | Model sweep | UI *Experiments → model override* (`openrouter:vendor/model`) | quality vs cost vs latency |
| E12 | Synthetic vs real | `evalh synthesize skill-queries` vs imported traces; compare by `source` | does synthetic data predict logged behaviour? |

Re-grading without re-running the agent: `evalh regrade <experiment-id>` (the answer to criteria drift).

## Any agent: profiles and variants
The toy agent is just the first **profile** (`copilot`). A profile is one agent under test: its tools and skills (metadata), its **conventions** (how its traces show skill loads, tool failures, citations), where its traces live, and its own datasets and suites. A **variant** is one way to run or read it (an improvement candidate, an ablation, `staging`, read-only `prod-traces`); what it can do (chat, re-run, fault injection...) comes from its target, and the UI and runner refuse what it cannot do. Try the bundled second agent: `evalh --profile demo-external run traces`, or pick it in the UI's **agent profile** selector. See `.agents/RUNBOOK.md` §4.18.

## Testing
`cd backend && uv run pytest` (136 tests, offline, ~40 s, including the golden no-regression gate in `tests/golden/`) · `cd frontend && npm test && npm run build` · Docker: `docker compose --profile test run --rm tests`.

## Design notes
- **Everything is a transcript.** Targets return a normalized `Transcript` (OpenAI-format messages + tool-call records + skills loaded); graders never touch LangChain types.
- **Layered graders, fail-fast.** Layer 1 code → 2 trajectory → 3 LLM judge. A cheap failure skips the expensive layers (`fail_fast`).
- **Every experiment snapshots its cause**: agent config, resolved model per role, prompt hash, tools/skills, dataset hash, git SHA.
- **The offline `scripted` model** exists to exercise plumbing and CI. Only real models produce meaningful scores.
