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
        assert "add a newline without sending" in plain
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
