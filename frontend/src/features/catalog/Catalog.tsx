import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/shared/api";
import { Badge, Card, ErrorBox, Loading, PageHead, Tabs } from "@/shared/ui";

const TABS = ["models", "tools", "skills", "graders", "agents", "suites", "plugins"] as const;
type Tab = (typeof TABS)[number];
const LAYER = { 1: "code", 2: "trajectory", 3: "model" } as Record<number, string>;

export function Catalog() {
  const q = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const [tab, setTab] = useState<Tab>("tools");
  const [open, setOpen] = useState<string | null>(null);
  const c = q.data;
  return (
    <>
      <PageHead title="Catalog" sub="Everything pluggable. Add a tool, grader, skill or agent as a file and it appears here." />
      <ErrorBox error={q.error} />
      {!c ? <Loading /> : (
        <>
          <Tabs tabs={TABS} value={tab} onChange={setTab} />
          {tab === "models" && (
            <Card title="Model roles (from .env)">
              <table><thead><tr><th>role</th><th>provider</th><th>model</th><th>temp</th></tr></thead><tbody>
                {Object.values(c.models).map((m) => (
                  <tr key={m.role}><td>{m.role}</td><td>{m.provider}</td><td className="mono">{m.model || <span className="muted">not set</span>}</td><td>{m.temperature}</td></tr>
                ))}</tbody></table>
              <p className="small muted">Judge configured: {String(c.judge_configured)} · LangSmith: {c.langsmith.enabled ? `on (${c.langsmith.project})` : "off"}</p>
            </Card>
          )}
          {tab === "tools" && (
            <Card title={`${c.tools.length} general tools`}><div className="scroll-x"><table><thead><tr><th>name</th><th>what it does</th><th>flags</th></tr></thead><tbody>
              {c.tools.map((t) => (
                <tr key={t.name}><td className="mono">{t.name}</td><td>{t.description.split("\n")[0]}</td>
                  <td className="row">{t.replayable ? <Badge kind="info">replayable</Badge> : <Badge>live only</Badge>}<Badge>{t.cost_hint}</Badge>{t.tags.map((x) => <Badge key={x}>{x}</Badge>)}</td></tr>
              ))}</tbody></table></div></Card>
          )}
          {tab === "skills" && (
            <Card title={`${c.skills.length} skills (loaded on demand via tool call)`}>
              {c.skills.map((s) => (
                <div key={s.name} style={{ marginBottom: 10 }}>
                  <div className="row spread"><div><strong>{s.name}</strong> <span className="muted">{s.description}</span></div>
                    <div className="row"><Badge kind="info">{s.tool}</Badge><Badge>~{s.tokens} tokens</Badge>{s.assets.length > 0 && <Badge>{s.assets.length} assets</Badge>}
                      <button onClick={() => setOpen(open === s.name ? null : s.name)}>{open === s.name ? "hide" : "view"}</button></div></div>
                  {open === s.name && <pre style={{ marginTop: 6 }}>{s.body}</pre>}
                </div>
              ))}
            </Card>
          )}
          {tab === "graders" && (
            <Card title={`${c.graders.length} graders`}><table><thead><tr><th>type</th><th>layer</th><th>checks</th></tr></thead><tbody>
              {c.graders.map((g) => <tr key={g.type}><td className="mono">{g.type}</td><td><Badge kind={g.layer === 3 ? "warn" : "good"}>{LAYER[g.layer]}</Badge></td><td>{g.description}</td></tr>)}
            </tbody></table></Card>
          )}
          {tab === "agents" && (
            <Card title="Agent configs (evals/agents/*.yaml)"><table><thead><tr><th>name</th><th>loader</th><th>skills</th><th>description</th></tr></thead><tbody>
              {c.agents.map((a) => <tr key={a.name}><td className="mono">{a.name}</td><td>{a.skill_loader_mode}</td><td>{Array.isArray(a.skills) ? a.skills.join(", ") : a.skills}</td><td>{a.description}</td></tr>)}
            </tbody></table></Card>
          )}
          {tab === "suites" && (
            <Card title="Suites (evals/suites/*.yaml)"><table><thead><tr><th>name</th><th>k</th><th>agent</th><th>datasets</th><th>graders</th></tr></thead><tbody>
              {c.suites.map((s) => <tr key={s.name}><td><strong>{s.name}</strong> <Link className="small" to={`/suites?name=${s.name}`}>edit</Link> · <Link className="small" to={`/experiments?suite=${s.name}`}>run</Link><div className="small muted">{s.description}</div></td><td>{s.k}</td><td className="mono">{s.agent}</td><td>{s.datasets.join(", ")}</td><td className="small">{s.graders.join(", ")}</td></tr>)}
            </tbody></table></Card>
          )}
          {tab === "plugins" && (
            <div className="grid g2">
              <Card title="Targets">{c.targets.map((t) => <div key={t} className="mono">{t}</div>)}</Card>
              <Card title="Metrics">{c.metrics.map((t) => <div key={t} className="mono">{t}</div>)}</Card>
              <Card title="Middleware">{c.middleware.map((t) => <div key={t} className="mono">{t}</div>)}</Card>
              <Card title="Data generators">{c.generators.map((g) => <div key={g.type}><span className="mono">{g.type}</span> <span className="muted small">{g.description}</span></div>)}</Card>
            </div>
          )}
        </>
      )}
    </>
  );
}
