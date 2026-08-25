"""Native mode shortcuts in the command registry (bug 1 of the mode-parity fix).

``/evaluation``, ``/audit``, ``/machete`` etc. must resolve exactly like any
built-in — this is the registry-level ("CLI-style") half of that proof,
mirroring ``tests/test_commands_mcp_prompts.py`` (the chosen template) and
``tests/test_commands_skills.py`` (the sibling dynamic-registration story).
The interactive TUI-path half lives in ``tests/test_flow_mode_shortcuts.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

from amplifier_app_tui.commands.builtin import build_registry
from amplifier_app_tui.commands.modes import (
    ModeCollision,
    mode_collision_spans,
    plan_mode_commands,
    register_mode_commands_reporting,
    sync_mode_commands_reporting,
)
from amplifier_app_tui.commands.registry import CommandRegistry, CommandSpec
from amplifier_app_tui.commands.skills import register_skill_commands_reporting


def _skill(name: str, description: str = "", shortcut: str = "") -> SimpleNamespace:
    return SimpleNamespace(name=name, description=description, shortcut=shortcut)


def _existing(name: str, *, tag: str = "built-in") -> CommandSpec:
    return CommandSpec(
        group="During",
        name=name,
        desc="existing",
        tag=tag,
        handler=lambda _ctx, _args: None,
    )


# --- registration ------------------------------------------------------


def test_registers_one_row_per_shortcut() -> None:
    registry = build_registry()
    plan = register_mode_commands_reporting(
        registry, {"evaluation": "evaluation", "audit": "amplifier-way-audit"}
    )
    assert {spec.name for spec in plan.specs} == {"/evaluation", "/audit"}
    assert plan.collisions == ()
    spec = registry.get("/evaluation")
    assert spec is not None and spec.tag == "mode"
    assert registry.source_of("/evaluation") == "mode"


def test_shortcut_key_and_mode_name_are_independent(fake_command_context) -> None:
    """``get_shortcuts()`` maps shortcut -> mode name; an author-chosen
    alias need not match the mode's own name."""
    registry = build_registry()
    register_mode_commands_reporting(registry, {"audit": "amplifier-way-audit"})
    assert registry.parse_and_run(fake_command_context, "/audit")
    assert fake_command_context.calls == ["set_native_mode:amplifier-way-audit"]


def test_invalid_shortcut_tokens_are_skipped() -> None:
    registry = build_registry()
    plan = plan_mode_commands(registry, {"bad shortcut": "x", "": "y", "ok": "z"})
    assert [spec.name for spec in plan.specs] == ["/ok"]


# --- dispatch (v1 scope: activation only) -------------------------------


def test_parse_and_run_activates_the_mode(fake_command_context) -> None:
    registry = build_registry()
    register_mode_commands_reporting(registry, {"evaluation": "evaluation"})
    assert registry.parse_and_run(fake_command_context, "/evaluation")
    assert fake_command_context.calls == ["set_native_mode:evaluation"]
    assert fake_command_context.notices == []  # no trailing text -> no notice
    assert fake_command_context.user_lines == ["/evaluation"]


def test_trailing_text_activates_and_notices_it_was_ignored(fake_command_context) -> None:
    registry = build_registry()
    register_mode_commands_reporting(registry, {"evaluation": "evaluation"})
    registry.parse_and_run(fake_command_context, "/evaluation focus on latency")
    assert fake_command_context.calls == ["set_native_mode:evaluation"]
    assert fake_command_context.notices == [
        "mode evaluation activated \u00b7 trailing text ignored: focus on latency"
    ]


# --- descriptions (optional duck-typed listing) -------------------------


def test_description_falls_back_without_a_listing() -> None:
    registry = build_registry()
    plan = plan_mode_commands(registry, {"evaluation": "evaluation"})
    assert plan.specs[0].desc == "activate native mode evaluation"


def test_description_enriched_from_a_dict_shaped_listing() -> None:
    """The exact shape ``kernel.runtime.RealRuntime.list_native_modes()``
    produces: a list of plain dicts."""
    registry = build_registry()
    listing = [{"name": "evaluation", "description": "Score a design against a rubric"}]
    plan = plan_mode_commands(registry, {"evaluation": "evaluation"}, listing)
    assert (
        plan.specs[0].desc
        == "activate native mode evaluation \u00b7 Score a design against a rubric"
    )


def test_description_enriched_from_an_attribute_shaped_listing() -> None:
    registry = build_registry()
    listing = [SimpleNamespace(name="evaluation", description="Score a design")]
    plan = plan_mode_commands(registry, {"evaluation": "evaluation"}, listing)
    assert "Score a design" in plan.specs[0].desc


# --- collisions (AC4-style diagnostics, mirroring skills.py/mcp_prompts.py) ---


