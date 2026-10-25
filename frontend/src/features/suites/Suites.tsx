import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/shared/api";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

/** Suites = which datasets × which graders × which target/agent. Saving validates grader/target/agent names. */
export function Suites() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const name = params.get("name");
  const [text, setText] = useState("");
  const [isNew, setIsNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [template, setTemplate] = useState("smoke");
  const file = useQuery({ queryKey: ["suite", name], queryFn: () => api.suiteYaml(name!), enabled: !!name && !isNew });
  useEffect(() => { if (file.data && !isNew) setText(file.data.yaml); }, [file.data, isNew]);

  const save = useMutation({
    mutationFn: () => api.saveSuite(name!, text),
    onSuccess: () => {
      setIsNew(false);
      void qc.invalidateQueries({ queryKey: ["suite", name] });
      void qc.invalidateQueries({ queryKey: ["catalog"] });
    },
  });
  const create = useMutation({
    mutationFn: async () => {
      const src = await api.suiteYaml(template);
      return src.yaml.replace(/^name:.*$/m, `name: ${newName}`);
    },
    onSuccess: (yaml) => { setIsNew(true); setText(yaml); save.reset(); setParams({ name: newName }); setNewName(""); },
  });
  const open = (n: string) => { setIsNew(false); save.reset(); setParams({ name: n }); };
  const dirty = isNew || (file.data ? file.data.yaml !== text : false);
  const validName = /^[a-z0-9][a-z0-9_-]{0,63}$/.test(newName);
  const exists = catalog.data?.suites.some((s) => s.name === newName);
  const groups = Object.keys(catalog.data?.datasets ?? {});

  return (
    <>
      <PageHead title="Suites" sub="A suite picks datasets, graders and a target. Edit or create one here; saving checks every grader, target and agent name." />
      <div className="grid" style={{ gridTemplateColumns: "280px minmax(0,1fr)" }}>
        <div>
          <Card title="Suites">
            {!catalog.data ? <Loading /> : catalog.data.suites.map((s) => (
              <div key={s.name} style={{ marginBottom: 6 }}>
                <a href="#" onClick={(e) => { e.preventDefault(); open(s.name); }} style={{ fontWeight: s.name === name ? 700 : 400 }}>{s.name}</a>
                <div className="small muted">{s.target} · {s.datasets.join(", ")}</div>
              </div>))}
          </Card>
          <Card title="New suite">
            <label>name<input value={newName} onChange={(e) => setNewName(e.target.value.toLowerCase())} placeholder="my-suite" /></label>
            <label>copy from<select value={template} onChange={(e) => setTemplate(e.target.value)}>
              {catalog.data?.suites.map((s) => <option key={s.name}>{s.name}</option>)}</select></label>
            <div className="row" style={{ marginTop: 8 }}>
              <button disabled={!validName || exists || create.isPending} onClick={() => create.mutate()}>Create draft</button>
              {exists && <span className="small muted">already exists</span>}
            </div>
            <ErrorBox error={create.error} />
          </Card>
        </div>
        <Card title={name ? `${name}.yaml${isNew ? " (new, unsaved)" : ""}` : "Select a suite"} right={name && <div className="row">
          {dirty && <Badge kind="warn">unsaved</Badge>}
          {!dirty && file.data && <Badge>{file.data.n_tasks} tasks</Badge>}
          {save.data && !dirty && <Badge kind={save.data.warning ? "warn" : "good"}>saved · {save.data.n_tasks} tasks</Badge>}
          <button className="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save</button>
          {!dirty && <Link to={`/experiments?suite=${name}`}>Run…</Link>}</div>}>
          <ErrorBox error={file.error ?? save.error} />
          {save.data?.warning && <div className="notice">{save.data.warning}</div>}
          {name && <textarea rows={26} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label="suite yaml" />}
          {name && (
            <p className="small muted">
              dataset groups: {groups.map((g) => <code key={g} style={{ marginRight: 6 }}>{g}</code>)}
              {catalog.data?.profile && <> · variants (<code>variant:</code>): {catalog.data.profile.variants.map((v) => v.name).join(", ")}
                {" "}· modes (<code>mode:</code>): {(catalog.data.modes ?? []).join(", ")}</>}
              · graders: {catalog.data?.graders.map((g) => g.type).join(", ")}
              · targets (legacy <code>target:</code>): {catalog.data?.targets.join(", ")}
            </p>)}
          {!name && <p className="muted">Pick a suite on the left, or create one from a template. Fields: <code>name, description, variant, mode, datasets, include_tags, exclude_tags, kinds, graders, run</code> (older suites use <code>agent</code> / <code>target</code>, still supported).</p>}
        </Card>
      </div>
    </>
  );
}
