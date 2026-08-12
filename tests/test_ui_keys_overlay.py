"""Tests for ui/keys_overlay.py -- the f1 which-key overlay (read-only,
rendered from the keymap table itself)."""

from __future__ import annotations

import inspect
import re

import pytest
from rich.console import Console
from textual.app import App, ComposeResult

from amplifier_app_tui.ui import keys_overlay
from amplifier_app_tui.ui.keys_overlay import KeysOverlay
from amplifier_app_tui.ui.themes import DEFAULT_THEME, register_themes, theme_id

SIZE = (120, 50)


class KeysHost(App[None]):
    """Minimal host app: registers spec themes, records overlay messages."""

    def __init__(self) -> None:
        super().__init__()
        register_themes(self)
        self.theme = theme_id(DEFAULT_THEME)
        self.closed = 0

    def compose(self) -> ComposeResult:
        yield KeysOverlay(id="keys-overlay")

    def on_keys_overlay_closed(self, message: KeysOverlay.Closed) -> None:
        self.closed += 1


def _plain(overlay: KeysOverlay, width: int = 110) -> str:
    console = Console(width=width)
    return "".join(segment.text for segment in console.render(overlay.content))


@pytest.mark.asyncio
async def test_show_opens_with_the_anytime_table() -> None:
    app = KeysHost()
    async with app.run_test(size=SIZE) as pilot:
        overlay = app.query_one(KeysOverlay)
        assert not overlay.is_open
        overlay.show("idle")
        await pilot.pause()
        assert overlay.is_open
        assert overlay.context == "idle"
        plain = _plain(overlay)
        assert "Keys" in plain
        assert "ctrl+j" in plain
        # Rich's final ellipsis point differs by one cell between macOS and
        # Linux, but the visible semantic label must survive on both.
        assert "add a newline without" in plain
        assert "f1 keys" in plain, "the overlay teaches its own toggle"
        assert "idle:" not in plain, "idle has no context hint line (empty table entry)"


@pytest.mark.asyncio
async def test_context_line_follows_the_footer_hint_table() -> None:
    """A live context adds exactly its FOOTER_HINTS line -- never a
    hand-copied copy of the hint inside the overlay module."""
    app = KeysHost()
    async with app.run_test(size=SIZE) as pilot:
        overlay = app.query_one(KeysOverlay)
        overlay.show("running")
        await pilot.pause()
        plain = _plain(overlay)
        assert "running: " in plain
        assert "esc interrupt · enter steer · shift+enter queue" in plain


@pytest.mark.asyncio
async def test_reshow_rebuilds_in_place_for_a_new_context() -> None:
    app = KeysHost()
    async with app.run_test(size=SIZE) as pilot:
        overlay = app.query_one(KeysOverlay)
        overlay.show("running")
        await pilot.pause()
        overlay.show("idle")
        await pilot.pause()
        plain = _plain(overlay)
        assert overlay.context == "idle"
        assert "running: " not in plain
        assert overlay.is_open


@pytest.mark.asyncio
async def test_close_hides_and_posts_closed() -> None:
    app = KeysHost()
    async with app.run_test(size=SIZE) as pilot:
        overlay = app.query_one(KeysOverlay)
        overlay.show("idle")
        await pilot.pause()
        overlay.close()
        await pilot.pause()
        assert not overlay.is_open
        assert app.closed == 1


@pytest.mark.asyncio
async def test_never_focusable_so_the_composer_keeps_the_keyboard() -> None:
    app = KeysHost()
    async with app.run_test(size=SIZE) as pilot:
        overlay = app.query_one(KeysOverlay)
        overlay.show("idle")
        await pilot.pause()
        assert overlay.can_focus is False
        assert app.focused is not overlay


@pytest.mark.asyncio
async def test_narrow_terminal_renders_single_column() -> None:
    app = KeysHost()
    async with app.run_test(size=(70, 40)) as pilot:
        overlay = app.query_one(KeysOverlay)
        overlay.show("idle")
        await pilot.pause()
        plain = _plain(overlay, width=70)
        assert "ctrl+j" in plain, "single-column fallback still lists the reference"


