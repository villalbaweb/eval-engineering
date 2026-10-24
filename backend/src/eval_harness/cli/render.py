"""Rich rendering of experiment summaries for the terminal."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from eval_harness.evals.domain.experiment import Experiment
from eval_harness.evals.domain.trial import Trial

console = Console()


def pct(x: float | None) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def render_summary(exp: Experiment, trials: list[Trial] | None = None, *, failures: bool = False) -> None:
    s = exp.summary or {}
    pr = s.get("pass_rates", {})
    snap = exp.snapshot
    agent = snap.get("models", {}).get("agent", {})
    console.print(f"\n[bold]{exp.name}[/bold]  id={exp.id}  status={exp.status}  suite={exp.suite}  "
                  f"target={exp.target}")
    console.print(f"model=[cyan]{agent.get('provider')}:{agent.get('model')}[/cyan]  k={pr.get('k')}  "
                  f"tasks={pr.get('n_tasks')}  trials={pr.get('n_trials')}  git={snap.get('git_sha')}")
    if snap.get("self_judged"):
        console.print("[yellow]warning: judge model == agent model (self-judged)[/yellow]")
    if exp.langsmith_url:
        console.print(f"LangSmith: {exp.langsmith_url}")
    if exp.error:
        console.print(f"[red]{exp.error}[/red]")
    if not pr:
        return
    lo, hi = pr.get("ci95", [0, 0])
    console.print(f"\n[bold]trial pass rate {pct(pr['trial_pass_rate'])}[/bold]  95% CI [{pct(lo)}, {pct(hi)}]   "
                  f"pass@k {pct(pr['mean_pass_at_k'])}   pass^k {pct(pr['mean_pass_pow_k'])}")

    for title, key in (("by grader", "by_grader"), ("by tag", "by_tag")):
        data = s.get(key, {})
        if data:
            t = Table(title=title, show_edge=False)
            t.add_column("name")
            t.add_column("n", justify="right")
            t.add_column("pass", justify="right")
            if key == "by_grader":
                t.add_column("skipped", justify="right")
            for name, v in data.items():
                row = [name, str(v["n"]), pct(v["pass_rate"]) if v["n"] else "-"]
                if key == "by_grader":
                    row.append(str(v.get("skipped", 0)))
                t.add_row(*row)
            console.print(t)

    fl = s.get("flakiness", {})
    if fl:
        console.print(f"reliable={len(fl['reliable'])}  [yellow]flaky={fl['flaky']}[/yellow]  "
                      f"[red]systematic={fl['systematic']}[/red]")
    cl = s.get("cost_latency", {})
    if cl:
        cost = f"${cl['cost_total_usd']:.4f}" if cl.get("cost_total_usd") is not None else "n/a"
        console.print(f"latency p50 {cl['latency_p50_s']:.1f}s p95 {cl['latency_p95_s']:.1f}s   tokens {cl['tokens_total']}   "
                      f"cost {cost}   errors {cl['errors']}")
    if failures and trials:
        t = Table(title="failed trials", show_edge=False)
        t.add_column("task")
        t.add_column("#")
        t.add_column("status")
        t.add_column("failed graders")
        for tr in sorted(trials, key=lambda x: (x.task_id, x.index)):
            if not tr.passed:
                bad = [f"{g.grader}: {g.rationale[:60]}" for g in tr.grades if g.passed is False]
                t.add_row(tr.task_id, str(tr.index), tr.outcome.status, "\n".join(bad) or (tr.outcome.error or ""))
        console.print(t)
