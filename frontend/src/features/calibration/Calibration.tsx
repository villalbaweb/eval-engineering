import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/shared/api";
import { num, pct } from "@/shared/format";
import { Badge, Card, ErrorBox, Loading, PageHead } from "@/shared/ui";

export function Calibration() {
  const [sp] = useSearchParams();
  const exp = sp.get("experiment") ?? undefined;
  const q = useQuery({ queryKey: ["calibration", exp], queryFn: () => api.calibration(exp) });
  const c = q.data;
  const rows = c ? [["(whole trial)", c.trial_level] as const, ...Object.entries(c.graders)] : [];

  return (
    <>
      <PageHead title="Calibration" sub="Validate the validators: how well does each grader agree with your labels?" />
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {c && c.n_labeled === 0 && <Card><p>{c.message}</p></Card>}
      {c && c.n_labeled > 0 && (
        <>
          <Card title={`${c.n_labeled} labelled trials`}>
            <div className="scroll-x"><table><thead><tr><th>grader</th><th>n</th><th title="share of human-BAD outputs the grader also fails">coverage ↑</th>
              <th title="share of human-GOOD outputs the grader wrongly fails">false failure rate ↓</th><th>alignment ↑</th><th>kappa ↑</th><th>TP / TN / FP / FN</th></tr></thead><tbody>
              {rows.filter(([, m]) => m).map(([name, m]) => m && (
                <tr key={name}><td className="mono">{name}</td><td>{m.n}</td><td>{pct(m.coverage)}</td><td>{pct(m.ffr)}</td>
                  <td><Badge kind={(m.alignment ?? 0) >= 0.8 ? "good" : (m.alignment ?? 0) >= 0.6 ? "warn" : "bad"}>{pct(m.alignment)}</Badge></td>
                  <td>{num(m.kappa)}</td><td className="mono small">{m.tp} / {m.tn} / {m.fp} / {m.fn}</td></tr>
              ))}</tbody></table></div>
            <p className="small muted">Grader “pass” is the positive class. Coverage needs at least one human-bad label, and false-failure rate at least one human-good label, otherwise they show “–”.</p>
          </Card>
          {c.failure_tags && Object.keys(c.failure_tags).length > 0 && (
            <Card title="Your failure taxonomy (from bad labels)"><div className="row">
              {Object.entries(c.failure_tags).map(([t, n]) => <Badge key={t} kind="warn">{t} × {n}</Badge>)}</div>
              <p className="small muted">Each frequent category deserves its own grader and new tasks (see the error-analysis skill).</p></Card>
          )}
        </>
      )}
    </>
  );
}
