# Validation Target Adapter (high-level design)

> **Status:** proposed, not started. No code exists for this yet.
> **Date:** 2026-10-24
> **One line:** a small plug-in that lets the lab's evaluation engine (graders, metrics, comparison, calibration) validate **your real production agent**, instead of only the toy agent it ships with.

---

## 1. Why this exists

The lab was built to teach and practise evaluation engineering on a toy `create_agent` agent. Its value for a real agent is the *method and the engine*, not the toy's results. Today the engine only knows how to evaluate that toy. The **validation target adapter** closes the gap: it turns "call the real agent (or read its traces)" into the neutral format the engine already understands.

What this unlocks for the real agent:
- the same layered graders (code → trajectory → LLM judge) on real behaviour
- regression and capability suites, k-trial reliability (pass@k / pass^k), significance-tested comparisons
- judge calibration against your own labels
- the trace flywheel: real failures → reviewed tasks → regression tests

It does **not** make the toy's datasets, thresholds or scores meaningful for the real agent. Those must be rebuilt from the real agent's traffic (section 9).

---

## 2. Where it plugs in (what already exists)

The engine is deliberately independent of how the agent is run. The seam is the `Target` interface in `backend/src/eval_harness/evals/targets/base.py`:

```
Target.run(task, run_settings, trial_info) -> (Transcript, Outcome)
Target.snapshot()  -> dict      # recorded with every experiment (what explains the results)
Target.create(suite, **options) # built from the suite's `target:` and any target options
@register_target("name")        # registration; discovered automatically (or via entry point group eval_harness.targets)
```

Existing targets for reference: `local_agent` (in-process toy agent), `multiturn_sim`, `replay` (re-grade stored transcripts), `trace` (grade logged transcripts, nothing re-run).

Everything downstream (graders, metrics, storage, UI, LangSmith mirroring, compare, calibrate) consumes only the `Transcript`/`Outcome`, so **a new target gets all of it for free**.

Helpers that already exist for building transcripts from foreign data: `normalize_messages` and `transcript_from_messages` (`evals/data_sources/traces/base.py`), which convert LangChain/OpenAI-style messages and rebuild tool-call records and loaded skills.

Scaffold: `uv run evalh scaffold target my_agent` creates the file and a test.

---

## 3. Two integration modes

| | **A. Trace-based** (read what happened) | **B. Live** (call the agent) |
|---|---|---|
| How | Read logged runs (LangSmith project, JSONL export, or another trace store) and grade them | Send each task's input to the real agent (HTTP endpoint or SDK call) and capture its response/trajectory |
| Needs from the agent | Nothing new: it already produces traces | A callable interface that can be driven by the lab, ideally returning or exposing its trajectory |
| Side effects | **None** (read-only) | **Possible**: tools may write to real systems |
| Cost | Only grader calls | Agent calls + grader calls |
| Answers | "How is it behaving in production?" (online-style evals) | "Does this change/model/prompt break anything?" (regression, A/B, capability) |
| Already in the lab | Largely (`trace` target + importer; needs the real trace format) | **No**: this is the adapter |

**Recommendation:** start with mode A (zero risk, answers real questions immediately), then add mode B against a **staging** environment.

---

## 4. What the adapter must do (mode B)

1. **Translate a task into a request.** `task.input.messages` (OpenAI-style list) → the agent's request format. Support per-task options when needed (thread/session id, user/tenant, feature flags).
2. **Call the agent safely.** Auth, timeouts (`run.timeout_s`), bounded retries for *infrastructure* errors only (never retry model failures), concurrency limit, rate limiting.
3. **Capture a full transcript.** At minimum the final answer. For trajectory graders it must also get the intermediate steps: assistant messages with tool calls, tool results, and ideally loaded skills, token usage and latency (see section 5).
4. **Report status honestly.** Map transport/agent failures to `Outcome(status="error" | "timeout")` with a reason, so failed calls are visible and never counted as passes.
5. **Describe itself.** `snapshot()` returns what explains the result: endpoint/environment name, agent version or build id, model identifiers if exposed, config hash. This is what makes two experiments comparable later.
6. **Stay inside the safety envelope** (section 7).

### Getting the trajectory (the hard part)

The adapter has three ways to get tool calls and steps, in order of preference:

