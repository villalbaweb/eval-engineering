import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/shared/api";
import { num, pct, signedPct } from "@/shared/format";
import { Badge, Card, ErrorBox, Kpi, Loading, PageHead } from "@/shared/ui";

export function Compare() {
  const [sp, setSp] = useSearchParams();
  const a = sp.get("a") ?? "", b = sp.get("b") ?? "";
  const list = useQuery({ queryKey: ["experiments"], queryFn: api.experiments });
  const cmp = useQuery({ queryKey: ["compare", a, b], queryFn: () => api.compare(a, b), enabled: !!a && !!b });
  const set = (k: "a" | "b", v: string) => { const n = new URLSearchParams(sp); n.set(k, v); setSp(n); };
  const opts = (list.data ?? []).filter((e) => e.status === "completed");
  const r = cmp.data;
  const sig = r && r.two_proportion_z.p_value < 0.05;

  return (
    <>
      <PageHead title="Compare" sub="B against A: regressions first, with significance tests. Compare only runs of the same suite." />
      <Card><div className="row">
        {(["a", "b"] as const).map((k) => (
          <label key={k}>{k === "a" ? "A (baseline)" : "B (candidate)"}
            <select value={k === "a" ? a : b} onChange={(e) => set(k, e.target.value)} style={{ minWidth: 300 }}>
              <option value="">select…</option>
              {opts.map((e) => <option key={e.id} value={e.id}>{e.name} · {e.suite} · {pct(e.summary?.pass_rates?.trial_pass_rate)}</option>)}
            </select></label>
        ))}</div></Card>
      <ErrorBox error={cmp.error} />
      {cmp.isLoading && <Loading />}
      {r && (
        <>
          <div className="grid g4" style={{ marginBottom: 14 }}>
            <Kpi label={`A · ${r.a.name}`} value={pct(r.a.pass_rate)} sub={`n=${r.a.n_trials}`} />
            <Kpi label={`B · ${r.b.name}`} value={pct(r.b.pass_rate)} sub={`n=${r.b.n_trials}`} />
            <Kpi label="difference (B − A)" value={signedPct(r.delta)} sub={sig ? "significant (p<0.05)" : "not significant"} />
            <Kpi label="p-values" value={`z ${num(r.two_proportion_z.p_value, 3)}`} sub={`McNemar ${num(r.mcnemar.p_value, 3)}`} />
          </div>
          {(r.warnings ?? []).map((w) => <div key={w} className="notice">{w}</div>)}
          {!sig && <div className="notice">The difference is within noise at this sample size. Run more trials (higher k) or more tasks before concluding anything.</div>}
          {Object.keys(r.config_diff).length > 0 && <Card title="What differs between the runs"><pre>{JSON.stringify(r.config_diff, null, 2).slice(0, 1500)}</pre></Card>}
          <Card title={`Per task (${r.regressions.length} regressions · ${r.improvements.length} improvements · ${r.unchanged} unchanged)`}>
            <table><thead><tr><th>task</th><th>A</th><th>B</th><th>Δ</th></tr></thead><tbody>
              {r.per_task.filter((t) => t.delta !== 0).map((t) => (
                <tr key={t.task_id}><td className="mono"><Link to={`/experiments/${a}`}>{t.task_id}</Link></td><td>{pct(t.a)}</td><td>{pct(t.b)}</td>
                  <td><Badge kind={t.delta < 0 ? "bad" : "good"}>{signedPct(t.delta)}</Badge></td></tr>
              ))}</tbody></table>
            {r.per_task.every((t) => t.delta === 0) && <p className="muted">Identical per-task results.</p>}
          </Card>
        </>
      )}
    </>
  );
}
