"""CLI interface for the multi-model AI debate system."""

import asyncio
import subprocess
import sys

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

from .engine import run_moa, run_expert_review, run_debate, run_cascade
from .models import TIERS, REVIEWER_ROLES, ALL_MODELS, available_models

load_dotenv()

app = typer.Typer(
    name="moa",
    help="Multi-model AI debate system — MoA, Expert Panel, Cascade, and Debate",
    no_args_is_help=True,
)
console = Console()


@app.command()
def ask(
    query: str = typer.Argument(..., help="The question to send to the model ensemble"),
    tier: str = typer.Option("lite", "--tier", "-t", help="Routing tier: flash, lite, pro, ultra"),
    cascade: bool = typer.Option(False, "--cascade", "-c", help="Use cascade flow: lite → evaluate → premium if needed"),
    show_proposals: bool = typer.Option(False, "--proposals", "-p", help="Show individual model proposals"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw text without formatting"),
):
    """Run a Mixture-of-Agents query across multiple models.
    
    Use --cascade for the best quality/cost tradeoff: starts cheap, 
    escalates to premium only when models disagree or confidence is low.
    """
    if cascade:
        with console.status("[bold cyan]Running cascade (lite → evaluate → premium if needed)...[/bold cyan]"):
            result = asyncio.run(run_cascade(query))
    else:
        if tier not in TIERS:
            console.print(f"[red]Unknown tier: {tier}. Options: {list(TIERS.keys())}[/red]")
            raise typer.Exit(1)
        tier_info = TIERS[tier]
        available = tier_info.available_proposers
        if not available:
            console.print(f"[red]No models available for tier '{tier}'.[/red]")
            console.print(f"Set API keys: {list(set(m.env_key for m in tier_info.proposers))}")
            raise typer.Exit(1)
        with console.status(
            f"[bold cyan]Running MoA ({tier})...[/bold cyan] "
            f"{len(available)} proposers → aggregator"
        ):
            result = asyncio.run(run_moa(query, tier))

    if raw:
        print(result["response"])
        return

    # Show proposals if requested
    if show_proposals and result.get("proposals"):
        for name, proposal in zip(
            result.get("model_names", []), result["proposals"]
        ):
            console.print(Panel(
                Markdown(proposal),
                title=f"[dim]{name}[/dim]",
                border_style="dim",
            ))
        console.print()

    # Title
    cost = result["cost"]
    title_suffix = f" 🔺 ESCALATED" if cost.escalated else ""
    title_color = "red" if cost.escalated else "green"
    title = f"[bold {title_color}]{cost.tier}{title_suffix}[/bold {title_color}]"

    console.print(Panel(Markdown(result["response"]), title=title, border_style=title_color))

    # Escalation reason
    if result.get("escalation_reason"):
        console.print(f"[yellow]⚠  Escalated: {result['escalation_reason']}[/yellow]")

    # Cost summary
    warning = result.get("warning", "")
    meta = cost.summary()
    if warning:
        meta += f" | ⚠️  {warning}"
    meta += f" | ⏱  {result['latency_ms']}ms"
    console.print(f"[dim]{meta}[/dim]")


@app.command()
def review(
    path: str = typer.Argument(None, help="Path to diff file, or omit for --staged"),
    staged: bool = typer.Option(False, "--staged", "-s", help="Review git staged changes"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw text"),
):
    """Run Expert Panel code review (Security + Architecture + Performance + Correctness)."""
    if staged:
        try:
            diff = subprocess.check_output(["git", "diff", "--staged"], text=True)
        except subprocess.CalledProcessError:
            console.print("[red]Not in a git repository or no staged changes.[/red]")
            raise typer.Exit(1)
        if not diff.strip():
            console.print("[yellow]No staged changes to review.[/yellow]")
            raise typer.Exit(0)
    elif path:
        try:
            with open(path) as f:
                diff = f.read()
        except FileNotFoundError:
            console.print(f"[red]File not found: {path}[/red]")
            raise typer.Exit(1)
    else:
        if not sys.stdin.isatty():
            diff = sys.stdin.read()
        else:
            console.print("[yellow]Provide a diff file, use --staged, or pipe a diff.[/yellow]")
            raise typer.Exit(1)

    available = [(r, r.model if r.model.available else r.fallback) 
                 for r in REVIEWER_ROLES if r.model.available or r.fallback.available]
    with console.status(
        f"[bold cyan]Running Expert Panel...[/bold cyan] "
        f"{len(available)} reviewers → synthesizer"
    ):
        result = asyncio.run(run_expert_review(diff))

    if raw:
        print(result["response"])
        return

    console.print(Panel(
        Markdown(result["response"]),
        title="[bold magenta]Expert Panel Review[/bold magenta]",
        border_style="magenta",
    ))
    console.print(f"[dim]{result['cost'].summary()} | ⏱  {result['latency_ms']}ms[/dim]")


@app.command()
def debate(
    query: str = typer.Argument(..., help="The question to debate"),
    rounds: int = typer.Option(2, "--rounds", "-n", help="Number of debate rounds"),
    tier: str = typer.Option("pro", "--tier", "-t", help="Model tier"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw text"),
):
    """Run a multi-round debate where models revise based on each other."""
    available = TIERS.get(tier, TIERS["pro"]).available_proposers
    if len(available) < 2:
        console.print("[red]Debate requires at least 2 models with valid API keys.[/red]")
        raise typer.Exit(1)

    with console.status(
        f"[bold cyan]Debating ({rounds} rounds)...[/bold cyan] {len(available)} models"
    ):
        result = asyncio.run(run_debate(query, rounds=rounds, tier_name=tier))

    if raw:
        print(result["response"])
        return

    console.print(Panel(
        Markdown(result["response"]),
        title=f"[bold yellow]Debate ({rounds} rounds)[/bold yellow]",
        border_style="yellow",
    ))
    console.print(f"[dim]{result['cost'].summary()} | ⏱  {result['latency_ms']}ms[/dim]")


@app.command()
def status():
    """Show available models, tiers, and API key status."""
    # Models table
    table = Table(title="Model Roster (14 models, 6 providers)")
    table.add_column("Model", style="cyan", max_width=45)
    table.add_column("Provider", style="white")
    table.add_column("$/Mtok (in/out)", style="dim")
    table.add_column("Status")
    table.add_column("Strengths", style="dim", max_width=40)

    for model in ALL_MODELS:
        s = "✅" if model.available else "❌"
        style = "green" if model.available else "red"
        price = f"${model.input_cost_per_mtok:.2f} / ${model.output_cost_per_mtok:.2f}"
        strengths = ", ".join(model.strengths[:3]) if model.strengths else ""
        table.add_row(
            model.name, model.provider, price,
            f"[{style}]{s}[/{style}]", strengths
        )

    console.print(table)
    console.print()

    # Tiers
    console.print("[bold]Tiers:[/bold]")
    for name, tier in TIERS.items():
        avail = len(tier.available_proposers)
        total = len(tier.proposers)
        agg = tier.aggregator
        agg_status = f"→ {agg.provider}" if agg and agg.available else ("→ ❌" if agg else "direct")
        console.print(
            f"  [cyan]{name:8s}[/cyan] {avail}/{total} proposers {agg_status} "
            f"~${tier.estimated_cost:.4f}/query — {tier.description}"
        )

    console.print()
    console.print("[bold]Flows:[/bold]")
    console.print("  [green]moa ask[/green]            Standard MoA (single tier)")
    console.print("  [green]moa ask --cascade[/green]  Best quality/cost: lite → evaluate → premium if needed")
    console.print("  [green]moa review[/green]         Expert Panel (4 specialist reviewers)")
    console.print("  [green]moa debate[/green]         Multi-round debate with convergence")


@app.command()
def serve(
    port: int = typer.Option(8787, "--port", "-p", help="HTTP server port"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
):
    """Start the HTTP API server (for n8n / webhook integration)."""
    import uvicorn
    from .server import create_app
    
    app_instance = create_app()
    console.print(f"[bold green]Starting MoA server on {host}:{port}[/bold green]")
    uvicorn.run(app_instance, host=host, port=port)


if __name__ == "__main__":
    app()
