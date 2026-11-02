import argparse
import shutil
import sys

from rich.table import Table

from . import config, counterbalance, export, paths, preflight
from .console import console


def cmd_check(args):
    results = preflight.run([args.group] if args.group else None, lenient=args.dry_run)
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
    from .server import ServerThread, create_app
    from .session import Session, SessionExists

    cfg = config.load()
    try:
        session = Session(cfg, args.group, args.participant, fast=args.fast, pilot=args.pilot, resume=args.resume)
    except (SessionExists, config.ConfigError, ValueError) as exc:
        console.print(f"[red]{exc}[/]")
        return 1

    def discard():
        # a session that never started leaves no trace in data/
        session.store.close()
        if not args.resume:
            shutil.rmtree(session.folder, ignore_errors=True)
            for parent in (session.folder.parent, session.folder.parent.parent):
                if parent not in (paths.DATA,) and parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()

    console.print(f"[bold]{args.group}/{args.participant}[/]\n{counterbalance.describe(session.plan)}\n")
    session._save()

    host, port = cfg.experiment["server"]["host"], cfg.experiment["server"]["port"]
    try:
        server = ServerThread(create_app(session), host, port).start()
    except RuntimeError as exc:
        discard()
        console.print(f"[red]{exc}[/]")
        return 1

    browser = None
    if args.no_browser:
        console.print(f"Open [bold]{server.url}[/] in a browser.")
    else:
        browser = Browser(cfg.experiment.get("browser", "edge"), kiosk=not args.windowed).open(server.url)

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
    group = cfg.group(args.group)
    site = group["site"]
    menu = args.menu or group["menus"][0]
    if menu not in group["menus"]:
        raise config.ConfigError(f"Menu {menu} is not part of {args.group}. {args.group} uses: {', '.join(group['menus'])}")
    host, port = cfg.experiment["server"]["host"], cfg.experiment["server"]["port"]
    server = ServerThread(create_app(preview_site=site, preview_menu=menu, cfg=cfg), host, port).start()
    url = f"{server.url}/core/site.html?site={site}&menu={menu}" + ("&debug=1" if args.debug else "")
    browser = None if args.no_browser else Browser(cfg.experiment.get("browser", "edge"), kiosk=False).open(url)
    info = cfg.menu(menu)
    console.print(f"Previewing [bold]{menu} {info['name']}[/] on [bold]{site}[/] at {url}\n"
                  f"Nothing is recorded{'; the green box shows the events the menu would log' if args.debug else ' (add --debug to show the logged events)'}. Ctrl+C to stop.")
    try:
        while server.thread.is_alive():
            server.thread.join(0.5)   # short joins keep Ctrl+C responsive on Windows
    except KeyboardInterrupt:
        pass
    if browser:
        browser.close()
    server.stop()
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
    p = argparse.ArgumentParser(prog="run.py", description="HCI emotion-induction trial platform")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="test config, task answers, menus, stimuli and browser")
    c.add_argument("--group", choices=["G1", "G2", "G3"])
    c.add_argument("--dry-run", action="store_true", help="missing videos are warnings, as in a --pilot session")
    c.set_defaults(func=cmd_check)

    s = sub.add_parser("session", help="run one participant")
    s.add_argument("--group", required=True, choices=["G1", "G2", "G3"])
    s.add_argument("--participant", required=True, help="e.g. P01")
    s.add_argument("--fast", action="store_true", help="shorten every timing (testing only)")
    s.add_argument("--pilot", action="store_true", help="dry run: save under data/_pilot/; missing videos become placeholders")
    s.add_argument("--resume", action="store_true", help="continue an interrupted session")
    s.add_argument("--windowed", action="store_true", help="normal window instead of fullscreen kiosk")
    s.add_argument("--no-browser", action="store_true", help="don't open a browser (print the URL)")
    s.set_defaults(func=cmd_session)

    v = sub.add_parser("preview", help="browse a group's website with one of its menus, without recording")
    v.add_argument("--group", required=True, choices=["G1", "G2", "G3"])
    v.add_argument("--menu", help="M1..M9 (must belong to the group; default: the group's first menu)")
    v.add_argument("--debug", action="store_true", help="show the green box of logged events (hidden by default)")
    v.add_argument("--no-browser", action="store_true")
    v.set_defaults(func=cmd_preview)

    e = sub.add_parser("export", help="combine all sessions into data/exports/")
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
