"""The durable-settings registry every settings surface is rendered from.

This is the Workstream-2 domain model of the settings-UX campaign
(``docs/plans/2026-08-09-settings-ux-and-hygiene-campaign.md``): a pure,
Textual-free, amplifier-free description of each setting the app owns — its
display path, where it is read from in *projected* settings
(``kernel.config.project_tui_preferences`` semantics), where it is
canonically written in a raw scope file, its value kind and validation
bounds, its default, and whether it is a secret that must never be echoed.

The kernel service (:mod:`amplifier_app_tui.kernel.settings_service`) turns
these records into effective resolutions and durable writes; the
``settings get|set|unset`` CLI trio and the WS3 panel only ever see this
schema plus that service. Adding a setting means adding one
:class:`SettingsField` here — no CLI or panel code changes.

Two defaults are mirrored as literals from the kernel layer (which ``model/``
must not import — ADR-0007 layering): the default bundle name ``tui``
(``kernel.config.DEFAULT_BUNDLE``) and the default routing matrix
``balanced`` (``kernel.routing_admin.DEFAULT_MATRIX``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .config import parse_value

SettingKind = Literal["bool", "int", "float", "str", "list", "choice", "secret"]
"""Value shapes the surfaces know how to parse, render, and validate."""

AppliesWhen = Literal["now", "this-session", "next-session", "restart"]
"""When a written value takes effect. WS2 ships no live-applied fields:
every field is ``next-session`` so no surface may claim otherwise."""

SpecialWriter = Literal["", "active_bundle", "routing_matrix"]
"""Fields whose write path is owned by an existing kernel admin module."""


@dataclass(frozen=True)
class SettingsSection:
    """One sidebar section of the settings surface (panel + CLI share it)."""

    id: str
    title: str
    summary: str


SECTIONS: tuple[SettingsSection, ...] = (
    SettingsSection(
        "providers",
        "Providers",
        "API credentials providers read at boot (stored in keys.env, never echoed)",
    ),
    SettingsSection(
        "models-routing", "Models & routing", "Opt-in model routing and the active matrix"
    ),
    SettingsSection(
        "bundles", "Bundles", "Active bundle, always-on overlays, and deferred overlays"
    ),
    SettingsSection(
        "directory-access",
        "Directory access",
        "Write boundary and approval-governance posture",
    ),
    SettingsSection(
        "notifications", "Notifications", "Bell/desktop ceiling and off-machine ntfy push"
    ),
    SettingsSection(
        "behavior", "Behavior", "Context window, hooks, pricing, resume, and preflight"
    ),
)
"""Section display order, shared by the control center, CLI, and WS3 panel."""


@dataclass(frozen=True)
class SettingsField:
    """One durable setting: schema data only, never behavior.

    ``read_path`` locates the value in one scope's *projected* view (the
    kernel's per-scope ``project_tui_preferences`` output), so canonical
    ``tui:`` values and their legacy top-level fallbacks resolve through a
    single path. ``write_path`` is where a raw scope file is updated — the
    canonical namespaced location for app-owned keys. Keys.env-backed fields
    have an empty ``write_path`` and persist through ``kernel.setup`` instead.
    """

    path: str
    section: str
    kind: SettingKind
    read_path: tuple[str, ...]
    help: str
    write_path: tuple[str, ...] = ()
    default: Any = None
    env_var: str = ""
    keys_env: bool = False
    secret: bool = False
    choices: tuple[str, ...] = ()
    minimum_exclusive: float | None = None
    maximum_inclusive: float | None = None
    special_writer: SpecialWriter = ""
    applies: AppliesWhen = "next-session"


FIELDS: tuple[SettingsField, ...] = (
    # -- providers (keys.env-backed; never in a settings scope) -------------
    SettingsField(
        "providers.anthropic.api_key",
        "providers",
        "secret",
        (),
        "Anthropic API key",
        env_var="ANTHROPIC_API_KEY",
        keys_env=True,
        secret=True,
    ),
    SettingsField(
        "providers.openai.api_key",
        "providers",
        "secret",
        (),
        "OpenAI API key",
        env_var="OPENAI_API_KEY",
        keys_env=True,
        secret=True,
    ),
    SettingsField(
        "providers.azure-openai.api_key",
        "providers",
        "secret",
        (),
        "Azure OpenAI API key",
        env_var="AZURE_OPENAI_API_KEY",
        keys_env=True,
        secret=True,
    ),
    SettingsField(
        "providers.azure-openai.endpoint",
        "providers",
        "str",
        (),
        "Azure OpenAI endpoint URL",
        env_var="AZURE_OPENAI_ENDPOINT",
        keys_env=True,
    ),
    SettingsField(
        "providers.gemini.api_key",
        "providers",
        "secret",
        (),
        "Gemini API key",
        env_var="GEMINI_API_KEY",
        keys_env=True,
        secret=True,
    ),
    SettingsField(
        "providers.google.api_key",
        "providers",
        "secret",
        (),
        "Google API key (Gemini alias)",
        env_var="GOOGLE_API_KEY",
        keys_env=True,
        secret=True,
    ),
    SettingsField(
        "providers.github-copilot.token",
        "providers",
        "secret",
        (),
        "GitHub token for Copilot provider",
        env_var="GITHUB_TOKEN",
        keys_env=True,
        secret=True,
    ),
    # -- models & routing ----------------------------------------------------
    SettingsField(
        "routing.matrix",
        "models-routing",
        "str",
        ("routing", "matrix"),
        "Routing matrix name (naming one opts into routing)",
        write_path=("routing", "matrix"),
        default="balanced",  # kernel.routing_admin.DEFAULT_MATRIX (layering-exempt mirror)
        special_writer="routing_matrix",
    ),
    SettingsField(
        "routing.enabled",
        "models-routing",
        "bool",
        ("routing", "enabled"),
        "Explicit routing switch; unset means a named matrix opts in",
        write_path=("routing", "enabled"),
    ),
    # -- bundles --------------------------------------------------------------
    SettingsField(
        "tui.bundle.active",
        "bundles",
        "str",
        ("bundle", "active"),
        "Active bundle name (legacy bundle.active falls back)",
        write_path=("tui", "bundle", "active"),
        default="tui",  # kernel.config.DEFAULT_BUNDLE (layering-exempt mirror)
        special_writer="active_bundle",
    ),
    SettingsField(
        "bundle.app",
        "bundles",
        "list",
        ("bundle", "app"),
        "Overlay bundle URIs composed onto every session",
        write_path=("bundle", "app"),
    ),
    SettingsField(
        "tui.bundle.deferred",
        "bundles",
        "list",
        ("bundle", "deferred"),
        "Overlays held back from boot, loaded in-session on demand",
        write_path=("tui", "bundle", "deferred"),
    ),
    # -- directory access ------------------------------------------------------
    SettingsField(
        "tui.permissions.write_boundary",
        "directory-access",
        "choice",
        ("permissions", "write_boundary"),
        "open allows project-tree writes; guarded asks first",
        write_path=("tui", "permissions", "write_boundary"),
        default="open",
        choices=("open", "guarded"),
    ),
    SettingsField(
        "tui.permissions.governance",
        "directory-access",
        "choice",
        ("permissions", "governance"),
        "gated parks risky actions for approval in the default posture",
        write_path=("tui", "permissions", "governance"),
        default="open",
        choices=("open", "gated"),
    ),
    # -- notifications ----------------------------------------------------------
    SettingsField(
        "notifications.suppress",
        "notifications",
        "bool",
        ("config", "notifications", "suppress"),
        "Silence bell + desktop delivery and remove the ntfy push hook",
        write_path=("config", "notifications", "suppress"),
    ),
    SettingsField(
        "notifications.desktop.enabled",
        "notifications",
        "bool",
        ("config", "notifications", "desktop", "enabled"),
        "Desktop rung: false=off, true=force on any terminal",
        write_path=("config", "notifications", "desktop", "enabled"),
    ),
    SettingsField(
        "notifications.push.enabled",
        "notifications",
        "bool",
        ("config", "notifications", "push", "enabled"),
        "ntfy push on/off",
        write_path=("config", "notifications", "push", "enabled"),
    ),
    SettingsField(
        "notifications.push.server",
        "notifications",
        "str",
        ("config", "notifications", "push", "server"),
        "ntfy server URL",
        write_path=("config", "notifications", "push", "server"),
    ),
    SettingsField(
        "notifications.push.priority",
        "notifications",
        "choice",
        ("config", "notifications", "push", "priority"),
        "ntfy delivery priority",
        write_path=("config", "notifications", "push", "priority"),
        choices=("min", "low", "default", "high", "urgent"),
    ),
    SettingsField(
        "notifications.push.tags",
        "notifications",
        "list",
        ("config", "notifications", "push", "tags"),
        "ntfy emoji tags (comma-separated)",
        write_path=("config", "notifications", "push", "tags"),
    ),
    SettingsField(
        "notifications.push.topic",
        "notifications",
        "secret",
        (),
        "ntfy topic — a secret, stored in keys.env (never a settings file)",
        env_var="AMPLIFIER_NTFY_TOPIC",
        keys_env=True,
        secret=True,
    ),
    # -- behavior ----------------------------------------------------------------
    SettingsField(
        "context.max_tokens",
        "behavior",
        "int",
        ("context", "max_tokens"),
        "Context window cap for the session's context module",
        write_path=("context", "max_tokens"),
        minimum_exclusive=0,
    ),
    SettingsField(
        "context.compact_threshold",
        "behavior",
        "float",
        ("context", "compact_threshold"),
        "Fraction of the window that triggers compaction (0–1]",
        write_path=("context", "compact_threshold"),
        minimum_exclusive=0,
        maximum_inclusive=1,
    ),
    SettingsField(
        "context.auto_compact",
        "behavior",
        "bool",
        ("context", "auto_compact"),
        "Compact automatically at the threshold; unset keeps module defaults",
        write_path=("context", "auto_compact"),
    ),
    SettingsField(
        "tui.hooks.suppress",
        "behavior",
        "list",
        ("hooks", "suppress"),
        "Hook module ids to leave unmounted at boot",
        write_path=("tui", "hooks", "suppress"),
    ),
    SettingsField(
        "tui.pricing.live",
        "behavior",
        "bool",
        ("pricing", "live"),
        "Fetch live model pricing; false keeps the packaged fallback table",
        write_path=("tui", "pricing", "live"),
        default=True,
    ),
    SettingsField(
        "tui.resume.use_active_bundle",
        "behavior",
        "bool",
        ("resume", "use_active_bundle"),
        "Resume sessions on the currently active bundle, not the recorded one",
        write_path=("tui", "resume", "use_active_bundle"),
        default=False,
    ),
    SettingsField(
        "tui.preflight.verify_provider",
        "behavior",
        "bool",
        ("preflight", "verify_provider"),
        "Validate provider configuration before session boot",
        write_path=("tui", "preflight", "verify_provider"),
        default=True,
    ),
    SettingsField(
        "tui.preflight.verify_live",
        "behavior",
        "bool",
        ("preflight", "verify_live"),
        "Also run the networked models-list check during preflight",
        write_path=("tui", "preflight", "verify_live"),
        default=False,
    ),
)
"""Every durable setting, in display order within sections (registry order)."""


_FIELDS_BY_PATH = {field.path: field for field in FIELDS}
_SECTIONS_BY_ID = {section.id: section for section in SECTIONS}

_TRUE_STRINGS = frozenset({"true", "1", "yes", "on"})
_FALSE_STRINGS = frozenset({"false", "0", "no", "off"})


def field_by_path(path: str) -> SettingsField | None:
    """The field registered under *path*, or ``None`` for unknown paths."""
    return _FIELDS_BY_PATH.get(path)


def section_by_id(section_id: str) -> SettingsSection | None:
    return _SECTIONS_BY_ID.get(section_id)


def fields_in_section(section_id: str) -> tuple[SettingsField, ...]:
    """The section's fields in registry order (``()`` for unknown sections)."""
    return tuple(field for field in FIELDS if field.section == section_id)


