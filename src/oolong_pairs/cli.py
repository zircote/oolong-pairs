"""CLI interface for OOLONG-Pairs benchmark."""

import uuid
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .dataset import get_dataset_stats, load_oolong_tasks
from .models import BenchmarkRun, ExecutionMode, Strategy
from .storage import Storage
from .strategies import get_strategy

console = Console()


@click.group()
@click.option("--db", default="data/benchmark.db", help="Database path")
@click.pass_context
def cli(ctx: click.Context, db: str) -> None:
    """OOLONG-Pairs benchmark harness for Claude Code plugin testing."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db)
    ctx.obj["storage"] = Storage(Path(db))


@cli.command()
@click.option(
    "--strategy",
    type=click.Choice(["rlm_rs", "truncation"]),
    required=True,
    help="Execution strategy",
)
@click.option(
    "--mode",
    type=click.Choice(["sdk", "hooks"]),
    default="sdk",
    help="Execution mode",
)
@click.option("--limit", type=int, default=None, help="Max tasks to run")
@click.option(
    "--min-context",
    type=int,
    default=100_000,
    help="Minimum context length in chars",
)
@click.option("--dataset", default="trec_coarse", help="Dataset filter")
@click.pass_context
def run(
    ctx: click.Context,
    strategy: str,
    mode: str,
    limit: int | None,
    min_context: int,
    dataset: str,
) -> None:
    """Run benchmark with specified strategy."""
    storage: Storage = ctx.obj["storage"]

    # Parse enums
    strategy_enum = Strategy(strategy)
    mode_enum = ExecutionMode(mode)

    # Create run record
    run_id = str(uuid.uuid4())[:8]
    benchmark_run = BenchmarkRun(
        id=run_id,
        timestamp=datetime.now(),
        mode=mode_enum,
        strategy=strategy_enum,
    )
    storage.save_run(benchmark_run)

    console.print(f"[bold]Starting benchmark run:[/bold] {run_id}")
    console.print(f"  Strategy: {strategy_enum.value}")
    console.print(f"  Mode: {mode_enum.value}")
    console.print(f"  Dataset filter: {dataset}")
    console.print(f"  Min context: {min_context:,} chars")
    console.print()

    # Load tasks
    console.print("[dim]Loading tasks from HuggingFace...[/dim]")
    tasks = load_oolong_tasks(
        dataset_filter=dataset,
        min_context_length=min_context,
        limit=limit,
    )

    if not tasks:
        console.print("[red]No tasks found matching criteria[/red]")
        return

    console.print(f"[green]Loaded {len(tasks)} tasks[/green]")
    console.print()

    # Get strategy instance
    exec_strategy = get_strategy(strategy_enum, mode_enum)

    # Run benchmark
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_progress = progress.add_task(f"Running {len(tasks)} tasks...", total=len(tasks))

        for i, task in enumerate(tasks):
            progress.update(
                task_progress,
                description=f"Task {i + 1}/{len(tasks)}: {task.id[:16]}...",
            )

            try:
                result = exec_strategy.execute(task, run_id)
                storage.save_result(result)

                if result.error:
                    console.print(f"  [yellow]Task {task.id}: Error - {result.error}[/yellow]")
                else:
                    score_color = "green" if result.score >= 0.8 else "yellow" if result.score >= 0.5 else "red"
                    console.print(
                        f"  Task {task.id}: [{score_color}]{result.score:.2f}[/{score_color}] "
                        f"({result.latency_ms:.0f}ms)"
                    )

            except Exception as e:
                console.print(f"  [red]Task {task.id}: Exception - {e}[/red]")

            progress.advance(task_progress)

    # Update run stats
    storage.update_run_stats(run_id)

    # Show summary
    console.print()
    ctx.invoke(show, run_id=run_id)


@cli.command()
@click.argument("run_id")
@click.pass_context
def show(ctx: click.Context, run_id: str) -> None:
    """Show results for a benchmark run."""
    storage: Storage = ctx.obj["storage"]

    summary = storage.get_run_summary(run_id)
    if not summary:
        console.print(f"[red]Run not found: {run_id}[/red]")
        return

    table = Table(title=f"Benchmark Run: {run_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Strategy", summary.strategy.value)
    table.add_row("Mode", summary.mode.value)
    table.add_row("Tasks Completed", str(summary.tasks_completed))
    table.add_row("Tasks Failed", str(summary.tasks_failed))
    table.add_row("Average Score", f"{summary.avg_score:.4f}")
    table.add_row("Min Score", f"{summary.min_score:.4f}")
    table.add_row("Max Score", f"{summary.max_score:.4f}")
    table.add_row("Total Latency", f"{summary.total_latency_ms:.0f}ms")
    table.add_row("Avg Latency", f"{summary.avg_latency_ms:.0f}ms")

    console.print(table)


@cli.command()
@click.argument("run_id1")
@click.argument("run_id2")
@click.pass_context
def compare(ctx: click.Context, run_id1: str, run_id2: str) -> None:
    """Compare two benchmark runs."""
    storage: Storage = ctx.obj["storage"]

    s1 = storage.get_run_summary(run_id1)
    s2 = storage.get_run_summary(run_id2)

    if not s1 or not s2:
        console.print("[red]One or both runs not found[/red]")
        return

    table = Table(title="Benchmark Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column(f"{run_id1} ({s1.strategy.value})", style="yellow")
    table.add_column(f"{run_id2} ({s2.strategy.value})", style="green")
    table.add_column("Diff", style="magenta")

    def diff_str(v1: float, v2: float, higher_better: bool = True) -> str:
        diff = v2 - v1
        if diff == 0:
            return "="
        sign = "+" if diff > 0 else ""
        color = "green" if (diff > 0) == higher_better else "red"
        return f"[{color}]{sign}{diff:.4f}[/{color}]"

    table.add_row(
        "Tasks Completed",
        str(s1.tasks_completed),
        str(s2.tasks_completed),
        diff_str(s1.tasks_completed, s2.tasks_completed),
    )
    table.add_row(
        "Average Score",
        f"{s1.avg_score:.4f}",
        f"{s2.avg_score:.4f}",
        diff_str(s1.avg_score, s2.avg_score),
    )
    table.add_row(
        "Min Score",
        f"{s1.min_score:.4f}",
        f"{s2.min_score:.4f}",
        diff_str(s1.min_score, s2.min_score),
    )
    table.add_row(
        "Max Score",
        f"{s1.max_score:.4f}",
        f"{s2.max_score:.4f}",
        diff_str(s1.max_score, s2.max_score),
    )
    table.add_row(
        "Avg Latency (ms)",
        f"{s1.avg_latency_ms:.0f}",
        f"{s2.avg_latency_ms:.0f}",
        diff_str(s1.avg_latency_ms, s2.avg_latency_ms, higher_better=False),
    )

    console.print(table)

    # Calculate improvement
    if s1.avg_score > 0:
        improvement = ((s2.avg_score - s1.avg_score) / s1.avg_score) * 100
        console.print()
        if improvement > 0:
            console.print(f"[green]Score improvement: +{improvement:.1f}%[/green]")
        else:
            console.print(f"[red]Score change: {improvement:.1f}%[/red]")


@cli.command()
@click.option("--limit", type=int, default=20, help="Max runs to show")
@click.pass_context
def list_runs(ctx: click.Context, limit: int) -> None:
    """List recent benchmark runs."""
    storage: Storage = ctx.obj["storage"]
    runs = storage.list_runs(limit=limit)

    if not runs:
        console.print("[dim]No runs found[/dim]")
        return

    table = Table(title="Recent Benchmark Runs")
    table.add_column("ID", style="cyan")
    table.add_column("Timestamp", style="dim")
    table.add_column("Strategy", style="yellow")
    table.add_column("Mode", style="blue")
    table.add_column("Tasks", style="green")
    table.add_column("Avg Score", style="magenta")

    for run in runs:
        table.add_row(
            run.id,
            str(run.timestamp)[:19],
            run.strategy.value,
            run.mode.value,
            str(run.tasks_completed),
            f"{run.avg_score:.4f}",
        )

    console.print(table)


@cli.command()
@click.argument("run_id")
@click.argument("output", type=click.Path())
@click.option("--format", "fmt", type=click.Choice(["json", "jsonl", "csv"]), default="json")
@click.pass_context
def export(ctx: click.Context, run_id: str, output: str, fmt: str) -> None:
    """Export run results to file."""
    storage: Storage = ctx.obj["storage"]
    storage.export_results(run_id, Path(output), format=fmt)
    console.print(f"[green]Exported to {output}[/green]")


@cli.command()
@click.option("--dataset", default="trec_coarse", help="Dataset filter")
@click.option("--split", default="validation", help="Dataset split")
def stats(dataset: str, split: str) -> None:
    """Show dataset statistics."""
    console.print("[dim]Loading dataset statistics...[/dim]")

    stats_data = get_dataset_stats(dataset_filter=dataset, split=split)

    table = Table(title=f"Dataset Statistics: {dataset} ({split})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total in split", str(stats_data["total_in_split"]))
    table.add_row("Filtered count", str(stats_data["filtered_count"]))
    table.add_row("Min context length", f"{stats_data['context_length']['min']:,}")
    table.add_row("Max context length", f"{stats_data['context_length']['max']:,}")
    table.add_row("Avg context length", f"{stats_data['context_length']['avg']:,.0f}")

    console.print(table)

    # Task types
    if stats_data["task_types"]:
        console.print()
        task_table = Table(title="Task Types")
        task_table.add_column("Type", style="cyan")
        task_table.add_column("Count", style="green")
        for task_type, count in sorted(stats_data["task_types"].items()):
            task_table.add_row(task_type, str(count))
        console.print(task_table)

    # Answer types
    if stats_data["answer_types"]:
        console.print()
        ans_table = Table(title="Answer Types")
        ans_table.add_column("Type", style="cyan")
        ans_table.add_column("Count", style="green")
        for ans_type, count in sorted(stats_data["answer_types"].items()):
            ans_table.add_row(ans_type, str(count))
        console.print(ans_table)


if __name__ == "__main__":
    cli()