def test_collision_with_existing_builtin_is_reported_and_builtin_wins() -> None:
    registry = build_registry()
    plan = register_mode_commands_reporting(registry, {"mode": "somemode"})
    assert plan.specs == ()
    assert plan.collisions == (ModeCollision(trigger="/mode", mode="somemode", owner="builtin"),)
    kept = registry.get("/mode")
    assert kept is not None and kept.tag == "built-in"


def test_registering_the_same_shortcut_twice_reports_a_collision_the_second_time() -> None:
    registry = build_registry()
    register_mode_commands_reporting(registry, {"evaluation": "evaluation"})
    second = register_mode_commands_reporting(registry, {"evaluation": "a-different-mode"})
    assert second.specs == ()
    assert second.collisions == (
        ModeCollision(trigger="/evaluation", mode="a-different-mode", owner="mode"),
    )
    # First registration still wins.
    assert registry.get("/evaluation") is not None


def test_plan_is_pure_and_does_not_mutate_the_registry() -> None:
    registry = build_registry()
    before = registry.names
    plan_mode_commands(registry, {"evaluation": "evaluation"})
    assert registry.names == before


def test_synthetic_existing_command_wins_and_is_reported() -> None:
    existing = _existing("/evaluation")
    registry = CommandRegistry((existing,))
    plan = register_mode_commands_reporting(registry, {"evaluation": "evaluation"})
    assert plan.specs == ()
    assert plan.collisions[0].trigger == "/evaluation"
    assert plan.collisions[0].owner == "builtin"
    assert registry.get("/evaluation") is existing


# --- precedence: modes beat skills when modes register first (AC4) -----


def test_mode_shortcut_wins_over_a_same_named_skill_registered_after() -> None:
    """Boot precedence (built-ins > modes > skills, app-cli parity): a mode
    shortcut registered first keeps the trigger when a same-named skill
    shortcut is discovered afterward."""
    registry = build_registry()
    register_mode_commands_reporting(registry, {"review": "code-review-mode"})

    skill_plan = register_skill_commands_reporting(
        registry, (_skill("full-review", "does a review", shortcut="review"),)
    )

    assert skill_plan.collisions
    assert skill_plan.collisions[0].trigger == "/review"
    assert skill_plan.collisions[0].owner == "mode"
    kept = registry.get("/review")
    assert kept is not None and kept.tag == "mode"


def test_mode_shortcut_loses_to_an_earlier_skill_registration() -> None:
    """The reverse order: whichever registers first wins — proving the
    precedence is a registration-ORDER property (enforced by ``ui/app.py``
    registering modes before skills), not something hardcoded in either
    module."""
    registry = build_registry()
    register_skill_commands_reporting(
        registry, (_skill("full-review", "does a review", shortcut="review"),)
    )

    mode_plan = register_mode_commands_reporting(registry, {"review": "code-review-mode"})

    assert mode_plan.specs == ()
    assert mode_plan.collisions[0].owner == "skill"
    kept = registry.get("/review")
    assert kept is not None and kept.tag == "skill"


# --- sync (live reconciliation, mirrors sync_skill_commands_reporting) --


def test_sync_removes_stale_and_registers_fresh_shortcuts() -> None:
    registry = build_registry()
    sync_mode_commands_reporting(registry, {"evaluation": "evaluation"})
    assert registry.get("/evaluation") is not None

    plan = sync_mode_commands_reporting(registry, {"audit": "amplifier-way-audit"})

    assert registry.get("/evaluation") is None  # stale shortcut vanished
    assert registry.get("/audit") is not None
    assert [spec.name for spec in plan.specs] == ["/audit"]
    assert registry.contributions("mode") == plan.specs


def test_sync_is_idempotent_over_unchanged_shortcuts() -> None:
    registry = build_registry()
    first = sync_mode_commands_reporting(registry, {"evaluation": "evaluation"})
    second = sync_mode_commands_reporting(registry, {"evaluation": "evaluation"})
    assert [s.name for s in first.specs] == [s.name for s in second.specs] == ["/evaluation"]


def test_sync_leaves_builtins_and_skills_untouched() -> None:
    registry = build_registry()
    register_skill_commands_reporting(registry, (_skill("keep-me", "a skill", shortcut="km"),))
    sync_mode_commands_reporting(registry, {"evaluation": "evaluation"})

    sync_mode_commands_reporting(registry, {})  # no shortcuts left at all

    assert registry.get("/evaluation") is None
    assert registry.get("/status") is not None  # built-in survives
    assert registry.get("/km") is not None  # skill survives


# --- rendering (mirrors alias_collision_spans / mcp_prompt_collision_spans) --


def test_mode_collision_spans_render_expected_text() -> None:
    collisions = (ModeCollision(trigger="/status", mode="statusmode", owner="built-in"),)
    text = "".join(seg.text for seg in mode_collision_spans(collisions))
    assert "Mode shortcuts" in text
    assert "/status" in text
    assert "wanted by mode statusmode" in text
    assert "already claimed by built-in" in text


def test_no_collisions_renders_nothing() -> None:
    assert mode_collision_spans(()) == ()
