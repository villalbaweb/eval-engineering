import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { can, findVariant } from "@/entities/profile";
import { api, type LaunchBody } from "@/shared/api";
import { ago, pct } from "@/shared/format";
import { Badge, Card, ErrorBox, Loading, PageHead, StatusBadge } from "@/shared/ui";

export function Experiments() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const list = useQuery({ queryKey: ["experiments"], queryFn: api.experiments, refetchInterval: 3000 });
  // ?suite=traces&datasets=accepted pre-fills the form (links from Datasets, Data sources, Suites)
  const [form, setForm] = useState<LaunchBody>(() => ({
    suite: params.get("suite") ?? "smoke",
    datasets: params.get("datasets")?.split(",").filter(Boolean) || undefined,
  }));
  const [model, setModel] = useState("");
  const profile = catalog.data?.profile;
  const suite = catalog.data?.suites.find((s) => s.name === form.suite);
  // what will actually run: the chosen variant, else the suite's, else the profile default
  const suiteVariant = suite?.variant || (findVariant(profile, suite?.agent) ? suite?.agent : profile?.default_variant);
  const variant = form.variant || suiteVariant || undefined;
  const MODE_OF_TARGET: Record<string, string> = { local_agent: "live", multiturn_sim: "multiturn", trace: "trace", replay: "replay" };
  const mode = form.mode || suite?.mode || MODE_OF_TARGET[suite?.target ?? ""] || "live";
  const runsAgent = mode === "live" || mode === "multiturn";
  const blocked = runsAgent && profile && !can(profile, variant, mode === "multiturn" ? "chat" : "rerun")
    ? `variant ${variant} cannot ${mode === "multiturn" ? "hold a conversation" : "be run from the lab"} (only its logged runs exist): pick mode "trace"`
    : null;
  const groups = Object.entries(catalog.data?.datasets ?? {});
  const override = !!form.datasets?.length;
  const launch = useMutation({
    mutationFn: () => api.launch({ ...form, model: model || undefined }),
    onSuccess: (r) => nav(`/experiments/${r.id}`),
  });
  const set = (patch: Partial<LaunchBody>) => setForm((f) => ({ ...f, ...patch }));
  const num = (v: string) => (v === "" ? undefined : +v);
  const suiteData = (name: string) => catalog.data?.suites.find((s) => s.name === name)?.datasets.join(",");
  const toggleGroup = (g: string) => {
    const cur = new Set(form.datasets ?? []);
    cur.has(g) ? cur.delete(g) : cur.add(g);
    set({ datasets: cur.size ? [...cur] : undefined });
  };

  return (
    <>
      <PageHead title="Experiments" sub="An experiment = suite × agent × model × k trials. Every run stores a full snapshot of what produced it." />
      <Card title="Launch">
        <div className="row" style={{ alignItems: "end" }}>
          <label>suite<select value={form.suite} onChange={(e) => set({ suite: e.target.value })}>{catalog.data?.suites.map((s) => <option key={s.name}>{s.name}</option>)}</select></label>
          <label>variant<select value={form.variant ?? ""} onChange={(e) => set({ variant: e.target.value || undefined })}>
            <option value="">suite default ({suiteVariant ?? "–"})</option>
            {(profile?.variants.map((v) => v.name) ?? catalog.data?.agents.map((a) => a.name) ?? []).map((n) => <option key={n}>{n}</option>)}</select></label>
          <label>mode<select value={form.mode ?? ""} onChange={(e) => set({ mode: e.target.value || undefined })}
            title="live: send tasks to the agent · multiturn: simulated user · trace: grade logged runs stored in the tasks">
            <option value="">suite default ({suite?.mode || MODE_OF_TARGET[suite?.target ?? ""] || suite?.target})</option>
            {(catalog.data?.modes ?? ["live", "multiturn", "trace"]).filter((m) => m !== "replay").map((m) => <option key={m}>{m}</option>)}</select></label>
          <label>k trials<input type="number" min={1} max={20} placeholder={String(suite?.k ?? 1)} style={{ width: 80 }} onChange={(e) => set({ k: num(e.target.value) })} /></label>
          <label>max tasks<input type="number" min={1} style={{ width: 80 }} onChange={(e) => set({ max_tasks: num(e.target.value) })} /></label>
          <label>concurrency<input type="number" min={1} max={32} placeholder="suite" style={{ width: 80 }} onChange={(e) => set({ concurrency: num(e.target.value) })} /></label>
          {runsAgent && can(profile, variant, "record_replay") && <label>tools<select value={form.tool_mode ?? ""} onChange={(e) => set({ tool_mode: e.target.value || undefined })}>
            <option value="">suite default</option><option>live</option><option>record</option><option>replay</option></select></label>}
          {runsAgent && can(profile, variant, "model_override") && <label>model override<input placeholder="openrouter:openai/gpt-4o-mini" value={model} onChange={(e) => setModel(e.target.value)} style={{ width: 250 }} /></label>}
          <label>name<input placeholder="auto" onChange={(e) => set({ name: e.target.value || undefined })} style={{ width: 160 }} /></label>
          <button className="primary" disabled={launch.isPending || !!blocked} onClick={() => launch.mutate()}>Run experiment</button>
        </div>
        {blocked && <div className="notice" style={{ marginTop: 8 }}>{blocked}</div>}

        <div style={{ marginTop: 10 }}>
          <div className="small muted">datasets · {override
            ? <>running <strong>{form.datasets!.join(", ")}</strong> with the graders, mode and variant of <strong>{form.suite}</strong> (suite tag filters are dropped)</>
            : <>suite default: {suite?.datasets.join(", ")} · tick groups to run other data with this suite's graders</>}</div>
          <div className="row" style={{ marginTop: 4 }}>
            {groups.map(([g, n]) => (
              <label key={g} className="row" style={{ gap: 4, fontWeight: 400 }}>
                <input type="checkbox" checked={!!form.datasets?.includes(g)} onChange={() => toggleGroup(g)} />
                <span className="mono small">{g}</span><span className="muted small">({n})</span>
                {suite?.datasets.includes(g) && !override && <Badge>in suite</Badge>}
              </label>))}
            {override && <button onClick={() => set({ datasets: undefined })}>use suite datasets</button>}
          </div>
        </div>
        {suite && <p className="small muted" style={{ margin: "8px 0 0" }}>{suite.description} · graders: {suite.graders.join(", ")} · <Link to={`/suites?name=${suite.name}`}>edit suite</Link></p>}
        <ErrorBox error={launch.error} />
      </Card>
      <Card title="History">
        {list.isLoading ? <Loading /> : (
          <div className="scroll-x"><table><thead><tr><th>name</th><th>suite</th><th>agent / model</th><th>status</th><th>pass</th><th>pass@k</th><th>pass^k</th><th>when</th></tr></thead><tbody>
            {list.data?.map((e) => {
              const pr = e.summary?.pass_rates;
              return (
                <tr key={e.id}>
                  <td><Link to={`/experiments/${e.id}`}>{e.name}</Link></td>
                  <td>{e.suite}{e.datasets && suiteData(e.suite) !== e.datasets.join(",") && <div className="small muted">data: {e.datasets.join(", ")}</div>}</td>
                  <td className="small mono">{e.agent ?? e.variant ?? "–"}{e.mode && e.mode !== "live" ? ` · ${e.mode}` : ""}<br />{e.model}</td><td><StatusBadge status={e.status} /></td>
                  <td>{pct(pr?.trial_pass_rate)}</td><td>{pct(pr?.mean_pass_at_k)}</td><td>{pct(pr?.mean_pass_pow_k)}</td><td className="muted">{ago(e.created_at)}</td>
                </tr>
              );
            })}</tbody></table></div>
        )}
        {list.data?.length === 0 && <p className="muted">No experiments yet. Run the smoke suite to start.</p>}
      </Card>
    </>
  );
}
