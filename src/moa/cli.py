"""CLI interface for the multi-model AI debate system."""

import asyncio
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

from .config import MOA_HOME, GLOBAL_ENV, ensure_moa_home
from .engine import run_moa, run_expert_review, run_debate, run_cascade, run_adaptive, run_deep_research
from .models import TIERS, REVIEWER_ROLES, ALL_MODELS, CORE_MODELS, OPTIONAL_MODELS, available_models, ADAPTIVE_TIERS
from .cache import get_cached, set_cached
from .history import log_query, get_history, get_history_stats
from .context import build_context

# Load .env files: project-local first, then global ~/.moa/.env
load_dotenv()
if GLOBAL_ENV.exists():
    load_dotenv(GLOBAL_ENV)

app = typer.Typer(
    name="moa",
    help="Multi-model AI debate system — MoA, Expert Panel, Cascade, and Debate",
    no_args_is_help=True,
)
console = Console()


def _show_model_status(model_status: dict):
    """Print model status line."""
    parts = [f"[dim]{name}[/dim] {status}" for name, status in model_status.items()]
    console.print("  ".join(parts))


def _confidence_bar(score: float, width: int = 20) -> str:
    """Render a confidence bar: ██████████░░░░░░░░░░"""
    filled = int(score * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def _confidence_label(score: float, consensus: bool, researched: bool) -> tuple:
    """Return (label, color) for the confidence level."""
    if researched and not consensus:
        return "MODERATE — grounded in docs after initial split", "blue"
    if score > 0.7:
        return "HIGH — models converged on the same answer", "green"
    if score > 0.4:
        return "MODERATE — models mostly aligned with some variation", "yellow"
    if score > 0.2:
        return "MIXED — significant differences between models", "yellow"
    return "LOW — models substantially disagree", "red"


def _display_rich_result(result: dict, con: Console):
    """Display a rich, trust-building output panel with confidence and attribution."""
    cost = result["cost"]
    classification = result.get("classification", "")
    domain = result.get("domain", "")
    agreement_score = result.get("agreement_score", None)
    consensus = result.get("consensus", True)
    researched = result.get("researched", False)
    threshold = result.get("agreement_threshold", 0.35)

    # ── Title ──────────────────────────────────────────────────────────
    title_parts = [cost.tier]
    if domain:
        title_parts.append(f"({domain})")
    if cost.escalated:
        title_parts.append("🔺 ESCALATED")
        title_color = "red"
    elif researched:
        title_parts.append("🔍 RESEARCHED")
        title_color = "blue"
    elif not consensus and agreement_score is not None:
        title_parts.append(f"⚠️ SPLIT ({agreement_score:.0%})")
        title_color = "yellow"
    else:
        title_color = "green"

    title = " ".join(title_parts)

    # ── Main response panel ────────────────────────────────────────────
    con.print(Panel(
        Markdown(result["response"]),
        title=f"[bold {title_color}]{title}[/bold {title_color}]",
        border_style=title_color,
    ))

    # ── Confidence panel (only for adaptive with agreement data) ───────
    if agreement_score is not None:
        label, label_color = _confidence_label(agreement_score, consensus, researched)
        bar = _confidence_bar(agreement_score)

        model_count = len(result.get("model_names", []))
        aligned = int(agreement_score * model_count) if model_count > 0 else 0
        aligned = max(aligned, 1) if model_count > 0 else 0

        conf_parts = []
        conf_parts.append(f"  [bold]Agreement:[/bold] {agreement_score:.0%} ({aligned}/{model_count} models aligned)")
        if domain:
            conf_parts.append(f"  [bold]Domain:[/bold] {domain} · Threshold: {threshold:.0%}")
        conf_parts.append(f"  [{label_color}]{bar}[/{label_color}] {label}")
        if researched:
            conf_parts.append("  [blue]🔍 Models initially disagreed → web search → re-asked with docs[/blue]")

        con.print("\n".join(conf_parts))
        con.print()

    # ── Escalation reason ──────────────────────────────────────────────
    if result.get("escalation_reason"):
        con.print(f"[yellow]⚠  Escalated: {result['escalation_reason']}[/yellow]")

    # ── Model status line ──────────────────────────────────────────────
    if result.get("model_status"):
        _show_model_status(result["model_status"])

    # ── Rich footer ────────────────────────────────────────────────────
    footer_parts = [f"${cost.estimated_cost_usd:.4f}"]
    footer_parts.append(f"{cost.total_input_tokens + cost.total_output_tokens:,} tokens")
    footer_parts.append(f"⏱  {result['latency_ms']}ms")

    if result.get("ranking"):
        best_idx = result["ranking"].get("best_index", 0)
        names = result.get("model_names", [])
        if best_idx < len(names):
            footer_parts.append(f"👑 Best: {names[best_idx]}")

    if result.get("layers", 1) > 1:
        footer_parts.append(f"📐 {result['layers']} layers")

    warning = result.get("warning", "")
    if warning:
        footer_parts.append(f"⚠️ {warning}")

    con.print(f"[dim]  {'  ·  '.join(footer_parts)}[/dim]")


@app.command()
def ask(
    query: str = typer.Argument(..., help="The question to send to the model ensemble"),
    tier: str = typer.Option("lite", "--tier", "-t", help="Routing tier: flash, lite, pro, ultra"),
    cascade: bool = typer.Option(False, "--cascade", "-c", help="Use legacy cascade flow"),
    adaptive: bool = typer.Option(True, "--adaptive/--no-adaptive", "-a", help="Use adaptive routing (default)"),
    context: str = typer.Option(None, "--context", "-x", help="Path to project/dir/file for auto-context injection"),
    show_proposals: bool = typer.Option(False, "--proposals", "-p", help="Show individual model proposals"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw text without formatting"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass response cache"),
    research: str = typer.Option("auto", "--research", "-R", help="Research mode: auto, lite, deep, off"),
    layers: int = typer.Option(1, "--layers", "-L", help="MoA aggregation layers (1-3, default 1)"),
    persona: str = typer.Option(None, "--persona", help="Persona names (comma-separated) or category: code, product, content, architecture, builder"),
):
    """Run a Mixture-of-Agents query across multiple models.

    Default: adaptive routing (classifies query, selects models automatically).
    Use --context to auto-inject project structure and key files.
    Use --cascade for legacy flow. Use --tier for manual tier selection.
    Use --research deep for thorough multi-hop web research.
    Use --persona "DHH,Shreya Doshi" or --persona product for persona-flavored responses.
    """
    # ── Context injection ──────────────────────────────────────────────────
    if context:
        ctx = build_context(context)
        if not raw:
            console.print(f"[dim]📁 Injected context from: {context}[/dim]")
        query = f"{ctx}\n\nQuestion: {query}"
    elif not sys.stdin.isatty():
        # Only read stdin if there's actually data waiting (avoid hanging on piped output)
        import select
        if select.select([sys.stdin], [], [], 0.1)[0]:
            stdin_content = sys.stdin.read().strip()
            if stdin_content:
                query = f"[PIPED CONTEXT]\n{stdin_content}\n[/PIPED CONTEXT]\n\nQuestion: {query}"

    # ── Persona injection ───────────────────────────────────────────────
    if persona:
        from .models import get_personas, PERSONA_CATEGORIES
        # Check if it's a category name
        if persona.lower() in PERSONA_CATEGORIES:
            selected = get_personas(category=persona)
        else:
            selected = get_personas(names=persona)
        if selected and not raw:
            names = ", ".join(p.name for p in selected)
            console.print(f"[dim]🎭 Personas: {names}[/dim]")
        if selected:
            persona_block = "\n".join(
                f"- {p.name}: {p.system_prompt}" for p in selected
            )
            query = (
                f"[PERSONA PERSPECTIVES]\n"
                f"Answer from these specific perspectives:\n{persona_block}\n"
                f"[/PERSONA PERSPECTIVES]\n\n{query}"
            )

    effective_tier = "cascade" if cascade else ("adaptive" if adaptive else tier)

    # ── Cache check ─────────────────────────────────────────────────────
    if not no_cache:
        cached = get_cached(query, effective_tier)
        if cached:
            if raw:
                print(cached.get("response", ""))
                return
            console.print(Panel(
                Markdown(cached.get("response", "")),
                title=f"[bold blue]📦 Cached ({cached.get('_cache_age_mins', '?')}m ago)[/bold blue]",
                border_style="blue",
            ))
            console.print(f"[dim]Cache hit — $0.00 | {cached.get('cost_summary', '')}[/dim]")
            return

    # ── Run models ──────────────────────────────────────────────────────
    if research == "deep":
        with console.status("[bold cyan]Deep research (searching → reading → synthesizing)...[/bold cyan]"):
            try:
                result = asyncio.run(run_deep_research(query))
            except RuntimeError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1)
        # Deep research has its own display format
        set_cached(query, "deep-research", result)
        cost = result["cost"]
        log_query(
            query=query, tier=cost.tier, cost_usd=cost.estimated_cost_usd,
            models_used=cost.models_used, escalated=False,
            latency_ms=result["latency_ms"],
            response_preview=result["response"][:500],
        )
        if raw:
            print(result["response"])
            return
        # Show research steps
        for step in result.get("research_steps", []):
            console.print(f"[dim]  🔍 {step}[/dim]")
        console.print(Panel(
            Markdown(result["response"]),
            title="[bold blue]deep-research[/bold blue]",
            border_style="blue",
        ))
        if result.get("model_status"):
            _show_model_status(result["model_status"])
        console.print(f"[dim]{cost.summary()} | ⏱  {result['latency_ms']}ms[/dim]")
        return

    elif cascade:
        with console.status("[bold cyan]Running cascade (lite → evaluate → premium if needed)...[/bold cyan]"):
            result = asyncio.run(run_cascade(query))
    elif adaptive and not cascade:
        with console.status("[bold cyan]Running adaptive (classify → route → propose → synthesize)...[/bold cyan]"):
            result = asyncio.run(run_adaptive(query, research_mode=research))
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
            result = asyncio.run(run_moa(query, tier, layers=layers))

    # ── Cache store + history log ───────────────────────────────────────
    set_cached(query, effective_tier, result)
    cost = result["cost"]
    log_query(
        query=query, tier=cost.tier, cost_usd=cost.estimated_cost_usd,
        models_used=cost.models_used, escalated=cost.escalated,
        latency_ms=result["latency_ms"],
        response_preview=result["response"][:500],
    )

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

    # ── Rich output display ────────────────────────────────────────────
    _display_rich_result(result, console)