def parse_field_value(field: SettingsField, raw: str) -> Any:
    """Parse and validate a raw CLI/form string for *field*.

    Raises :class:`ValueError` with a plain-language message the CLI can show
    verbatim. Secrets pass through unvalidated beyond non-emptiness — the
    writer never echoes them back for confirmation either way.
    """
    if field.kind == "secret":
        value = raw.strip()
        if not value:
            raise ValueError(
                f"{field.path} needs a value — use `settings unset {field.path}` "
                "to remove the stored key"
            )
        return value
    if field.kind == "bool":
        lowered = raw.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
        raise ValueError(
            f"expected true or false for {field.path} (also yes/no, on/off, 1/0) — got {raw!r}"
        )
    if field.kind == "list":
        return [item.strip() for item in raw.split(",") if item.strip()]
    if field.kind == "choice":
        lowered = raw.strip().lower()
        for choice in field.choices:
            if lowered == choice:
                return choice
        options = ", ".join(field.choices)
        raise ValueError(f"expected one of {options} for {field.path} — got {raw!r}")
    if field.kind == "str":
        value = raw.strip()
        if not value:
            raise ValueError(
                f"{field.path} needs a value — use `settings unset {field.path}` to clear it"
            )
        return value
    parsed = parse_value(raw)
    if isinstance(parsed, bool) or not isinstance(parsed, (int, float)):
        expected = "a whole number" if field.kind == "int" else "a number"
        raise ValueError(f"expected {expected} for {field.path} — got {raw!r}")
    if field.kind == "int" and not isinstance(parsed, int):
        raise ValueError(f"expected a whole number for {field.path} — got {raw!r}")
    numeric: int | float
    if field.kind == "int" and isinstance(parsed, int):
        numeric = parsed
    else:  # float: whole numbers are fine (3 → 3.0)
        numeric = float(parsed)
    if field.minimum_exclusive is not None and numeric <= field.minimum_exclusive:
        raise ValueError(
            f"{field.path} must be greater than {field.minimum_exclusive:g} — got {numeric:g}"
        )
    if field.maximum_inclusive is not None and numeric > field.maximum_inclusive:
        raise ValueError(
            f"{field.path} must be at most {field.maximum_inclusive:g} — got {numeric:g}"
        )
    return numeric


