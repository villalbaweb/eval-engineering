import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "@/shared/api";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

export function Datasets() {
  const qc = useQueryClient();
  const files = useQuery({ queryKey: ["dataset-files"], queryFn: api.datasetFiles });
  const [path, setPath] = useState<string | null>(null);
  const [text, setText] = useState("");
  const file = useQuery({ queryKey: ["dataset-file", path], queryFn: () => api.datasetFile(path!), enabled: !!path });
  useEffect(() => { if (file.data) setText(file.data.content); }, [file.data]);
  const save = useMutation({
    mutationFn: () => api.saveDatasetFile(path!, text),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["dataset-file", path] }); void qc.invalidateQueries({ queryKey: ["catalog"] }); },
  });
  const dirty = file.data ? file.data.content !== text : false;

  const groups = new Map<string, string[]>();
  (files.data ?? []).forEach((f) => { const g = f.split("/")[0]; groups.set(g, [...(groups.get(g) ?? []), f]); });

  return (
    <>
      <PageHead title="Datasets" sub="Tasks are YAML files in evals/datasets. Edit here or in your editor; saving validates every task first." />
      <ErrorBox error={files.error} />
      <div className="grid" style={{ gridTemplateColumns: "260px minmax(0,1fr)" }}>
        <Card title="Files">
          {!files.data ? <Loading /> : [...groups].map(([g, fs]) => (
            <div key={g} style={{ marginBottom: 8 }}>
              <div className="small muted">{g}</div>
              {fs.map((f) => <div key={f}><a href="#" onClick={(e) => { e.preventDefault(); setPath(f); }} style={{ fontWeight: f === path ? 700 : 400 }}>{f.split("/").slice(1).join("/") || f}</a></div>)}
            </div>
          ))}
        </Card>
        <Card title={path ?? "Select a file"} right={path && <div className="row">
          {dirty && <Badge kind="warn">unsaved</Badge>}
          {save.data && !dirty && <Badge kind="good">saved · {save.data.tasks} tasks</Badge>}
          <button className="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save</button></div>}>
          <ErrorBox error={save.error} />
          {path && <textarea rows={28} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label="dataset yaml" />}
          {!path && <p className="muted">Pick a dataset file on the left. Fields: <code>id, kind, tags, input, expected, graders, setup, source</code>.</p>}
        </Card>
      </div>
    </>
  );
}
