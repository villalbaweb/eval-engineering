# Eval Engineering Harness — Implementation Plan

> **Purpose.** A learning and experimentation lab for evaluation engineering. It runs a **toy** LangChain `create_agent` agent (tools + skills loaded via tool calling, the same shape as a real production agent). Around that agent sits a **strong, pluggable evaluation engine**, which is the actual focus: you try out eval approaches, measure them, and learn which techniques work. Applying the lessons to a real production agent is out of scope for this repo.
>
> **Status:** Plan only. Nothing is implemented yet.
> **Location:** `D:\Git\eval-engineering`
> **Stack:** Python 3.12 + `uv` · LangChain v1 `create_agent` · OpenRouter · LangSmith · FastAPI · SQLite/Postgres · React + Vite + TypeScript · Docker Compose

---

## 0. Research basis (NotebookLM + LangChain docs)

These decisions come from the four NotebookLM notebooks and the current LangChain docs:

| Source | Key takeaways applied in this plan |
|---|---|
| **AI Harness Evals** (EvalGen paper) | Core vocabulary: *Task, Trial, Transcript, Outcome, Grader, Suite*. Use code graders + LLM judges + human grades together. **"Validate the validators"**: measure each grader against human labels with **Coverage** and **False Failure Rate (FFR)**. **Criteria drift**: grading outputs changes the criteria, so the system must support fast iteration on criteria. Layer graders: cheap code checks run first, LLM judges only if those pass. |
| **Mastering GenAI with LangChain & LangGraph** | Evaluate at three levels: **final response**, **trajectory**, and **single step**. T-Eval decomposition (plan → tool selection → arg formatting → output interpretation). Score trajectories by subsequence for partial credit. Keep offline eval (curated datasets) separate from online eval (sampled production traces). Golden/silver datasets. Limit an agent to 5–15 tools. |
| **Agentic Design Patterns** | 3-layer eval stack: assertions → trajectory match → LLM judge. Trajectory match modes (exact / in-order / subsequence). Small JSON test files for unit-style checks, eval sets for regression. **Never let an agent grade its own homework**: use a separate judge model. Put guardrails at tool interfaces. Use shadow/canary comparison of v1 and v2. |
| **Mastering AI Agents, Frameworks & Orchestration Runtimes** | *Agent = Model + Harness* (7 subsystems: loop, LLM integration, tools, memory/context, safety, orchestration, extensibility). **SKILL.md with 3-tier progressive disclosure** (catalog in prompt → tool call → just-in-time content). Agent-Computer Interface (ACI) tool design ("poka-yoke" tools, strict schemas). Tracing hierarchy *Run → Trace → Thread → Trajectory*. Use pass@k on small datasets to separate systematic failures (0/k) from flaky ones. Keep policy as data. |
| **LangChain docs** (`create_agent`, skills, `agentevals`, `openevals`, LangSmith) | `create_agent(model, tools, middleware=[...])`. Skills pattern: a `load_skill` tool plus skill descriptions in the system prompt. `agentevals.create_trajectory_match_evaluator` modes `strict / unordered / subset / superset` and tool-args match modes. `create_trajectory_llm_as_judge`. `openevals.create_llm_as_judge` with prebuilt prompts (correctness, conciseness, hallucination). Multi-turn simulation (`run_multiturn_simulation`, `create_llm_simulated_user`). LangSmith `evaluate()` / pytest plugin (`num_repetitions`, `max_concurrency`). |

---

## 1. Goals and non-goals

### Goals
1. **Center: `create_agent`.** The system under test is built with `langchain.agents.create_agent` and middleware, the same building blocks a production agent would use.
2. **At least 5 general tools** plus **at least 5 skills**, each skill with its own **on-demand loader tool**.
3. **Eval engine as a plugin system.** Add a new *grader, dataset, scenario, target, metric, tool, or skill* by dropping **one file** into a well-known folder. No core edits.
4. **Concepts map directly to code.** Each eval-engineering concept (Task, Trial, Transcript, Grader, Suite, Experiment) is a module with the same name.
5. **Reproducibility.** Record and replay tool outputs, pin models and temperatures, run k trials, and store every transcript.
6. **The agent is a toy; the evals are the product.** The agent only needs to be realistic enough to produce interesting transcripts and failures. Effort goes into graders, metrics, datasets and analysis.
7. **React UI** to run experiments, inspect transcripts, compare experiments, and hand-label outputs (for grader calibration).
8. **Docker Compose** brings up the whole stack, with optional profiles for extra infrastructure.

### Non-goals (v1)
- Not a replacement for LangSmith. **LangSmith is the observability and experiment-tracking backbone** (traces, datasets, experiments, feedback). The local DB keeps a copy so the UI stays fast and the lab still works if LangSmith is unreachable (`LANGSMITH_TRACING=false`).
- No auth or multi-tenancy. This is a local lab.
- No fine-tuning or RL loops.

---

## 2. The two roles of the agent

The `create_agent` harness plays **two roles** at once, which makes the lab self-reinforcing:

```
                ┌──────────────────────────────────────────────┐
                │  "Eval Copilot" agent  (create_agent)        │
                │  tools: search, KB, fetch, stats, traces...  │
                │  skills: rubric design, error analysis, ...  │
                └───────────────┬──────────────────────────────┘
          Role A: ASSISTANT     │       Role B: SYSTEM UNDER TEST
   helps you design evals,      │   the eval engine runs suites against it
   analyze failures, write      │   (and against its own config variants)
   rubrics (uses the skills)    │   to measure tool use, skill selection, etc.
```

- **Role A:** In the Playground you chat with an agent whose skills are eval-engineering skills. You learn the domain by using it.
- **Role B:** The same agent is a realistic tools + skills agent with **observable decisions** (which skill it loaded, which tools it called, and in what order). Those decisions are exactly what agent evals need to measure.
- **Variants:** Agent configs are data (YAML). You can define `copilot-baseline`, `copilot-generic-loader`, `copilot-no-skills`, `copilot-haiku`, and so on, then A/B them.

