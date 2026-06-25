#!/usr/bin/env python3
"""
Replay a past task execution step-by-step for debugging.

Usage:
    python scripts/replay.py --task-id <task_id>
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


def replay(task_id: str) -> None:
    from orchestration.memory.working import get_all_working_memory

    wm = get_all_working_memory(task_id)
    state_data = wm.get("state", {})

    if not state_data:
        console.print(f"[red]No working memory found for task {task_id}[/red]")
        return

    events = state_data.get("trace_events", [])
    if not events:
        console.print("[yellow]No trace events recorded for this task.[/yellow]")
        return

    console.print(Panel.fit(f"[bold]Replaying task:[/bold] {task_id}\n[bold]Events:[/bold] {len(events)}", title="Replay Mode"))

    for i, ev in enumerate(events):
        agent = ev.get("agent", "?")
        etype = ev.get("event_type", "?")
        data = ev.get("data", {})

        console.print(f"\n[bold cyan]Step {i+1}/{len(events)}[/bold cyan] — {agent} · {etype}")
        console.print_json(data=data)

        if i < len(events) - 1:
            action = Prompt.ask("[dim]Press Enter to continue, 'q' to quit[/dim]", default="")
            if action.lower() == "q":
                break

    console.print("\n[green]Replay complete.[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True, help="Task ID to replay")
    args = parser.parse_args()
    replay(args.task_id)
