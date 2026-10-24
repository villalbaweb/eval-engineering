import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/shared/api";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

function Result({ data }: { data: unknown }) {
  return data ? <pre style={{ marginTop: 8 }}>{JSON.stringify(data, null, 2)}</pre> : null;
}

export function DataSources() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["candidates"] });
  const configs = useQuery({ queryKey: ["syn-configs"], queryFn: api.synthesisConfigs });
  const cands = useQuery({ queryKey: ["candidates"], queryFn: api.candidates });
  const [config, setConfig] = useState("skill-queries");
  const [n, setN] = useState(10);
  const [fault, setFault] = useState(0.3);
  const [group, setGroup] = useState("accepted");
  const [sel, setSel] = useState<Set<string>>(new Set());

  const synth = useMutation({ mutationFn: () => api.synthesize(config), onSuccess: refresh });
  const traffic = useMutation({ mutationFn: () => api.simulateTraffic(n, fault) });
  const imp = useMutation({ mutationFn: () => api.importTraces(50), onSuccess: refresh });
  const accept = useMutation({ mutationFn: () => api.acceptCandidates([...sel], group), onSuccess: () => { setSel(new Set()); void refresh(); void qc.invalidateQueries({ queryKey: ["catalog"] }); } });
  const reject = useMutation({ mutationFn: () => api.rejectCandidates([...sel]), onSuccess: () => { setSel(new Set()); void refresh(); } });
  const toggle = (id: string) => setSel((s) => { const x = new Set(s); x.has(id) ? x.delete(id) : x.add(id); return x; });
  const all = cands.data ?? [];

  return (
    <>
      <PageHead title="Data sources" sub="Two ways to get tasks: synthetic generators, and traces logged from simulated traffic. Both land in the same review queue." />
      <div className="grid g3">
        <Card title="1 · Synthesize">
          <div className="row"><label>generator config
            <select value={config} onChange={(e) => setConfig(e.target.value)}>{(configs.data ?? [config]).map((c) => <option key={c}>{c}</option>)}</select></label>
            <button className="primary" disabled={synth.isPending} onClick={() => synth.mutate()}>Generate</button></div>
          <ErrorBox error={synth.error} /><Result data={synth.data && { generated: synth.data.generated, queued: synth.data.queued, duplicates: synth.data.duplicates_dropped, leaks: synth.data.leaks_dropped }} />
        </Card>
        <Card title="2 · Simulate traffic">
          <div className="row"><label>sessions<input type="number" min={1} max={200} value={n} onChange={(e) => setN(+e.target.value)} style={{ width: 80 }} /></label>
            <label>fault rate<input type="number" min={0} max={1} step={0.1} value={fault} onChange={(e) => setFault(+e.target.value)} style={{ width: 80 }} /></label>
            <button className="primary" disabled={traffic.isPending} onClick={() => traffic.mutate()}>Run</button></div>
          <p className="small muted">Simulated users talk to the agent; runs are traced to LangSmith (source=traffic) and saved locally.</p>
          <ErrorBox error={traffic.error} /><Result data={traffic.data} />
        </Card>
        <Card title="3 · Import traces">
          <button className="primary" disabled={imp.isPending} onClick={() => imp.mutate()}>Import logged traces</button>
          <p className="small muted">LangSmith when enabled, otherwise the local traffic files. PII is scrubbed; duplicates dropped.</p>
          <ErrorBox error={imp.error} /><Result data={imp.data && { fetched: imp.data.fetched, queued: imp.data.queued, duplicates: imp.data.duplicates_dropped }} />
        </Card>
      </div>

      <Card title={`Review queue (${all.length})`} right={
        <div className="row"><label>dataset group<input value={group} onChange={(e) => setGroup(e.target.value)} style={{ width: 110 }} /></label>
          <button className="good" disabled={!sel.size || accept.isPending} onClick={() => accept.mutate()}>Accept {sel.size || ""}</button>
          <button className="bad" disabled={!sel.size || reject.isPending} onClick={() => reject.mutate()}>Reject</button>
          <button onClick={() => setSel(new Set(all.map((c) => c.id)))}>Select all</button></div>}>
        <ErrorBox error={accept.error ?? reject.error} />
        {cands.isLoading ? <Loading /> : all.length === 0 ? <p className="muted">Nothing waiting for review. Generate or import some above.</p> : (
          <div className="scroll-x"><table><thead><tr><th /><th>id</th><th>source</th><th>input</th><th>expects</th><th>signals</th></tr></thead><tbody>
            {all.map((c) => (
              <tr key={c.id}><td><input type="checkbox" checked={sel.has(c.id)} onChange={() => toggle(c.id)} aria-label={`select ${c.id}`} /></td>
                <td className="mono">{c.id}</td><td><Badge kind="info">{c.source}</Badge></td>
                <td style={{ maxWidth: 380 }}>{c.input?.messages?.[0]?.content}</td>
                <td className="small mono">{Object.entries(c.expected).filter(([, v]) => (Array.isArray(v) ? v.length : v != null)).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ").slice(0, 90) || <span className="muted">none yet</span>}</td>
                <td className="row">{c.has_transcript && <Badge>transcript</Badge>}{c.thumbs === 0 && <Badge kind="bad">👎</Badge>}{c.tags.includes("error") && <Badge kind="bad">error</Badge>}</td></tr>
            ))}</tbody></table></div>
        )}
      </Card>
    </>
  );
}
