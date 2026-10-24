import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { GradeBadge } from "@/entities/GradeBadge";
import { TranscriptTimeline } from "@/entities/TranscriptTimeline";
import { api } from "@/shared/api";
import { num, usd } from "@/shared/format";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

export function TrialPage() {
  const { id = "" } = useParams();
  const q = useQuery({ queryKey: ["trial", id], queryFn: () => api.trial(id) });
  if (!q.data) return q.error ? <ErrorBox error={q.error} /> : <Loading />;
  const { trial: t, task, passed } = q.data;
  const tr = t.transcript;
  return (
    <>
      <PageHead title={`${t.task_id} · trial ${t.index}`} sub={`${tr.model_slug} · ${num(tr.latency_s, 1)}s · ${tr.usage.total_tokens} tokens · ${usd(tr.usage.cost_usd)}`}
        actions={<><Badge kind={passed ? "good" : "bad"}>{passed ? "passed" : "failed"}</Badge><Link to={`/experiments/${t.experiment_id}`}>← experiment</Link>
          {tr.meta.langsmith_run_id && <span className="small muted mono" title="Find this run in LangSmith via metadata.trial_id">run {String(tr.meta.langsmith_run_id).slice(0, 8)}</span>}</>} />
      {t.outcome.status !== "ok" && <ErrorBox error={`${t.outcome.status}: ${t.outcome.error}`} />}
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.4fr) minmax(0,1fr)" }}>
        <Card title="Transcript"><TranscriptTimeline messages={tr.messages} toolCalls={tr.tool_calls} /></Card>
        <div>
          <Card title="Grader verdicts">
            {t.grades.length === 0 && <p className="muted">No grades (the trial did not complete).</p>}
            {t.grades.map((g) => (
              <div key={g.grader} style={{ marginBottom: 10 }}>
                <div className="row"><GradeBadge g={g} /><span className="small muted">layer {g.layer}{g.score != null ? ` · score ${num(g.score)}` : ""}</span></div>
                <div className="small">{g.rationale}</div>
              </div>
            ))}
          </Card>
          {tr.skills_loaded.length > 0 && <Card title="Skills loaded">{tr.skills_loaded.map((s) => <Badge key={s} kind="info">{s}</Badge>)}</Card>}
          {task && <Card title="Task & expectations"><div className="small muted">{task.kind} · {task.source} · {task.tags.join(", ")}</div><pre style={{ marginTop: 6 }}>{JSON.stringify(Object.fromEntries(Object.entries(task.expected).filter(([, v]) => (Array.isArray(v) ? v.length > 0 : v != null))), null, 2)}</pre></Card>}
          {(tr.meta.guardrail_events?.length ?? 0) > 0 && <Card title="Guardrail events"><pre>{JSON.stringify(tr.meta.guardrail_events, null, 2)}</pre></Card>}
        </div>
      </div>
    </>
  );
}