def render_value(field: SettingsField, value: Any, present: bool) -> str:
    """Human-facing rendering of one value, with secrets always redacted.

    ``present`` distinguishes an explicitly configured value from a default;
    for secrets it is the difference between ``configured`` and ``not set``
    — the stored value itself never leaves this function.
    """
    if field.secret:
        return "configured" if present else "not set"
    if value is None:
        return "unset"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "(empty)"
    return str(value)


class _Unset:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: cover - debug aid
        return "<unset>"


_UNSET = _Unset()


@dataclass(frozen=True)
class SettingChange:
    """One entry of a settings diff review, values pre-rendered and redacted."""

    path: str
    action: Literal["added", "changed", "removed"]
    old: str = ""
    new: str = ""


def _render_side(field: SettingsField | None, value: Any) -> str:
    if value is _UNSET:
        return "" if field is None else render_value(field, None, present=False)
    if field is None:
        return str(value)
    return render_value(field, value, present=True)


def diff_settings(old: dict[str, Any], new: dict[str, Any]) -> tuple[SettingChange, ...]:
    """Diff two ``{field path: value}`` mappings, schema-ordered and redacted.

    Known fields appear in registry order and render through their schema
    (secrets never expose a value); unknown paths sort to the end and render
    plainly. This is the data behind the WS3 diff-before-save review.
    """
    known = [field.path for field in FIELDS if field.path in old or field.path in new]
    extras = sorted(path for path in (*old, *new) if field_by_path(path) is None)
    changes: list[SettingChange] = []
    for path in (*known, *extras):
        before = old.get(path, _UNSET)
        after = new.get(path, _UNSET)
        if before is not _UNSET and after is not _UNSET and before == after:
            continue
        field = field_by_path(path)
        if before is _UNSET:
            action: Literal["added", "changed", "removed"] = "added"
        elif after is _UNSET:
            action = "removed"
        else:
            action = "changed"
        changes.append(
            SettingChange(
                path=path,
                action=action,
                old=_render_side(field, before),
                new=_render_side(field, after),
            )
        )
    return tuple(changes)


__all__ = [
    "FIELDS",
    "SECTIONS",
    "AppliesWhen",
    "SettingChange",
    "SettingKind",
    "SettingsField",
    "SettingsSection",
    "SpecialWriter",
    "diff_settings",
    "field_by_path",
    "fields_in_section",
    "parse_field_value",
    "render_value",
    "section_by_id",
]
