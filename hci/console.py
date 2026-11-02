"""Live researcher view in the terminal (the participant never sees this)."""

import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

PHASE_STYLE = {"baseline": "cyan", "practice": "blue", "induction": "magenta", "booster": "magenta", "tasks": "green",
               "rating": "yellow", "menu_rank": "yellow", "washout": "cyan"}


def _clock(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def render(snap):
    head = Table.grid(padding=(0, 2))
    head.add_column(style="bold")
    head.add_column()
    flags = " ".join(f"[reverse] {k.upper()} [/]" for k, v in snap["flags"].items() if v)
    head.add_row("Participant", f"{snap['group']} / {snap['participant']}  {flags}")
    phase = snap["phase"]
    label = f"[{PHASE_STYLE.get(phase, 'white')}]{phase}[/]"
    if snap["emotion"]:
        label += f"  ·  {snap['emotion']}"
    if snap["emotion_block"]:
        label += f"  ·  block {snap['emotion_block']}"
    if snap["sub_block"]:
        label += f"  ·  sub-block {snap['sub_block']}"
    if snap["menu_id"]:
        label += f"  ·  {snap['menu_id']} {snap['menu_name']}"
    if snap["task"]:
        label += f"  ·  task {snap['task']}"
    head.add_row("Step", f"{snap['step'] + 1}/{snap['steps']}  {snap['type']}  ({label})")
    head.add_row("Elapsed", _clock(snap["elapsed"]))
    head.add_row("Saving to", snap["folder"])
    head.add_row("Plan", snap["plan"])

    parts = [head]
    if snap["warnings"]:
        parts += [Text(""), Text("\n".join(f"{t}  {m}" for t, m in snap["warnings"]), style="yellow")]
    parts += [Text(""), Text("Ctrl+C here or Ctrl+Shift+Q in the browser stops and saves.", style="dim")]
    return Panel(Group(*parts), title="[bold]HCI trial[/]", border_style="grey50")


def watch(session):
    with Live(render(session.snapshot()), console=console, refresh_per_second=2, transient=False) as live:
        while not session.done.is_set():
            live.update(render(session.snapshot()))
            time.sleep(0.5)
        live.update(render(session.snapshot()))
