import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "@/shared/api";
import { features } from "./routes";

const GROUPS = ["Build", "Run", "Analyze"];

export function App() {
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const nav = features.filter((f) => f.nav);
  const c = catalog.data;
  return (
    <div className="shell">
      <nav className="nav" aria-label="Main">
        <div className="brand">Eval Lab</div>
        {GROUPS.map((g) => (
          <div key={g}>
            <div className="group">{g}</div>
            {nav.filter((f) => f.nav!.group === g).map((f) => (
              <NavLink key={f.nav!.to} to={f.nav!.to}>{f.nav!.label}</NavLink>
            ))}
          </div>
        ))}
        {c && (
          <div className="small muted" style={{ padding: "16px 10px" }}>
            agent: <span className="mono">{c.models.agent.provider}:{c.models.agent.model}</span><br />
            judge: <span className="mono">{c.judge_configured ? `${c.models.judge.provider}:${c.models.judge.model || "—"}` : "not configured"}</span><br />
            LangSmith: {c.langsmith.enabled ? c.langsmith.project : "off"}
          </div>
        )}
      </nav>
      <main className="main">
        {c && !c.judge_configured && (
          <div className="notice">No judge model configured: LLM-judge graders are skipped. Set <code>JUDGE_MODEL</code> in <code>.env</code>.</div>
        )}
        {c?.self_judged && <div className="notice">Judge model equals the agent model, so results are self-judged.</div>}
        <Routes>
          <Route path="/" element={<Navigate to="/playground" replace />} />
          {features.flatMap((f) => f.routes).map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
          <Route path="*" element={<p>Not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
