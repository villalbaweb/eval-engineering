import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "@/shared/api";
import { getProfile, setProfile } from "@/shared/profile";
import { features } from "./routes";

const GROUPS = ["Build", "Run", "Analyze"];

/** Which agent the whole UI works on. Switching resets every cached query and remounts the pages. */
function ProfileSwitcher({ onSwitch }: { onSwitch: () => void }) {
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: api.profiles, retry: false });
  const p = profiles.data;
  if (!p) return null;
  return (
    <label className="small" style={{ display: "block", padding: "0 10px 12px" }}>agent profile
      <select value={p.active} onChange={(e) => { setProfile(e.target.value); onSwitch(); }} aria-label="agent profile"
        style={{ width: "100%" }}>
        {p.profiles.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
      </select>
    </label>
  );
}

export function App() {
  const qc = useQueryClient();
  const [epoch, setEpoch] = useState(0);
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const nav = features.filter((f) => f.nav);
  const c = catalog.data;
  const prof = c?.profile;
  const switched = () => { void qc.resetQueries(); setEpoch((n) => n + 1); };
  useEffect(() => {  // a stored profile that no longer exists on the server: fall back to the default
    if (catalog.error && getProfile() && /profile '.*' not found/.test(String(catalog.error))) {
      setProfile(null);
      void qc.resetQueries();
      setEpoch((n) => n + 1);
    }
  }, [catalog.error, qc]);
  return (
    <div className="shell">
      <nav className="nav" aria-label="Main">
        <div className="brand">Eval Lab</div>
        <ProfileSwitcher onSwitch={switched} />
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
      <main className="main" key={epoch}>
        {prof && (
          <div className="small muted" style={{ marginBottom: 10 }} aria-label="agent under test">
            agent under test: <strong>{prof.name}</strong>
            {prof.default_variant && <> · default variant <span className="mono">{prof.default_variant}</span></>}
            {prof.description && <> · {prof.description}</>}
          </div>
        )}
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
