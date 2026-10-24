import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { GradeBadge } from "@/entities/GradeBadge";
import { api } from "@/shared/api";
import { num, pct, usd } from "@/shared/format";
import { streamSSE } from "@/shared/sse";
import type { RateStat } from "@/shared/types";
import { Badge, Card, ErrorBox, Kpi, Loading, PageHead, RateBar, StatusBadge } from "@/shared/ui";

function Breakdown({ title, data }: { title: string; data?: Record<string, RateStat> }) {
  const rows = Object.entries(data ?? {});
  if (!rows.length) return null;
  return (
    <Card title={title}>
      <table><tbody>{rows.map(([k, v]) => (
        <tr key={k}><td style={{ width: "42%" }}>{k}</td><td><RateBar rate={v.pass_rate} label={v.n ? pct(v.pass_rate) : "–"} /></td>
          <td className="muted small" style={{ width: 90 }}>n={v.n}{v.skipped ? ` · ${v.skipped} skipped` : ""}</td></tr>
      ))}</tbody></table>
    </Card>
  );
}

export function ExperimentDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const exp = useQuery({ queryKey: ["experiment", id], queryFn: () => api.experiment(id), refetchInterval: (q) => (q.state.data?.status === "running" || q.state.data?.status === "pending" ? 1500 : false) });
  const trials = useQuery({ queryKey: ["trials", id], queryFn: () => api.trials(id), refetchInterval: exp.data?.status === "running" ? 2000 : false });
  const [filter, setFilter] = useState<"all" | "failed" | "passed">("failed");
  const [live, setLive] = useState<string[]>([]);

  // live progress feed while the run is active
  const running = exp.data?.status === "running" || exp.data?.status === "pending";
  useEffect(() => {
    if (!running) return;
    const ctl = new AbortController();
    streamSSE(`/api/experiments/${id}/events`, {}, ({ event, data }) => {
      if (event === "trial_done") setLive((l) => [`${data.passed ? "PASS" : "FAIL"} ${data.task_id}#${data.index}`, ...l].slice(0, 8));
      if (event === "experiment_done") { void qc.invalidateQueries({ queryKey: ["experiment", id] }); void qc.invalidateQueries({ queryKey: ["trials", id] }); }
    }, ctl.signal).catch(() => undefined);
    return () => ctl.abort();
  }, [id, running, qc]);

  const regrade = useMutation({ mutationFn: () => api.regrade(id), onSuccess: (r) => nav(`/experiments/${r.id}`) });
  const cancel = useMutation({ mutationFn: () => api.cancel(id) });

  const rows = useMemo(() => (trials.data ?? []).filter((t) => (filter === "all" ? true : filter === "failed" ? !t.passed : t.passed)), [trials.data, filter]);
  const e = exp.data;
  if (!e) return exp.error ? <ErrorBox error={exp.error} /> : <Loading />;
  const s = e.summary, pr = s.pass_rates, cl = s.cost_latency;
  const agentModel = e.snapshot.models?.agent;

  return (
    <>
      <PageHead title={e.name} sub={`${e.suite} · target ${e.target} · ${agentModel?.provider}:${agentModel?.model} · git ${e.snapshot.git_sha ?? "–"}`}
        actions={<>
          <StatusBadge status={e.status} />
          {e.langsmith_url && <a href={e.langsmith_url} target="_blank" rel="noreferrer">LangSmith ↗</a>}
          {running && <button onClick={() => cancel.mutate()}>Cancel</button>}
          {!running && e.target !== "replay" && <button onClick={() => regrade.mutate()} disabled={regrade.isPending} title="Re-run the graders on the stored transcripts (agent is not re-run)">Re-grade</button>}
          <Link to={`/compare?a=${e.id}`}>Compare…</Link>
        </>} />
      <ErrorBox error={e.error ?? regrade.error} />
      {e.snapshot.self_judged && <div className="notice">Self-judged run: judge model equals the agent model.</div>}
      {running && (
        <Card title={`Running… ${e.done_trials}/${e.total_trials}`}>
          <RateBar rate={e.total_trials ? e.done_trials / e.total_trials : 0} label={`${e.done_trials}/${e.total_trials}`} />
          <div className="mono small" style={{ marginTop: 8 }}>{live.map((l, i) => <div key={i}>{l}</div>)}</div>
        </Card>
      )}
      {pr && (
        <div className="grid g4" style={{ marginBottom: 14 }}>
          <Kpi label="trial pass rate" value={pct(pr.trial_pass_rate)} sub={`95% CI ${pct(pr.ci95[0])}–${pct(pr.ci95[1])}`} />
          <Kpi label={`pass@${pr.k}`} value={pct(pr.mean_pass_at_k)} sub="can it succeed?" />
          <Kpi label={`pass^${pr.k}`} value={pct(pr.mean_pass_pow_k)} sub="does it always?" />
          <Kpi label="tasks · trials" value={`${pr.n_tasks} · ${pr.n_trials}`} sub={`k=${pr.k}`} />
        </div>
      )}
      <div className="grid g2">
        <Breakdown title="By grader" data={s.by_grader} />
        <Breakdown title="By tag" data={s.by_tag} />
      </div>
      {s.flakiness && (
        <Card title="Reliability">
          <div className="row"><Badge kind="good">{s.flakiness.reliable.length} reliable</Badge>
            <Badge kind="warn">{s.flakiness.flaky.length} flaky</Badge><Badge kind="bad">{s.flakiness.systematic.length} systematic failures</Badge>
            {!s.flakiness.informative && <span className="small muted">use k ≥ 3 to separate flaky from systematic</span>}</div>
          {s.flakiness.systematic.length > 0 && <p className="small"><strong>Systematic (0 passes):</strong> {s.flakiness.systematic.join(", ")}</p>}
          {s.flakiness.flaky.length > 0 && <p className="small"><strong>Flaky:</strong> {s.flakiness.flaky.join(", ")}</p>}
        </Card>
      )}
      {cl && (
        <Card title="Cost & latency"><div className="row">
          <Badge>p50 {num(cl.latency_p50_s, 1)}s</Badge><Badge>p95 {num(cl.latency_p95_s, 1)}s</Badge><Badge>{cl.tokens_total} tokens</Badge>
          <Badge>{usd(cl.cost_total_usd)}</Badge><Badge>{num(cl.steps_mean, 1)} steps/trial</Badge><Badge>{num(cl.tool_calls_mean, 1)} tool calls/trial</Badge>
          {cl.errors > 0 && <Badge kind="bad">{cl.errors} errored</Badge>}</div></Card>
      )}
      <Card title="Trials" right={<div className="row">{(["failed", "passed", "all"] as const).map((f) => <button key={f} className={filter === f ? "primary" : ""} onClick={() => setFilter(f)}>{f}</button>)}</div>}>
        {trials.isLoading ? <Loading /> : (
          <div className="scroll-x"><table><thead><tr><th>task</th><th>#</th><th /><th>request</th><th>skills / tools</th><th>graders</th></tr></thead><tbody>
            {rows.map((t) => (
              <tr key={t.id} className="click" onClick={() => nav(`/trials/${t.id}`)}>
                <td className="mono">{t.task_id}</td><td>{t.index}</td><td><Badge kind={t.passed ? "good" : "bad"}>{t.passed ? "pass" : t.status !== "ok" ? t.status : "fail"}</Badge></td>
                <td style={{ maxWidth: 300 }}>{t.user_text.slice(0, 110)}</td>
                <td className="small">{t.skills_loaded.map((x) => <Badge key={x} kind="info">{x}</Badge>)} <span className="mono muted">{t.tools.filter((x) => !x.startsWith("load_skill")).join(", ")}</span></td>
                <td className="row">{t.grades.filter((g) => !g.skipped).map((g) => <GradeBadge key={g.grader} g={g} />)}</td>
              </tr>
            ))}</tbody></table></div>
        )}
        {rows.length === 0 && !trials.isLoading && <p className="muted">No {filter} trials.</p>}
      </Card>
    </>
  );
}