---

## 3. Repository layout

The monorepo has one folder per deployable. Inside the backend, **one package per concept**.

```
eval-engineering/
├── .agents/
│   └── IMPLEMENTATION_PLAN.md          ← this file
├── AGENTS.md                           # conventions for AI coding agents working in the repo
├── README.md
├── docker-compose.yml
├── docker-compose.override.yml         # dev: hot reload, bind mounts
├── .env.example
├── Makefile / justfile                 # thin wrappers: up, test, eval, lint
│
├── backend/
│   ├── pyproject.toml                  # uv-managed; [project.entry-points] for plugins
│   ├── uv.lock
│   ├── Dockerfile
│   ├── src/eval_harness/
│   │   ├── core/                       # cross-cutting: settings, logging, registry, errors
│   │   │   ├── settings.py             # pydantic-settings (env → typed config)
│   │   │   ├── registry.py             # generic Registry[T] + @register decorator + discovery
│   │   │   └── ids.py, clock.py, logging.py
│   │   │
│   │   ├── llm/                        # ── MODEL PROVIDER LAYER ──
│   │   │   ├── settings.py             # LLM_PROVIDER + per-provider keys/models/base URLs
│   │   │   ├── resolver.py             # explicit provider or auto-detect (Google first)
│   │   │   ├── factory.py              # make_chat_model(role="agent"|"judge"|"simulator")
│   │   │   └── providers/              # one file per provider
│   │   │       ├── openrouter.py       # ChatOpenRouter (langchain-openrouter)  ← default
│   │   │       ├── google.py, anthropic.py, openai.py, vertex.py
│   │   │
│   │   ├── agent/                      # ── THE HARNESS (create_agent) ──
│   │   │   ├── factory.py              # build_agent(AgentConfig) -> CompiledAgent
│   │   │   ├── config.py               # AgentConfig (model, prompt, tools, skills, middleware)
│   │   │   ├── prompts/                # system prompt templates (Jinja/markdown)
│   │   │   ├── state.py                # custom AgentState (skills_loaded, step_budget...)
│   │   │   └── middleware/             # one file per middleware
│   │   │       ├── transcript_capture.py   # records every model/tool event → Transcript
│   │   │       ├── tool_replay.py          # record/replay tool outputs (determinism)
│   │   │       ├── fault_injection.py      # inject tool errors/latency (robustness evals)
│   │   │       ├── skill_tracking.py       # writes loaded skills into state
│   │   │       └── guardrails.py           # input/output/tool-arg policy checks
│   │   │
│   │   ├── tools/                      # ── GENERAL TOOLS (one file each) ──
│   │   │   ├── base.py                 # ToolSpec metadata (side_effects, cost, replayable)
│   │   │   ├── web_search.py
│   │   │   ├── fetch_url.py
│   │   │   ├── knowledge_base_search.py
│   │   │   ├── trace_lookup.py
│   │   │   ├── results_query.py
│   │   │   ├── stats_calculator.py
│   │   │   └── current_datetime.py
│   │   │
│   │   ├── skills/                     # ── SKILLS (progressive disclosure) ──
│   │   │   ├── loader.py               # parse SKILL.md frontmatter → SkillSpec
│   │   │   ├── tools.py                # generates load_skill_<name> tools (+ generic mode)
│   │   │   ├── catalog.py              # renders the Tier-1 catalog for the system prompt
│   │   │   └── library/                # content lives here, NOT in code
│   │   │       ├── eval-case-design/SKILL.md
│   │   │       ├── rubric-authoring/SKILL.md
│   │   │       ├── trajectory-analysis/SKILL.md
│   │   │       ├── error-analysis/SKILL.md
│   │   │       ├── grader-calibration/SKILL.md
│   │   │       ├── synthetic-data-generation/SKILL.md
│   │   │       └── experiment-comparison/SKILL.md
│   │   │
│   │   ├── evals/                      # ── THE EVAL ENGINE ──
│   │   │   ├── domain/                 # pure pydantic models, no I/O
│   │   │   │   ├── task.py             # Task (= eval case)
│   │   │   │   ├── suite.py            # Suite (tasks + graders + run settings)
│   │   │   │   ├── trial.py            # Trial (one execution of a Task)
│   │   │   │   ├── transcript.py       # normalized messages/tool calls/usage/latency
│   │   │   │   ├── outcome.py          # final answer + side-effects/state
│   │   │   │   ├── grade.py            # GradeResult(score, passed, label, rationale)
│   │   │   │   └── experiment.py       # Experiment (suite × target × config × k)
│   │   │   ├── datasets/               # loaders: yaml, jsonl, csv, langsmith
│   │   │   ├── data_sources/           # where new tasks come from (§6.8)
│   │   │   │   ├── traffic/            # traffic simulator: runs the agent on synthetic "users"
│   │   │   │   ├── traces/             # trace importers: langsmith, jsonl
│   │   │   │   ├── synthesis/          # synthetic generators (one file each)
│   │   │   │   └── review.py           # candidate → dedup/PII scrub → accept into dataset
│   │   │   ├── targets/                # what gets evaluated
│   │   │   │   ├── base.py             # Target protocol: run(task) -> Transcript
│   │   │   │   ├── local_agent.py      # in-process create_agent from AgentConfig
│   │   │   │   └── multiturn_sim.py    # wraps a target with an LLM simulated user
│   │   │   ├── graders/                # one file per grader; @register_grader
│   │   │   │   ├── base.py             # Grader protocol + GraderSpec + layering (fail-fast)
│   │   │   │   ├── code/               # deterministic
│   │   │   │   ├── model/              # LLM-as-judge
│   │   │   │   └── human/              # annotation-queue grader
│   │   │   ├── metrics/                # pass@k, pass^k, bootstrap CI, alignment...
│   │   │   ├── runner/                 # orchestrates trials (async, concurrency, retries)
│   │   │   │   ├── executor.py
│   │   │   │   ├── scheduler.py
│   │   │   │   └── events.py           # progress events → SSE to UI
│   │   │   ├── analysis/               # experiment diffing, failure clustering
│   │   │   └── exporters/              # jsonl, csv, html report
│   │   │
│   │   ├── integrations/
│   │   │   └── langsmith/              # tracing metadata, dataset sync, experiment mirror, feedback
│   │   │
│   │   ├── storage/                    # SQLModel repos (SQLite default, Postgres via URL)
│   │   │   ├── models.py
│   │   │   ├── repositories/           # one repo per aggregate
│   │   │   └── migrations/             # alembic
│   │   │
│   │   ├── api/                        # FastAPI; one router per resource
│   │   │   ├── main.py
│   │   │   ├── deps.py
│   │   │   └── routers/
│   │   │       ├── chat.py             # playground (streaming)
│   │   │       ├── catalog.py          # tools, skills, graders, targets, agent configs
│   │   │       ├── datasets.py
│   │   │       ├── suites.py
│   │   │       ├── experiments.py      # launch / status (SSE) / results
│   │   │       ├── transcripts.py
│   │   │       ├── annotations.py      # human labels
│   │   │       └── calibration.py      # grader-vs-human alignment
│   │   │
│   │   └── cli/                        # Typer: `uv run evalh run suites/regression.yaml`
│   │
│   └── tests/
│       ├── unit/                       # graders, metrics, loaders (no LLM)
│       ├── integration/                # agent with FakeChatModel + replayed tools
│       └── evals/                      # pytest-style eval suites (langsmith plugin optional)
│
├── evals/                              # ── EXPERIMENT CONTENT (data, not code) ──
│   ├── agents/                         # AgentConfig variants (YAML)
│   │   ├── copilot-baseline.yaml
│   │   ├── copilot-generic-loader.yaml
│   │   └── copilot-no-skills.yaml
│   ├── datasets/                       # tasks (YAML/JSONL), grouped by capability
│   │   ├── skill-selection/
│   │   ├── tool-use/
│   │   ├── grounded-answers/
│   │   ├── safety/
│   │   └── multi-turn/
│   ├── suites/                         # suite = datasets + graders + run settings
│   │   ├── smoke.yaml
│   │   ├── regression.yaml
│   │   └── capability.yaml
│   ├── rubrics/                        # LLM-judge rubric prompts (markdown)
│   ├── synthesis/                      # synthetic data generation configs (dimensions, counts)
│   ├── candidates/                     # imported/generated tasks awaiting review (git-ignored)
│   ├── cassettes/                      # recorded tool outputs for replay
│   └── corpus/                         # documents for knowledge_base_search
│
├── frontend/
│   ├── package.json, vite.config.ts, Dockerfile, nginx.conf
│   └── src/ (see §9)
│
└── plugins/                            # optional out-of-tree plugins (uv workspace members)
    └── example_plugin/                 # shows how to ship a grader/tool as a package
```

