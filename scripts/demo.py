#!/usr/bin/env python3
"""
Demo script — runs a full research task through the orchestration system locally
(without Docker, for quick portfolio demos).

Usage:
    python scripts/demo.py
    python scripts/demo.py --task "Your custom task here"
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Make sure the package is importable from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

console = Console()

DEMO_TASK = (
    "Research the top 3 large language model providers in 2024 (OpenAI, Anthropic, Google). "
    "For each, identify their flagship model, key capabilities, and pricing tier. "
    "Then write a 300-word executive summary comparing them for a CTO audience."
)


def run_demo(task: str) -> None:
    console.print(Panel.fit("[bold cyan]Agent Orchestration System — Live Demo[/bold cyan]", border_style="cyan"))
    console.print(f"\n[bold]Task:[/bold] {task}\n")

    # Import here so env vars are loaded first
    from orchestration.graph.state import AgentState, TaskStatus
    from orchestration.graph.workflow import compile_graph
    from orchestration.memory.semantic import retrieve_relevant_memories
    from orchestration.observability.metrics import start_task_metrics
    from orchestration.observability.tracing import setup_tracing
    from orchestration.tools.setup import register_all_tools

    setup_tracing(use_console=False)
    register_all_tools()

    task_id = f"demo-{int(time.time())}"
    metrics = start_task_metrics(task_id)

    console.print("[yellow]Retrieving relevant memories...[/yellow]")
    try:
        memories = retrieve_relevant_memories(task)
        if memories:
            console.print(f"[green]Found {len(memories)} relevant past experiences[/green]")
        else:
            console.print("[dim]No prior memories found (first run)[/dim]")
    except Exception:
        memories = []
        console.print("[dim]Memory retrieval skipped (ChromaDB not running)[/dim]")

    state = AgentState(
        task_id=task_id,
        user_id="demo_user",
        original_request=task,
        retrieved_memories=memories,
    )

    graph = compile_graph()
    console.print("\n[bold cyan]Starting agent workflow...[/bold cyan]\n")

    event_count = 0
    final_state = state

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        prog_task = progress.add_task("Running agents...", total=None)

        for event in graph.stream(state, stream_mode="values"):
            event_count += 1
            current = AgentState(**event) if isinstance(event, dict) else event
            final_state = current

            progress.update(prog_task, description=f"Status: [bold]{current.status.value}[/bold] | Events: {event_count}")

            if current.status == TaskStatus.AWAITING_HUMAN:
                progress.stop()
                console.print("\n[red bold]⚠️  HUMAN REVIEW REQUIRED[/red bold]")
                if current.pending_review:
                    console.print(Panel(
                        f"[bold]Level:[/bold] {current.pending_review.level}\n"
                        f"[bold]Reason:[/bold] {current.pending_review.trigger_reason}\n"
                        f"[bold]Proposed Action:[/bold] {current.pending_review.proposed_action}",
                        title="Review Request",
                        border_style="red",
                    ))
                    try:
                        decision = console.input("\nApprove? [y/N]: ").strip().lower()
                    except EOFError:
                        decision = "y"
                        console.print("[dim]No stdin — auto-approving for demo.[/dim]")
                    from orchestration.hitl.escalation import apply_human_resolution
                    current = apply_human_resolution(current, resolution="Demo approval", approved=(decision == "y"))
                    if not current.human_approved:
                        console.print("[red]Task cancelled by operator.[/red]")
                        return
                    state = current
                progress.start()

            if current.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break

    console.print()

    # ── Trace summary ──────────────────────────────────────────────────────
    if final_state.trace_events:
        tree = Tree("[bold]Agent Execution Trace[/bold]")
        for ev in final_state.trace_events:
            agent = ev.agent
            etype = ev.event_type
            latency = f"{ev.latency_ms:.0f}ms" if ev.latency_ms else ""
            icons = {"supervisor": "🧠", "researcher": "🔍", "analyst": "📊", "writer": "✍️", "coder": "💻", "reviewer": "🔎"}
            icon = icons.get(agent, "⚙️")
            tree.add(f"{icon} [cyan]{agent}[/cyan] · {etype} {latency}")
        console.print(tree)
        console.print()

    # ── Metrics ────────────────────────────────────────────────────────────
    metrics.complete()
    m = metrics.to_dict()
    table = Table(title="Task Metrics", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Tokens", str(m["total_tokens"]))
    table.add_row("Estimated Cost", f"${m['total_cost_usd']:.4f}")
    table.add_row("Wall Clock", f"{m['wall_clock_seconds']:.1f}s")
    table.add_row("Escalations", str(m["escalation_count"]))
    console.print(table)
    console.print()

    # ── Final output ────────────────────────────────────────────────────────
    if final_state.status == TaskStatus.COMPLETED and final_state.final_output:
        console.print(Panel(final_state.final_output, title="[bold green]Final Output[/bold green]", border_style="green"))
    elif final_state.status == TaskStatus.FAILED:
        console.print(Panel(final_state.error or "Unknown error", title="[bold red]Task Failed[/bold red]", border_style="red"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Orchestration Demo")
    parser.add_argument("--task", type=str, default=DEMO_TASK, help="Task to execute")
    args = parser.parse_args()
    run_demo(args.task)
