import argparse
import shutil
import sys

from rich.table import Table

from . import config, export, paths, preflight
from .console import console


def cmd_check(args):
    results = preflight.run(sensors=not args.no_sensors, mock=args.mock)
    table = Table(show_edge=False, header_style="bold dim")
    for col in ("Check", "", "Detail"):
        table.add_column(col)
    style = {"ok": "[green]✔[/]", "warn": "[yellow]![/]", "fail": "[red]✘[/]"}
    for name, level, msg in results:
        table.add_row(name, style[level], msg)
    console.print(table)
    failed = [r for r in results if r[1] == "fail"]
    if failed:
        console.print(f"\n[red bold]{len(failed)} problem(s) to fix before running a participant.[/]")
        return 1
    console.print("\n[green bold]Ready.[/]")
    return 0


def cmd_session(args):
    from .browser import Browser
    from .sensing import Sensing, planned
    from .sensors import SensorError
    from .server import ServerThread, create_app
    from .session import Session, SessionExists

    cfg = config.load()
    plan = planned(cfg.devices, mode=args.sensors)
    try:
        session = Session(cfg, args.participant, fast=args.fast, pilot=args.pilot, resume=args.resume,
                          sensor_plan=plan)
    except (SessionExists, config.ConfigError, ValueError) as exc:
        console.print(f"[red]{exc}[/]")
        return 1

    def discard():
        session.store.close()
        if not args.resume:
            shutil.rmtree(session.folder, ignore_errors=True)
            parent = session.folder.parent
            if parent != paths.DATA and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()

    p = session.plan
    console.print(f"[bold]{args.participant}[/]  query order: {' > '.join(p['order'])}")
    console.print("  starting looks: " + "  ".join(f"{q}={lk}" for q, lk in p["start_looks"].items()))
    if plan:
        console.print("Starting sensors: " + ", ".join(f"{k} = {v}" for k, v in plan.items()) + " …")
        sensing = Sensing(session.store, mode=args.sensors, devices=cfg.devices)
        try:
            sensing.start()
        except (SensorError, Exception) as exc:
            discard()
            console.print(f"[red]Sensors failed: {exc}[/]\nRun [bold]python run.py check[/], or try "
                          f"--sensors mock (simulated) / --sensors off (no webcam).")
            return 1
        session.attach_sensing(sensing)
    else:
        console.print("[yellow]No sensors: emotion is not recorded and answers only change on request.[/]")
    session._save()

    host, port = cfg.study["server"]["host"], cfg.study["server"]["port"]
    try:
        server = ServerThread(create_app(session), host, port).start()
    except RuntimeError as exc:
        if session.sensing is not None:
            session.sensing.stop()
        discard()
        console.print(f"[red]{exc}[/]")
        return 1

    browser = None
    if args.no_browser:
        console.print(f"Open [bold]{server.url}[/] in a browser.")
    else:
        browser = Browser(cfg.study.get("browser", "edge"), kiosk=not args.windowed).open(server.url)
    if plan:
        console.print(f"Researcher webcam view: [bold]{server.url}/monitor[/] (open it on your own screen only)")

    from .console import watch
    try:
        watch(session)
    except KeyboardInterrupt:
        session.abort("Ctrl+C in terminal")

    if session.status == "complete":
        console.print(f"\n[green bold]Session complete.[/] Data saved in [bold]{paths.rel(session.folder)}[/]")
        if browser:
            try:
                input("Press Enter to close the participant's browser … ")
            except (EOFError, KeyboardInterrupt):
                pass
    elif session.withdrawn:
        console.print(f"\n[yellow bold]Session {session.status}.[/] The participant's data was deleted, as they asked.")
    else:
        console.print(f"\n[yellow bold]Session {session.status}.[/] Partial data kept in "
                      f"[bold]{paths.rel(session.folder)}[/] (resume with --resume)")
    if browser:
        browser.close()
    server.stop()
    return 0


def cmd_preview(args):
    from .browser import Browser
    from .server import ServerThread, create_app

    cfg = config.load()
    host, port = cfg.study["server"]["host"], cfg.study["server"]["port"]
    server = ServerThread(create_app(cfg=cfg), host, port).start()
    url = f"{server.url}/review/"
    browser = None if args.no_browser else Browser(cfg.study.get("browser", "edge"), kiosk=False).open(url)
    console.print(f"Reviewing all answers at {url} (nothing is recorded). Ctrl+C to stop.")
    try:
        while server.thread.is_alive():
            server.thread.join(0.5)
    except KeyboardInterrupt:
        pass
    if browser:
        browser.close()
    server.stop()
    return 0


def cmd_camera(args):
    """Live webcam window with the emotion model (nothing recorded)."""
    from .monitor import camera_demo
    from .sensing import load_devices
    from .sensors import SensorError
    devices = load_devices()
    if args.index is not None:
        devices.setdefault("camera", {})["index"] = args.index
    try:
        camera_demo(devices)
    except SensorError as exc:
        console.print(f"[red]{exc}[/]")
        return 1
    return 0


def cmd_export(args):
    sessions, written = export.export_all(rebuild=args.rebuild)
    console.print(f"Exported {len(sessions)} session(s):")
    for path in written:
        console.print(f"  {paths.rel(path)}")
    return 0


def cmd_clean_pilot(args):
    if paths.PILOT.exists():
        shutil.rmtree(paths.PILOT)
        console.print("Removed data/_pilot/")
    else:
        console.print("Nothing to clean.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="run.py", description="Emotion-adaptive Generative UI study")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="test config, answer content, browser and webcam")
    c.add_argument("--no-sensors", action="store_true", help="skip the webcam / emotion-model test")
    c.add_argument("--mock", action="store_true", help="test simulated sensors instead of the webcam")
    c.set_defaults(func=cmd_check)

    s = sub.add_parser("session", help="run one participant")
    s.add_argument("--participant", required=True, help="e.g. P01")
    s.add_argument("--sensors", choices=["config", "mock", "off"], default="config",
                   help="config: webcam as in config/devices.yaml (default); mock: simulated; off: none")
    s.add_argument("--fast", action="store_true", help="shorten every timing (testing only)")
    s.add_argument("--pilot", action="store_true",
                   help="save under data/_pilot/ and enable the simulated-frown key (Ctrl+Shift+F)")
    s.add_argument("--resume", action="store_true", help="continue an interrupted session")
    s.add_argument("--windowed", action="store_true", help="normal window instead of fullscreen kiosk")
    s.add_argument("--no-browser", action="store_true", help="don't open a browser (print the URL)")
    s.set_defaults(func=cmd_session)

    v = sub.add_parser("preview", help="review every answer in every look (nothing recorded)")
    v.add_argument("--no-browser", action="store_true")
    v.set_defaults(func=cmd_preview)

    w = sub.add_parser("camera", help="live webcam demo of the emotion model (nothing recorded)")
    w.add_argument("--index", type=int, help="camera index (default: config/devices.yaml)")
    w.set_defaults(func=cmd_camera)

    e = sub.add_parser("export", help="combine all participants into data/exports/")
    e.add_argument("--rebuild", action="store_true", help="rebuild every merged.csv first")
    e.set_defaults(func=cmd_export)

    k = sub.add_parser("clean-pilot", help="delete data/_pilot/")
    k.set_defaults(func=cmd_clean_pilot)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except config.ConfigError as exc:
        console.print(f"[red]{exc}[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
