"""Flow tests \u2014 native mode shortcuts as live slash commands (bug 1).

End-to-end over DemoRuntime + Pilot: ``ModeDiscovery.get_shortcuts()``
(surfaced through ``RuntimeAdapter.native_mode_shortcuts()``) is registered
as ``mode``-sourced palette rows at boot, so ``/evaluation`` activates the
mode exactly like ``/mode evaluation`` would \u2014 and an unrecognized slash
still shows the "did you mean" notice with mode shortcuts in the mix. The
registry-level ("CLI-style") half of this proof lives in
``tests/test_commands_modes.py``; this file mirrors
``tests/test_flow_skill_aliases.py``'s TUI-path structure.
"""

from __future__ import annotations

import pytest

from amplifier_app_tui.kernel.session_ops import SkillInfo
from amplifier_app_tui.ui.app import TuiApp
from amplifier_app_tui.ui.demo_wiring import DemoRuntimeAdapter

from .test_flow_helpers import SIZE, blocks_of, seed_done, type_text, wait_for


class ModeShortcutDemoAdapter(DemoRuntimeAdapter):
    """Demo adapter that advertises a fixed shortcut -> mode-name catalog."""

    def __init__(self) -> None:
        super().__init__(instant=True)
        self.activated: list[str | None] = []
        self.shortcuts: dict[str, str] = {
            "evaluation": "evaluation",
            "audit": "amplifier-way-audit",
        }

    async def native_mode_shortcuts(self) -> dict[str, str]:
        return dict(self.shortcuts)

    async def set_native_mode(self, name: str | None) -> tuple[bool, str]:
        self.activated.append(name)
        return (True, f"mode {'off' if name is None else name}")


class CollidingModeAndSkillDemoAdapter(DemoRuntimeAdapter):
    """A mode shortcut and a discovered skill's shortcut collide by design
    (both want ``/review``) \u2014 proving boot precedence end-to-end."""

    def __init__(self) -> None:
        super().__init__(instant=True)
        self.activated: list[str | None] = []

    async def native_mode_shortcuts(self) -> dict[str, str]:
        return {"review": "code-review-mode"}

    async def list_skills(self) -> tuple[SkillInfo, ...]:
        return (SkillInfo("full-review", "a skill that also wants /review", shortcut="review"),)

    async def set_native_mode(self, name: str | None) -> tuple[bool, str]:
        self.activated.append(name)
        return (True, f"mode {'off' if name is None else name}")


def _answer_text(app: TuiApp) -> str:
    return "".join(seg.text for block in blocks_of(app, "answer") for seg in block.spans)


@pytest.mark.asyncio
async def test_mode_shortcuts_register_at_boot_and_show_in_palette() -> None:
    adapter = ModeShortcutDemoAdapter()
    app = TuiApp(adapter)
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert await wait_for(pilot, lambda: app._commands.get("/evaluation") is not None)
        assert app._commands.get("/audit") is not None
        spec = app._commands.get("/evaluation")
        assert spec is not None and spec.tag == "mode"

        await type_text(pilot, "/eval")
        assert await wait_for(pilot, lambda: app.palette.is_open)
        assert any(c.name == "/evaluation" for c in app.palette.filtered_commands)


@pytest.mark.asyncio
async def test_shortcut_activates_the_mode() -> None:
    """Acceptance criterion 1: ``/evaluation`` has the same effect as
    ``/mode evaluation`` (both drive ``ctx.set_native_mode``)."""
    adapter = ModeShortcutDemoAdapter()
    app = TuiApp(adapter)
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert await wait_for(pilot, lambda: app._commands.get("/evaluation") is not None)

        await type_text(pilot, "/evaluation")
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: adapter.activated == ["evaluation"])


@pytest.mark.asyncio
async def test_shortcut_can_map_to_a_differently_named_mode() -> None:
    adapter = ModeShortcutDemoAdapter()
    app = TuiApp(adapter)
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert await wait_for(pilot, lambda: app._commands.get("/audit") is not None)

        await type_text(pilot, "/audit")
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: adapter.activated == ["amplifier-way-audit"])


@pytest.mark.asyncio
async def test_trailing_text_does_not_prevent_activation() -> None:
    """v1 scope is activation-only: trailing text after a shortcut is
    ignored (never submitted as a prompt), but the mode still activates.

    The exact "trailing text ignored" notice text is pinned deterministically
    at the registry level
    (``test_commands_modes.py::test_trailing_text_activates_and_notices_it_was_ignored``,
    driven synchronously against a ``FakeCommandContext``). Here, over a real
    running app, the mode-activation worker's OWN completion notice (``mode
    evaluation \u00b7 native (bundle)``) fires asynchronously right after and
    deterministically supersedes it in ``notice_slot.current`` before any
    poll can observe it \u2014 so this flow test asserts only the durable,
    non-racy behavior: the mode activated despite the trailing text (never
    silently dropped, never crashed).
    """
    adapter = ModeShortcutDemoAdapter()
    app = TuiApp(adapter)
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert await wait_for(pilot, lambda: app._commands.get("/evaluation") is not None)

        await type_text(pilot, "/evaluation focus on latency")
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: adapter.activated == ["evaluation"])


@pytest.mark.asyncio
async def test_unknown_slash_still_shows_the_suggestion_notice() -> None:
    """A registered mode shortcut must not swallow an unrelated typo into
    a false match; the registry-wide unknown-command path (story #1)
    stays intact with mode shortcuts in the mix."""
    adapter = ModeShortcutDemoAdapter()
    app = TuiApp(adapter)
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert await wait_for(pilot, lambda: app._commands.get("/evaluation") is not None)

        await type_text(pilot, "/frobnicate now")
        await pilot.press("enter")
        assert await wait_for(
            pilot,
            lambda: (
                app.notice_slot.current == "unknown command: /frobnicate \u00b7 / lists commands"
            ),
        )
        assert adapter.activated == []


@pytest.mark.asyncio
async def test_native_mode_activation_refreshes_mode_shortcuts() -> None:
    """Post-composition refresh (mirrors the skill-refresh flow test): a
    live change in the shortcut catalog is picked up at the next mode
    transition, not just at boot."""
    adapter = ModeShortcutDemoAdapter()
    app = TuiApp(adapter)
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert await wait_for(pilot, lambda: app._commands.get("/evaluation") is not None)
        assert app._commands.get("/machete") is None

        adapter.shortcuts = {"machete": "occams-machete"}
        await type_text(pilot, "/mode occams-machete")
        await pilot.press("enter")
        assert await wait_for(
            pilot,
            lambda: (
                adapter.activated == ["occams-machete"]
                and app._commands.get("/machete") is not None
            ),
        )
        assert app._commands.get("/evaluation") is None  # stale shortcut reconciled away
        assert app._commands.get("/status") is not None  # built-ins never reconciled away


@pytest.mark.asyncio
async def test_mode_shortcut_beats_a_colliding_skill_registered_after_it() -> None:
    """Acceptance criterion 4, end-to-end: modes register before skills at
    boot (``ui/app.py``), so a mode shortcut wins a same-named skill
    alias, and the collision is surfaced \u2014 never a silent skip."""
    app = TuiApp(CollidingModeAndSkillDemoAdapter())
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)

        assert await wait_for(pilot, lambda: "Skill aliases" in _answer_text(app))
        text = _answer_text(app)
        assert "/review" in text
        assert "already claimed by mode" in text

        kept = app._commands.get("/review")
        assert kept is not None and kept.tag == "mode"
