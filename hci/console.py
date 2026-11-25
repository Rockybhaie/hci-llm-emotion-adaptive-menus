"""Live researcher view in the terminal (the participant never sees this)."""

import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def _clock(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def render(snap):
    head = Table.grid(padding=(0, 2))
    head.add_column(style="bold")
    head.add_column()
    flags = " ".join(f"[reverse] {k.upper()} [/]" for k, v in snap["flags"].items() if v)
    head.add_row("Participant", f"{snap['participant']}  {flags}")
    step = f"{snap['step'] + 1}/{snap['steps']}  {snap['type']}"
    if snap["query"]:
        step += f"  ·  query {snap['query']}  ·  look [cyan]{snap['look']}[/]  ·  switches {snap['switches']}"
    head.add_row("Step", step)
    e = snap["emotion"]
    if e:
        face = f"[green]{e.get('emotion', '')}[/] {e.get('confidence', 0):.0%}  ·  valence {e.get('valence', 0):+.2f}" \
            if e.get("face") else "[yellow]no face[/]"
        head.add_row("Face", face)
    head.add_row("Elapsed", _clock(snap["elapsed"]))
    head.add_row("Saving to", snap["folder"])
    parts = [head]

    if snap["sensors"]:
        sensors = Table(expand=True, show_edge=False, header_style="bold dim")
        for col in ("Sensor", "Adapter", "Rate", "Samples", "Status"):
            sensors.add_column(col)
        for s in snap["sensors"]:
            if s.get("error"):
                status = Text(s["error"], style="red")
            elif s.get("last_age") is None:
                status = Text("waiting", style="yellow")
            elif s["last_age"] > 3:
                status = Text(f"no data for {s['last_age']:.0f}s", style="red")
            else:
                status = Text(s.get("note") or "ok", style="green")
            sensors.add_row(s.get("slot", s["kind"]), s["adapter"], f"{s['hz']:.0f} Hz", f"{s['samples']:,}", status)
        parts += [Text(""), sensors]
    if snap["warnings"]:
        parts += [Text(""), Text("\n".join(f"{t}  {m}" for t, m in snap["warnings"]), style="yellow")]
    keys = "Ctrl+C here or Ctrl+Shift+Q in the browser stops and saves."
    if snap["flags"].get("pilot"):
        keys += "  Ctrl+Shift+F in the browser simulates a frown."
    parts += [Text(""), Text(keys, style="dim")]
    return Panel(Group(*parts), title="[bold]GenUI study[/]", border_style="grey50")


def watch(session):
    with Live(render(session.snapshot()), console=console, refresh_per_second=2, transient=False) as live:
        while not session.done.is_set():
            live.update(render(session.snapshot()))
            time.sleep(0.5)
        live.update(render(session.snapshot()))
