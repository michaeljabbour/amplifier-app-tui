"""Interactive control center behind ``amplifier-tui config``.

This module owns terminal presentation and menu orchestration only.  Durable
reads and writes still go through the existing kernel admin modules, while
the Click command callbacks remain thin wiring in :mod:`amplifier_app_tui.main`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal

import click
from rich.console import Console
from rich.table import Table

from ..kernel import bundle_admin, directory_permissions, notify_admin, routing_admin, setup
from ..kernel.config import DEFAULT_BUNDLE, load_merged_settings
from ..product import BRAND_NAME, EXECUTABLE_NAME

WriteScope = Literal["global", "project", "local"]


@dataclass(frozen=True)
class ConfigPaths:
    """Every durable app-owned settings location, without secret values."""

    global_settings: str
    project_settings: str
    local_settings: str
    keys: str
    routing: str


@dataclass(frozen=True)
class ConfigSnapshot:
    """Small, redacted picture used by the dashboard and ``config show``."""

    command: str
    provider: str | None
    provider_type: str | None
    model: str | None
    provider_count: int
    routing: str
    bundle: str
    allowed_directories: int
    denied_directories: int
    notification_ceiling: str
    desktop_notifications: str
    push_notifications: str
    push_topic_configured: bool
    paths: ConfigPaths

    def as_dict(self) -> dict[str, object]:
        """Stable script output; no credential or ntfy-topic value is exposed."""

        return {
            "schema": "amplifier-app-tui/config/v1",
            **asdict(self),
        }


@dataclass(frozen=True)
class ConfigActions:
    """Existing admin flows injected into the control-center menu."""

    providers: Callable[[WriteScope], WriteScope]
    routing: Callable[[WriteScope], WriteScope]
    bundles: Callable[[WriteScope], WriteScope]
    directories: Callable[[WriteScope], WriteScope]
    notifications: Callable[[WriteScope], WriteScope]
    maintenance: Callable[[], None]
    change_scope: Callable[[Console, WriteScope], WriteScope]


def config_paths() -> ConfigPaths:
    """Resolve the actual paths for this cwd and Amplifier home."""

    paths = bundle_admin.settings_paths(None, None)
    home = paths.global_settings.parent
    return ConfigPaths(
        global_settings=str(paths.global_settings),
        project_settings=str(paths.project_settings),
        local_settings=str(paths.local_settings),
        keys=str(setup.keys_file()),
        routing=str(home / "routing"),
    )


def write_target(scope: WriteScope) -> str:
    """Return the exact settings file changed by the selected scope."""

    paths = config_paths()
    return {
        "global": paths.global_settings,
        "project": paths.project_settings,
        "local": paths.local_settings,
    }[scope]


def snapshot() -> ConfigSnapshot:
    """Build a read-only, redacted configuration summary."""

    paths = bundle_admin.settings_paths(None, None)
    settings = load_merged_settings(paths)
    providers = setup.configured_providers()
    primary = next(
        (entry for entry in providers if entry.primary), providers[0] if providers else None
    )
    notifications = notify_admin.load_status()
    push = (
        "off"
        if notifications.suppress or notifications.push_enabled is False
        else "on"
        if notifications.push_enabled is True
        else "default"
    )
    return ConfigSnapshot(
        command=EXECUTABLE_NAME,
        provider=primary.name if primary else None,
        provider_type=primary.module_id if primary else None,
        model=primary.model if primary else None,
        provider_count=len(providers),
        routing=routing_admin.active_matrix(settings),
        bundle=bundle_admin.current_bundle() or DEFAULT_BUNDLE,
        allowed_directories=len(directory_permissions.configured_entries(paths, "allowed")),
        denied_directories=len(directory_permissions.configured_entries(paths, "denied")),
        notification_ceiling=notifications.ceiling,
        desktop_notifications=notifications.desktop_gate,
        push_notifications=push,
        push_topic_configured=notifications.topic,
        paths=config_paths(),
    )


def render_snapshot(*, as_json: bool = False, console: Console | None = None) -> None:
    """Render ``config show`` in scriptable JSON or friendly text."""

    state = snapshot()
    if as_json:
        click.echo(json.dumps(state.as_dict(), sort_keys=True))
        return
    console = console or Console(highlight=False)
    console.print(f"[bold]{BRAND_NAME} configuration[/bold]")
    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column("Setting", style="dim", no_wrap=True)
    table.add_column("Value")
    provider = state.provider or "not configured"
    if state.model:
        provider += f" · {state.model}"
    table.add_row("Provider", provider)
    table.add_row("Routing", state.routing)
    table.add_row("Bundle", state.bundle)
    table.add_row(
        "Directory access",
        f"{state.allowed_directories} allowed · {state.denied_directories} denied",
    )
    table.add_row(
        "Notifications",
        f"{state.notification_ceiling} · desktop {state.desktop_notifications} · "
        f"push {state.push_notifications}",
    )
    console.print(table)


def render_paths(*, as_json: bool = False, console: Console | None = None) -> None:
    """Render settings locations; keys are named but never read or printed."""

    paths = config_paths()
    if as_json:
        click.echo(
            json.dumps(
                {"schema": "amplifier-app-tui/config-paths/v1", **asdict(paths)},
                sort_keys=True,
            )
        )
        return
    console = console or Console(highlight=False)
    console.print("[bold]Settings paths[/bold]")
    for label, value in (
        ("Global", paths.global_settings),
        ("Project", paths.project_settings),
        ("Local", paths.local_settings),
        ("Keys", paths.keys),
        ("Routing", paths.routing),
    ):
        exists = "exists" if Path(value).exists() else "not created"
        console.print(f"  [cyan]{label:<8}[/cyan] {value}  [dim]({exists})[/dim]")
    console.print("\n[dim]Secret values are never shown.[/dim]")


_CHOICES: dict[str, str] = {
    "1": "providers",
    "provider": "providers",
    "providers": "providers",
    # Undocumented compatibility keys from the legacy ``init`` dashboard.
    "p": "providers",
    "2": "routing",
    "model": "routing",
    "models": "routing",
    "routing": "routing",
    "models and routing": "routing",
    "r": "routing",
    "3": "bundles",
    "bundle": "bundles",
    "bundles": "bundles",
    "b": "bundles",
    "4": "directories",
    "directory": "directories",
    "directories": "directories",
    "directory access": "directories",
    "permissions": "directories",
    "5": "notifications",
    "notification": "notifications",
    "notifications": "notifications",
    "6": "paths",
    "path": "paths",
    "paths": "paths",
    "settings paths": "paths",
    "7": "maintenance",
    "maintain": "maintenance",
    "maintenance": "maintenance",
    "s": "scope",
    "w": "scope",
    "scope": "scope",
    "q": "done",
    "d": "done",
    "quit": "done",
    "done": "done",
    "exit": "done",
    "": "done",
}


def run_control_center(
    actions: ConfigActions,
    *,
    scope: WriteScope = "global",
    start: Literal["dashboard", "providers"] = "dashboard",
) -> int:
    """Run the durable settings menu; Enter/back never writes by itself."""

    console = Console(highlight=False)
    if start == "providers" and snapshot().provider_count == 0:
        scope = actions.providers(scope)

    while True:
        console.rule(f"[bold]{BRAND_NAME} control center[/bold]")
        render_snapshot(console=console)
        console.print(f"[dim]Write target: {scope} · {write_target(scope)}[/dim]", soft_wrap=True)
        console.print(
            "\n"
            "  [cyan]1[/cyan]  Providers\n"
            "  [cyan]2[/cyan]  Models and routing\n"
            "  [cyan]3[/cyan]  Bundles\n"
            "  [cyan]4[/cyan]  Directory access\n"
            "  [cyan]5[/cyan]  Notifications\n"
            "  [cyan]6[/cyan]  Settings paths\n"
            "  [cyan]7[/cyan]  Maintenance previews\n"
            "  [dim]s  Change write scope · q  Done[/dim]\n"
        )
        try:
            raw = click.prompt("Choose a number or name", default="q", show_default=False)
        except (click.Abort, EOFError):
            console.print("[dim]Done · no additional changes.[/dim]")
            return 0
        choice = _CHOICES.get(raw.strip().casefold())
        if choice is None:
            console.print("[yellow]Choose 1-7, an action name, or q to finish.[/yellow]")
            continue
        if choice == "done":
            console.print("[green]✓ Configuration complete[/green]")
            return 0
        if choice == "providers":
            scope = actions.providers(scope)
        elif choice == "routing":
            scope = actions.routing(scope)
        elif choice == "bundles":
            scope = actions.bundles(scope)
        elif choice == "directories":
            scope = actions.directories(scope)
        elif choice == "notifications":
            scope = actions.notifications(scope)
        elif choice == "paths":
            render_paths(console=console)
            click.pause("Press Enter to return")
        elif choice == "maintenance":
            actions.maintenance()
        elif choice == "scope":
            scope = actions.change_scope(console, scope)


__all__ = [
    "ConfigActions",
    "ConfigPaths",
    "ConfigSnapshot",
    "WriteScope",
    "config_paths",
    "render_paths",
    "render_snapshot",
    "run_control_center",
    "snapshot",
    "write_target",
]
