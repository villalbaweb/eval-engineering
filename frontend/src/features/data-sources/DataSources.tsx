import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { runGroupHref, suggestedSuite, suitesUsing } from "@/entities/datasetGroups";
import { api, type ImportOpts } from "@/shared/api";
import type { ProfileView } from "@/shared/types";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

function Result({ data }: { data: unknown }) {
  return data ? <pre style={{ marginTop: 8 }}>{JSON.stringify(data, null, 2)}</pre> : null;
}

/** Edit one candidate (typically: add `expected`) before accepting it. The logged transcript is kept server-side. */
function CandidateEditor({ id, onDone, profile }: { id: string; onDone: () => void; profile?: ProfileView }) {
  const q = useQuery({ queryKey: ["candidate-yaml", id], queryFn: () => api.candidateYaml(id) });
  const [text, setText] = useState("");
  useEffect(() => { if (q.data) setText(q.data.content); }, [q.data]);
  const save = useMutation({
    mutationFn: () => api.saveCandidateYaml(id, text),
    onSuccess: (r) => { if (!r.warnings?.length) onDone(); },  // keep the editor open to show warnings
  });
  const inv = profile?.inventory;
  return (
    <Card title={`Edit ${id}`} right={<div className="row">
      <button className="primary" disabled={save.isPending || text === q.data?.content} onClick={() => save.mutate()}>Save</button>
      <button onClick={onDone}>Close</button></div>}>
      <ErrorBox error={q.error ?? save.error} />
      {save.data?.warnings?.length ? <div className="notice">Saved, but check these names: {save.data.warnings.join("; ")}</div> : null}
      <p className="small muted" style={{ marginTop: 0 }}>Add what the right behaviour is, e.g. <code>expected: {"{ skills_loaded: [...], tool_calls: [{ name: ... }] }"}</code>. Without
        expectations only reference-free graders (judge, groundedness, guardrails, efficiency) can say anything. The transcript is hidden here and preserved.</p>
      {inv && (inv.tools.length > 0 || inv.skills.length > 0) && (
        <p className="small muted">{profile?.name} skills: {inv.skills.map((s) => <code key={s.name} style={{ marginRight: 4 }}>{s.name}</code>)}
          · tools: {inv.tools.filter((t) => !t.name.startsWith("load_skill_")).map((t) => <code key={t.name} style={{ marginRight: 4 }}>{t.name}</code>)}</p>)}
      {q.isLoading ? <Loading /> : <textarea rows={16} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label="candidate yaml" />}
    </Card>
  );
}

