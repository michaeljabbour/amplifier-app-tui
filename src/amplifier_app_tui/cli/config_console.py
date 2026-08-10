"""Scriptable, redacted config reads behind ``amplifier-tui config show|paths``.

The interactive half of durable-settings management moved to the full-screen
settings panel (:mod:`amplifier_app_tui.ui.settings_panel`, WS3); this module
keeps only the offline, script-stable renderers.  Durable reads still go
through the existing kernel admin modules, while the Click command callbacks
remain thin wiring in :mod:`amplifier_app_tui.main`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal

import click
from rich.console import Console
from rich.table import Table

from ..kernel import bundle_admin, directory_permissions, notify_admin, settings_service, setup
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


def snapshot() -> ConfigSnapshot:
    """Build a read-only, redacted configuration summary."""

    paths = bundle_admin.settings_paths(None, None)
    keys = setup.keys_file()
    routing = settings_service.resolve_path(paths, keys, "routing.matrix")
    bundle = settings_service.resolve_path(paths, keys, "tui.bundle.active")
    assert routing is not None and bundle is not None  # registered schema paths
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
        routing=routing.value,
        bundle=bundle.value,
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


__all__ = [
    "ConfigPaths",
    "ConfigSnapshot",
    "WriteScope",
    "config_paths",
    "render_paths",
    "render_snapshot",
    "snapshot",
]
