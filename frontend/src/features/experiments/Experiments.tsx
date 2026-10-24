import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type LaunchBody } from "@/shared/api";
import { ago, pct } from "@/shared/format";
import { Card, ErrorBox, Loading, PageHead, StatusBadge } from "@/shared/ui";

export function Experiments() {
  const nav = useNavigate();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const list = useQuery({ queryKey: ["experiments"], queryFn: api.experiments, refetchInterval: 3000 });
  const [form, setForm] = useState<LaunchBody>({ suite: "smoke" });
  const [model, setModel] = useState("");
  const suite = catalog.data?.suites.find((s) => s.name === form.suite);
  const launch = useMutation({
    mutationFn: () => api.launch({ ...form, model: model || undefined }),
    onSuccess: (r) => nav(`/experiments/${r.id}`),
  });
  const set = (patch: Partial<LaunchBody>) => setForm((f) => ({ ...f, ...patch }));
  const num = (v: string) => (v === "" ? undefined : +v);

  return (
    <>
      <PageHead title="Experiments" sub="An experiment = suite × agent × model × k trials. Every run stores a full snapshot of what produced it." />
      <Card title="Launch">
        <div className="row" style={{ alignItems: "end" }}>
          <label>suite<select value={form.suite} onChange={(e) => set({ suite: e.target.value })}>{catalog.data?.suites.map((s) => <option key={s.name}>{s.name}</option>)}</select></label>
          <label>agent<select value={form.agent ?? ""} onChange={(e) => set({ agent: e.target.value || undefined })}>
            <option value="">suite default ({suite?.agent})</option>{catalog.data?.agents.map((a) => <option key={a.name}>{a.name}</option>)}</select></label>
          <label>k trials<input type="number" min={1} max={20} placeholder={String(suite?.k ?? 1)} style={{ width: 80 }} onChange={(e) => set({ k: num(e.target.value) })} /></label>
          <label>max tasks<input type="number" min={1} style={{ width: 80 }} onChange={(e) => set({ max_tasks: num(e.target.value) })} /></label>
          <label>tools<select value={form.tool_mode ?? ""} onChange={(e) => set({ tool_mode: e.target.value || undefined })}>
            <option value="">suite default</option><option>live</option><option>record</option><option>replay</option></select></label>
          <label>model override<input placeholder="openrouter:openai/gpt-4o-mini" value={model} onChange={(e) => setModel(e.target.value)} style={{ width: 250 }} /></label>
          <button className="primary" disabled={launch.isPending} onClick={() => launch.mutate()}>Run experiment</button>
        </div>
        {suite && <p className="small muted" style={{ margin: "8px 0 0" }}>{suite.description} · datasets: {suite.datasets.join(", ")} · graders: {suite.graders.join(", ")}</p>}
        <ErrorBox error={launch.error} />
      </Card>
      <Card title="History">
        {list.isLoading ? <Loading /> : (
          <div className="scroll-x"><table><thead><tr><th>name</th><th>suite</th><th>agent / model</th><th>status</th><th>pass</th><th>pass@k</th><th>pass^k</th><th>when</th></tr></thead><tbody>
            {list.data?.map((e) => {
              const pr = e.summary?.pass_rates;
              return (
                <tr key={e.id}>
                  <td><Link to={`/experiments/${e.id}`}>{e.name}</Link></td><td>{e.suite}</td>
                  <td className="small mono">{e.agent}<br />{e.model}</td><td><StatusBadge status={e.status} /></td>
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
