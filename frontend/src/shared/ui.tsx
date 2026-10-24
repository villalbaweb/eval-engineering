import type { ReactNode } from "react";
import { pct, rateClass } from "./format";

export function PageHead({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="page-head row spread">
      <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

export const Card = ({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) => (
  <section className="card">
    {(title || right) && <div className="row spread"><h2>{title}</h2>{right}</div>}
    {children}
  </section>
);

export const Kpi = ({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) => (
  <div className="kpi"><div className="v">{value}</div><div className="l">{label}{sub ? ` · ${sub}` : ""}</div></div>
);

export const Badge = ({ kind = "neutral", children }: { kind?: "good" | "bad" | "warn" | "info" | "neutral"; children: ReactNode }) => (
  <span className={`badge ${kind}`}>{children}</span>
);

export function RateBar({ rate, label }: { rate: number; label?: string }) {
  return (
    <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
      <div className={`bar ${rateClass(rate)}`} style={{ flex: 1 }} role="img" aria-label={`${pct(rate)} pass rate`}>
        <i style={{ width: `${Math.round(rate * 100)}%` }} />
      </div>
      <span className="mono" style={{ minWidth: 40, textAlign: "right" }}>{label ?? pct(rate)}</span>
    </div>
  );
}

export const StatusBadge = ({ status }: { status: string }) => (
  <Badge kind={status === "completed" ? "good" : status === "failed" ? "bad" : status === "running" ? "info" : "neutral"}>{status}</Badge>
);

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: readonly T[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t} role="tab" aria-selected={t === value} className={t === value ? "on" : ""} onClick={() => onChange(t)}>{t}</button>
      ))}
    </div>
  );
}

export const ErrorBox = ({ error }: { error: unknown }) =>
  error ? <div className="error" role="alert">{error instanceof Error ? error.message : String(error)}</div> : null;

export const Loading = ({ what = "Loading" }: { what?: string }) => <p className="muted">{what}…</p>;
