// Hand-written API types. Regenerate from /openapi.json with openapi-typescript if the API grows.

export type ExperimentStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface RateStat { n: number; pass_rate: number; skipped?: number }

export interface PerTask { n: number; passed: number; pass_rate: number; pass_at_k: number; pass_pow_k: number }

export interface Summary {
  pass_rates?: {
    k: number; n_trials: number; n_tasks: number; trial_pass_rate: number; ci95: [number, number];
    mean_pass_at_k: number; mean_pass_pow_k: number; task_pass_rate: number; per_task: Record<string, PerTask>;
  };
  by_tag?: Record<string, RateStat>;
  by_kind?: Record<string, RateStat>;
  by_source?: Record<string, RateStat>;
  by_grader?: Record<string, RateStat>;
  flakiness?: { reliable: string[]; flaky: string[]; systematic: string[]; informative: boolean };
  cost_latency?: {
    latency_p50_s: number; latency_p95_s: number; tokens_mean: number; tokens_total: number;
    cost_total_usd: number | null; steps_mean: number; tool_calls_mean: number; errors: number;
  };
}

export interface ModelSpec { role: string; provider: string; model: string; temperature: number }

export interface Experiment {
  id: string; name: string; suite: string; target: string; status: ExperimentStatus;
  created_at: string; finished_at: string | null; total_trials: number; done_trials: number;
  summary: Summary; langsmith_url: string | null; error: string | null;
  snapshot: Record<string, any>; model?: string; agent?: string; datasets?: string[];
  profile?: string; variant?: string | null; mode?: string;
}

export type Capability = "chat" | "rerun" | "fault_injection" | "record_replay" | "model_override" | "traffic_sim";

export interface VariantView { name: string; description: string; target: string; aliases: string[];
  capabilities: Capability[]; capabilities_declared: boolean }

export interface InventoryItem { name: string; description: string; side_effects: boolean }

export interface ProfileView {
  name: string; description: string; active: boolean; legacy_layout: boolean; default_variant: string | null;
  variants: VariantView[];
  defaults: { quick_suite: string; trace_suite: string; trace_group: string; langsmith_prefix: string | null };
  traces: { adapter: string | null; project: string | null; path: string | null; filters: Record<string, any>; window_hours: number };
  conventions: Record<string, any>;
  inventory?: { tools: InventoryItem[]; skills: InventoryItem[]; from_registry: boolean };
}

export interface Profiles { active: string; modes: string[]; capabilities: Capability[]; profiles: ProfileView[] }

export interface GradeLite { grader: string; passed: boolean | null; skipped: boolean; score: number | null; layer: number }

export interface TrialRow {
  id: string; task_id: string; index: number; passed: boolean; status: string; error: string | null;
  duration_s: number; tags: string[]; source: string | null; user_text: string; grades: GradeLite[];
  skills_loaded: string[]; tools: string[]; answer: string;
}

export interface Grade extends GradeLite { rationale: string; details: Record<string, any>; label?: string | null }

export interface ToolCall { id: string; name: string; args: Record<string, any>; result: string; error: boolean;
  latency_s: number; replayed: boolean; injected_fault: string | null }

export interface TrialDetail {
  trial: {
    id: string; experiment_id: string; task_id: string; index: number; duration_s: number;
    transcript: { messages: any[]; tool_calls: ToolCall[]; skills_loaded: string[]; model_slug: string;
      latency_s: number; usage: { total_tokens: number; model_calls: number; cost_usd: number | null };
      meta: Record<string, any> };
    outcome: { status: string; error: string | null; final_answer: string };
    grades: Grade[];
  };
  task: { id: string; kind: string; tags: string[]; input: any; expected: Record<string, any>; source: string } | null;
  passed: boolean;
}

export interface Catalog {
  models: Record<string, ModelSpec>; judge_configured: boolean; self_judged: boolean;
  langsmith: { enabled: boolean; project: string };
  tools: { name: string; description: string; side_effects: boolean; replayable: boolean; cost_hint: string; tags: string[] }[];
  skills: { name: string; description: string; version: string; tokens: number; assets: string[]; tool: string; body: string }[];
  graders: { type: string; layer: number; description: string }[];
  targets: string[]; metrics: string[]; middleware: string[];
  generators: { type: string; description: string }[];
  agents: { name: string; description: string; skill_loader_mode: string; skills: string | string[]; tools: string | string[] }[];
  suites: { name: string; description: string; agent: string; target: string; k: number; graders: string[]; datasets: string[];
    variant?: string | null; mode?: string | null }[];
  datasets: Record<string, number>;
  /** the active agent profile (added with profiles; absent on older servers) */
  profile?: ProfileView; modes?: string[]; trace_adapters?: string[];
}

export interface Candidate { id: string; source: string; tags: string[]; input: any; expected: Record<string, any>;
  has_transcript: boolean; thumbs: number | null }

export interface CompareResult {
  a: { id: string; name: string; model: string | null; pass_rate: number; n_trials: number };
  b: { id: string; name: string; model: string | null; pass_rate: number; n_trials: number };
  delta: number; two_proportion_z: { z: number; p_value: number };
  mcnemar: { chi2: number; p_value: number; a_pass_b_fail: number; b_pass_a_fail: number };
  regressions: string[]; improvements: string[]; unchanged: number;
  per_task: { task_id: string; a: number; b: number; delta: number }[];
  cost_latency: { a: Record<string, number>; b: Record<string, number> };
  config_diff: Record<string, any>;
  warnings?: string[];
}

export interface AlignmentStats { coverage: number | null; ffr: number | null; alignment: number | null; kappa: number;
  n: number; tp: number; tn: number; fp: number; fn: number; disagreements: { trial_id: string }[] }

export interface Calibration { n_labeled: number; message?: string; trial_level: AlignmentStats | null;
  graders: Record<string, AlignmentStats>; failure_tags?: Record<string, number> }
