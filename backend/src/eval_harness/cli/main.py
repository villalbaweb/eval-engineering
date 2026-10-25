"""`evalh` - command line for the eval-engineering lab."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import typer
from rich.table import Table

from eval_harness.cli.render import console, render_summary
from eval_harness.core.logging import setup_logging

app = typer.Typer(help="Evaluation-engineering lab CLI", no_args_is_help=True)
datasets_app = typer.Typer(help="Dataset utilities", no_args_is_help=True)
app.add_typer(datasets_app, name="datasets")


@app.callback()
def _main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
          profile: Annotated[str | None, typer.Option(
              "--profile", help="agent profile to work on (default: EVAL_PROFILE, else copilot)")] = None) -> None:
    setup_logging(logging.DEBUG if verbose else logging.WARNING)
    if profile:
        from eval_harness.profiles import ProfileNotFound, set_active_profile

        try:
            set_active_profile(profile)
        except ProfileNotFound as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(2) from e


@app.command()
def profiles() -> None:
    """List agent profiles and their variants (the active profile is marked)."""
    from eval_harness.profiles import active_profile_name, is_legacy_layout, list_profiles, list_variants

    active = active_profile_name()
    t = Table(show_edge=False)
    for c in ("profile", "variant", "target", "info"):
        t.add_column(c)
    for p in list_profiles():
        mark = " [green](active)[/green]" if p.name == active else ""
        t.add_row(f"[bold]{p.name}[/bold]{mark}", "", "", p.description)
        for v in list_variants(p.name):
            default = " (default)" if v.name == p.default_variant else ""
            aliases = f" aliases: {', '.join(v.aliases)}" if v.aliases else ""
            t.add_row("", v.name + default, v.target, (v.description[:70] + aliases).strip())
    console.print(t)
    if is_legacy_layout():
        console.print("[dim]legacy flat evals/ layout (read as profile 'copilot'); "
                      "`evalh migrate-profiles` shows how to move to evals/profiles/[/dim]")


@app.command("migrate-profiles")
def migrate_profiles(
    apply_: Annotated[bool, typer.Option("--apply", help="actually move the files (default: dry run)")] = False,
    revert: Annotated[bool, typer.Option("--revert", help="undo a previous --apply")] = False,
) -> None:
    """Move the flat evals/ layout into evals/profiles/copilot/ (optional; old names keep working)."""
    from eval_harness.core.settings import get_settings
    from eval_harness.profiles import migrate

    evals = get_settings().evals_dir
    if revert:
        console.print(migrate.revert(evals))
        return
    p = migrate.apply(evals) if apply_ else migrate.plan(evals)
    if p.note:
        console.print(p.note)
        return
    verb = "moved" if apply_ else "would move"
    for src, dst in p.moves:
        console.print(f"  {verb} evals/{src} -> evals/{dst}")
    for src, dst in p.variants:
        console.print(f"  {verb} evals/{src} -> evals/{dst} (variant; old name kept as alias)")
    for c in p.created:
        console.print(f"  {'created' if apply_ else 'would create'} evals/{c}")
    if not apply_:
        console.print("[dim]dry run - re-run with --apply (undo later with --revert)[/dim]")


@app.command()
def run(
    suite: str,
    agent: Annotated[str | None, typer.Option(help="agent config name (evals/agents)")] = None,
    k: Annotated[int | None, typer.Option(help="trials per task")] = None,
    concurrency: Annotated[int | None, typer.Option()] = None,
    tool_mode: Annotated[str | None, typer.Option(help="live | record | replay")] = None,
    target: Annotated[str | None, typer.Option(help="local_agent | multiturn_sim | ...")] = None,
    max_tasks: Annotated[int | None, typer.Option()] = None,
    name: Annotated[str | None, typer.Option()] = None,
    dataset: Annotated[list[str] | None, typer.Option(
        help="run this dataset group instead of the suite's own (repeatable); the suite supplies graders/target")] = None,
    variant: Annotated[str | None, typer.Option(help="variant of the active profile (replaces --agent)")] = None,
    mode: Annotated[str | None, typer.Option(help="live | multiturn | trace | replay (replaces --target)")] = None,
    failures: Annotated[bool, typer.Option("--failures/--no-failures")] = True,
) -> None:
    """Run a suite and print the metrics table."""
    from eval_harness.evals.runner.service import prepare_runner
    from eval_harness.storage.repositories import trials

    def on_event(e: dict) -> None:
        if e["type"] == "trial_done":
            mark = "[green]PASS[/green]" if e["passed"] else "[red]FAIL[/red]"
            console.print(f"  {e['done']}/{e['total']} {mark} {e['task_id']}#{e['index']}")

    try:
        runner = prepare_runner(suite, name=name, on_event=on_event, overrides={
            "agent": agent, "k": k, "concurrency": concurrency, "tool_mode": tool_mode, "target": target,
            "max_tasks": max_tasks, "datasets": dataset, "variant": variant, "mode": mode})
    except (FileNotFoundError, KeyError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    console.print(f"running [bold]{suite}[/bold]: {len(runner.tasks)} tasks x k={runner.suite.run.k} "
                  f"(agent={runner.exp.snapshot.get('variant') or runner.suite.agent}, target={runner.suite.target}"
                  + (f", profile={runner.profile.name}" if runner.profile.name != "copilot" else "") + ")")
    exp = asyncio.run(runner.run())
    render_summary(exp, trials.for_experiment(exp.id), failures=failures)
    raise typer.Exit(0 if exp.status == "completed" else 1)


@app.command()
def regrade(experiment_id: str, suite: Annotated[str | None, typer.Option()] = None) -> None:
    """Re-grade a stored experiment with the suite's current graders (no agent run)."""
    from eval_harness.evals.runner.service import prepare_regrade
    from eval_harness.storage.repositories import trials

    try:
        runner = prepare_regrade(experiment_id, suite_name=suite)
    except (FileNotFoundError, KeyError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    exp = asyncio.run(runner.run())
    render_summary(exp, trials.for_experiment(exp.id))


@app.command()
def show(experiment_id: str, failures: bool = True) -> None:
    """Show a stored experiment."""
    from eval_harness.storage.repositories import experiments, trials

    exp = experiments.get(experiment_id if experiment_id != "latest" else experiments.latest_id() or "")
    if exp is None:
        raise typer.BadParameter("experiment not found")
    render_summary(exp, trials.for_experiment(exp.id), failures=failures)


@app.command()
def compare(a: str, b: str) -> None:
    """Compare experiment B against A (regressions first, with significance tests)."""
    from eval_harness.evals.analysis.compare import compare as do_compare

    r = do_compare(a, b)
    console.print(f"[bold]{r['a']['name']}[/bold] {r['a']['pass_rate']:.0%}  ->  [bold]{r['b']['name']}[/bold] "
                  f"{r['b']['pass_rate']:.0%}   delta {r['delta']:+.1%}")
    console.print(f"two-proportion z={r['two_proportion_z']['z']:.2f} p={r['two_proportion_z']['p_value']:.3f}   "
                  f"McNemar p={r['mcnemar']['p_value']:.3f}")
    console.print(f"[red]regressions: {r['regressions']}[/red]\n[green]improvements: {r['improvements']}[/green]")
    for w in r.get("warnings", []):
        if w.startswith("different agents"):  # the suite case is covered by the like-for-like note below
            console.print(f"\n[yellow]warning: {w}[/yellow]")
    if r["config_changes"]:
        console.print("\n[bold]what differs between the runs[/bold]")
        for c in r["config_changes"]:
            console.print(f"  {c['path']}: [red]{c['a']}[/red] -> [green]{c['b']}[/green]")
    n_a, n_b = r["a"]["n_trials"], r["b"]["n_trials"]
    if r["only_in_a"] or r["only_in_b"] or n_a != n_b:
        console.print(f"\n[yellow]note: the runs are not like-for-like (trials {n_a} vs {n_b}; tasks only in A: "
                      f"{r['only_in_a']}, only in B: {r['only_in_b']}). The headline rates cover all trials; the per-task "
                      f"list and McNemar cover only the tasks both runs share.[/yellow]")


@app.command("calibrate")
def calibrate_cmd(experiment_id: Annotated[str | None, typer.Argument()] = None) -> None:
    """Grader-vs-human alignment (coverage, FFR, kappa) from Annotate-view labels."""
    from eval_harness.evals.analysis.calibration import calibrate

    r = calibrate(experiment_id)
    if not r["n_labeled"]:
        console.print(r["message"])
        return
    t = Table(title=f"calibration ({r['n_labeled']} labelled trials)", show_edge=False)
    for c in ("grader", "n", "coverage", "ffr", "alignment", "kappa"):
        t.add_column(c)
    f = lambda v: "-" if v is None else f"{v:.2f}"  # noqa: E731
    rows = {"(all graders)": r["trial_level"], **r["graders"]}
    for name, m in rows.items():
        if m:
            t.add_row(name, str(m["n"]), f(m["coverage"]), f(m["ffr"]), f(m["alignment"]), f(m["kappa"]))
    console.print(t)


@app.command("list")
def list_(what: Annotated[str, typer.Argument(help="suites|datasets|graders|tools|skills|agents|targets|"
                                                    "metrics|middleware|generators|experiments")]) -> None:
    """List available components."""
    t = Table(show_edge=False)
    t.add_column("name")
    t.add_column("info")
    if what == "suites":
        from eval_harness.evals.datasets.loader import list_suites
        for s in list_suites():
            t.add_row(s.name, f"{s.description[:80]} (k={s.run.k}, agent={s.agent})")
    elif what == "datasets":
        from eval_harness.evals.datasets.loader import dataset_groups
        for g, n in dataset_groups().items():
            t.add_row(g, f"{n} tasks")
    elif what == "graders":
        from eval_harness.evals.graders.base import grader_registry
        for n, c in grader_registry.items():
            t.add_row(n, f"layer {c.layer}: {c.description}")
    elif what == "tools":
        from eval_harness.tools.base import TOOL_SPECS, tool_registry
        tool_registry.discover()
        for n, s in TOOL_SPECS.items():
            t.add_row(n, f"{s.description[:90]}")
    elif what == "skills":
        from eval_harness.skills.loader import load_library
        for n, s in load_library().items():
            t.add_row(n, f"{s.description[:80]} (~{s.tokens} tokens, assets: {len(s.assets)})")
    elif what == "agents":
        from eval_harness.agent.config import list_agent_configs
        for a in list_agent_configs():
            t.add_row(a.name, a.description)
    elif what in ("targets", "metrics", "middleware", "generators"):
        reg = _registry_for(what)
        for n in reg.names():
            t.add_row(n, "")
    elif what == "experiments":
        from eval_harness.storage.repositories import experiments

        t = Table(show_edge=False)
        for c in ("id", "name", "suite", "agent", "model", "k x tasks", "status", "pass"):
            t.add_column(c, no_wrap=(c == "id"), overflow="fold" if c != "id" else "ellipsis")  # ids must stay copyable
        for e in experiments.list(30):
            pr = e.summary.get("pass_rates", {})
            m = e.snapshot.get("models", {}).get("agent", {})
            model = f"{m.get('provider', '?')}:{m.get('model', '?')}"
            rate = pr.get("trial_pass_rate")
            t.add_row(e.id, e.name, e.suite, e.snapshot.get("target", {}).get("agent_config", {}).get("name", "-"),
                      f"[dim]{model} (offline)[/dim]" if m.get("provider") == "fake" else model,
                      f"{pr.get('k', '-')} x {pr.get('n_tasks', '-')}", e.status,
                      "-" if rate is None else f"{rate:.0%}")
        console.print(t)
        return
    else:
        raise typer.BadParameter(f"unknown listing '{what}'")
    console.print(t)


def _registry_for(what: str):
    if what == "targets":
        from eval_harness.evals.targets.base import target_registry as r
    elif what == "metrics":
        from eval_harness.evals.metrics.registry import metric_registry as r
    elif what == "middleware":
        from eval_harness.agent.middleware.registry import middleware_registry as r
    else:
        from eval_harness.evals.data_sources.synthesis.base import generator_registry as r
    return r


@datasets_app.command("push")
def datasets_push(group: str) -> None:
    """Push local tasks of a dataset group to LangSmith."""
    from eval_harness.evals.datasets.loader import load_tasks
    from eval_harness.integrations.langsmith.datasets import push_tasks

    res = push_tasks(group, load_tasks([group]))
    console.print(res if res else "LangSmith disabled or push failed (check LANGSMITH_API_KEY / tracing).")


@datasets_app.command("pull")
def datasets_pull(name: str) -> None:
    """Pull a LangSmith dataset into evals/datasets/langsmith/."""
    from eval_harness.integrations.langsmith.datasets import pull_dataset

    console.print(pull_dataset(name) or "LangSmith disabled or pull failed.")


@datasets_app.command("validate")
def datasets_validate() -> None:
    """Validate every dataset file and suite."""
    from eval_harness.evals.datasets.loader import list_suites, load_tasks, suite_tasks

    tasks = load_tasks()
    console.print(f"{len(tasks)} tasks OK")
    for s in list_suites():
        console.print(f"suite {s.name}: {len(suite_tasks(s))} tasks selected")


@app.command()
def synthesize(config: str, accept: Annotated[bool, typer.Option(help="skip review, write to datasets")] = False) -> None:
    """Generate synthetic candidate tasks from evals/synthesis/<config>.yaml."""
    from eval_harness.evals.data_sources.synthesis.runner import run_synthesis

    res = run_synthesis(config, accept=accept)
    console.print(res)


@app.command()
def traffic(n: int = 10, personas: Annotated[str | None, typer.Option()] = None,
            agent: Annotated[str | None, typer.Option(
                "--agent", "--variant", help="variant of the active profile (default: its default variant)")] = None,
            fault_rate: float = 0.0) -> None:
    """Simulate user traffic against the agent (traced to LangSmith as source=traffic)."""
    from eval_harness.evals.data_sources.traffic.simulator import simulate_traffic

    console.print(asyncio.run(simulate_traffic(n=n, agent=agent, fault_rate=fault_rate)))


@app.command("import-traces")
def import_traces(adapter: Annotated[str | None, typer.Option(help="langsmith | jsonl (default: langsmith if enabled)")] = None, limit: int = 50, source: Annotated[str | None, typer.Option()] = None,
                  errors_only: bool = False, path: Annotated[str | None, typer.Option()] = None) -> None:
    """Import logged traces as candidate tasks (review them, then accept)."""
    from eval_harness.evals.data_sources.traces.importer import default_adapter
    from eval_harness.evals.data_sources.traces.importer import import_traces as do_import

    adapter = adapter or default_adapter()  # the profile's trace source, else langsmith if enabled, else jsonl
    console.print(do_import(adapter, limit=limit, source=source, errors_only=errors_only, path=path))


@app.command()
def candidates(accept: Annotated[list[str] | None, typer.Option(help="candidate ids (or 'all')")] = None,
               group: str = "accepted") -> None:
    """List candidate tasks awaiting review, or accept some into a dataset group."""
    from eval_harness.evals.data_sources import review

    if accept:
        console.print(review.accept(accept, group=group))
        return
    t = Table(show_edge=False)
    for c in ("id", "source", "input"):
        t.add_column(c)
    for c in review.list_candidates():
        t.add_row(c.id, c.source, c.user_text[:90])
    console.print(t)


@app.command()
def scaffold(kind: Annotated[str, typer.Argument(help="grader|tool|metric|target|skill|generator")], name: str) -> None:
    """Create a new component from a template (plus a unit test)."""
    from eval_harness.cli.scaffold import scaffold as do_scaffold

    for p in do_scaffold(kind, name):
        console.print(f"created {p}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the API server."""
    import uvicorn

    uvicorn.run("eval_harness.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