**Rule of thumb:** *Code* goes in `backend/src/eval_harness/**`. *Experiment content* (agents, datasets, suites, rubrics, skills) is YAML or markdown and goes in `evals/**` or `skills/library/**`. Most experiments should need **no Python changes at all**.

---

## 4. The agent harness (`agent/`)

### 4.1 Factory
```python
# agent/factory.py (sketch)
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

def build_agent(cfg: AgentConfig, *, run_ctx: RunContext | None = None):
    model  = make_chat_model(role="agent", override=cfg.model)    # llm/factory.py (§4.3)
    tools  = tool_registry.resolve(cfg.tools)                    # general tools
    tools += skill_tools.build(cfg.skills, mode=cfg.skill_loader_mode)  # per-skill or generic
    prompt = render_system_prompt(cfg.prompt, skill_catalog=catalog.render(cfg.skills))
    mw     = middleware_registry.resolve(cfg.middleware, run_ctx=run_ctx)
    return create_agent(model=model, tools=tools, system_prompt=prompt,
                        middleware=mw, state_schema=HarnessState)
```

### 4.2 `AgentConfig` (YAML, the main experiment variable)
```yaml
# evals/agents/copilot-baseline.yaml
name: copilot-baseline
model:                            # optional; omitted fields fall back to .env
  provider: openrouter            # google | openrouter | anthropic | openai | vertex
  name: openai/gpt-4o-mini        # any OpenRouter slug → variants = just change this line
  temperature: 0.0
prompt: prompts/copilot_system.md
tools: [web_search, fetch_url, knowledge_base_search, trace_lookup,
        results_query, stats_calculator, current_datetime]
skills: all                       # or an explicit list
skill_loader_mode: per_skill      # per_skill | generic  ← an experiment in itself
middleware:
  - transcript_capture
  - skill_tracking
  - { name: tool_call_limit, args: { run_limit: 15 } }
  - { name: model_call_limit, args: { run_limit: 25 } }
  - guardrails
```
The model comes from the provider layer (§4.3). The judge model is configured **separately** (see §6.3), following "never grade your own homework".

### 4.3 Model provider layer (`llm/`)
**OpenRouter is the lab's provider.** One key gives access to many models, which makes the harness flexible for model comparisons. The `LLM_PROVIDER` switch with auto-detect is kept, so other providers can be added the same way:

```dotenv
# --- LLM PROVIDER SWITCH ---  google | openrouter | anthropic | openai | vertex
# Unset → auto-detect (first configured key wins, Google first)
LLM_PROVIDER=openrouter

OPENROUTER_API_KEY=sk-...
OPENROUTER_MODEL=openai/gpt-4o-mini             # agent (system under test)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# --- JUDGE MODEL (LLM-as-judge graders) — you choose the slug ---
JUDGE_PROVIDER=openrouter                       # defaults to LLM_PROVIDER when unset
JUDGE_MODEL=                                    # REQUIRED for model graders; must differ from agent model
JUDGE_TEMPERATURE=0

# --- SIMULATOR MODEL (simulated user for multi-turn evals) ---
SIMULATOR_PROVIDER=openrouter                   # defaults to LLM_PROVIDER
SIMULATOR_MODEL=openai/gpt-4o-mini              # defaults to the agent model
```

