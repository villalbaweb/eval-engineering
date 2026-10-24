import type {
  Calibration, Candidate, Catalog, CompareResult, Experiment, TrialDetail, TrialRow,
} from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" }, ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) => req<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export interface LaunchBody {
  suite: string; name?: string; agent?: string; k?: number; concurrency?: number; tool_mode?: string;
  target?: string; max_tasks?: number; model?: string;
}

export const api = {
  catalog: () => req<Catalog>("/catalog"),
  experiments: () => req<Experiment[]>("/experiments"),
  experiment: (id: string) => req<Experiment>(`/experiments/${id}`),
  trials: (id: string) => req<TrialRow[]>(`/experiments/${id}/trials`),
  trial: (id: string) => req<TrialDetail>(`/trials/${id}`),
  launch: (b: LaunchBody) => post<{ id: string; total: number }>("/experiments", b),
  cancel: (id: string) => post(`/experiments/${id}/cancel`),
  regrade: (id: string, body: { suite?: string; name?: string } = {}) =>
    post<{ id: string }>(`/experiments/${id}/regrade`, body),
  compare: (a: string, b: string) => req<CompareResult>(`/compare?a=${a}&b=${b}`),
  queue: (experimentId: string, onlyUnlabeled: boolean) =>
    req<any[]>(`/annotations/queue?experiment_id=${experimentId}&only_unlabeled=${onlyUnlabeled}`),
  annotate: (b: { trial_id: string; good: boolean; failure_tags: string[]; note: string }) =>
    post("/annotations", b),
  calibration: (experimentId?: string) =>
    req<Calibration>(`/calibration${experimentId ? `?experiment_id=${experimentId}` : ""}`),
  datasetFiles: () => req<string[]>("/datasets/files"),
  datasetFile: (p: string) => req<{ path: string; content: string }>(`/datasets/files/${p}`),
  saveDatasetFile: (p: string, content: string) =>
    req<{ saved: string; tasks: number }>(`/datasets/files/${p}`, { method: "PUT", body: JSON.stringify({ content }) }),
  suiteYaml: (name: string) => req<{ yaml: string; n_tasks: number }>(`/suites/${name}`),
  synthesisConfigs: () => req<string[]>("/synthesis/configs"),
  synthesize: (config: string) => post<Record<string, any>>("/synthesis/run", { config }),
  simulateTraffic: (n: number, fault_rate: number) => post<Record<string, any>>("/traffic/simulate", { n, fault_rate }),
  importTraces: (limit: number) => post<Record<string, any>>("/traces/import", { limit }),
  candidates: () => req<Candidate[]>("/candidates"),
  acceptCandidates: (ids: string[], group: string) => post<Record<string, any>>("/candidates/accept", { ids, group }),
  rejectCandidates: (ids: string[]) => post<Record<string, any>>("/candidates/reject", { ids }),
  chatFeedback: (run_id: string, thumbs: number) => post("/chat/feedback", { run_id, thumbs }),
};
