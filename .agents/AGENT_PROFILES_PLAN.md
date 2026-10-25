# Agent Profiles: decoupling the lab from the toy agent (implementation plan)

> **Status:** implemented (P0-P7), 2026-10-24/25. Not committed. See "Implementation status" at the end.
> **Date:** 2026-10-24
> **Goal:** the eval engine and UI work with *any* agent. The toy Eval Copilot becomes the first **profile** (`copilot`), and switching to another agent means switching profile, not editing graders or pages.
> **Prerequisite for:** [VALIDATION_TARGET_ADAPTER.md](VALIDATION_TARGET_ADAPTER.md). With profiles in place, evaluating the real agent becomes "write a profile (data) + an `http_agent` target (code) + a trace adapter only if its traces are not in a supported format".

---

## 1. Vocabulary

| Term | Meaning | Toy example | Real-agent example |
|---|---|---|---|
| **Profile** | One agent under test. Owns everything specific to it: inventory (tools, skills), conventions (how to read its transcripts), where its traces live, and its own datasets, suites, rubrics, review queue | `copilot` | `support-agent` |
| **Variant** | One way to run or read that agent. Names the **target** that executes it plus that target's config | `baseline`, `generic-loader`, `no-skills` | `staging`, `prod-traces`, `prompt-v2` |
| **Target** | Engine plug-in that executes a variant and returns a transcript (exists today) | `local_agent` | `http_agent` (adapter doc), `trace_source` |
| **Mode** | How a *suite* evaluates (new name for what suites call `target:` today): call the variant live, simulate a user over several turns, grade transcripts stored in the tasks, or re-grade an experiment | `live`, `multiturn`, `trace`, `replay` | same |
| **Trace adapter** | Engine plug-in that fetches and parses one trace format (exists today) | `langsmith`, `jsonl` | `langsmith`, later `otel` / custom |
| **Capabilities** | What a variant supports, derived from its target | chat, rerun, fault injection, record/replay, model override, traffic sim | chat + rerun (`http_agent`); read-only (`trace_source`) |

Variant ids are written `profile:variant`, e.g. `copilot:baseline`; inside the active profile `baseline` is enough.

**Profile vs. variant rule.** Variants are created as needed: improvement candidates (`prompt-v2`, `new-retriever`, `model-sonnet`), ablations (`no-skills`), environments (`staging`, `prod-traces`). Variants share tools, skills and tasks, so their results are directly comparable. A change that would invalidate the datasets or expectations (different tools, a different job) is a **new profile**, not a variant.

Why "variant", not "version": the toy's three are *parallel* configurations (ablation). For a real agent variants also cover deployments and candidates. Order in time belongs to the experiment history, not the name.

### Mapping from today

| Today | After |
|---|---|
| `evals/agents/copilot-baseline.yaml` | `evals/profiles/copilot/variants/baseline.yaml` |
| `evals/agents/copilot-generic-loader.yaml` | `.../variants/generic-loader.yaml` |
| `evals/agents/copilot-no-skills.yaml` | `.../variants/no-skills.yaml` |
| suite `agent: copilot-baseline` | suite `variant: baseline` |
| suite `target: local_agent` / `multiturn_sim` / `trace` / `replay` | suite `mode: live` / `multiturn` / `trace` / `replay` |
| run override `--agent`, `--target` | `--variant`, `--mode` |
| UI "agent" dropdown (Playground, Experiments, Traffic) | "variant" dropdown under a **profile switcher** |

Old names (`agent:`, `target:` in suites, `--agent`, `--target`, API `agent`) stay accepted as aliases for one release, with a deprecation warning.

---

## 2. Who does what: profile, trace adapter, target

| Piece | Answers | Kind | Where |
|---|---|---|---|
| **Profile** | *What* the agent is and *how to read* its data: inventory, conventions, default trace source | data (YAML) | `evals/profiles/<name>/profile.yaml` |
| **Trace adapter** | *How to fetch and parse* a trace format | code, shared | `evals/data_sources/traces/` |
| **Target** | *How to run* a variant (in-process, HTTP, read-only from traces) | code, shared | `evals/targets/` |