- `settings.py` maps these variables to a typed `ModelRoleSettings` per role: `agent`, `judge`, `simulator`. Each role resolves `<ROLE>_PROVIDER` → `LLM_PROVIDER`, and `<ROLE>_MODEL` → `<PROVIDER>_MODEL`.
- `resolver.py`: an explicit provider wins, otherwise the first configured key wins in the order google → openrouter → anthropic → openai → vertex.
- `providers/openrouter.py` builds `ChatOpenRouter` (the `langchain-openrouter` package) with `model`, `base_url` and `api_key` from settings.
- `make_chat_model(role=...)` is the **only** place models get built. The agent, the LLM judges (openevals/agentevals receive the model instance instead of a model string), and the simulated user all call it. Swapping models is config-only.
- **Judge rules:**
  - If `JUDGE_MODEL` is empty, model graders are reported as `skipped (no judge configured)`. Code graders still run.
  - If `JUDGE_MODEL` equals the agent model, the run logs a warning, and the UI marks the experiment as "self-judged".
- Every experiment records the **resolved provider + slug for each role** in its config snapshot. OpenRouter slugs can disappear (`nex-agi/nex-n2.5-pro:free` already did), so results must say exactly which models produced them.
- A startup check queries OpenRouter's model list. It fails fast if a slug no longer exists or (for the agent role) does not support tool calling, which `create_agent` needs.
- **Model sweeps come almost for free:** the experiment launcher accepts a list of slugs and runs the same suite across all of them (see E11).

### 4.4 Middleware (one concern per file)
| Middleware | Hook(s) | Why it matters for evals |
|---|---|---|
| `transcript_capture` | `before_model`, `after_model`, `wrap_tool_call` | Builds the normalized **Transcript**: messages, tool calls and args, tool results, tokens, latency per step. |
| `tool_replay` | `wrap_tool_call` | **record** mode writes tool I/O to a cassette, and **replay** mode serves it back. This separates model reasoning from external flakiness. |
| `fault_injection` | `wrap_tool_call` | Injects errors, timeouts, or empty results from config. Use it to test the *recovery* trajectory. |
| `skill_tracking` | `after_model` / tool hook | Adds `skills_loaded: list[str]` to state, which skill-selection graders consume. |
| `guardrails` | `before_model`, `wrap_tool_call`, `after_model` | Input, tool-arg, and output policy checks, with tripwire events logged for safety evals. |
| built-ins | `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`, `SummarizationMiddleware` | Budget limits, loop prevention, and context-management experiments. |

> Verify exact middleware hook names and built-in class names against the installed `langchain` version during Phase 1 (with the docs MCP or reference MCP).

---

## 5. Tools and skills

### 5.1 General tools (7, at least 5 required)
Each tool is one file that declares a `ToolSpec` (name, description, `side_effects`, `replayable`, `cost_hint`). Following ACI guidance, schemas are strict and descriptions are clear.

| # | Tool | What it does | Eval angle |
|---|---|---|---|
| 1 | `web_search` | Web search through **Tavily** (`langchain-tavily`, `TAVILY_API_KEY`). DuckDuckGo is the fallback when the key is missing. | Retrieval quality, citation grounding |
| 2 | `fetch_url` | Fetches a URL and returns clean markdown (size-capped) | Multi-hop tool chains (search → fetch) |
| 3 | `knowledge_base_search` | BM25 (plus optional embeddings) over `evals/corpus/` | **Deterministic** retrieval with known ground truth, which makes groundedness/faithfulness evals reliable |
| 4 | `trace_lookup` | Fetches a stored transcript by trial id, or filters by failure | Lets the Copilot do error analysis on real runs |
| 5 | `results_query` | Read-only structured queries over experiment results (pass rates by grader/tag) | Agent reasoning over data |
| 6 | `stats_calculator` | Safe statistics: pass@k, pass^k, bootstrap CI, Cohen's κ, proportion z-test | Exact-arg tool calls that are easy to grade |
| 7 | `current_datetime` | Current time and timezone | Simple "should it call a tool at all?" checks |

### 5.2 Skills (7, at least 5 required): `SKILL.md` with progressive disclosure
Each skill is a folder holding a `SKILL.md` (YAML frontmatter: `name`, `description`, optional `metadata.include_tools`, `version`). It can also hold referenced assets such as templates and examples, which the agent reads only when needed (reference awareness).

| Skill | Teaches the agent (and you) to… | Loader tool |
|---|---|---|
| `eval-case-design` | Write unambiguous tasks with clear success criteria, reference outputs/trajectories, and capability vs regression tags | `load_skill_eval_case_design` |
| `rubric-authoring` | Design LLM-judge rubrics: binary criteria, anchored scales, few-shot examples, bias mitigations (position, verbosity) | `load_skill_rubric_authoring` |
| `trajectory-analysis` | Read transcripts and spot wrong tool choice, bad args, loops, skipped steps, and poor error recovery (T-Eval steps) | `load_skill_trajectory_analysis` |
| `error-analysis` | Open- and axial-code failures into a **failure taxonomy**, then turn the categories into new graders and tasks | `load_skill_error_analysis` |
| `grader-calibration` | Validate the validators: Coverage, FFR, alignment, κ against human labels, and how to fix judge drift | `load_skill_grader_calibration` |
| `synthetic-data-generation` | Generate tasks from dimensions × tuples, build adversarial/edge cases, and avoid leaking labels into synthetic data | `load_skill_synthetic_data_generation` |
| `experiment-comparison` | Compare experiments statistically: pass@k vs pass^k, CIs, significance, cost/latency trade-offs | `load_skill_experiment_comparison` |

**Three-tier disclosure:**
1. **Tier 1:** `catalog.py` puts only `name` + one-line `description` of each skill into the system prompt.
2. **Tier 2:** The agent calls `load_skill_<name>()`, which returns the SKILL.md body as a `ToolMessage`. `skill_tracking` records it in state.
3. **Tier 3:** The skill body references assets (`templates/rubric.md`, `examples/*.yaml`) that the agent fetches only when needed, through a `read_skill_asset(skill, path)` tool.

