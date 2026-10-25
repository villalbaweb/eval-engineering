import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { runGroupHref, suggestedSuite, suitesUsing } from "@/entities/datasetGroups";
import { api } from "@/shared/api";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

const NEW_FILE = "tasks:\n  - id: my-task-01\n    kind: capability\n    tags: []\n    input: { messages: [{ role: user, content: \"...\" }] }\n    expected: {}\n";

export function Datasets() {
  const qc = useQueryClient();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const files = useQuery({ queryKey: ["dataset-files"], queryFn: api.datasetFiles });
  const ls = useQuery({ queryKey: ["langsmith"], queryFn: api.langsmith });
  const [path, setPath] = useState<string | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [text, setText] = useState("");
  const [newPath, setNewPath] = useState("");
  const [pullName, setPullName] = useState("");
  const file = useQuery({ queryKey: ["dataset-file", path], queryFn: () => api.datasetFile(path!), enabled: !!path && !isNew });
  useEffect(() => { if (file.data && !isNew) setText(file.data.content); }, [file.data, isNew]);
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["dataset-files"] });
    void qc.invalidateQueries({ queryKey: ["dataset-file", path] });
    void qc.invalidateQueries({ queryKey: ["catalog"] });
  };
  const save = useMutation({ mutationFn: () => api.saveDatasetFile(path!, text), onSuccess: () => { setIsNew(false); refresh(); } });
  const push = useMutation({ mutationFn: (g: string) => api.pushDataset(g) });
  const pull = useMutation({ mutationFn: () => api.pullDataset(pullName), onSuccess: refresh });
  const dirty = isNew || (file.data ? file.data.content !== text : false);

  const groups = new Map<string, string[]>();
  (files.data ?? []).forEach((f) => { const g = f.includes("/") ? f.split("/")[0] : f.replace(/\.(ya?ml|jsonl)$/, ""); groups.set(g, [...(groups.get(g) ?? []), f]); });
  const group = path ? (path.includes("/") ? path.split("/")[0] : path.replace(/\.(ya?ml|jsonl)$/, "")) : null;
  const usedBy = group ? suitesUsing(catalog.data, group) : [];
  const hasTranscripts = text.includes("transcript:");
  const startNew = () => {
    const p = newPath.endsWith(".yaml") ? newPath : `${newPath}.yaml`;
    setIsNew(true); setPath(p); setText(NEW_FILE); setNewPath(""); save.reset();
  };

  return (
    <>
      <PageHead title="Datasets" sub="Tasks are YAML files in evals/datasets; the folder is the group name. Edit here or in your editor; saving validates every task first." />
      <ErrorBox error={files.error} />
      <div className="grid" style={{ gridTemplateColumns: "300px minmax(0,1fr)" }}>
        <div>
          <Card title="Groups & files">
            {!files.data ? <Loading /> : [...groups].map(([g, fs]) => {
              const used = suitesUsing(catalog.data, g);
              return (
                <div key={g} style={{ marginBottom: 10 }}>
                  <div className="row spread"><span className="small"><strong>{g}</strong> <span className="muted">{catalog.data?.datasets[g] ?? "?"} tasks</span></span>
                    <Link className="small" to={runGroupHref(g, used[0])}>run</Link></div>
                  <div className="small muted">{used.length ? `in: ${used.join(", ")}` : "in no suite"}</div>
                  {fs.map((f) => <div key={f}><a href="#" onClick={(e) => { e.preventDefault(); setIsNew(false); save.reset(); setPath(f); }} style={{ fontWeight: f === path ? 700 : 400 }}>{f.split("/").slice(1).join("/") || f}</a></div>)}
                </div>);
            })}
          </Card>
          <Card title="New file">
            <label>path<input value={newPath} onChange={(e) => setNewPath(e.target.value.trim())} placeholder="my-group/basic.yaml" /></label>
            <button style={{ marginTop: 8 }} disabled={!newPath || newPath.includes("..")} onClick={startNew}>Create draft</button>
            <p className="small muted">A new folder is a new group. Nothing is written until you save.</p>
          </Card>
          <Card title="LangSmith">
            {ls.data && !ls.data.enabled ? <p className="small muted">Disabled (set LANGSMITH_API_KEY and LANGSMITH_TRACING=true).</p> : (
              <>
                <label>pull dataset<input value={pullName} onChange={(e) => setPullName(e.target.value)} placeholder="LangSmith dataset name" /></label>
                <button style={{ marginTop: 8 }} disabled={!pullName || pull.isPending} onClick={() => pull.mutate()}>Pull into evals/datasets</button>
                <ErrorBox error={pull.error} />{pull.data && <pre>{JSON.stringify(pull.data, null, 2)}</pre>}
              </>)}
          </Card>
        </div>
        <Card title={path ? `${path}${isNew ? " (new, unsaved)" : ""}` : "Select a file"} right={path && <div className="row">
          {dirty && <Badge kind="warn">unsaved</Badge>}
          {save.data && !dirty && <Badge kind="good">saved · {save.data.tasks} tasks</Badge>}
          <button className="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save</button></div>}>
          <ErrorBox error={save.error} />
          {path && group && !isNew && (
            <div className="row" style={{ marginBottom: 8 }}>
              <span className="small">group <strong>{group}</strong> · {usedBy.length ? <>used by {usedBy.map((s) => <Link key={s} to={`/suites?name=${s}`} style={{ marginRight: 4 }}>{s}</Link>)}</> : <span className="muted">in no suite</span>}</span>
              <Link to={runGroupHref(group, usedBy[0] ?? suggestedSuite(hasTranscripts))}>Run this group…</Link>
              {ls.data?.enabled && <button disabled={push.isPending} onClick={() => push.mutate(group)}>Push to LangSmith</button>}
            </div>)}
          <ErrorBox error={push.error} />{push.data && <pre>{JSON.stringify(push.data, null, 2)}</pre>}
          {path && <textarea rows={28} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label="dataset yaml" />}
          {!path && <p className="muted">Pick a dataset file on the left. Fields: <code>id, kind, tags, input, expected, graders, setup, source</code>.</p>}
        </Card>
      </div>
    </>
  );
}