@app.command()
def review(
    path: str = typer.Argument(None, help="Path to diff file, or omit for --staged"),
    staged: bool = typer.Option(False, "--staged", "-s", help="Review git staged changes"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw text"),
    discourse: bool = typer.Option(False, "--discourse", "-d", help="Enable reviewer discourse round"),
    personas: bool = typer.Option(False, "--personas", "-P", help="Use default code review personas"),
    persona: str = typer.Option(None, "--persona", help="Persona names or category: code, architecture, product"),
):
    """Run Expert Panel code review (Security + Architecture + Performance + Correctness).

    Use --personas for Fowler/Beck/Hickey/Metz review style.
    Use --persona "DHH,Kelsey Hightower" for specific personas.
    Use --discourse for reviewers to react to each other's findings.
    """
    from .config import MAX_DIFF_LINES

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

    # Warn on large diffs
    line_count = diff.count('\n')
    if line_count > MAX_DIFF_LINES:
        console.print(
            f"[yellow]⚠ Diff is {line_count} lines (limit: {MAX_DIFF_LINES}). "
            f"Large diffs will be truncated and may miss issues.[/yellow]"
        )

    from .models import PERSONA_ROLES, get_personas, PERSONA_CATEGORIES
    if persona:
        if persona.lower() in PERSONA_CATEGORIES:
            selected = get_personas(category=persona)
        else:
            selected = get_personas(names=persona)
        review_roles = [p.as_reviewer_role() for p in selected]
        label = "Persona Panel"
    elif personas:
        review_roles = PERSONA_ROLES
        label = "Persona Panel"
    else:
        review_roles = REVIEWER_ROLES
        label = "Expert Panel"
    available = [(r, r.model if r.model.available else r.fallback)
                 for r in review_roles if r.model.available or r.fallback.available]
    disc_label = " + discourse" if discourse else ""
    with console.status(
        f"[bold cyan]Running {label}{disc_label}...[/bold cyan] "
        f"{len(available)} reviewers → synthesizer"
    ):
        result = asyncio.run(run_expert_review(diff, discourse=discourse, roles=review_roles))

    if raw:
        print(result["response"])
        return

    console.print(Panel(
        Markdown(result["response"]),
        title="[bold magenta]Expert Panel Review[/bold magenta]",
        border_style="magenta",
    ))

    if result.get("model_status"):
        _show_model_status(result["model_status"])

    meta = result['cost'].summary() + f" | ⏱  {result['latency_ms']}ms"
    if result.get("warning"):
        meta += f" | ⚠️  {result['warning']}"
    console.print(f"[dim]{meta}[/dim]")


@app.command()
def debate(
    query: str = typer.Argument(..., help="The question to debate"),
    rounds: int = typer.Option(2, "--rounds", "-n", help="Number of debate rounds"),
    tier: str = typer.Option("pro", "--tier", "-t", help="Model tier"),
    style: str = typer.Option("peer", "--style", "-s", help="Debate style: peer or adversarial"),
    context: str = typer.Option(None, "--context", "-x", help="Path to project/dir/file for auto-context injection"),
    persona: str = typer.Option(None, "--persona", help="Persona names or category for debate perspectives"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw text"),
):
    """Run a multi-round debate where models revise based on each other.

    Use --style adversarial for angel/devil/judge pattern.
    Use --context to inject project files for architecture debates.
    Use --persona "DHH,Kelsey Hightower" for persona-flavored debate.
    """
    # ── Persona injection ─────────────────────────────────────────────────
    if persona:
        from .models import get_personas, PERSONA_CATEGORIES
        if persona.lower() in PERSONA_CATEGORIES:
            selected = get_personas(category=persona)
        else:
            selected = get_personas(names=persona)
        if selected and not raw:
            names = ", ".join(p.name for p in selected)
            console.print(f"[dim]🎭 Personas: {names}[/dim]")
        if selected:
            persona_block = "\n".join(
                f"- {p.name}: {p.system_prompt}" for p in selected
            )
            query = (
                f"[PERSONA PERSPECTIVES]\n"
                f"Debate from these perspectives:\n{persona_block}\n"
                f"[/PERSONA PERSPECTIVES]\n\n{query}"
            )

    # ── Context injection ──────────────────────────────────────────────────
    if context:
        ctx = build_context(context)
        if not raw:
            console.print(f"[dim]📁 Injected context from: {context}[/dim]")
        query = f"{ctx}\n\nDebate question: {query}"

    available = TIERS.get(tier, TIERS["pro"]).available_proposers
    if len(available) < 2:
        console.print("[red]Debate requires at least 2 models with valid API keys.[/red]")
        raise typer.Exit(1)

    status_msg = (
        f"[bold cyan]Adversarial debate ({rounds} rounds)...[/bold cyan]"
        if style == "adversarial"
        else f"[bold cyan]Debating ({rounds} rounds)...[/bold cyan] {len(available)} models"
    )
    with console.status(status_msg):
        result = asyncio.run(run_debate(query, rounds=rounds, tier_name=tier, debate_style=style))

    if raw:
        print(result["response"])
        return

    converged = result.get("converged_at")
    style_label = result.get("debate_style", "peer")
    total_rounds = len(result.get("rounds", [])) - 1  # subtract round 0

    if converged:
        title = f"[bold green]Debate — converged at round {converged}/{rounds}[/bold green]"
        border = "green"
    elif style_label == "adversarial":
        title = f"[bold red]Adversarial Debate ({rounds} rounds)[/bold red]"
        border = "red"
    else:
        title = f"[bold yellow]Debate ({rounds} rounds)[/bold yellow]"
        border = "yellow"

    console.print(Panel(Markdown(result["response"]), title=title, border_style=border))

    # Model status
    if result.get("model_status"):
        _show_model_status(result["model_status"])

    # Debate footer
    cost = result["cost"]
    footer_parts = [f"${cost.estimated_cost_usd:.4f}"]
    footer_parts.append(f"{cost.total_input_tokens + cost.total_output_tokens:,} tokens")
    footer_parts.append(f"⏱  {result['latency_ms']}ms")
    if converged:
        footer_parts.append(f"🎯 Converged at round {converged}/{rounds}")
    else:
        footer_parts.append(f"📊 {total_rounds} rounds completed")
    if style_label == "adversarial":
        footer_parts.append("⚔️ Adversarial")
    console.print(f"[dim]  {'  ·  '.join(footer_parts)}[/dim]")


@app.command()
def verify():
    """Verify that model names work by pinging each available model."""
    from .verify import verify_all_models

    console.print("[bold]Verifying model connections...[/bold]\n")

    with console.status("[cyan]Pinging models...[/cyan]"):
        results = asyncio.run(verify_all_models())

    table = Table(title="Model Verification")
    table.add_column("Model", style="cyan", max_width=45)
    table.add_column("Provider")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    ok_count = 0
    fail_count = 0

    for r in results:
        if r["status"] == "ok":
            ok_count += 1
            table.add_row(
                r["model"], r.get("provider", ""),
                "[green]✅ OK[/green]",
                f"{r['latency_s']}s — \"{r['response']}\"",
            )
        elif r["status"] == "skipped":
            table.add_row(
                r["model"], r.get("provider", ""),
                "[dim]⏭ Skipped[/dim]",
                r.get("reason", ""),
            )
        elif r["status"] == "timeout":
            fail_count += 1
            table.add_row(
                r["model"], r.get("provider", ""),
                "[yellow]⏱ Timeout[/yellow]",
                r.get("reason", ""),
            )
        else:
            fail_count += 1
            suggestion = r.get("suggestion", "")
            detail = r.get("reason", "")[:80]
            if suggestion:
                detail += f"\n  💡 {suggestion}"
            table.add_row(
                r["model"], r.get("provider", ""),
                "[red]❌ Error[/red]",
                detail,
            )

    console.print(table)
    console.print(f"\n[bold]{ok_count} passed[/bold], {fail_count} failed, {len(results) - ok_count - fail_count} skipped")


@app.command()
def history(
    n: int = typer.Option(20, "--last", "-n", help="Number of recent queries to show"),
    cost_only: bool = typer.Option(False, "--cost", help="Show only spend summary"),
):
    """Show query history and spend summary."""
    stats = get_history_stats()

    if cost_only:
        console.print(f"[bold]Spend Summary[/bold]")
        console.print(f"  Today:  ${stats['cost_today']:.4f}")
        console.print(f"  Total:  ${stats['total_cost']:.4f}")
        console.print(f"  Queries: {stats['total_queries']} ({stats['queries_today']} today)")
        console.print(f"  Avg latency: {stats['avg_latency_ms']}ms")
        console.print(f"  Escalation rate: {stats['escalation_rate']}%")
        return

    entries = get_history(n)
    if not entries:
        console.print("[dim]No query history yet.[/dim]")
        return

    table = Table(title=f"Last {len(entries)} Queries")
    table.add_column("Time", style="dim", max_width=12)
    table.add_column("Tier", max_width=20)
    table.add_column("Cost", style="green", max_width=10)
    table.add_column("Latency", style="dim", max_width=8)
    table.add_column("Query", max_width=50)

    for e in entries:
        ts = e.get("ts", "")[:16].replace("T", " ")
        tier = e.get("tier", "?")
        esc = " 🔺" if e.get("escalated") else ""
        cost = f"${e.get('cost_usd', 0):.4f}"
        latency = f"{e.get('latency_ms', 0)}ms"
        query_str = e.get("query", "")[:50]
        table.add_row(ts, f"{tier}{esc}", cost, latency, query_str)

    console.print(table)
    console.print()
    console.print(
        f"[bold]Total:[/bold] ${stats['total_cost']:.4f} across {stats['total_queries']} queries | "
        f"Escalation rate: {stats['escalation_rate']}%"
    )


@app.command()
def status():
    """Show available models, tiers, and API key status."""
    table = Table(title="Model Roster (14 models, 6 providers)")
    table.add_column("Model", style="cyan", max_width=45)
    table.add_column("Provider", style="white")
    table.add_column("$/Mtok (in/out)", style="dim")
    table.add_column("Status")
    table.add_column("Strengths", style="dim", max_width=40)

    # Core models first
    for model in CORE_MODELS:
        s = "✅" if model.available else "❌"
        style = "green" if model.available else "red"
        price = f"${model.input_cost_per_mtok:.2f} / ${model.output_cost_per_mtok:.2f}"
        strengths = ", ".join(model.strengths[:3]) if model.strengths else ""
        table.add_row(model.name, model.provider, price, f"[{style}]{s}[/{style}]", strengths)

    # Optional models with separator
    table.add_section()
    for model in OPTIONAL_MODELS:
        s = "✅" if model.available else "⚪"
        style = "green" if model.available else "dim"
        price = f"${model.input_cost_per_mtok:.2f} / ${model.output_cost_per_mtok:.2f}"
        strengths = ", ".join(model.strengths[:3]) if model.strengths else ""
        table.add_row(model.name, f"[dim]{model.provider}[/dim]", price, f"[{style}]{s}[/{style}]", strengths)

    console.print(table)
    console.print()

    # Tiers
    console.print("[bold]Tiers:[/bold]")
    for name, tier in TIERS.items():
        avail = len(tier.available_proposers)
        core_count = len(tier.proposers)
        bonus_count = len([m for m in tier.optional_proposers if m.available])
        agg = tier.aggregator
        agg_status = f"→ {agg.provider}" if agg and agg.available else ("→ ❌" if agg else "direct")
        bonus_str = f" +{bonus_count} bonus" if bonus_count else ""
        console.print(
            f"  [cyan]{name:8s}[/cyan] {avail} proposers ({core_count} core{bonus_str}) {agg_status} "
            f"~${tier.estimated_cost:.4f}/query — {tier.description}"
        )

    console.print()
    console.print("[bold]Flows:[/bold]")
    console.print("  [green]moa ask[/green]            Standard MoA (single tier)")
    console.print("  [green]moa ask --cascade[/green]  Best quality/cost: lite → evaluate → premium if needed")
    console.print("  [green]moa review[/green]         Expert Panel (4 specialist reviewers)")
    console.print("  [green]moa debate[/green]         Multi-round debate with convergence")
    console.print()
    console.print("[bold]New:[/bold]")
    console.print("  [green]moa verify[/green]         Ping each model to verify names work")

    # Budget display
    from .budget import get_spend_summary
    budget = get_spend_summary()
    console.print()
    console.print("[bold]Budget:[/bold]")
    console.print(
        f"  Today: ${budget['today']:.4f} / ${budget['cap']:.2f} "
        f"(${budget['remaining_today']:.4f} remaining)"
    )
    console.print(f"  7-day: ${budget['week']:.4f} | 30-day: ${budget['month']:.4f}")
    console.print()
    console.print(f"[dim]Config: {GLOBAL_ENV} | Home: {MOA_HOME}[/dim]")


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
