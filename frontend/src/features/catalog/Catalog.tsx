import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CAPABILITY_HELP } from "@/entities/profile";
import { api } from "@/shared/api";
import { Badge, Card, ErrorBox, Loading, PageHead, Tabs } from "@/shared/ui";

// "agent" tabs describe the active profile's agent; "engine" tabs are the lab itself (same for every agent)
const TABS = ["models", "tools", "skills", "variants", "conventions", "graders", "suites", "plugins"] as const;
type Tab = (typeof TABS)[number];
const LAYER = { 1: "code", 2: "trajectory", 3: "model" } as Record<number, string>;

export function Catalog() {
  const q = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const [tab, setTab] = useState<Tab>("tools");
  const [open, setOpen] = useState<string | null>(null);
  const c = q.data;
  const p = c?.profile;
  const declared = p?.inventory && !p.inventory.from_registry;  // a non-lab agent: its declared inventory
  return (
    <>
      <PageHead title="Catalog" sub={`Agent tabs (tools, skills, variants, conventions) describe ${p ? `the '${p.name}' agent` : "the agent under test"}; the others are the evaluation engine, shared by every agent.`} />
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
              <p className="small muted">Judge configured: {String(c.judge_configured)} · LangSmith: {c.langsmith.enabled ? `on (${c.langsmith.project})` : "off"}
                {declared && <> · the agent role applies to in-process agents only; '{p!.name}' runs its own models</>}</p>
            </Card>
          )}
          {tab === "tools" && (declared ? (
            <Card title={`${p!.inventory!.tools.length} tools of ${p!.name} (declared in its profile; the lab never runs them)`}>
              <table><thead><tr><th>name</th><th>description</th><th>flags</th></tr></thead><tbody>
                {p!.inventory!.tools.map((t) => <tr key={t.name}><td className="mono">{t.name}</td><td>{t.description}</td>
                  <td>{t.side_effects && <Badge kind="warn">side effects</Badge>}</td></tr>)}</tbody></table></Card>
          ) : (
            <Card title={`${c.tools.length} general tools`}><div className="scroll-x"><table><thead><tr><th>name</th><th>what it does</th><th>flags</th></tr></thead><tbody>
              {c.tools.map((t) => (
                <tr key={t.name}><td className="mono">{t.name}</td><td>{t.description.split("\n")[0]}</td>
                  <td className="row">{t.replayable ? <Badge kind="info">replayable</Badge> : <Badge>live only</Badge>}<Badge>{t.cost_hint}</Badge>{t.tags.map((x) => <Badge key={x}>{x}</Badge>)}</td></tr>
              ))}</tbody></table></div></Card>
          ))}
          {tab === "skills" && (declared ? (
            <Card title={`${p!.inventory!.skills.length} skills of ${p!.name}`}>
              <table><tbody>{p!.inventory!.skills.map((s) => <tr key={s.name}><td className="mono">{s.name}</td><td>{s.description}</td></tr>)}</tbody></table>
              <p className="small muted">How a skill load is recognised in its traces: see the conventions tab.</p></Card>
          ) : (
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
          ))}
          {tab === "variants" && (
            <Card title={p ? `Variants of ${p.name}` : "Agent configs"}>
              <div className="scroll-x"><table><thead><tr><th>name</th><th>target</th><th>can</th><th>details</th></tr></thead><tbody>
                {(p?.variants ?? c.agents.map((a) => ({ name: a.name, description: a.description, target: "local_agent", aliases: [], capabilities: [] }))).map((v) => {
                  const a = c.agents.find((x) => x.name === v.name);
                  return (
                    <tr key={v.name}><td className="mono">{v.name}{v.name === p?.default_variant && <> <Badge>default</Badge></>}
                      {v.aliases.length > 0 && <div className="small muted">also: {v.aliases.join(", ")}</div>}</td>
                      <td className="mono">{v.target}</td>
                      <td className="row">{v.capabilities.length ? v.capabilities.map((x) => <span key={x} title={CAPABILITY_HELP[x]}><Badge kind="info">{x}</Badge></span>)
                        : <Badge kind="warn">read-only: grade its logged runs</Badge>}</td>
                      <td className="small">{v.description}{a && <div className="muted">loader {a.skill_loader_mode} · skills {Array.isArray(a.skills) ? a.skills.join(", ") : a.skills}</div>}</td></tr>);
                })}</tbody></table></div>
              <p className="small muted">A variant is one way to run or read this agent (an improvement candidate, an ablation, an environment). Variants share tools, skills and tasks, so their results compare directly.</p>
            </Card>
          )}
          {tab === "conventions" && (
            <Card title={p ? `How ${p.name}'s transcripts are read` : "Conventions"}>
              {p ? <>
                <p className="small muted">Applied to imported traces and live runs alike: which tool calls load a skill, which tool calls failed, how citations look.</p>
                <pre>{JSON.stringify(p.conventions, null, 2)}</pre>
                <p className="small muted">Traces: {JSON.stringify(p.traces)} · defaults: {JSON.stringify(p.defaults)}</p>
              </> : <p className="muted">This server predates agent profiles.</p>}
            </Card>
          )}
          {tab === "graders" && (
            <Card title={`${c.graders.length} graders`}><table><thead><tr><th>type</th><th>layer</th><th>checks</th></tr></thead><tbody>
              {c.graders.map((g) => <tr key={g.type}><td className="mono">{g.type}</td><td><Badge kind={g.layer === 3 ? "warn" : "good"}>{LAYER[g.layer]}</Badge></td><td>{g.description}</td></tr>)}
            </tbody></table></Card>
          )}
          {tab === "suites" && (
            <Card title={p ? `Suites of ${p.name}` : "Suites (evals/suites/*.yaml)"}><table><thead><tr><th>name</th><th>k</th><th>variant · mode</th><th>datasets</th><th>graders</th></tr></thead><tbody>
              {c.suites.map((s) => <tr key={s.name}><td><strong>{s.name}</strong> <Link className="small" to={`/suites?name=${s.name}`}>edit</Link> · <Link className="small" to={`/experiments?suite=${s.name}`}>run</Link><div className="small muted">{s.description}</div></td><td>{s.k}</td>
                <td className="mono small">{s.variant ?? s.agent}<br />{s.mode ?? s.target}</td><td>{s.datasets.join(", ")}</td><td className="small">{s.graders.join(", ")}</td></tr>)}
            </tbody></table></Card>
          )}
          {tab === "plugins" && (
            <div className="grid g2">
              <Card title="Targets">{c.targets.map((t) => <div key={t} className="mono">{t}</div>)}</Card>
              <Card title="Metrics">{c.metrics.map((t) => <div key={t} className="mono">{t}</div>)}</Card>
              <Card title="Middleware">{c.middleware.map((t) => <div key={t} className="mono">{t}</div>)}</Card>
              <Card title="Data generators">{c.generators.map((g) => <div key={g.type}><span className="mono">{g.type}</span> <span className="muted small">{g.description}</span></div>)}</Card>
              {c.trace_adapters && <Card title="Trace adapters">{c.trace_adapters.map((t) => <div key={t} className="mono">{t}</div>)}</Card>}
              {c.modes && <Card title="Suite modes">{c.modes.map((t) => <div key={t} className="mono">{t}</div>)}</Card>}
            </div>
          )}
        </>
      )}
    </>
  );
}
