"""The single resolver + writer behind every durable-settings surface.

Workstream 2 of the settings-UX campaign
(``docs/plans/2026-08-09-settings-ux-and-hygiene-campaign.md``). One service
feeds the scriptable ``settings get|set|unset`` trio, the redacted
``config show`` snapshot, and the WS3 settings panel, so no two surfaces can
disagree about what a setting is, where it lives, or whether it is secret.

**Resolution** mirrors :func:`kernel.config.load_merged_settings` exactly,
field by field: the most specific scope whose *projected*
(``project_tui_preferences``) view contains the read-path leaf wins,
including a ``null`` tombstone; a non-dict intermediate masks the whole
subtree from less-specific scopes; a leaf the runtime resolvers would ignore
(wrong type, out of range, non-canonical choice) resolves to the schema
default with source ``default``. Keys.env-backed fields resolve
environment → ``keys.env`` → unset, because ``load_keys_env`` sources the
file without overriding an already-set environment variable.

**Writes** stay atomic and canonical: scope files go through
``bundle_admin.write_scope`` (tmp → replace, empty dict unlinks), app-owned
keys land in their namespaced ``tui:`` location, secrets only ever go to
``keys.env`` via ``setup.write_key`` / ``setup.remove_key``. Every write is
appended to ``<home>/settings-changes.jsonl`` with the value pre-redacted —
the log exists so the WS3 panel can answer "what changed?" without ever
risking a secret on disk.

Nothing here raises into a caller: public entry points return
``(ok, message)`` like ``config_ops.save_config``, and the change log is
strictly best-effort.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ..model.settings_schema import (
    SettingsField,
    field_by_path,
    fields_in_section,
    parse_field_value,
    render_value,
)
from . import bundle_admin, routing_admin, setup
from .bundle_admin import Scope, read_scope, scope_file, write_scope
from .config import SettingsPaths, project_tui_preferences

SettingSource = Literal["env", "keys.env", "local", "project", "global", "default"]
"""Where an effective value came from, most authoritative first."""

_SCOPE_PRECEDENCE: tuple[Scope, ...] = ("local", "project", "global")
"""Read precedence, most specific first (mirror-reversed merge order)."""


@dataclass(frozen=True)
class EffectiveSetting:
    """One resolved setting: value, provenance, and a redacted display form."""

    field: SettingsField
    value: Any
    present: bool
    """True when explicitly configured; False when the schema default is in use."""
    source: SettingSource
    source_file: Path | None
    display: str
    """``render_value`` output — a secret's value never appears here."""


# ---------------------------------------------------------------------------
# Reads — merge-mirroring resolution
# ---------------------------------------------------------------------------


def _dig(data: dict[str, Any], path: tuple[str, ...]) -> tuple[str, Any]:
    """Walk *path*: ``("found", value)`` / ``("absent", None)`` / ``("masked", None)``.

    "masked" means an intermediate node exists but is not a dict — under
    deep-merge semantics that node replaces the whole subtree from
    less-specific scopes, so the leaf is unreachable everywhere below.
    """
    node: Any = data
    for key in path[:-1]:
        if not isinstance(node, dict) or key not in node:
            return ("absent", None)
        node = node[key]
        if not isinstance(node, dict):
            return ("masked", None)
    if isinstance(node, dict) and path[-1] in node:
        return ("found", node[path[-1]])
    return ("absent", None)


def _coerce(field: SettingsField, value: Any) -> tuple[bool, Any]:
    """Validate a stored value the way the runtime resolvers tolerate it.

    The runtime reads exact shapes (``active_matrix`` wants a non-empty str,
    ``permissions`` wants a canonical choice, bools must be real bools) and
    falls back to defaults on anything else; coercion mirrors that so a junk
    value is reported as "default", not as a surprising effective setting.
    """
    if field.kind == "bool":
        return (isinstance(value, bool), value)
    if field.kind == "int":
        ok = isinstance(value, int) and not isinstance(value, bool)
        if ok and field.minimum_exclusive is not None and value <= field.minimum_exclusive:
            ok = False
        return (ok, value)
    if field.kind == "float":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        if ok and field.minimum_exclusive is not None and float(value) <= field.minimum_exclusive:
            ok = False
        if ok and field.maximum_inclusive is not None and float(value) > field.maximum_inclusive:
            ok = False
        return (ok, float(value) if ok else value)
    if field.kind == "choice":
        # Exact canonical match, mirroring the runtime's raw == "guarded" reads.
        return (isinstance(value, str) and value in field.choices, value)
    if field.kind == "list":
        if isinstance(value, list):
            return (True, [str(item) for item in value if item])
        return (False, value)
    return (isinstance(value, str) and bool(value.strip()), value)