1. **The response includes them** (messages/steps in the payload). Simplest and exact.
2. **The response includes a trace/run id**, and the adapter fetches the trajectory from the trace store (same code as the mode-A importer). Works when the endpoint only returns the final answer.
3. **Only the final answer is available.** Trajectory graders (`tool_called`, `trajectory_match`, `skill_selection`, `step_efficiency`, `error_recovery`) then cannot run and report *skipped*; outcome graders (answer checks, citations, LLM judges) still work. This is a valid but weaker setup.

---

## 5. Contract: what the engine needs back

Target output is a `Transcript` (`evals/domain/transcript.py`) plus an `Outcome`. Which fields each grader family needs:

| Field | Needed by | If missing |
|---|---|---|
| `messages` (OpenAI-format; final assistant message) | all graders | adapter is unusable; this is the minimum |
| `tool_calls` (name, args, result, error, latency) | `tool_called`, `tool_not_called`, `tool_errors`, `trajectory_match`, `step_efficiency`, `error_recovery`, `citation_grounding` (tool results) | those graders skip |
| `skills_loaded` | `skill_selection` | skips. Derived by `transcript_from_messages` from `load_skill*` tool names; **adapter must map the real agent's own skill/tool naming** |
| `usage` (tokens, cost), `latency_s` | `budget`, cost/latency metrics | metrics show n/a |
| `meta.guardrail_events` | `guardrail_tripwire` | that grader reports no events |
| `model_slug` | experiment snapshot, comparisons | shown as unknown |

