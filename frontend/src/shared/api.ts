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
  /** run these dataset groups instead of the suite's own (the suite supplies graders/target/agent) */
  datasets?: string[];
}

export interface ImportOpts { limit: number; adapter?: string; source?: string; errors_only?: boolean }

const put = <T,>(path: string, content: string) => req<T>(path, { method: "PUT", body: JSON.stringify({ content }) });

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
  saveDatasetFile: (p: string, content: string) => put<{ saved: string; tasks: number }>(`/datasets/files/${p}`, content),
  suiteYaml: (name: string) => req<{ yaml: string; n_tasks: number }>(`/suites/${name}`),
  saveSuite: (name: string, content: string) =>
    put<{ saved: string; n_tasks: number; warning: string | null }>(`/suites/${name}`, content),
  faults: () => req<string[]>("/faults"),
  synthesisConfigs: () => req<string[]>("/synthesis/configs"),
  synthesize: (config: string, accept = false) => post<Record<string, any>>("/synthesis/run", { config, accept }),
  simulateTraffic: (n: number, fault_rate: number, agent?: string) =>
    post<Record<string, any>>("/traffic/simulate", { n, fault_rate, ...(agent ? { agent } : {}) }),
  importTraces: (o: ImportOpts) => post<Record<string, any>>("/traces/import", o),
  candidates: () => req<Candidate[]>("/candidates"),
  candidateYaml: (id: string) => req<{ id: string; content: string }>(`/candidates/${id}/yaml`),
  saveCandidateYaml: (id: string, content: string) => put<{ saved: string }>(`/candidates/${id}/yaml`, content),
  langsmith: () => req<{ enabled: boolean; has_key: boolean; tracing: boolean; project: string }>("/integrations/langsmith"),
  pushDataset: (group: string) => post<Record<string, any>>(`/integrations/langsmith/datasets/${group}/push`),
  pullDataset: (name: string) => post<Record<string, any>>(`/integrations/langsmith/datasets/${name}/pull`),
  acceptCandidates: (ids: string[], group: string) => post<Record<string, any>>("/candidates/accept", { ids, group }),
  rejectCandidates: (ids: string[]) => post<Record<string, any>>("/candidates/reject", { ids }),
  chatFeedback: (run_id: string, thumbs: number) => post("/chat/feedback", { run_id, thumbs }),
};