Import flow for a real agent: the profile says where to look (`traces.source/project/filters`) → the trace adapter fetches runs and turns them into messages → the **profile's conventions** decide which calls are skill loads and which tool calls failed. A live target builds its transcript with **the same conventions**, so an imported production trace and the same task re-run on `staging` are graded by identical rules (that is what makes them comparable).

The lab **never executes the real agent's tools**. The inventory is metadata for the UI and for validating expectations; the agent runs its own tools.

---

## 3. Where the toy is hard-wired today (what this plan removes)

| Place | Coupling |
|---|---|
| `api/routers/chat.py` (Playground) | builds the toy agent in-process |
| `evals/data_sources/traffic/simulator.py` | runs the toy agent |
| `api/routers/catalog.py` tools/skills | read from the toy's tool and skill registries |
| `agent/config.py` + `evals/agents/` | the only kind of "agent" the lab knows |
| `evals/data_sources/traces/base.py:97-102` | skill = tool `load_skill_*` / `load_skill(name=…)`; failure = result starts with `ERROR` |
| `agent/middleware/transcript_capture.py`, `skill_tracking.py` | same `ERROR` convention (stays: toy-internal, matches the `copilot` conventions) |
| `evals/graders/code/citation_grounding.py` | toy citation format `[doc-id]` |
| `tools/knowledge_base_search.py` (`corpus_dir`), `agent/middleware/tool_replay.py` (`cassettes_dir`), `graders/model/judge_base.py` (`rubrics_dir`), synthesis (`synthesis_dir`) | global paths that are really toy/profile content |
| `evals/datasets/loader.py::validate_suite_refs`, Experiments UI | suites validated against `evals/agents` |
| Suites' `target:` field | mixes "how to run the agent" with "how to evaluate" (resolved by variant target + suite mode, §5.4) |
| Frontend `entities/datasetGroups.ts::suggestedSuite` and the accept default group `traces` | hard-coded toy suite/group names (`traces`, `smoke`) |
| LangSmith dataset names `eval-eng/<suite>` | not profile-scoped (two profiles with a `smoke` suite would collide) |
| `.gitignore` (`/evals/candidates/*`, `/evals/datasets/{synthetic,traces,accepted,langsmith}/`), `tests/conftest.py` (creates `evals/candidates`, `evals/cassettes`) | old paths |

Already neutral (no logic change, only profile scoping/filters): runner, metrics, storage, Results/Trial/Compare/Annotate/Calibration pages, review queue, dataset/suite/candidate editors, dataset-group runs.

---

## 4. Target layout

```
evals/
  profiles/
    copilot/                      # the toy agent (migrated, behaviour unchanged)
      profile.yaml                # inventory, conventions, traces, defaults
      variants/{baseline,generic-loader,no-skills}.yaml
      datasets/  suites/  rubrics/  synthesis/  faults/  corpus/  cassettes/
      candidates/                 # review queue for this profile (git-ignored)
    <your-agent>/                 # later: same shape; corpus/faults/cassettes only if relevant
  rubrics/                        # shared generic rubrics (a profile's rubric with the same name wins)
```

Shared across profiles: graders, metrics, generators, targets, trace adapters, generic rubrics. Toy implementation code (`agent/`, `tools/`, `skills/library/`, `agent/prompts/`) stays in the backend package: it is what the `local_agent` target runs for `copilot`.

Infra that follows the move: `.gitignore` → `/evals/profiles/*/candidates/*`, `/evals/profiles/*/datasets/{synthetic,traces,accepted,langsmith}/`; `tests/conftest.py` creates per-profile `candidates/`, `cassettes/`; Docker needs no change (it mounts/copies all of `evals/`); `.env.example` gains `EVAL_PROFILE` (optional).

---

## 5. File schemas (indicative)

### 5.1 `profile.yaml`

