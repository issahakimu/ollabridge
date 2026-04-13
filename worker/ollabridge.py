#!/usr/bin/env python3
"""
OllaBridge — Local Ollama AI for Shared Hosting
================================================
Commands:
  run     Start the AI worker
  setup   Interactive setup wizard
  status  Check Ollama + server connectivity
  db      Manage the local SQLite job history database
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from config.loader import load_config, save_config
from modules.db import JobDatabase
from modules.ollama_manager import ensure_running, is_running
from modules.model_manager import ensure_model, list_installed_models, pull_model
from modules.poller import Poller

console = Console()
VERSION = "1.0.0"

BANNER = """[bold cyan]
  ___  _ _       ____       _     _
 / _ \\| | | __ _| __ ) _ __(_) __| | __ _  ___
| | | | | |/ _` |  _ \\| '__| |/ _` |/ _` |/ _ \\
| |_| | | | (_| | |_) | |  | | (_| | (_| |  __/
 \\___/|_|_|\\__,_|____/|_|  |_|\\__,_|\\__, |\\___|
                                     |___/[/]
[dim]v{version}  —  Local AI Bridge for Shared Hosting[/]
""".format(version=VERSION)


# ──────────────────────────────────────────────────────────────
# CLI PARSER
# ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ollabridge",
        description="OllaBridge — Connect local Ollama AI to your shared hosting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ollabridge run --site-url https://mysite.com --secret-key mykey123
  ollabridge run                          (uses config.ini or ~/.config/ollabridge/config.ini)
  ollabridge setup                        (interactive wizard)
  ollabridge status                       (check Ollama + server)
  ollabridge db stats
  ollabridge db clear
  ollabridge db export --output backup.sql

Environment Variables:
  OLLABRIDGE_SITE_URL         Your shared hosting URL
  OLLABRIDGE_SECRET_KEY       Authentication secret key
  OLLABRIDGE_DEFAULT_MODEL    Ollama model (default: gemma4:e2b)
  OLLABRIDGE_FALLBACK_MODEL   Fallback model  (default: llama3.2)
  OLLABRIDGE_OLLAMA_HOST      Ollama API URL  (default: http://localhost:11434)
  OLLABRIDGE_POLL_INTERVAL    Seconds between polls (default: 5)
  OLLABRIDGE_LOG_LEVEL        DEBUG|INFO|WARNING|ERROR
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # ── run ──────────────────────────────────────────────────
    run_p = sub.add_parser("run", help="Start the AI worker")
    _add_common_flags(run_p)
    run_p.add_argument("--interval",       dest="poll_interval",      type=int, metavar="SEC")
    run_p.add_argument("--model",          dest="default_model",      metavar="NAME")
    run_p.add_argument("--fallback-model", dest="fallback_model",     metavar="NAME")
    run_p.add_argument("--ollama-host",    dest="ollama_host",        metavar="URL")
    run_p.add_argument("--db-path",        dest="db_path",            metavar="PATH")
    run_p.add_argument("--no-auto-start",  dest="auto_start_ollama",  action="store_false", default=None)
    run_p.add_argument("--no-auto-pull",   dest="auto_pull_model",    action="store_false", default=None)
    run_p.add_argument("--log-level",      dest="log_level",          choices=["DEBUG","INFO","WARNING","ERROR"])

    # ── setup ────────────────────────────────────────────────
    setup_p = sub.add_parser("setup", help="Interactive setup wizard")
    setup_p.add_argument("--config", metavar="FILE",
                          default=str(Path.home() / ".config/ollabridge/config.ini"))
    setup_p.add_argument("--ollama-host", dest="ollama_host", metavar="URL",
                         default="http://localhost:11434")

    # ── status ───────────────────────────────────────────────
    stat_p = sub.add_parser("status", help="Check Ollama + server connectivity")
    _add_common_flags(stat_p)
    stat_p.add_argument("--ollama-host", dest="ollama_host", metavar="URL")

    # ── db ───────────────────────────────────────────────────
    db_p   = sub.add_parser("db", help="Manage the local SQLite job history")
    db_sub = db_p.add_subparsers(dest="subcmd")

    # db stats
    stats_p = db_sub.add_parser("stats", help="Show job history and statistics")
    stats_p.add_argument("--db-path", dest="db_path", metavar="PATH")
    stats_p.add_argument("--limit",   type=int, default=30, metavar="N",
                         help="Number of recent records to show (default: 30)")

    # db clear
    clear_p = db_sub.add_parser("clear", help="Delete all job history records")
    clear_p.add_argument("--db-path", dest="db_path", metavar="PATH")
    clear_p.add_argument("--yes",     action="store_true",
                         help="Skip confirmation prompt")

    # db export
    export_p = db_sub.add_parser("export", help="Export job history to a SQL file")
    export_p.add_argument("--db-path", dest="db_path", metavar="PATH")
    export_p.add_argument("--output",  metavar="FILE",
                          help="Output file (default: ollabridge_export_<date>.sql)")

    # ── uninstall ─────────────────────────────────────
    sub.add_parser("uninstall", help="Remove OllaBridge from this system")

    # ── update ───────────────────────────────────────
    up_p = sub.add_parser("update", help="Update OllaBridge to the latest version")
    up_p.add_argument("--yes", action="store_true", help="Skip confirmation")

    return parser


def _add_common_flags(p: argparse.ArgumentParser):
    p.add_argument("--site-url",   dest="site_url",   metavar="URL")
    p.add_argument("--secret-key", dest="secret_key", metavar="KEY")
    p.add_argument("--config",     metavar="FILE")


# ──────────────────────────────────────────────────────────────
# SETUP HELPERS — URL validation & model picker
# ──────────────────────────────────────────────────────────────

def _validate_url(url: str) -> tuple:
    """
    Validate a URL and test its connectivity.
    Returns (is_valid: bool, message: str).
    """
    url = url.strip()
    if not url:
        return False, "URL cannot be empty."
    if not re.match(r'^https?://', url):
        return False, "URL must start with http:// or https://"

    # Test reachability
    try:
        import requests
        r = requests.get(url, timeout=6)
        # Any HTTP response means the server is reachable
        return True, f"Reachable — HTTP {r.status_code}"
    except Exception as exc:
        msg = str(exc)
        if "Name or service not known" in msg or "getaddrinfo" in msg:
            return False, "Hostname not found. Check for typos."
        if "Connection refused" in msg:
            return False, "Connection refused. Is the server up?"
        if "timed out" in msg.lower():
            return False, "Connection timed out. Check the URL."
        # Reachable but with TLS / other errors — still a valid URL
        return True, f"Reachable (with warning: {msg[:60]})"


def _pick_model(prompt_label: str, default: str, ollama_host: str) -> str:
    """
    Interactive model picker used by the setup wizard.

    • If Ollama is running and has models: shows a numbered list.
      User can pick by number OR type any model name directly.
    • Option [P] lets the user pull a new model.
    • If the pull fails, offers a retry loop.
    • Works identically for default_model and fallback_model.
    """
    # ── 1. Get installed models ──────────────────────────────
    if is_running(ollama_host):
        models = list_installed_models(ollama_host)
    else:
        console.print(f"    [yellow]⚠  Ollama not reachable at {ollama_host} — enter model name manually.[/]")
        models = []

    # ── 2. Show picker ───────────────────────────────────────
    while True:
        if models:
            console.print(f"\n    [bold]Installed models:[/]")
            for i, m in enumerate(models, 1):
                marker = " [dim](current default)[/]" if m == default else ""
                console.print(f"    [{i}] {m}{marker}")
            console.print( "    [P] Pull a new model from Ollama registry")
            console.print( "    [S] Skip / keep current default")

            choice = Prompt.ask(
                f"\n    {prompt_label}",
                default="1" if models else "P",
            ).strip()

            # Numeric pick
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(models):
                    return models[idx - 1]
                console.print("    [red]Invalid number — try again.[/]")
                continue

            choice_upper = choice.upper()

            if choice_upper == "S":
                return default

            if choice_upper != "P":
                # They typed a model name directly
                return choice

        # ── 3. Pull a new model ──────────────────────────────
        while True:
            model_name = Prompt.ask(
                "    Enter model name to pull",
                default=default,
            ).strip()

            if not model_name:
                continue

            console.print(f"    [dim]Pulling '{model_name}'… this may take a while[/]")
            if pull_model(model_name):
                console.print(f"    [green]✅  '{model_name}' ready.[/]")
                # Refresh model list and return
                models = list_installed_models(ollama_host) if is_running(ollama_host) else [model_name]
                return model_name

            # Pull failed
            console.print(f"    [red]❌  Pull failed for '{model_name}'.[/]")
            retry = Confirm.ask("    Try again with a different model name?", default=True)
            if not retry:
                console.print("    [yellow]Using name anyway — you can pull it later: ollama pull " + model_name + "[/]")
                return model_name
            # Loop back to ask for a new name


# ──────────────────────────────────────────────────────────────
# COMMAND: setup
# ──────────────────────────────────────────────────────────────

def cmd_setup(args):
    config_file  = getattr(args, "config", None) or str(Path.home() / ".config/ollabridge/config.ini")
    ollama_host  = getattr(args, "ollama_host", "http://localhost:11434")

    console.print(Panel("[bold cyan]OllaBridge Setup Wizard[/]", expand=False))
    console.print()

    # Load existing config as defaults
    existing = {}
    try:
        existing = load_config(config_file=config_file)
    except Exception:
        pass

    # ── Step 1: Site URL ─────────────────────────────────────
    console.print("[bold]Step 1 — Shared Hosting Server[/]")
    console.print("  [dim]Enter the full URL to the directory where you uploaded the PHP files.[/]")
    console.print("  [dim]Examples:  https://mysite.com/ollabridge   or   https://ai.mysite.com[/]")
    while True:
        site_url = Prompt.ask(
            "  Server URL",
            default=existing.get("site_url") or "",
        ).strip().rstrip("/")

        valid, msg = _validate_url(site_url)
        if valid:
            console.print(f"  [green]✅  {msg}[/]")
            break
        else:
            console.print(f"  [red]❌  {msg}[/]")
            if not Confirm.ask("  Try a different URL?", default=True):
                console.print("  [yellow]Proceeding with unverified URL.[/]")
                break

    secret_key = Prompt.ask(
        "  Secret key  (any strong random string)",
        default=existing.get("secret_key") or "",
    )

    # ── Step 2: Ollama / Models ──────────────────────────────
    console.print()
    console.print("[bold]Step 2 — Ollama Settings[/]")
    ollama_host = Prompt.ask(
        "  Ollama API URL",
        default=existing.get("ollama_host") or "http://localhost:11434",
    )

    # Verify Ollama before model selection
    console.print(f"  [dim]Checking Ollama at {ollama_host}…[/]", end=" ")
    if is_running(ollama_host):
        console.print("[green]✅ Running[/]")
    else:
        console.print("[yellow]⚠  Not reachable — you can still choose a model name[/]")

    console.print()
    console.print("  [bold]Default model[/] — used for all incoming jobs:")
    default_model = _pick_model(
        "Pick number, type name, or [P] to pull",
        existing.get("default_model") or "gemma4:e2b",
        ollama_host,
    )

    console.print()
    console.print("  [bold]Fallback model[/] — used when the default is unavailable:")
    fallback_model = _pick_model(
        "Pick number, type name, or [P] to pull",
        existing.get("fallback_model") or "llama3.2",
        ollama_host,
    )

    # ── Step 3: Polling ──────────────────────────────────────
    console.print()
    console.print("[bold]Step 3 — Polling[/]")
    poll_interval = Prompt.ask(
        "  Poll interval (seconds between server checks)",
        default=str(existing.get("poll_interval") or "5"),
    )

    # ── Save ─────────────────────────────────────────────────
    config = {
        "site_url":           site_url,
        "secret_key":         secret_key,
        "default_model":      default_model,
        "fallback_model":     fallback_model,
        "ollama_host":        ollama_host,
        "poll_interval":      poll_interval,
        "auto_start_ollama":  "true",
        "auto_pull_model":    "true",
        "db_path":            existing.get("db_path") or "local_jobs.db",
        "log_level":          existing.get("log_level") or "INFO",
    }
    save_config(config, config_file)

    console.print()
    console.print(f"[bold green]✅  Config saved → {config_file}[/]")
    console.print(f"[dim]Run the worker:  ollabridge run[/]")


# ──────────────────────────────────────────────────────────────
# COMMAND: status
# ──────────────────────────────────────────────────────────────

def cmd_status(args):
    config_file = getattr(args, "config", None) or str(Path.home() / ".config/ollabridge/config.ini")
    config = load_config(args=args, config_file=config_file)

    console.print(Panel("[bold cyan]OllaBridge Status[/]", expand=False))
    console.print()

    t = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    t.add_column("Check", style="bold")
    t.add_column("Result")
    t.add_column("Detail", style="dim")

    ollama_ok = is_running(config["ollama_host"])
    t.add_row(
        "Ollama service",
        "[green]✅ Running[/]" if ollama_ok else "[red]❌ Not running[/]",
        config["ollama_host"],
    )

    if ollama_ok:
        models  = list_installed_models(config["ollama_host"])
        preview = ", ".join(models[:4]) + ("…" if len(models) > 4 else "")
        t.add_row("Models installed", str(len(models)), preview or "none")

    if config.get("site_url") and config.get("secret_key"):
        import requests
        try:
            r = requests.get(
                f"{config['site_url'].rstrip('/')}/get_jobs.php",
                headers={"X-OllaBridge-Key": config["secret_key"]},
                timeout=10,
            )
            ok = r.status_code in (200, 204)
            t.add_row(
                "Shared server",
                "[green]✅ Reachable[/]" if ok else f"[red]❌ HTTP {r.status_code}[/]",
                config["site_url"],
            )
        except Exception as exc:
            t.add_row("Shared server", "[red]❌ Unreachable[/]", str(exc))
    else:
        t.add_row("Shared server", "[yellow]⚠  Not configured[/]",
                  "run: ollabridge setup")

    console.print(t)


# ──────────────────────────────────────────────────────────────
# COMMAND: run
# ──────────────────────────────────────────────────────────────

def cmd_run(args):
    config_file = getattr(args, "config", None) or str(Path.home() / ".config/ollabridge/config.ini")
    config = load_config(args=args, config_file=config_file)

    missing = [k for k in ("site_url", "secret_key") if not config.get(k)]
    if missing:
        console.print(f"[bold red]❌  Missing required config: {', '.join(missing)}[/]")
        console.print("[dim]Run: ollabridge setup[/]  or pass via CLI flags.")
        sys.exit(1)

    log_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console.print(BANNER)

    ct = Table(title="Active Configuration", box=box.ROUNDED,
               title_style="bold cyan", show_header=True, header_style="bold")
    ct.add_column("Setting"); ct.add_column("Value")
    ct.add_row("Site URL",           config["site_url"])
    ct.add_row("Secret Key",         "*" * min(len(config["secret_key"]), 8) + "…")
    ct.add_row("Ollama Host",        config["ollama_host"])
    ct.add_row("Default Model",      config["default_model"])
    ct.add_row("Fallback Model",     config["fallback_model"])
    ct.add_row("Poll Interval",      f"{config['poll_interval']}s")
    ct.add_row("Auto-start Ollama",  "✅ Yes" if config.get("auto_start_ollama", True) else "❌ No")
    ct.add_row("Auto-pull Models",   "✅ Yes" if config.get("auto_pull_model",   True) else "❌ No")
    ct.add_row("Local DB",           config["db_path"])
    ct.add_row("Log Level",          config.get("log_level", "INFO"))
    console.print(ct)
    console.print()

    console.print("[bold]🔍  Checking Ollama…[/]", end=" ")
    if not ensure_running(config["ollama_host"], config.get("auto_start_ollama", True)):
        console.print("[red]FAILED[/]")
        sys.exit(1)
    console.print("[green]✅ Running[/]")

    console.print(f"[bold]🤖  Checking model '{config['default_model']}'…[/]", end=" ")
    model = ensure_model(
        config["ollama_host"], config["default_model"],
        config["fallback_model"], config.get("auto_pull_model", True),
    )
    if model is None:
        console.print("[red]FAILED[/]")
        sys.exit(1)
    if model != config["default_model"]:
        console.print(f"[yellow]⚠  Fallback: {model}[/]")
        config["default_model"] = model
    else:
        console.print("[green]✅ Ready[/]")

    console.print(f"[bold]💾  Opening local database ({config['db_path']})…[/]", end=" ")
    db    = JobDatabase(config["db_path"])
    stats = db.get_stats()
    console.print(
        f"[green]✅ Ready[/] "
        f"[dim]({stats['done']} done, {stats['failed']} failed in history)[/]"
    )

    console.print()
    console.print("[bold green]🚀  OllaBridge is LIVE![/]")
    console.print(
        f"[dim]Polling [underline]{config['site_url']}[/underline] "
        f"every {config['poll_interval']}s — press Ctrl+C to stop.[/]\n"
    )

    poller = Poller(config, db)
    try:
        poller.run()
    except KeyboardInterrupt:
        console.print(
            f"\n[bold yellow]⏹  Stopped.[/]  "
            f"Processed: [green]{poller.jobs_processed}[/]  "
            f"Failed: [red]{poller.jobs_failed}[/]"
        )


# ──────────────────────────────────────────────────────────────
# COMMAND: db
# ──────────────────────────────────────────────────────────────

def cmd_db(args):
    subcmd = getattr(args, "subcmd", None)

    if not subcmd:
        console.print("[yellow]Usage:  ollabridge db <stats|clear|export>[/]")
        console.print("  [dim]stats            Show job history[/]")
        console.print("  [dim]clear            Delete all history records[/]")
        console.print("  [dim]export [--output FILE]  Export to SQL file[/]")
        return

    # Resolve DB path: CLI arg → config.ini → default
    db_path = getattr(args, "db_path", None)
    if not db_path:
        try:
            cfg_file = str(Path.home() / ".config/ollabridge/config.ini")
            cfg = load_config(config_file=cfg_file)
            db_path = cfg.get("db_path", "local_jobs.db")
        except Exception:
            db_path = "local_jobs.db"

    db = JobDatabase(db_path)

    # ── db stats ─────────────────────────────────────────────
    if subcmd == "stats":
        stats = db.get_stats()
        limit = getattr(args, "limit", 30)
        rows  = db.get_recent(limit=limit)

        db_size = "?"
        try:
            db_size = f"{os.path.getsize(db_path) / 1024:.1f} KB"
        except Exception:
            pass

        console.print()
        console.print(Panel(
            f"[bold]Path:[/] {db_path}   [bold]Size:[/] {db_size}\n"
            f"[green]Done: {stats['done']}[/]   "
            f"[red]Failed: {stats['failed']}[/]   "
            f"[dim]Total: {stats['total']}[/]",
            title="[bold cyan]OllaBridge Job Database[/]",
            expand=False,
        ))

        if not rows:
            console.print("\n[dim]No records yet.[/]\n")
            return

        t = Table(box=box.ROUNDED, show_header=True, header_style="bold",
                  title=f"Recent {min(limit, len(rows))} of {stats['total']} record(s)")
        t.add_column("Job ID",       style="dim",  no_wrap=True, max_width=36)
        t.add_column("Status",       justify="center")
        t.add_column("Model",        style="cyan")
        t.add_column("Duration",     justify="right")
        t.add_column("Completed At", style="dim")

        for r in rows:
            status_fmt = (
                "[green]done[/]"   if r["status"] == "done"
                else "[red]failed[/]"
            )
            dur_fmt = (
                f"{r['duration_ms'] / 1000:.1f}s"
                if r["duration_ms"] is not None else "[dim]—[/]"
            )
            t.add_row(
                r["job_id"],
                status_fmt,
                r["model_used"] or "—",
                dur_fmt,
                r["completed_at"] or "—",
            )

        console.print(t)
        console.print()

        if stats["total"] > limit:
            console.print(
                f"[dim]Showing {limit} of {stats['total']}. "
                f"Use --limit {stats['total']} to see all.[/]\n"
            )

    # ── db clear ─────────────────────────────────────────────
    elif subcmd == "clear":
        stats = db.get_stats()
        if stats["total"] == 0:
            console.print("[yellow]Database is already empty.[/]")
            return

        console.print(f"\n  [bold yellow]⚠  About to delete {stats['total']} record(s) "
                      f"from {db_path}[/]")

        yes = getattr(args, "yes", False) or \
              Confirm.ask("  Are you sure?", default=False)

        if yes:
            deleted = db.clear_all()
            console.print(f"  [green]✅  Deleted {deleted} record(s). Database is now empty.[/]\n")
        else:
            console.print("  [dim]Aborted — nothing was deleted.[/]\n")

    # ── db export ────────────────────────────────────────────
    elif subcmd == "export":
        output = getattr(args, "output", None) or \
                 f"ollabridge_export_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.sql"

        stats = db.get_stats()
        if stats["total"] == 0:
            console.print("[yellow]No records to export.[/]")
            return

        count = db.export_sql(output)
        size  = os.path.getsize(output)
        console.print(
            f"\n  [green]✅  Exported {count} record(s) → [bold]{output}[/bold] "
            f"({size} bytes)[/]\n"
        )

    else:
        console.print(f"[red]Unknown db subcommand: {subcmd}[/]")


# ──────────────────────────────────────────────────────────────
# COMMAND: uninstall
# ──────────────────────────────────────────────────────────────

def cmd_uninstall(_args):
    """
    Remove OllaBridge from the system.
    Removes: systemd service, ~/.local/bin/ollabridge, venv+worker data.
    Optionally removes: ~/.config/ollabridge/ (config + history).
    """
    console.print(Panel("[bold red]OllaBridge Uninstaller[/]", expand=False))
    console.print()

    home        = Path.home()
    bin_link    = home / ".local/bin/ollabridge"
    data_dir    = home / ".local/share/ollabridge"
    config_dir  = home / ".config/ollabridge"
    service_file = home / ".config/systemd/user/ollabridge.service"

    # Show what will be removed
    console.print("  [bold]The following will be removed:[/]")
    console.print(f"    {bin_link}  (command)")
    console.print(f"    {data_dir}/  (venv + worker files)")
    console.print(f"    {service_file}  (systemd service)")
    console.print()

    keep_config = Confirm.ask(
        "  Keep your config + job history (~/.config/ollabridge/)?\n"
        "  [dim]Say No to fully wipe everything[/]",
        default=True,
    )
    console.print()

    if not Confirm.ask("  [bold red]Proceed with uninstall?[/]", default=False):
        console.print("  [dim]Aborted — nothing was changed.[/]")
        return

    console.print()

    # 1. Stop + disable systemd service
    for cmd in (
        ["systemctl", "--user", "stop",    "ollabridge.service"],
        ["systemctl", "--user", "disable", "ollabridge.service"],
    ):
        try:
            subprocess.run(cmd, capture_output=True)
        except Exception:
            pass

    if service_file.exists():
        service_file.unlink()
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        except Exception:
            pass
        console.print("  [green]✅  Service stopped and removed[/]")

    # 2. Remove the symlink in ~/.local/bin/
    if bin_link.is_symlink() or bin_link.exists():
        bin_link.unlink(missing_ok=True)
        console.print(f"  [green]✅  Command removed ({bin_link})[/]")

    # 3. Remove venv + worker data directory
    if data_dir.exists():
        shutil.rmtree(data_dir)
        console.print(f"  [green]✅  Data directory removed ({data_dir})[/]")

    # 4. Optionally remove config
    if not keep_config and config_dir.exists():
        shutil.rmtree(config_dir)
        console.print(f"  [green]✅  Config directory removed ({config_dir})[/]")

    console.print()
    console.print("  [bold green]✅  OllaBridge has been fully removed.[/]")
    if keep_config:
        console.print(f"  [dim]Config kept at {config_dir}[/]")
        console.print(f"  [dim]To also remove it:  rm -rf {config_dir}[/]")
    console.print()


# ──────────────────────────────────────────────────────────────
# COMMAND: update
# ──────────────────────────────────────────────────────────────

def cmd_update(args):
    """
    Update OllaBridge worker to the latest version.
    Strategy:
      1. git pull (if running from a cloned repo)
      2. pip install --upgrade . (into the installed venv)
      3. systemctl restart (if service exists)
    """
    console.print(Panel("[bold cyan]OllaBridge Updater[/]", expand=False))
    console.print()

    home        = Path.home()
    venv_pip    = home / ".local/share/ollabridge/venv/bin/pip"
    src_dir     = Path(__file__).resolve().parent   # worker/ package directory

    yes = getattr(args, "yes", False)
    if not yes:
        console.print(f"  [dim]Source: {src_dir}[/]")
        console.print(f"  [dim]Pip   : {venv_pip}[/]")
        console.print()
        if not Confirm.ask("  Proceed with update?", default=True):
            console.print("  [dim]Aborted.[/]")
            return

    console.print()

    # Step 1: git pull
    console.print("  [bold]Step 1[/] — Pulling latest code from git…")
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True, text=True, cwd=src_dir.parent,
        )
        if result.returncode == 0:
            msg = result.stdout.strip() or "Already up to date."
            console.print(f"  [green]✅  {msg}[/]")
        else:
            console.print(f"  [yellow]⚠  git pull skipped: {result.stderr.strip()[:80]}[/]")
    except FileNotFoundError:
        console.print("  [yellow]⚠  git not found — skipping[/]")
    except Exception as exc:
        console.print(f"  [yellow]⚠  {exc}[/]")

    # Step 2: pip install --upgrade
    console.print("  [bold]Step 2[/] — Upgrading package…")
    if venv_pip.exists():
        result = subprocess.run(
            [str(venv_pip), "install", "--upgrade", "-q", str(src_dir)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print("  [green]✅  Package upgraded[/]")
        else:
            console.print(f"  [red]❌  pip failed: {result.stderr.strip()[:120]}[/]")
    else:
        console.print("  [yellow]⚠  Installed venv not found — run: bash install.sh[/]")

    # Step 3: restart service
    console.print("  [bold]Step 3[/] — Restarting service…")
    result = subprocess.run(
        ["systemctl", "--user", "restart", "ollabridge.service"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("  [green]✅  Service restarted[/]")
    else:
        console.print("  [yellow]⚠  Service not running (start with: ollabridge run)[/]")

    console.print()
    console.print("  [bold green]🚀  Update complete![/]")
    console.print("  [dim]Run [bold]ollabridge status[/] to verify.[/]")
    console.print()

def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "db":
        cmd_db(args)
    elif args.command in ("run", None):
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