def _resolved_default(field: SettingsField) -> EffectiveSetting:
    return EffectiveSetting(
        field=field,
        value=field.default,
        present=False,
        source="default",
        source_file=None,
        display=render_value(field, field.default, False),
    )


def _resolve_file(paths: SettingsPaths, field: SettingsField) -> EffectiveSetting:
    for scope in _SCOPE_PRECEDENCE:
        file = scope_file(paths, scope)
        data = read_scope(file)
        if not data:
            continue
        status, raw = _dig(project_tui_preferences(data), field.read_path)
        if status == "absent":
            continue
        if status == "found":
            ok, value = _coerce(field, raw)
            if ok:
                return EffectiveSetting(
                    field=field,
                    value=value,
                    present=True,
                    source=scope,
                    source_file=file,
                    display=render_value(field, value, True),
                )
        # Masked subtree or a junk leaf: merged resolution yields the default.
        break
    return _resolved_default(field)


def _resolve_keys(
    keys_path: Path, field: SettingsField, environ: Mapping[str, str]
) -> EffectiveSetting:
    raw_env = environ.get(field.env_var)
    if raw_env is not None and raw_env.strip():
        value = raw_env.strip()
        return EffectiveSetting(
            field=field,
            value=value,
            present=True,
            source="env",
            source_file=None,
            display=render_value(field, value, True),
        )
    stored = setup.read_keys(keys_path).get(field.env_var)
    if stored is not None and stored.strip():
        value = stored.strip()
        return EffectiveSetting(
            field=field,
            value=value,
            present=True,
            source="keys.env",
            source_file=keys_path,
            display=render_value(field, value, True),
        )
    return _resolved_default(field)


def resolve_field(
    paths: SettingsPaths,
    keys_path: Path,
    field: SettingsField,
    *,
    environ: Mapping[str, str] | None = None,
) -> EffectiveSetting:
    """Resolve one field with full provenance (``environ`` injectable for tests)."""
    if field.keys_env:
        return _resolve_keys(keys_path, field, os.environ if environ is None else environ)
    return _resolve_file(paths, field)