```yaml
name: copilot
description: Toy Eval Copilot (LangChain create_agent) - the lab's built-in system under test.
default_variant: baseline

inventory:                      # metadata only: UI, expectation editor, validation. Never executed.
  from_registry: true           # copilot only: introspect the toy's tool/skill registries
  # a real agent declares it instead:
  # tools:  [{ name: search_orders, description: "...", side_effects: false }]
  # skills: [{ name: refunds, description: "..." }]

conventions:                    # how to read this agent's transcripts (imported AND live)
  skills:                       # first matching rule wins
    - { tool_pattern: "^load_skill_(?P<skill>.+)$", normalize: snake_to_kebab }
    - { tool: load_skill, arg: name }
  tool_error:                   # a tool call failed when ANY rule matches
    - { result_prefix: "ERROR" }
    - { message_status: error }
    # real-agent examples: { result_json_path: "$.error", present: true } / { result_regex: "^HTTP 5\\d\\d" }
  citations: { regex: "\\[([a-z0-9][a-z0-9_-]+)\\]" }   # null -> citation_grounding skips
  # conventions_hook: my_agent_rules   # optional Python plug-in for what rules cannot express

traces:                         # where this agent's traces live (import defaults)
  adapter: langsmith            # langsmith | jsonl | (later) otel / custom
  project: ${LANGSMITH_PROJECT} # copilot: the lab's own project
  filters: { source: [playground, traffic] }
  window_hours: 72

defaults:
  quick_suite: smoke            # used by "run" links for tasks with expectations
  trace_suite: traces           # used for imported traces (mode: trace)
  trace_group: traces           # default accept group for logged traces
  langsmith_prefix: copilot     # LangSmith datasets: <prefix>/<suite>
```

### 5.2 Variant (`variants/<name>.yaml`)

```yaml
name: baseline
description: All tools, all skills, one loader tool per skill.
target: local_agent             # local_agent | http_agent | trace_source
config:                         # passed to the target; for local_agent = today's AgentConfig fields
  prompt: copilot_system.md
  tools: all
  skills: all
  skill_loader_mode: per_skill
  middleware: [guardrails, { name: tool_call_limit, args: { run_limit: 15 } }]
  recursion_limit: 40
  # model: { provider: openrouter, name: openai/gpt-4o-mini }   # optional, else .env
```

Real-agent variants (later): `target: http_agent` with the adapter config (adapter doc §6); `target: trace_source` with `config: { adapter: langsmith, project: prod-support, filters: {...} }` for a read-only `prod-traces` variant.

### 5.3 Suite (changed fields only)

```yaml
name: traces
variant: baseline        # optional; default = profile.default_variant
mode: trace              # live (default) | multiturn | trace | replay
datasets: [traces]
graders: [...]
```

### 5.4 Variant target vs. suite mode (resolves today's overloaded `target:`)

- The **variant** decides *how the agent is run* (`local_agent`, `http_agent`, `trace_source`).
- The **suite mode** decides *how the evaluation uses it*:

| Mode | Behaviour | Needs |
|---|---|---|
| `live` | send each task to the variant's target | `rerun` |
| `multiturn` | wrap the variant's target with the simulated user (today's `multiturn_sim`, now agent-agnostic) | `chat` |
| `trace` | grade the transcript stored in each task (imported traces); the variant is only recorded | nothing (works for any profile) |
| `replay` | re-grade an earlier experiment's transcripts | nothing |

A run whose mode needs a capability the variant lacks is refused before it starts, with the reason (e.g. "`prod-traces` is read-only: use mode `trace`").

### 5.5 Capabilities (declared by each target class)

| Capability | `local_agent` | `http_agent` | `trace_source` |
|---|---|---|---|
| `chat` (Playground, `multiturn`) | ✓ | ✓ if the endpoint is conversational | ✗ |
| `rerun` (`live`) | ✓ | ✓ | ✗ |
| `fault_injection`, `record_replay`, `model_override` | ✓ | ✗ (isolation comes from staging) | ✗ |
| `traffic_sim` | ✓ | ✓ (staging only) | ✗ |
| `model_id` known (self-judged check) | ✓ | if the endpoint reports it | if traces carry it |

---

## 6. No-regression contract (applies to every phase)

This is an **additive** decoupling: nothing that works today may stop working or change its results.