def test_keys_overlay_has_no_hex_literals() -> None:
    """Row styles read theme tokens at render time; the module must not
    smuggle hex values past tests/test_ui_themes.py's single-source rule."""
    source = inspect.getsource(keys_overlay)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)


# -- app wiring (the real TuiApp over the demo runtime) --------------------------

from amplifier_app_tui.ui.app import TuiApp  # noqa: E402
from amplifier_app_tui.ui.demo_wiring import DemoRuntimeAdapter  # noqa: E402

from .test_flow_helpers import seed_done, set_mode, type_text, wait_for  # noqa: E402


async def _reach_pytest_approval(pilot, app: TuiApp) -> None:
    """Seed, switch to chat (auto is the boot default), run the build turn
    up to its chat-mode pytest approval."""
    await seed_done(pilot, app)
    await set_mode(pilot, app, "chat")
    await type_text(pilot, "hi")
    await pilot.press("enter")
    assert await wait_for(pilot, lambda: app.approval_bar is not None)


@pytest.mark.asyncio
async def test_f1_opens_esc_closes_and_the_footer_tracks() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert not app.keys_overlay.is_open
        await pilot.press("f1")
        await pilot.pause()
        assert app.keys_overlay.is_open
        assert app.keys_overlay.context == "idle"
        assert app.footer_bar.state.context == "keys"
        await pilot.press("escape")
        await pilot.pause()
        assert not app.keys_overlay.is_open
        assert app.footer_bar.state.context == "idle"


@pytest.mark.asyncio
async def test_typing_still_reaches_the_composer_while_pinned() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await pilot.press("f1")
        await pilot.pause()
        await type_text(pilot, "hi")
        await pilot.pause()
        assert app.composer.text == "hi"
        assert app.keys_overlay.is_open


@pytest.mark.asyncio
async def test_f1_toggles_off() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await pilot.press("f1")
        await pilot.pause()
        assert app.keys_overlay.is_open
        await pilot.press("f1")
        await pilot.pause()
        assert not app.keys_overlay.is_open
        assert app.footer_bar.state.context == "idle"


@pytest.mark.asyncio
async def test_pinned_overlay_tracks_context_and_esc_orders_keys_before_palette() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await pilot.press("f1")
        await pilot.pause()
        await type_text(pilot, "/")
        await pilot.pause()
        assert app.palette.filter_text is not None
        assert app.keys_overlay.context == "palette", "pinned help follows the live context"
        # Esc closes the read-only overlay first (ESC_CHAIN); the stateful
        # palette survives that Esc and takes the next one.
        await pilot.press("escape")
        await pilot.pause()
        assert not app.keys_overlay.is_open
        assert app.palette.filter_text is not None
        await pilot.press("escape")
        await pilot.pause()
        assert app.palette.filter_text is None


@pytest.mark.asyncio
async def test_f1_is_ignored_while_an_approval_is_open() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await _reach_pytest_approval(pilot, app)
        await pilot.press("f1")
        await pilot.pause()
        assert not app.keys_overlay.is_open, "f1 is dead while the modal bar owns the keyboard"
        assert app.footer_bar.state.context == "approval"


@pytest.mark.asyncio
async def test_an_approval_opening_while_pinned_keeps_honest_footer_and_f1_close() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await set_mode(pilot, app, "chat")
        await pilot.press("f1")
        await pilot.pause()
        assert app.keys_overlay.is_open
        await type_text(pilot, "hi")
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: app.approval_bar is not None)
        # The pin survives -- but the footer tells the truth now: esc denies
        # the approval, it does not close the overlay.
        assert app.keys_overlay.is_open
        assert app.footer_bar.state.context == "approval"
        await pilot.press("f1")
        await pilot.pause()
        assert not app.keys_overlay.is_open
        assert app.footer_bar.state.context == "approval"
