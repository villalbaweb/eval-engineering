import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { GradeBadge } from "@/entities/GradeBadge";
import { api } from "@/shared/api";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

const TAGS = ["wrong_skill", "wrong_tool", "bad_args", "ungrounded", "ignored_error", "off_topic", "too_verbose", "incomplete", "other"];

export function Annotate() {
  const [sp, setSp] = useSearchParams();
  const expId = sp.get("experiment") ?? "";
  const qc = useQueryClient();
  const exps = useQuery({ queryKey: ["experiments"], queryFn: api.experiments });
  const queue = useQuery({ queryKey: ["queue", expId], queryFn: () => api.queue(expId, true), enabled: !!expId });
  const [tags, setTags] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const item = queue.data?.[0];
  const save = useMutation({
    mutationFn: (good: boolean) => api.annotate({ trial_id: item.trial_id, good, failure_tags: good ? [] : tags, note }),
    onSuccess: () => { setTags([]); setNote(""); void qc.invalidateQueries({ queryKey: ["queue", expId] }); void qc.invalidateQueries({ queryKey: ["calibration"] }); },
  });
  const toggle = (t: string) => setTags((x) => (x.includes(t) ? x.filter((y) => y !== t) : [...x, t]));

  return (
    <>
      <PageHead title="Annotate" sub="Your judgement is the ground truth. Label trials good/bad (without looking at the grader first if you can), then check calibration." />
      <Card><label>experiment
        <select value={expId} onChange={(e) => setSp({ experiment: e.target.value })} style={{ minWidth: 340 }}>
          <option value="">select…</option>{(exps.data ?? []).filter((e) => e.status === "completed").map((e) => <option key={e.id} value={e.id}>{e.name} · {e.suite}</option>)}</select></label></Card>
      <ErrorBox error={queue.error ?? save.error} />
      {expId && queue.isLoading && <Loading />}
      {expId && queue.data && !item && <Card><p>All trials in this experiment are labelled. <Link to={`/calibration?experiment=${expId}`}>See calibration →</Link></p></Card>}
      {item && (
        <Card title={`${item.task_id}`} right={<span className="muted small">{queue.data!.length} left</span>}>
          <h3>Request</h3><p>{item.user_text}</p>
          <h3>Answer</h3><pre>{item.answer || "(empty)"}</pre>
          <p className="small muted">skills: {item.skills.join(", ") || "none"} · tools: {item.tools.join(", ") || "none"}</p>
          <h3>Failure tags (if bad)</h3>
          <div className="row">{TAGS.map((t) => <button key={t} className={tags.includes(t) ? "primary" : ""} onClick={() => toggle(t)}>{t}</button>)}</div>
          <label style={{ marginTop: 10 }}>note<textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} style={{ fontFamily: "inherit" }} /></label>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="good" disabled={save.isPending} onClick={() => save.mutate(true)}>👍 Good</button>
            <button className="bad" disabled={save.isPending} onClick={() => save.mutate(false)}>👎 Bad</button>
            <Link to={`/trials/${item.trial_id}`} target="_blank">open full transcript ↗</Link>
          </div>
          <details style={{ marginTop: 12 }}><summary className="small muted">reveal grader verdicts (labels are less biased if you don’t peek)</summary>
            <div className="row" style={{ marginTop: 6 }}>{item.grades.map((g: any) => <GradeBadge key={g.grader} g={g} />)}<Badge kind={item.passed ? "good" : "bad"}>trial {item.passed ? "pass" : "fail"}</Badge></div></details>
        </Card>
      )}
    </>
  );
}