**Rules**
1. **Legacy layout keeps working.** If `evals/profiles/` does not exist, the flat `evals/` folder is loaded as an implicit `copilot` profile (`evals/agents/*` read as variants named by file, suites' `agent:`/`target:` read as `variant:`/`mode:`). Migration is opt-in (`evalh migrate-profiles --apply`), never automatic, and reversible (`--revert` restores the flat layout from the migration manifest).
2. **Old names keep working.** `copilot-baseline` resolves to `copilot:baseline` (alias table in `profile.yaml`), `--agent`/`--target`, API `agent`/`target` fields, suite `agent:`/`target:`. Deprecation warnings only; removal is a separate, later decision.
3. **APIs only grow.** No endpoint removed or renamed; no response field removed or retyped; new request fields are optional with today's behaviour as the default. Profile defaults to the active one, which is `copilot` when it is the only profile.
4. **Storage is additive.** No DB column dropped or changed; new data goes into the snapshot (`profile`, `variant`, `mode`). Experiments without these fields are read as `copilot`.
5. **Existing tests are not edited to pass.** The current suite (102 backend, 8 frontend) must pass unchanged at every phase; new behaviour gets new tests. A test may only change if it hard-codes a path that moved *and* the legacy-layout test (rule 1) still covers the old path.
6. **UI keeps every route and link.** `/experiments?suite=&datasets=`, `/suites?name=`, all pages; with a single profile the switcher is shown but nothing else changes.
7. **Grading is identical.** The `copilot` conventions must produce byte-identical transcripts (`skills_loaded`, tool `error` flags) to today's hard-coded rules.

**Gate (checked before P1 and after each phase)**
- **Golden baseline**, captured before any change by a script committed with P1 (`backend/tests/golden/`): for every suite in offline mode (`LLM_PROVIDER=fake`): pass rates, per-task pass/fail, per-grader verdicts, `skills_loaded`/tool-error flags per trial; plus JSON of `/api/catalog`, `/api/experiments` list item shape, `/api/suites/{name}`, `/api/candidates`. Each phase re-runs it and must match exactly (ignoring ids/timestamps).
- **Both layouts tested**: the golden run executes on the legacy flat layout *and* on the migrated layout; results must be equal.
- **Migration round-trip test**: migrate → revert → tree identical to the original (including git-ignored data).
- Full checks: `pytest`, `ruff`, `npm run typecheck && npm test && npm run build`, plus a manual UI pass of the Playground → import → accept → run loop.

**Rollback**: each phase is one mergeable change that can be reverted on its own; data migration is reversible via `--revert`.

---

## 7. Phases

Each phase ends green (§6 gate) and leaves `copilot` behaving exactly as today.

### P0 · Baseline
- Write the golden-baseline script and capture the current results (§6) **before touching code**. Add the legacy-layout test fixture. Nothing else.

### P1 · Domain, loading, migration
- `evals/domain/profile.py`: `Profile`, `Variant`, `Inventory`, `Conventions`, `TraceSource`, `ProfileDefaults` (pure pydantic, no I/O).
- `profiles/loader.py`: discover `evals/profiles/*`, validate, resolve `profile:variant`. Active profile = request (`X-Eval-Profile` / `?profile=` / `--profile`) → `EVAL_PROFILE` → the only/first profile.
- Settings: `datasets_dir`, `suites_dir`, `rubrics_dir` (profile then shared), `synthesis_dir`, `faults_dir`, `corpus_dir`, `cassettes_dir`, `candidates_dir` become profile-relative. Callers updated: `knowledge_base_search`, `tool_replay`, `fault_injection`, `judge_base`, synthesis, review queue, loader.
- **Legacy loader** first: the flat `evals/` layout is read as an implicit `copilot` profile (§6 rule 1), so nothing has to move for anything to keep working.
- **Migration** `evalh migrate-profiles` (opt-in, idempotent, dry-run by default, `--apply`, `--revert` from a manifest): moves `evals/{agents→variants, datasets, suites, rubrics, synthesis, faults, corpus, cassettes, candidates}` into `evals/profiles/copilot/`, rewrites agent YAML into variant shape, rewrites suites (`agent`→`variant`, `target`→`mode`). Moves git-ignored local data too (`datasets/accepted/`, `datasets/traces/`, candidates).
- Infra: `.gitignore` patterns, `tests/conftest.py` per-profile dirs, `.env.example` (`EVAL_PROFILE`).
- Tests: parsing, variant resolution (incl. aliases `copilot-baseline` → `copilot:baseline`), path resolution on both layouts, migration on a temp copy (dry-run, apply, apply twice = no-op, revert = original tree).

### P2 · Conventions instead of hard-coded rules
- `transcript_from_messages(msgs, conventions)` and the trace importer use the profile's `skills` / `tool_error` rules; `copilot` rules reproduce today's behaviour exactly.
- `citation_grounding` reads `conventions.citations` (skips when null, with the reason).
- `GraderContext` gains `profile` (read-only) so any grader can use conventions; graders whose convention is missing **skip with a reason** (never pass).
- Optional `conventions_hook` plug-in registry for rules data cannot express.
- Tests: existing tests unchanged; table tests for alternative conventions (generic loader tool, JSON `error` field, HTTP-status text, no citations).

### P3 · Targets, modes, runner
- Targets declare `capabilities`; `create(variant, **options)`. `local_agent` builds from `variant.config`. New `trace_source` target (read-only; used by `prod-traces`-style variants and by imports).
- Modes: `live`, `multiturn` (simulated user around any `chat`-capable target), `trace`, `replay`. Capability check before a run starts.
- Suite schema `variant` + `mode` (aliases `agent`/`target`); `validate_suite_refs` checks variants of the suite's profile; the suite editor (added earlier) uses it.
- Run overrides: `variant`, `mode`, `datasets` (dataset-group runs, already built), `model` (only with `model_override`, else 400 with reason).
- Snapshot: `profile`, `variant`, `target`, `mode`, capabilities. `compare` warns on different profiles (and keeps the existing suite/datasets like-for-like warnings).
- LangSmith: dataset names `<langsmith_prefix>/<suite>`; trace metadata adds `profile`, `variant`; import can filter by them.
- Traffic simulator and Playground chat run **the variant's target** (no direct `build_agent`); refused with a reason if the capability is missing.

### P4 · API
- `GET /profiles` → profiles, variants, capabilities, defaults; active marked.
- All profile-scoped endpoints take the profile (header or query); default = active: datasets, suites, faults, synthesis, candidates (incl. YAML editor), traces import (defaults from `profile.traces`), traffic, chat, experiments (list filtered by snapshot `profile`), annotations queue, calibration, LangSmith push/pull.
- `GET /catalog` splits **agent** (inventory, variants, conventions of the profile) from **engine** (graders, targets, modes, trace adapters, metrics, generators).
- Validation warnings: saving a dataset file, a candidate, or accepting candidates warns when `expected` names a tool/skill not in the profile inventory (warning, not error: inventories can lag).
- Chat body / experiments `agent` → `variant`, `target` → `mode` (aliases kept).

### P5 · UI
- **Profile switcher** in the sidebar (remembered per browser in `localStorage`); every request sends it; the profile name shows in each page header.
- **Catalog**: "Agent" tabs (tools, skills, variants with capabilities, conventions) from the profile; "Engine" tabs unchanged.
- **Playground**: variant dropdown lists the profile's variants; disabled with an explanation for variants without `chat`; fault dropdown only with `fault_injection`.
- **Experiments**: variant + mode dropdowns; tool mode / model override hidden without the capability; dataset groups and suites from the active profile; history filtered to the profile.
- **Suites / Datasets editors**: scoped to the profile; suite editor lists that profile's variants and the modes.
- **Data sources**: traffic card hidden without `traffic_sim`; import pre-filled from `profile.traces`; accept-group default from `defaults.trace_group`; candidate editor suggests tool/skill names from the inventory and shows the unknown-name warning.
- **Run links** (`entities/datasetGroups.ts`): suite suggestions come from `profile.defaults` (`quick_suite`, `trace_suite`) instead of hard-coded `smoke`/`traces`.
- **Compare / Annotate / Calibration**: experiment pickers filtered to the active profile.

### P6 · Prove the decoupling with a second, offline profile
- `evals/profiles/demo-external/`: trace-only profile with *different* conventions (skills via `use_capability(name=…)`, errors as `{"error": …}` JSON, no citations), declared inventory, `traces: { adapter: jsonl }`, one `trace_source` variant, its own `traces` suite.
- Integration test: import → edit expectation → accept → run (mode `trace`) → compare, asserting skills/errors are detected by *its* rules, `citation_grounding` skips, and Playground/traffic are refused with reasons.
- Rule: done only if this needs **no engine code changes**, only files in its folder. This is the dress rehearsal for the real agent.

### P7 · Docs
- Runbook: new "Profiles and variants" section; every path updated to `evals/profiles/copilot/...`; CLI `--profile`, `--variant`, `--mode`; UI profile switcher; the Playground→trace→dataset loop per profile.
- `README.md`, `AGENTS.md`: layout rule "agent-specific content lives under its profile"; new extension points (target capabilities, modes, conventions hooks).
- Adapter doc: replace §6 config sketch with "profile + `http_agent` variant + optional trace adapter"; add the profile / trace adapter / target split (§2 here) and the `tool_error` convention; Phase 0 checklist gains "how skills and tool failures appear in traces".

---

## 8. CLI after the change (old forms keep working)

```bash
evalh profiles                                   # profiles, variants, capabilities
evalh migrate-profiles [--apply | --revert]      # optional move to evals/profiles/copilot (dry run by default)
evalh run smoke --agent copilot-baseline         # still works (alias, deprecation warning)
evalh run smoke                                  # active profile (EVAL_PROFILE or the only one)
evalh run smoke --variant no-skills              # replaces --agent
evalh run traces --dataset accepted              # mode comes from the suite
evalh run traces --profile support-agent --dataset accepted
evalh import-traces --profile support-agent      # source/filters from its profile.yaml
```

---

## 9. Acceptance criteria

1. **No regressions** (§6): the golden baseline matches exactly on both layouts; the existing 102 backend and 8 frontend tests pass unchanged; every old command, API field, suite field, agent name and UI link still works.
2. `demo-external` is evaluated end to end (import → review → accept → run → compare) **without engine code changes**.
3. The UI never shows another profile's tools, skills, variants, datasets, suites, candidates or experiments; switching profile switches all of them.
4. Features a variant cannot support are hidden or disabled with a reason; a run needing a missing capability is refused before it starts.
5. Imported traces and live runs of the same profile are read with the same conventions.
6. Snapshots record profile, variant, target, mode; compare flags cross-profile comparisons.
7. Tests stay hermetic (no network, no `.env`).

---

## 10. Compatibility and risks

| Risk | Mitigation |
|---|---|
| A change silently alters grading or pass rates | golden baseline gate after every phase (§6); conventions for `copilot` must reproduce today's transcripts byte for byte |
| Moving `evals/` breaks local paths, uncommitted data, old snapshots | migration is optional (legacy layout still loads), dry run first, reversible; moves git-ignored data too; old snapshots without `profile` read as `copilot` |
| Old names in suites, CLI, API, bookmarks | aliases (`agent`, `target`, `copilot-baseline`…) kept with a deprecation warning; removal is a separate later decision; UI URLs keep working (`?suite=`, `?datasets=`) |
| Docs reference old paths | P7 updates them in the same change |
| Conventions too weak for a real agent | data rules first; `conventions_hook` plug-in for the rest |
| Expectations drift from the real agent's naming | inventory warnings on save/accept |
| Self-judged check needs the agent's model id | targets report `model_id` when known; otherwise the snapshot says "unknown" and the UI says the check could not run |
| Scope creep (multi-tenant platform) | one active profile per request; no permissions model; profiles are folders |

## 11. Out of scope (covered by the adapter doc)

- The real agent's `http_agent` target, auth, rate limits, safety envelope, staging setup.
- New trace adapters for non-LangSmith formats (OpenTelemetry, custom stores).
- Rebuilding datasets, expectations, rubrics and thresholds for the real agent.

## 12. Effort (rough)

P0 is small and comes first. P1–P3 are the core (largest: P1 migration + path plumbing, P3 modes). P4–P5 are wiring and UI. P6 is small but is the proof. Implement in order; each phase is independently mergeable.

## 13. Decisions (2026-10-24)

1. **Folder per profile** (§4). Flat folders with a `profile:` field rejected.
2. Toy profile name: **`copilot`**.
3. Toy variant names: **`baseline`, `generic-loader`, `no-skills`**.
4. **Profile vs. variant rule** as in §1: variants are created as needed (improvement candidates, ablations, environments) and stay comparable; anything that invalidates datasets or expectations is a new profile.
5. **Profile / trace adapter / target split** as in §2: the profile is data (what the agent is, how to read it, where its traces are); trace adapters and targets are shared engine code.
6. **Additive, no regressions** (§6): the legacy layout and every old name, field, command and link keep working; migration is optional and reversible; a golden baseline captured before any code change must match after every phase.

---

## 14. Implementation status (2026-10-25)

All phases done; the no-regression contract (section 6) holds.

**Verified**
- Golden baseline (`backend/tests/golden/baseline.json`, captured in P0 before any code change): every suite's per-trial verdicts, grader results, skills and tool-error flags, the traffic → import → accept → trace-grading loop, and API response shapes. Matches exactly on the legacy flat layout and on the migrated layout after every phase. A deliberate change (a grader removed from `smoke`) is detected.
- All pre-existing tests pass unchanged (only `tests/conftest.py` infrastructure changed: per-profile folders, narrower copy filter). Backend 136 tests, frontend 12, ruff, typecheck, build: green.
- Migration round trip (apply → revert) is byte for byte; apply twice is a no-op.
- `demo-external` (committed, `evals/profiles/demo-external/`) runs end to end via API and CLI with no engine code referring to it.
- Real repo smoke (offline, temp DB): `evalh profiles`, `evalh --profile demo-external run traces`, `evalh run smoke`, `--mode live` refusal.

**Not verified**
- The UI was not opened in a browser in this session (typecheck, unit tests and the API tests behind every page pass). Check visually: profile selector, Playground notice for `demo-external`, Experiments variant/mode, Catalog variants/conventions tabs, Data sources traffic card.
- LangSmith paths are covered by unit tests only (no live LangSmith run).

**Deviations from the plan (deliberate)**
- The copilot in this repo is **not migrated**: the flat layout and `evals/profiles/*` coexist (the flat folder is the `copilot` profile unless `evals/profiles/copilot/` exists). Migration stays opt-in (`evalh migrate-profiles`).
- Migration **moves suites unchanged** instead of rewriting `agent:`/`target:`; old names resolve through variant aliases. Less risk, same result.
- A migrated copilot keeps the LangSmith prefix `eval-eng` (not `copilot`) so existing LangSmith datasets keep matching.
- Default `tool_error` convention is the `ERROR` prefix only (the exact pre-profiles import rule); `message_status` is opt-in per profile, with statuses carried beside the messages so message shape is unchanged.
- `citations` gained `in_results` (how a cited id must appear in tool results; default `[{id}]`), needed to reproduce the old grader exactly and to support other formats.
- The `trace` target derives tool calls/skills from messages with the profile conventions when a stored transcript has messages only (hand-written datasets of another agent); copilot transcripts already carry tool calls and are untouched.
- `multiturn` mode currently wraps in-process agents only; other chat-capable targets are refused with a reason until they implement it.
- Targets that declare no capabilities (`None`, e.g. older plugins) are never gated.
- Simulated traffic of non-copilot agents goes to `data/traffic/<profile>/`; the experiment list is filtered to the active profile (`?all_profiles=true` lists all).

**Where things are**: `evals/domain/profile.py` (models), `profiles/{loader,conventions,inventory,migrate}.py`, `api/profile_context.py` (header middleware), `api/routers/profiles.py`, `evals/runner/service.py::resolve_run` (variant/mode/capabilities), `frontend/src/{shared/profile.ts,entities/profile.ts}`, docs in RUNBOOK 4.18 and 5.6.