**Loader modes are an experiment.** `skill_loader_mode: per_skill` (one tool per skill, as you requested) versus `generic` (a single `load_skill(name)` tool, like the LangChain tutorial). Comparing them on the `skill-selection` dataset is one of the first built-in experiments.

Adding a skill means creating `skills/library/<name>/SKILL.md`. The loader tool is generated automatically, with no code changes.

---

## 6. The eval engine (`evals/`)

### 6.1 Domain model (the vocabulary as code)
```
Suite ─┬─ Task (inputs, reference_outputs?, reference_trajectory?, tags, kind: capability|regression,
       │        grader overrides, target-specific setup e.g. cassette, fault profile)
       ├─ GraderSpec[] (ordered layers: code → trajectory → model; fail-fast policy)
       └─ RunSettings (k trials, concurrency, timeout, replay mode, seed)

Experiment = Suite × Target × AgentConfig × RunSettings   (immutable, hashed config snapshot)
   └─ Trial (task_id, attempt i of k) ──► Transcript ──► Outcome
                                            └──► GradeResult[] (one per grader)
```
Every experiment stores a **config snapshot hash** (agent config, prompt text, tool and skill versions, model id, git SHA). That way, results can always be explained later.

### 6.2 Task format (YAML)
```yaml
# evals/datasets/skill-selection/rubric-request.yaml
id: skill-sel-003
kind: regression
tags: [skill-selection, rubric-authoring]
input:
  messages:
    - { role: user, content: "Help me write an LLM-judge rubric for answer conciseness." }
expected:
  skills_loaded: [rubric-authoring]          # consumed by skill_selection grader
  trajectory:                                # consumed by agentevals trajectory match
    mode: superset
    tool_calls: [{ name: load_skill_rubric_authoring }]
  final_answer_criteria:                     # consumed by LLM judge
    - "Proposes binary or anchored criteria"
    - "Includes at least one pass and one fail example"
graders: [skill_selection, trajectory_match, rubric_judge, budget]
```

### 6.3 Graders (one file each, `@register_grader`)
All graders implement `Grader.grade(task, transcript, outcome) -> GradeResult`. The runner applies them **layered, fail-fast**: if a cheap code check fails, the expensive judge can be skipped (configurable per suite).

**Code graders (`graders/code/`)**
- `exact_match`, `regex_match`, `contains_all`/`contains_none`
- `json_schema` (output format)
- `tool_called` / `tool_not_called` / `tool_args_match` (exact, subset, or custom comparators)
- `trajectory_match` → wraps `agentevals.create_trajectory_match_evaluator` (`strict | unordered | subset | superset`, plus tool-args match modes)
- `trajectory_subsequence` (partial credit score from 0 to 1)
- `skill_selection` (precision/recall of `skills_loaded` against expected; flags over-loading)
- `step_efficiency` (steps against reference, redundant calls, loop detection)
- `budget` (tokens, cost, latency thresholds)
- `error_recovery` (after an injected fault: did the agent retry or adapt, or hallucinate?)
- `citation_grounding` (cited KB doc ids actually appear in tool results)

**Model graders (`graders/model/`)**: the judge model is configured separately from the agent model
- `llm_judge` → generic, rubric file driven (`evals/rubrics/*.md`), via `openevals.create_llm_as_judge`
- Prebuilt: `correctness`, `conciseness`, `hallucination`/`groundedness` (openevals prompts)
- `trajectory_judge` → `agentevals.create_trajectory_llm_as_judge`
- `pairwise_judge` → A vs B comparison with **position swapping** to reduce order bias
- `judge_ensemble` → majority vote or average across N judges/models (judge-variance experiments)

**Human grader (`graders/human/`)**
- `human_review` puts trials into an **annotation queue** in the UI (thumbs up/down, failure tag, note). These labels are the ground truth for grader calibration.

### 6.4 Targets (`targets/`)
- `LocalAgentTarget(AgentConfig)`: in-process `create_agent`
- `MultiTurnSimTarget(inner, persona)`: drives the target with `openevals` `create_llm_simulated_user` / `run_multiturn_simulation` for conversation-level evals.
- `ReplayTarget(experiment_id)`: re-grades stored transcripts **without re-running the agent**. You can iterate on graders cheaply, which is the answer to criteria drift.
- `TraceTarget(filter)`: grades **imported traces** (§6.8) as they are, without re-running anything. This is online-style evaluation of logged traffic.
- New targets (another agent, an HTTP service) are one file implementing the `Target` protocol, so the engine is not tied to the toy agent.

### 6.5 Metrics (`metrics/`)
- Per task: pass rate over k trials, **pass@k** (unbiased estimator `1 − C(n−c,k)/C(n,k)`), and **pass^k** (`(c/n)^k`, consistency)
- Per suite: mean ± **bootstrap 95% CI**, per-tag breakdown, per-grader breakdown
- Flakiness: tasks with 0 < c < n (flaky) vs c = 0 (systematic)
- Cost and latency: p50/p95 latency, tokens, $ per task
- **Grader alignment** (against human labels): Coverage, FFR, alignment (harmonic mean), Cohen's κ, confusion matrix
- Experiment diff: per-task regressions and improvements, McNemar / two-proportion test

### 6.6 Runner
- `asyncio` with a configurable concurrency semaphore, plus per-trial timeout and retry *only on infra errors* (never on model failures)
- Streams progress events, which the API forwards to the UI over **SSE**
- Tool modes per run: `live | record | replay`
- Hooks (`on_trial_start`, `on_trial_end`, `on_experiment_end`) so exporters and plugins can subscribe
- Optional: an `arq`/Redis worker for long runs (compose profile `worker`). By default the runner executes in-process as background tasks.

