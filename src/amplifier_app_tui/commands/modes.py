"""Native mode shortcuts as live slash commands (bug 1 of the mode-parity fix).

``hooks-mode``'s ``ModeDiscovery.get_shortcuts()`` maps a mode's optional
``shortcut:`` frontmatter (e.g. ``evaluation``) to its mode name — the SAME
source app-cli's ``CommandProcessor`` builds ``MODE_SHORTCUTS`` from.
Registering each shortcut as a ``mode``-sourced command row here is what
makes ``/evaluation`` dispatch like any built-in, rather than falling
through to the unknown-command notice. ``/mode <name>`` (the built-in,
``commands/builtin.py::_cmd_mode``) remains the free-form, full-name
activation path for every mode, shortcut or not — this module only adds
the SHORTCUT as an additional trigger.

Layering (ADR-0007, ``tests/test_layering_contract.py``): this package
imports nothing above ``model/`` — shortcuts arrive as a plain
``Mapping[str, str]`` (shortcut -> mode name), never a ``kernel/`` type.
An optional duck-typed *listing* sequence (each item exposing ``name`` /
``description`` either as attributes or mapping keys — the shape
``kernel.runtime.RealRuntime.list_native_modes()`` produces) lets a caller
enrich the palette description; omitting it is fine; dispatch never
depends on it.

v1 scope is activation only (mirrors plain ``/mode <name>``): a shortcut
invoked with trailing text activates the mode and notices that the
trailing text was ignored, rather than inventing a new
``CommandContext`` method to submit a generated prompt (out of scope —
see the zen-architect spec this module was built from).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from pydantic import ValidationError

from ..model.blocks import Segment
from .registry import CommandContext, CommandRegistry, CommandSpec


class ModeCollision(NamedTuple):
    """One ``/<shortcut>`` trigger a native mode wanted but couldn't have.

    The registry's own collision policy (first registration wins) already
    decided the OUTCOME — this just names it instead of a silent skip
    (mirrors :class:`~.skills.AliasCollision` / :class:`~.mcp_prompts.MCPPromptCollision`).
    """

    trigger: str
    """The slash trigger that collided, e.g. ``/evaluation``."""
    mode: str
    """The mode name that wanted *trigger* and did not get it."""
    owner: str
    """Who already holds *trigger*: ``built-in``, ``skill``, ``mode:<name>``, ..."""


class ModePlan(NamedTuple):
    """What :func:`plan_mode_commands` would register, plus any collisions."""

    specs: tuple[CommandSpec, ...]
    collisions: tuple[ModeCollision, ...]


def _activate_handler(mode_name: str) -> Any:
    def handler(ctx: CommandContext, args: str) -> None:
        ctx.set_native_mode(mode_name)
        rest = args.strip()
        if rest:
            ctx.show_notice(f"mode {mode_name} activated \u00b7 trailing text ignored: {rest}")

    return handler


def _entry_field(entry: Any, field: str) -> str:
    """Read *field* off a duck-typed listing entry: a ``Mapping`` (the
    ``list_native_modes()`` dict shape) or a plain attribute-bearing
    object — whichever the caller happened to pass."""
    if isinstance(entry, Mapping):
        return str(entry.get(field, "") or "")
    return str(getattr(entry, field, "") or "")


def _description_for(mode_name: str, listing: Sequence[Any]) -> str:
    for entry in listing:
        if _entry_field(entry, "name") != mode_name:
            continue
        desc = " ".join(_entry_field(entry, "description").split())
        return (
            f"activate native mode {mode_name} \u00b7 {desc}"
            if desc
            else f"activate native mode {mode_name}"
        )
    return f"activate native mode {mode_name}"


def _spec(trigger: str, mode_name: str, listing: Sequence[Any]) -> CommandSpec | None:
    try:
        return CommandSpec(
            group="During",
            name=f"/{trigger}",
            desc=_description_for(mode_name, listing),
            tag="mode",
            handler=_activate_handler(mode_name),
        )
    except ValidationError:
        return None  # not a valid slash trigger — nothing to collide with


def plan_mode_commands(
    registry: CommandRegistry,
    shortcuts: Mapping[str, str],
    listing: Sequence[Any] = (),
) -> ModePlan:
    """Plan ``/<shortcut>`` rows for *shortcuts* (shortcut -> mode name);
    existing commands win (built-ins, skills, or an earlier shortcut in
    this same pass — first registration wins, unchanged registry policy)."""

    owner = {name: registry.source_of(name) or "registered" for name in registry.names}
    specs: list[CommandSpec] = []
    collisions: list[ModeCollision] = []
    for shortcut, mode_name in shortcuts.items():
        spec = _spec(shortcut, mode_name, listing)
        if spec is None:
            continue
        if spec.name in owner:
            collisions.append(ModeCollision(spec.name, mode_name, owner[spec.name]))
            continue
        specs.append(spec)
        owner[spec.name] = f"mode:{mode_name}"
    return ModePlan(tuple(specs), tuple(collisions))


def register_mode_commands_reporting(
    registry: CommandRegistry,
    shortcuts: Mapping[str, str],
    listing: Sequence[Any] = (),
) -> ModePlan:
    """Register *shortcuts* into *registry*; returns both the specs
    actually added AND any collisions found (mirrors
    :func:`~.skills.register_skill_commands_reporting`)."""

    plan = plan_mode_commands(registry, shortcuts, listing)
    added = tuple(spec for spec in plan.specs if registry.register(spec, source="mode"))
    return ModePlan(added, plan.collisions)


def sync_mode_commands_reporting(
    registry: CommandRegistry,
    shortcuts: Mapping[str, str],
    listing: Sequence[Any] = (),
) -> ModePlan:
    """Replace only ``mode``-contributed commands with the live shortcut
    catalog (mirrors :func:`~.mcp_prompts.sync_mcp_prompt_commands_reporting`):
    stale shortcuts vanish and newly available ones become callable."""

    for spec in registry.contributions("mode"):
        registry.unregister(spec.name)
    return register_mode_commands_reporting(registry, shortcuts, listing)


def mode_collision_spans(collisions: Sequence[ModeCollision]) -> tuple[Segment, ...]:
    """A rich diagnostic listing for mode-shortcut collisions — one row per
    trigger a mode wanted but couldn't claim (mirrors
    :func:`~.skills.alias_collision_spans`)."""
    if not collisions:
        return ()
    count = len(collisions)
    noun = "collision" if count == 1 else "collisions"
    spans: list[Segment] = [
        Segment(text="\u00b7 ", style_token="blue"),
        Segment(text="Mode shortcuts", style_token="bright", bold=True),
        Segment(text=f"  {count} {noun} \u00b7 first registration wins\n", style_token="dim"),
    ]
    width = max(len(item.trigger) for item in collisions)
    for item in collisions:
        spans.append(Segment(text=f"  {item.trigger.ljust(width)}  ", style_token="orange"))
        spans.append(
            Segment(
                text=f"wanted by mode {item.mode} \u00b7 already claimed by {item.owner}\n",
                style_token="dim",
            )
        )
    return tuple(spans)


__all__ = [
    "ModeCollision",
    "ModePlan",
    "mode_collision_spans",
    "plan_mode_commands",
    "register_mode_commands_reporting",
    "sync_mode_commands_reporting",
]