Not applicable to a remote agent (they act inside the toy's process): **tool record/replay**, **fault injection**, per-run **guardrail middleware**. Equivalent isolation for a real agent has to come from the environment (staging data, mocked downstreams); see section 7.

---

## 6. Configuration sketch

Keep the contract **in data**, like the rest of the lab (indicative only; the exact schema is decided during design):

```yaml
# evals/targets/real-agent.yaml
name: real-agent
mode: live                       # live | trace
base_url: ${REAL_AGENT_URL}      # staging, never production by default
auth: { header: Authorization, value: "Bearer ${REAL_AGENT_TOKEN}" }
request:                         # how a task becomes a request
  body: { messages: "{{ task.input.messages }}", thread_id: "{{ trial.id }}" }
response:                        # where to find things (JSONPath-style)
  final_answer: $.output
  messages: $.messages           # optional: enables trajectory graders
  trace_id: $.trace_id           # optional: fetch trajectory from the trace store
  usage: $.usage                 # optional
skills:                          # how to detect "skill loaded" in this agent
  tool_name_pattern: "^load_skill_(.+)$"
limits: { timeout_s: 60, concurrency: 2, requests_per_minute: 30 }
environment: staging             # recorded in the experiment snapshot
```
A suite would then use `target: real_agent` (plus options). A code-based adapter handles anything the YAML contract cannot express (custom auth, streaming, multi-step handshakes).

---

## 7. Safety and risk (decide these before running anything live)

| Risk | Control |
|---|---|
| Tools with side effects (writes, emails, payments) triggered by test inputs | Evaluate **only staging/sandbox**. Production is read-only (mode A). Maintain an allow-list of tools that may run during evals; block or mock the rest. |
| Real user data in tests or traces | PII scrub on import (exists); never put real customer data in task files; retention limits; access control on stored transcripts |
| Cost and rate limits (real agent + LLM judges) | Concurrency and requests-per-minute caps in the adapter; `--max-tasks`, small `k` first; budget grader; provider-side spend limits |
| Tests that look like real traffic polluting analytics | Tag eval traffic (header/metadata), exclude it from product metrics |
| Judge self-preference | Judge model ≠ agent model (already enforced as a warning); calibrate judges on real labels first |
| Silent wrong results from partial adapters | Transport errors become `error` outcomes, never passes; missing trajectory makes trajectory graders *skip*, and the UI/CLI shows skipped counts |
| Secrets in config | Environment variables only; `.env` stays git-ignored (already the rule) |
| Nondeterminism and flakiness of a live agent | k ≥ 3, report pass^k, separate flaky from systematic failures (already built) |

---

## 8. Suggested phases

| Phase | Scope | Exit criteria |
|---|---|---|
| **0. Discovery** | Answer the questions in section 10; take 5 real traces/responses as fixtures | Written contract for request, response and trace format |
| **1. Trace-based validation (mode A)** | Importer for the real trace store/format; PII scrub; `trace` target works on real traces; reference-free suite (steps/loops, tool errors, budget, groundedness, conciseness) | Run `evalh run traces` on a sample of real traces; first failure taxonomy from reading them |
| **2. Live adapter against staging (mode B)** | `real_agent` target (YAML contract + code for gaps); safety envelope; snapshot with agent version | One suite passes end to end against staging with a mock server test (pattern: `tests/integration/test_openrouter_wire.py`) |
| **3. Real datasets and calibration** | Build golden/regression tasks from real traces (review queue); label 30+ trials; calibrate the judges | Alignment/kappa documented per grader; regression suite stable (low flakiness) |
| **4. Gate changes** | Run `regression` and `capability --k` on every prompt/model/tool change; compare candidate vs baseline with a decision rule written beforehand | Used on a real change before release |
| **5. Online monitoring** *(optional)* | Scheduled sampling of production traces, trend of key metrics, alerts | Dashboard or report with a few agreed metrics |

---

## 9. What must be rebuilt for the real agent (not reused from the toy)

- **Datasets:** tasks from real traffic and real failures (the toy's 56 tasks are not representative).
- **Expectations:** what correct behaviour means for your agent's domain, per task.
- **Rubrics and judge model:** written for your quality criteria, validated against your labels.
- **Thresholds:** pass-rate and latency/cost budgets derived from your own baseline.
- **Skill/tool naming rules:** in the adapter, so skill-selection and trajectory graders mean the same thing.

Reusable as-is: the engine, graders that only need messages/tool calls, metrics, comparison, calibration, the review queue, scaffolding, and the workflow in `.agents/RUNBOOK.md`.

---

## 10. Information needed to start (Phase 0 checklist)

1. **How is the real agent invoked?** HTTP endpoint (shape of request/response, auth, streaming?), SDK/function call, or queue. One sample request and response.
2. **Does the response carry the trajectory?** If not, is there a trace/run id to look up, and in which system (LangSmith project, OpenTelemetry, custom store)?
3. **Trace format and sample:** one exported trace; how skills and tool calls are named; where token usage and latency live.
4. **Environments:** is there a staging/sandbox? Are tools mockable or side-effect free there?
5. **State:** is the agent stateless per request, or does it need a thread/session id and prior history?
6. **Identity and tenancy:** which user/tenant should evals run as? Any feature flags to pin?
7. **Limits:** rate limits, cost ceiling, permitted time windows.
8. **Versioning:** how to identify the agent build/config under test (needed for comparisons).
9. **Data policy:** what may be stored from real traces, retention, who can see it.

---

## 11. Acceptance criteria

- A suite targeting the real agent runs from `evalh run <suite>` and from the UI, with results stored, compared and mirrored like any other experiment.
- Every transport/agent failure appears as an `error`/`timeout` outcome with a reason; none is counted as a pass.
- The experiment snapshot identifies environment, agent version and adapter config.
- Trajectory graders run when the trajectory is available and show as skipped (not passed) when it is not.
- Adapter tests run offline (mock server, no network), consistent with the repo rule that tests never use real services or `.env`.
- A documented safe-by-default configuration: staging only, concurrency and rate caps, tool allow-list.
- The runbook gains a section "Evaluating the real agent" with the exact commands.

---

## 12. Out of scope (for this document)

- Choosing the real agent's models, prompts or architecture.
- Building dashboards beyond what the lab already shows.
- Fine-tuning or automatic prompt optimisation from eval results.
- Evaluating anything against **production with write access**. Production access stays read-only trace analysis unless explicitly decided otherwise.

---

## 13. Related files

- `backend/src/eval_harness/evals/targets/base.py` (the `Target` contract) and `local_agent.py` (reference implementation)
- `backend/src/eval_harness/evals/targets/replay_target.py` (`replay` and `trace` targets)
- `backend/src/eval_harness/evals/data_sources/traces/` (trace adapters, `normalize_messages`, `transcript_from_messages`, importer)
- `backend/src/eval_harness/evals/domain/transcript.py` (what a target must produce)
- `backend/tests/integration/test_openrouter_wire.py` (pattern for testing an adapter against a local mock server)
- `.agents/IMPLEMENTATION_PLAN.md` and `.agents/RUNBOOK.md`
