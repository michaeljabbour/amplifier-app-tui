"""The scriptable ``settings get|set|unset`` trio over the settings service.

Terminal wiring only: the registry lives in
:mod:`amplifier_app_tui.model.settings_schema`, resolution and durable writes
in :mod:`amplifier_app_tui.kernel.settings_service`. These runners convert
service outcomes into exit codes — unknown paths and invalid values are usage
errors (click exits 2), write failures print the service message and exit 1,
and secret values are never echoed back.
"""

from __future__ import annotations

from pathlib import Path

import click

from ..kernel import setup, settings_service
from ..kernel.bundle_admin import Scope, settings_paths
from ..kernel.config import SettingsPaths
from ..model import settings_schema
from ..model.settings_schema import SettingsField


def _locations() -> tuple[SettingsPaths, Path]:
    """The scope triple plus keys.env for this cwd and Amplifier home."""

    return settings_paths(None, None), setup.keys_file()


def _unknown_message(dotted: str) -> str:
    return f"unknown setting '{dotted}' — run `settings get` to list known settings"


def _source_line(resolved: settings_service.EffectiveSetting) -> str:
    if resolved.source == "env":
        return f"source: env ({resolved.field.env_var})"
    if resolved.source_file is not None:
        return f"source: {resolved.source} ({resolved.source_file})"
    return f"source: {resolved.source}"


def _echo_field(field: SettingsField, resolved: settings_service.EffectiveSetting) -> None:
    click.echo(f"{field.path} = {resolved.display}")
    click.echo(f"  {_source_line(resolved)}")


def run_get(target: str | None) -> int:
    """Print all sections, one section's settings, or one redacted value."""

    paths, keys = _locations()
    if target is None:
        click.echo("Settings sections:")
        width = max(len(section.id) for section in settings_schema.SECTIONS)
        for section in settings_schema.SECTIONS:
            click.echo(f"  {section.id:<{width}}  {section.summary}")
        click.echo("")
        click.echo("`settings get <section>` lists its settings; `settings get <path>` reads one.")
        return 0
    field = settings_schema.field_by_path(target)
    if field is not None:
        resolved = settings_service.resolve_field(paths, keys, field)
        click.echo(resolved.display)
        click.echo(_source_line(resolved))
        return 0
    fields = settings_schema.fields_in_section(target)
    if not fields:
        click.echo(
            f"unknown setting or section '{target}' — run `settings get` to list sections",
            err=True,
        )
        return 1
    for section_field in fields:
        _echo_field(section_field, settings_service.resolve_field(paths, keys, section_field))
    return 0


def run_set(dotted: str, raw_value: str, scope: Scope) -> int:
    """Validate and persist one setting through the service."""

    field = settings_schema.field_by_path(dotted)
    if field is None:
        raise click.UsageError(_unknown_message(dotted))
    try:
        settings_schema.parse_field_value(field, raw_value)
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    paths, keys = _locations()
    ok, message = settings_service.set_value(paths, keys, dotted, raw_value, scope)
    if not ok:
        click.echo(message, err=True)
        return 1
    click.echo(message)
    return 0


def run_unset(dotted: str, scope: Scope) -> int:
    """Remove one setting (idempotent: unsetting an absent value succeeds)."""

    if settings_schema.field_by_path(dotted) is None:
        raise click.UsageError(_unknown_message(dotted))
    paths, keys = _locations()
    ok, message = settings_service.unset_value(paths, keys, dotted, scope)
    if not ok:
        click.echo(message, err=True)
        return 1
    click.echo(message)
    return 0


__all__ = ["run_get", "run_set", "run_unset"]