export function DataSources() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["candidates"] });
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const configs = useQuery({ queryKey: ["syn-configs"], queryFn: api.synthesisConfigs });
  const cands = useQuery({ queryKey: ["candidates"], queryFn: api.candidates });
  const [config, setConfig] = useState("skill-queries");
  const [skipReview, setSkipReview] = useState(false);
  const [n, setN] = useState(10);
  const [fault, setFault] = useState(0.3);
  const [trafficAgent, setTrafficAgent] = useState("");
  const [imp, setImp] = useState<ImportOpts>({ limit: 50 });
  const [group, setGroup] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<string | null>(null);
  const [lastAccepted, setLastAccepted] = useState<{ group: string; transcripts: boolean; warnings: string[] } | null>(null);

  const profile = catalog.data?.profile;
  const defaults = profile?.defaults;
  const all = cands.data ?? [];
  const chosen = all.filter((c) => sel.has(c.id));
  const allTraces = chosen.length > 0 && chosen.every((c) => c.has_transcript);
  // traces default to the profile's trace group, which its trace suite (grades logged runs) already runs
  const effectiveGroup = group || (allTraces ? defaults?.trace_group ?? "traces" : "accepted");
  const usedBy = suitesUsing(catalog.data, effectiveGroup);
  const trafficVariants = profile ? profile.variants.filter((v) => v.capabilities.includes("traffic_sim")) : null;
  const canTraffic = trafficVariants === null || trafficVariants.length > 0;

  const synth = useMutation({ mutationFn: () => api.synthesize(config, skipReview), onSuccess: () => { void refresh(); void qc.invalidateQueries({ queryKey: ["catalog"] }); } });
  const traffic = useMutation({ mutationFn: () => api.simulateTraffic(n, fault, trafficAgent || undefined) });
  const importM = useMutation({ mutationFn: () => api.importTraces(imp), onSuccess: refresh });
  const accept = useMutation({
    mutationFn: () => api.acceptCandidates([...sel], effectiveGroup),
    onSuccess: (r) => {
      setLastAccepted({ group: effectiveGroup, transcripts: allTraces, warnings: r.warnings ?? [] });
      setSel(new Set()); void refresh(); void qc.invalidateQueries({ queryKey: ["catalog"] });
    },
  });
  const reject = useMutation({ mutationFn: () => api.rejectCandidates([...sel]), onSuccess: () => { setSel(new Set()); void refresh(); } });
  const toggle = (id: string) => setSel((s) => { const x = new Set(s); x.has(id) ? x.delete(id) : x.add(id); return x; });
  const setI = (p: Partial<ImportOpts>) => setImp((o) => ({ ...o, ...p }));

  return (
    <>
      <PageHead title="Data sources" sub="Two ways to get tasks: synthetic generators, and traces logged from simulated traffic or the Playground. Both land in the same review queue." />
      <div className="grid g3">
        <Card title="1 · Synthesize">
          <div className="row"><label>generator config
            <select value={config} onChange={(e) => setConfig(e.target.value)}>{(configs.data ?? [config]).map((c) => <option key={c}>{c}</option>)}</select></label>
            <button className="primary" disabled={synth.isPending} onClick={() => synth.mutate()}>Generate</button></div>
          <label className="row small" style={{ gap: 4, marginTop: 6, fontWeight: 400 }}><input type="checkbox" checked={skipReview} onChange={(e) => setSkipReview(e.target.checked)} />skip review (write straight to datasets)</label>
          <ErrorBox error={synth.error} /><Result data={synth.data && { generated: synth.data.generated, queued: synth.data.queued, duplicates: synth.data.duplicates_dropped, leaks: synth.data.leaks_dropped, ...(synth.data.file ? { file: synth.data.file } : {}) }} />
        </Card>
        <Card title="2 · Simulate traffic">
          {!canTraffic ? <p className="small muted">{profile?.name} has no variant that can receive simulated traffic (none is runnable from the lab).
            Use <strong>Import traces</strong> to bring in its logged runs instead.</p> : <>
          <div className="row"><label>sessions<input type="number" min={1} max={200} value={n} onChange={(e) => setN(+e.target.value)} style={{ width: 80 }} /></label>
            <label>fault rate<input type="number" min={0} max={1} step={0.1} value={fault} onChange={(e) => setFault(+e.target.value)} style={{ width: 80 }} /></label>
            <label>variant<select value={trafficAgent} onChange={(e) => setTrafficAgent(e.target.value)}>
              <option value="">{profile?.default_variant ?? "copilot-baseline"} (default)</option>
              {(trafficVariants?.map((v) => v.name) ?? catalog.data?.agents.map((a) => a.name) ?? [])
                .filter((v) => v !== (profile?.default_variant ?? "copilot-baseline")).map((v) => <option key={v}>{v}</option>)}</select></label>
            <button className="primary" disabled={traffic.isPending} onClick={() => traffic.mutate()}>Run</button></div>
          <p className="small muted">Simulated users talk to the agent; runs are traced to LangSmith (source=traffic) and saved locally.</p>
          <ErrorBox error={traffic.error} /><Result data={traffic.data} /></>}
        </Card>
        <Card title="3 · Import traces">
          <div className="row">
            <label>from<select value={imp.adapter ?? ""} onChange={(e) => setI({ adapter: e.target.value || undefined })}>
              <option value="">{profile?.traces.adapter ? `profile default (${profile.traces.adapter})` : "auto"}</option>
              <option value="langsmith">LangSmith</option><option value="jsonl">local traffic files</option></select></label>
            <label>source<select value={imp.source ?? ""} onChange={(e) => setI({ source: e.target.value || undefined })}>
              <option value="">any</option><option>playground</option><option>traffic</option><option>experiment</option></select></label>
            <label>limit<input type="number" min={1} max={500} value={imp.limit} onChange={(e) => setI({ limit: +e.target.value || 50 })} style={{ width: 70 }} /></label>
          </div>
          <label className="row small" style={{ gap: 4, marginTop: 6, fontWeight: 400 }}><input type="checkbox" checked={!!imp.errors_only} onChange={(e) => setI({ errors_only: e.target.checked || undefined })} />errored runs only</label>
          <button className="primary" style={{ marginTop: 8 }} disabled={importM.isPending} onClick={() => importM.mutate()}>Import logged traces</button>
          <p className="small muted">{profile?.traces.adapter || profile?.traces.path || profile?.traces.project
            ? <>Defaults come from <strong>{profile.name}</strong>'s profile ({[profile.traces.adapter, profile.traces.project, profile.traces.path].filter(Boolean).join(", ")}); traces are read with its conventions. </>
            : <>auto = LangSmith when enabled, otherwise the local traffic files. </>}
            PII is scrubbed; duplicates dropped. Source filters apply to LangSmith.</p>
          <ErrorBox error={importM.error} /><Result data={importM.data && { fetched: importM.data.fetched, queued: importM.data.queued, duplicates: importM.data.duplicates_dropped }} />
        </Card>
      </div>

      {editing && <CandidateEditor id={editing} profile={profile} onDone={() => { setEditing(null); void refresh(); }} />}

      {lastAccepted && (
        <div className="notice">Accepted into <strong>{lastAccepted.group}</strong>.{" "}
          {suitesUsing(catalog.data, lastAccepted.group).length
            ? <>Used by {suitesUsing(catalog.data, lastAccepted.group).join(", ")}. </>
            : <>No suite lists this group yet, but you can still run it. </>}
          {lastAccepted.warnings.length > 0 && <>Check: {lastAccepted.warnings.join("; ")}. </>}
          <Link to={runGroupHref(lastAccepted.group, suitesUsing(catalog.data, lastAccepted.group)[0] ?? suggestedSuite(lastAccepted.transcripts, defaults))}>Run it now…</Link>
          {" · "}<Link to="/datasets">open in Datasets</Link>{" · "}<button onClick={() => setLastAccepted(null)}>dismiss</button>
        </div>)}

      <Card title={`Review queue (${all.length})`} right={
        <div className="row"><label>dataset group<input list="dataset-groups" value={group} placeholder={effectiveGroup} onChange={(e) => setGroup(e.target.value.trim())} style={{ width: 130 }} /></label>
          <datalist id="dataset-groups">{Object.keys(catalog.data?.datasets ?? {}).map((g) => <option key={g} value={g} />)}</datalist>
          <button className="good" disabled={!sel.size || accept.isPending} onClick={() => accept.mutate()}>Accept {sel.size || ""}</button>
          <button className="bad" disabled={!sel.size || reject.isPending} onClick={() => reject.mutate()}>Reject</button>
          <button onClick={() => setSel(new Set(all.map((c) => c.id)))}>Select all</button></div>}>
        <ErrorBox error={accept.error ?? reject.error} />
        {sel.size > 0 && <p className="small muted" style={{ marginTop: 0 }}>Accept writes to <code>evals/datasets/{effectiveGroup}/{effectiveGroup}.yaml</code> · {usedBy.length ? `run by suite(s): ${usedBy.join(", ")}` : "no suite lists this group (you can still run it from Experiments)"}</p>}
        {cands.isLoading ? <Loading /> : all.length === 0 ? <p className="muted">Nothing waiting for review. Generate or import some above.</p> : (
          <div className="scroll-x"><table><thead><tr><th /><th>id</th><th>source</th><th>input</th><th>expects</th><th>signals</th><th /></tr></thead><tbody>
            {all.map((c) => (
              <tr key={c.id}><td><input type="checkbox" checked={sel.has(c.id)} onChange={() => toggle(c.id)} aria-label={`select ${c.id}`} /></td>
                <td className="mono">{c.id}</td><td><Badge kind="info">{c.source}</Badge></td>
                <td style={{ maxWidth: 380 }}>{c.input?.messages?.[0]?.content}</td>
                <td className="small mono">{Object.entries(c.expected).filter(([, v]) => (Array.isArray(v) ? v.length : v != null)).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ").slice(0, 90) || <span className="muted">none yet</span>}</td>
                <td className="row">{c.has_transcript && <Badge>transcript</Badge>}{c.thumbs === 0 && <Badge kind="bad">👎</Badge>}{c.tags.includes("error") && <Badge kind="bad">error</Badge>}</td>
                <td><button onClick={() => setEditing(c.id)}>edit</button></td></tr>
            ))}</tbody></table></div>
        )}
      </Card>
    </>
  );
}