def resolve_path(
    paths: SettingsPaths,
    keys_path: Path,
    dotted: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> EffectiveSetting | None:
    """Resolve one schema path; ``None`` when *dotted* is not a known setting."""
    field = field_by_path(dotted)
    if field is None:
        return None
    return resolve_field(paths, keys_path, field, environ=environ)


def resolve_section(
    paths: SettingsPaths,
    keys_path: Path,
    section_id: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[EffectiveSetting, ...]:
    """Every field in one section, resolved in registry order."""
    return tuple(
        resolve_field(paths, keys_path, field, environ=environ)
        for field in fields_in_section(section_id)
    )


# ---------------------------------------------------------------------------
# Change log — redacted JSONL, strictly best-effort
# ---------------------------------------------------------------------------


def _change_log_path(home: Path) -> Path:
    return home / "settings-changes.jsonl"


def _record_change(
    home: Path,
    op: Literal["set", "unset"],
    field: SettingsField,
    *,
    scope: str,
    file: Path,
    value: Any,
) -> None:
    """Append one redacted change record; logging must never fail a write."""
    try:
        home.mkdir(parents=True, exist_ok=True)
        record = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "op": op,
            "path": field.path,
            "scope": scope,
            "value": render_value(field, value, value is not None),
            "file": str(file),
        }
        with _change_log_path(home).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:  # noqa: BLE001
        pass


def recent_changes(home: Path, limit: int = 20) -> list[dict[str, Any]]:
    """The newest *limit* change records (oldest-first); ``[]`` when absent."""
    try:
        lines = _change_log_path(home).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


# ---------------------------------------------------------------------------
# Writes — atomic scope updates; secrets to keys.env only
# ---------------------------------------------------------------------------


def _set_nested(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = data
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[path[-1]] = value


def _remove_nested(data: dict[str, Any], path: tuple[str, ...]) -> bool:
    """Remove the leaf at *path*, pruning containers left empty. Returns existed."""
    stack: list[tuple[dict[str, Any], str]] = []
    node = data
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            return False
        stack.append((node, key))
        node = child
    if path[-1] not in node:
        return False
    del node[path[-1]]
    for parent, key in reversed(stack):
        child = parent[key]
        if isinstance(child, dict) and not child:
            del parent[key]
        else:
            break
    return True


def set_value(
    paths: SettingsPaths,
    keys_path: Path,
    dotted: str,
    raw_value: str,
    scope: Scope,
) -> tuple[bool, str]:
    """Validate and persist one setting; ``(ok, message)``, never raises.

    The message redacts secrets. ``scope`` is ignored for keys.env-backed
    fields (credentials and the ntfy topic live outside the scope files).
    """
    field = field_by_path(dotted)
    if field is None:
        return (False, f"unknown setting '{dotted}' — run `settings get` to list known settings")
    try:
        value = parse_field_value(field, raw_value)
    except ValueError as error:
        return (False, str(error))
    home = keys_path.parent

    if field.keys_env:
        try:
            setup.write_key(keys_path, field.env_var, str(value))
        except Exception as error:  # noqa: BLE001
            return (False, f"could not write {keys_path}: {error}")
        _record_change(home, "set", field, scope="keys.env", file=keys_path, value=value)
        if field.secret:
            return (True, f"✓ {field.path} configured · {keys_path} (value not shown)")
        return (True, f"✓ Set {field.path} = {render_value(field, value, True)} · {keys_path}")

    try:
        if field.special_writer == "active_bundle":
            target = bundle_admin.set_active_bundle(paths, str(value), scope)
        elif field.special_writer == "routing_matrix":
            target = routing_admin.set_active_matrix(paths, str(value), scope)
        else:
            target = scope_file(paths, scope)
            data = read_scope(target)
            _set_nested(data, field.write_path, value)
            write_scope(target, data)
    except Exception as error:  # noqa: BLE001
        return (False, f"could not write {field.path} to the {scope} scope: {error}")
    _record_change(home, "set", field, scope=scope, file=target, value=value)
    return (
        True,
        f"✓ Set {field.path} = {render_value(field, value, True)} ({scope} · {target})",
    )


def unset_value(
    paths: SettingsPaths,
    keys_path: Path,
    dotted: str,
    scope: Scope,
) -> tuple[bool, str]:
    """Remove one setting from *scope* (or keys.env); ``(ok, message)``.

    Unsetting a value that was never set is an idempotent no-op, reported
    with ``ok=True`` so scripts can rely on the end state.
    """
    field = field_by_path(dotted)
    if field is None:
        return (False, f"unknown setting '{dotted}' — run `settings get` to list known settings")
    home = keys_path.parent

    if field.keys_env:
        try:
            removed = setup.remove_key(keys_path, field.env_var)
        except Exception as error:  # noqa: BLE001
            return (False, f"could not update {keys_path}: {error}")
        if not removed:
            return (True, f"{field.path} was not set in {keys_path} — nothing to do")
        _record_change(home, "unset", field, scope="keys.env", file=keys_path, value=None)
        return (True, f"✓ Removed {field.path} from {keys_path}")

    if field.special_writer == "active_bundle":
        try:
            cleared = bundle_admin.clear_active_bundle(paths, scope)
        except Exception as error:  # noqa: BLE001
            return (False, f"could not update the {scope} scope: {error}")
        if not cleared:
            return (True, f"{field.path} was not set in the {scope} scope — nothing to do")
        _record_change(home, "unset", field, scope=scope, file=scope_file(paths, scope), value=None)
        return (True, f"✓ Cleared {field.path} ({scope} · {scope_file(paths, scope)})")

    target = scope_file(paths, scope)
    try:
        data = read_scope(target)
        removed = _remove_nested(data, field.write_path)
        if removed:
            write_scope(target, data)
    except Exception as error:  # noqa: BLE001
        return (False, f"could not update {target}: {error}")
    if not removed:
        return (True, f"{field.path} was not set in the {scope} scope — nothing to do")
    _record_change(home, "unset", field, scope=scope, file=target, value=None)
    return (True, f"✓ Unset {field.path} ({scope} · {target})")


__all__ = [
    "EffectiveSetting",
    "SettingSource",
    "recent_changes",
    "resolve_field",
    "resolve_path",
    "resolve_section",
    "set_value",
    "unset_value",
]