### 6.7 LangSmith integration (`integrations/langsmith/`)
LangSmith is a first-class integration:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=eval-engineering
# Legacy aliases (older langchain versions read these names)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=eval-engineering
```

| Capability | How |
|---|---|
| **Tracing** | Every Playground chat and every trial is traced automatically (LangChain reads the env vars). Each trial's run gets metadata `experiment_id`, `task_id`, `trial_index`, `agent_config`, `model_slug`, so you can filter in LangSmith. The UI's transcript view deep-links to the LangSmith trace. |
| **Dataset sync** | `evalh datasets push <group>` / `pull`. Local YAML tasks ⇄ LangSmith datasets (inputs, reference outputs, metadata = tags/kind). The local YAML stays the source of truth and lives in git. |
| **Experiments** | An `ExperimentMirror` exporter subscribes to runner hooks and logs each experiment as a LangSmith experiment on the synced dataset: one run per trial, every `GradeResult` as **feedback** (key = grader name, score, comment = rationale). That lets you use LangSmith's compare view too. |
| **Alternative runner** | The `langsmith` backend runs a suite through `client.evaluate` / `aevaluate` (`num_repetitions=k`, `max_concurrency`), with our graders wrapped as LangSmith evaluators. Use it to compare the native runner against LangSmith's. |
| **pytest path** | `tests/evals/` uses `@pytest.mark.langsmith` + `langsmith.testing` for assertion-style evals in CI. |
| **Human labels** | Annotations from the UI are also written as LangSmith feedback, and optionally pushed to a LangSmith annotation queue. |
| **Trace source** | The LangSmith adapter of the trace importer (§6.8) reads the toy agent's own runs (Playground chats and simulated traffic) back from the project. |

Other exporters: JSONL / CSV / static HTML report.

### 6.8 Data sources: logged traces and synthetic data (`evals/data_sources/`)
A toy agent has no real users, so the lab **creates its own "production" traffic** and then treats it like the real thing. That keeps the online → offline loop available for learning. There are two ways to get new tasks, and both end in the **same review step** before anything becomes a dataset:

```
 logged traces ─► TraceImporter ─┐
                                 ├──► Candidate tasks ──► review (UI: accept/edit/reject) ──► evals/datasets/*.yaml
 generators  ──► Synthesizer ────┘         (dedup, PII scrub, auto-tags)                       (+ push to LangSmith)
```

**A) Simulated traffic + trace importer (`data_sources/traffic/`, `data_sources/traces/`)**
- **Traffic simulator:** runs the agent against a stream of simulated users (personas × intents from the synthesis module, single- or multi-turn) at a set volume. Runs are traced to LangSmith with `metadata.source = "traffic"`. Optional fault injection makes some sessions fail on purpose, so there is something to find.
- Playground chats are traced with `metadata.source = "playground"`. If you thumbs-up/down a reply in the UI, that becomes LangSmith feedback (a stand-in for real user feedback).
- **Importers**, one adapter per format:
  - `langsmith.py`: `Client.list_runs(project_name=LANGSMITH_PROJECT, filter=..., is_root=True)` with time window, sampling rate, and filters (source, errors only, negative feedback, tags)
  - `jsonl.py`: trace files, so external datasets can be loaded too
- **Normalization:** every adapter outputs the same `Transcript` model, so imported traces can be (1) **graded directly** with `TraceTarget` (online-style eval, no re-run) or (2) **converted into tasks**: the user input becomes `input`, and optionally the observed trajectory or answer becomes the reference once you approve it.
- **PII scrub** (regex + optional LLM pass) runs on import, which is good practice even with simulated data.

**B) Synthetic data module (`data_sources/synthesis/`)**, one generator per file, `@register_generator`:
| Generator | Technique |
|---|---|
| `dimensional.py` | Define **dimensions** (e.g. intent × persona × difficulty × skill needed), sample **tuples**, then turn each tuple into a natural-language query with the LLM. This gives good coverage without the clichés of "generate 50 questions". |
| `trace_seeded.py` | Take logged inputs and create **variations**: paraphrases, harder versions, missing info, multi-intent |
| `adversarial.py` | Prompt injection, out-of-scope requests, ambiguous asks, tool-misuse bait (for safety and guardrail suites) |
| `skill_targeted.py` | Generate queries that *should* trigger each skill, plus near-misses that should *not* (for the skill-selection dataset) |
| `multiturn_personas.py` | Persona definitions for `MultiTurnSimTarget` |

- Configured as YAML (`evals/synthesis/*.yaml`: dimensions, counts, generator, model role `synthesizer`, which defaults to the judge model).
- Built-in quality controls: embedding/fuzzy **dedup**, a **label-leak check** (the generator's expected answer must not appear in the input), and diversity stats per dimension shown in the UI.
- Generated tasks are tagged `source: synthetic:<generator>`. Imported ones are tagged `source: traces:<adapter>`. Metrics can then be split by source, which lets you check whether offline datasets predict behaviour on logged traffic.
- The `synthetic-data-generation` skill teaches the Copilot the same method, so you can also produce data by chatting with it.

---

## 7. Extensibility: how you add things

Everything is discovered from a **registry**: decorators for in-repo code, plus Python **entry points** (`eval_harness.graders`, `.tools`, `.targets`, `.metrics`, `.middleware`) for out-of-tree plugins in `plugins/`.

| I want to add… | Do this | Code? |
|---|---|---|
| A test case | New YAML in `evals/datasets/<group>/` | No |
| A suite / scenario | New YAML in `evals/suites/` | No |
| An agent variant (prompt, model, tools, skills) | New YAML in `evals/agents/` | No |
| An LLM-judge rubric | New markdown in `evals/rubrics/` + reference it from a `llm_judge` grader | No |
| A skill | New `skills/library/<name>/SKILL.md` (loader tool auto-generated) | No |
| A tool | New file in `tools/` with `@register_tool` | ~30 lines |
| A grader | New file in `graders/code|model/` with `@register_grader` | ~20 lines |
| A metric | New file in `metrics/` with `@register_metric` | ~20 lines |
| A target (e.g. another agent) | New file in `targets/` | ~50 lines |
| A packaged plugin | `plugins/<name>/` uv workspace member + entry points | Package |

A `uv run evalh scaffold grader my_grader` CLI command creates the file, a unit test, and an example YAML.

---

## 8. Backend API (FastAPI)

| Router | Endpoints (indicative) |
|---|---|
| `chat` | `POST /chat/stream` (SSE; streams tokens, tool calls, and skill loads) |
| `catalog` | `GET /catalog/{tools|skills|graders|targets|metrics|agents}` |
| `datasets` | CRUD for tasks; import traces; run synthesis; review candidates; validate |
| `suites` | list/get/validate suites |
| `experiments` | `POST /experiments` (launch) · `GET /experiments/{id}` · `GET /experiments/{id}/events` (SSE) · `GET /experiments/{id}/results` · `POST /experiments/{id}/regrade` |
| `transcripts` | `GET /trials/{id}/transcript` |
| `annotations` | queue, submit label, list labels |
| `calibration` | `GET /calibration/{grader}`: coverage/FFR/κ against human labels |
| `compare` | `GET /compare?a=…&b=…`: per-task diff + significance |

The OpenAPI schema generates the frontend TS client (`openapi-typescript`), so types never drift.

---

## 9. Frontend (React + Vite + TS)

**Libraries:** React Router, TanStack Query (server state), Zustand (light UI state), Tailwind + shadcn/ui, Recharts, Monaco (YAML/rubric editing), `openapi-typescript` client.

**Feature-sliced structure:** each feature owns its components, hooks, and api calls.
```
frontend/src/
├── app/            # router, providers, layout, theme
├── shared/         # ui primitives, api client (generated), hooks, utils
├── entities/       # reusable domain views: TaskCard, GradeBadge, TranscriptTimeline, MetricTile
└── features/
    ├── playground/     # chat with Copilot; live trace panel (tool calls, skill loads, tokens)
    ├── catalog/        # browse tools, skills (rendered SKILL.md), graders, agent configs
    ├── datasets/       # browse/edit tasks (Monaco YAML), import traces, run generators, review candidates
    ├── experiments/    # launch wizard (suite × agent × k × replay mode), live progress (SSE)
    ├── results/        # suite dashboard: pass@k / pass^k, per-tag & per-grader, flaky tasks, cost
    ├── transcripts/    # step-by-step trajectory viewer with grader verdicts inline
    ├── compare/        # A/B experiment diff, regressions first, significance
    ├── annotate/       # human labeling queue (thumbs + failure tags + notes)
    └── calibration/    # grader-vs-human alignment: coverage, FFR, κ, confusion matrix
```
Each feature folder holds `routes.tsx`, `api.ts`, `components/`, and `hooks/`. Adding a page means adding a feature folder and registering its route.

---

## 10. Docker Compose

```yaml
services:
  api:        # FastAPI + eval runner (uv-based image, multi-stage)
  web:        # React build served by nginx (dev override: vite dev server w/ HMR)
  db:         # postgres  — profile: postgres   (default is SQLite in a volume)
  redis:      # + worker  — profile: worker     (long-running experiments via arq)
  worker:     #             profile: worker
  phoenix:    # optional OTel trace UI (Arize Phoenix) — profile: observability
```
- `docker compose up` gives **api + web** with SQLite: the minimal lab.
- `docker compose --profile postgres --profile worker up` gives the scaled setup.
- Volumes: `./evals` and `./backend/src/eval_harness/skills/library` are **bind-mounted**, so new datasets, suites, rubrics, and skills are picked up without rebuilding.
- The backend Dockerfile uses the official `uv` image pattern: `uv sync --frozen --no-dev` in a builder stage, then a slim runtime.
- Healthchecks on `api` (`/health`), and `web` depends on `api` being healthy.
- Running evals inside compose: `docker compose run --rm api uv run evalh run evals/suites/regression.yaml`.

---

## 11. Quality, testing and conventions

- **uv**: `uv sync`, `uv run pytest`, `uv run evalh …`; a workspace for `plugins/*`
- **Lint/type**: `ruff` (lint + format) and `mypy --strict` on `evals/domain`, `metrics`, `graders`. Frontend: `eslint`, `prettier`, `tsc --noEmit`
- **Tests without LLM calls**: unit tests for metrics and graders against fixture transcripts. Integration tests use `GenericFakeChatModel` + tool replay, so the CI path is deterministic and free.
- **Eval suites in CI** (optional): `smoke` suite in replay mode on each PR; `capability` suite nightly with live models
- `AGENTS.md` at the root documents the module map and the "add X" recipes from §7 for coding agents
- Pre-commit: ruff, mypy, eslint, YAML schema validation of `evals/**` (JSON Schemas are generated from the pydantic models)

---

## 12. Built-in experiments (the curriculum)

Each experiment ships as a ready-to-run suite, so working through them teaches the discipline step by step:

| # | Experiment | Concept learned |
|---|---|---|
| E1 | **Smoke regression** in replay mode | Regression evals, determinism, code graders |
| E2 | **Skill selection accuracy**: per-skill vs generic loader | Trajectory/tool-selection evals, A/B with CIs |
| E3 | **pass@k vs pass^k** on the capability suite (k=5) | Non-determinism, flaky vs systematic failures |
| E4 | **Trajectory match modes** (strict/unordered/subset/superset) on the same tasks | How the choice of grader changes the conclusion |
| E5 | **Grounded answers** with KB search + hallucination judge | Outcome vs trajectory evaluation, faithfulness |
| E6 | **Judge calibration**: label 30 trials by hand, then compute Coverage/FFR/κ for 2 rubrics | Validate the validators, criteria drift |
| E7 | **Pairwise judge position bias**: run with and without swapping | LLM-judge biases |
| E8 | **Fault injection**: tool timeouts and errors | Error-recovery trajectories, robustness |
| E9 | **Multi-turn simulated user** | Conversation-level evals |
| E10 | **Trace flywheel**: simulate traffic (with injected faults) → import sampled traces → grade with `TraceTarget` → error analysis with the Copilot → new tasks → re-run | Online → offline flywheel |
| E11 | **OpenRouter model sweep**: same regression suite across 3–5 slugs (`openai/gpt-4o-mini` as baseline) | Quality vs cost vs latency trade-offs, choosing a model with evidence |
| E12 | **Synthetic vs real**: build a synthetic set (dimensional + trace-seeded) and a trace-imported set for the same intents, then compare pass rates by `source` | Whether synthetic datasets predict behaviour on logged traffic |

---

## 13. Delivery phases

| Phase | Scope | Exit criteria |
|---|---|---|
| **P0 – Scaffold** | Repo layout, `uv` project, ruff/mypy, FastAPI `/health`, Vite app shell, Dockerfiles, compose (api+web), `.env.example`, `AGENTS.md` | `docker compose up` serves the UI, and the UI calls `/health` |
| **P1 – Agent harness** | `AgentConfig`, factory over `create_agent`, 7 tools, skill loader + 7 SKILL.md, per-skill/generic loader tools, transcript-capture + skill-tracking middleware, `/chat/stream`, Playground UI with live trace, **LangSmith tracing on** (run metadata) | You can chat in the UI and watch skills load and tools fire |
| **P2 – Eval core** | Domain models, YAML loaders + JSON schema, `LocalAgentTarget`, runner (k trials, concurrency), code graders incl. agentevals trajectory match, metrics (pass@k/pass^k/CI), SQLite storage, CLI `evalh run`, LangSmith dataset sync + experiment mirror (grades as feedback) | `evalh run evals/suites/smoke.yaml` prints a metrics table, and the experiment appears in LangSmith |
| **P3 – Determinism & robustness** | Tool record/replay cassettes, fault injection, `ReplayTarget` (regrade without rerun), budget/efficiency graders | Smoke suite in replay mode is 100% reproducible |
| **P4 – Model graders** | Separate judge config, `llm_judge` from rubric files, openevals prebuilt, trajectory judge, pairwise (with swap), ensemble | E4, E5, E7 runnable |
| **P5 – UI for evals** | Experiments launch + SSE progress, Results dashboard, Transcript viewer, Compare view | E1–E3 fully operable from the UI |
| **P6 – Human-in-the-loop** | Annotation queue, labels storage, Calibration page (coverage/FFR/κ) | E6 runnable end-to-end |
| **P7 – Data sources** | Synthesis module (5 generators), traffic simulator, trace importers (LangSmith, JSONL), `TraceTarget`, PII scrub, candidate review UI, multi-turn sim target, LangSmith `evaluate` runner backend | E9, E10, E12 runnable end-to-end |
| **P8 – Scale & polish** | Postgres/worker/phoenix profiles, plugin entry points + `plugins/example_plugin`, `evalh scaffold`, CI workflow | You can add a grader as an external plugin without touching core |

Each phase ends with a working, demoable increment and its own tests.

---

## 14. Key dependencies (to be pinned at P0)

**Backend:** `langchain` (v1, `create_agent`), `langgraph`, `langchain-openrouter` (default provider), with `langchain-openai` / `langchain-anthropic` / `langchain-google-genai` / `langchain-google-vertexai` as optional uv extras, `agentevals`, `openevals`, `langsmith`, `langchain-tavily`, `fastapi`, `uvicorn`, `sse-starlette`, `pydantic`, `pydantic-settings`, `sqlmodel`, `alembic`, `typer`, `rich`, `pyyaml`, `jinja2`, `httpx`, `rank-bm25`, `trafilatura`/`markdownify`, `duckduckgo-search` (fallback), `numpy`/`scipy` (stats). Dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

**Frontend:** `react`, `react-router`, `@tanstack/react-query`, `zustand`, `tailwindcss`, shadcn/ui, `recharts`, `@monaco-editor/react`, `openapi-typescript`, `react-markdown`.

---

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| LangChain v1 API drift (middleware hooks, agentevals signatures) | Verify against docs MCP at P1/P2, isolate behind adapters in `agent/` and `graders/` |
| LLM cost of running k trials × judges | Replay mode, fail-fast grader layering, `ReplayTarget` regrading, per-experiment budget cap |
| Judge unreliability | Separate judge model, calibration page, ensembles, pairwise swap |
| Flaky external tools | Cassettes, deterministic KB corpus, fault-injection treated as a *feature* |
| Over-engineering a learning lab | Phased delivery; every phase must be usable on its own |
| OpenRouter slugs disappear or change (it has happened before) | Startup slug check, slug recorded in every experiment snapshot, baseline slug pinned in `.env` |
| `gpt-4o-mini` is weak as a judge, and judging with the same model is biased | Separate `JUDGE_MODEL` (stronger slug), calibrated against human labels (E6) |
| `:free` models are rate-limited and have unstable availability | Concurrency limit per provider, retry with backoff on 429 (infra errors only), avoid `:free` slugs for judges |

---

## 16. Decisions log

| # | Topic | Decision |
|---|---|---|
| 1 | Model provider | **OpenRouter** for the lab. Agent baseline `openai/gpt-4o-mini`. `ChatOpenRouter` client. See §4.3. |
| 2 | Judge model | Separate `JUDGE_PROVIDER` / `JUDGE_MODEL` keys. **You pick the slug.** Model graders are skipped until it is set. |
| 3 | Scope | **Toy agent; the focus is eval capability.** No production integration. "Production" traffic is simulated and logged to LangSmith (§6.8A). |
| 4 | Synthetic data | Internal synthesis module with five generators and a shared review step (§6.8B). |
| 5 | LangSmith | **First-class**: tracing, dataset sync, experiment mirroring, feedback, and trace source (§6.7). Local DB keeps a copy. |
| 6 | Web search | **Tavily** (`TAVILY_API_KEY`), with DuckDuckGo as fallback. |
| 7 | Skills | Filesystem `SKILL.md` folders, each loaded by its own tool. |

No open questions remain. The plan is ready for Phase 0.
