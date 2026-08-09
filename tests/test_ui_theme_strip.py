"""Tests for ui/theme_strip.py -- the live-preview theme picker strip
(bare ``/theme`` opens it; esc reverts, enter keeps)."""

from __future__ import annotations

import re

import pytest
from textual.app import App, ComposeResult

from amplifier_app_tui.ui.theme_strip import ThemeStrip, _ThemeRow
from amplifier_app_tui.ui.themes import DEFAULT_THEME, THEME_TOKENS, register_themes, theme_id

NAMES = tuple(THEME_TOKENS)


class ThemesHost(App[None]):
    """Minimal host app: registers spec themes, records strip messages."""

    def __init__(self) -> None:
        super().__init__()
        register_themes(self)
        self.theme = theme_id(DEFAULT_THEME)
        self.previewed: list[str] = []
        self.chosen: list[str] = []
        self.closed = 0

    def compose(self) -> ComposeResult:
        yield ThemeStrip(id="theme-strip")

    def on_theme_strip_preview_theme(self, message: ThemeStrip.PreviewTheme) -> None:
        self.previewed.append(message.name)

    def on_theme_strip_theme_chosen(self, message: ThemeStrip.ThemeChosen) -> None:
        self.chosen.append(message.name)

    def on_theme_strip_closed(self, message: ThemeStrip.Closed) -> None:
        self.closed += 1


# -- widget behavior ------------------------------------------------------


@pytest.mark.asyncio
async def test_show_picker_opens_on_the_current_theme() -> None:
    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        assert not strip.is_open
        strip.show_picker(NAMES, current="graphite")
        await pilot.pause()
        assert strip.is_open
        assert strip.names == NAMES
        assert strip.selected_name == "graphite"
        assert len(list(strip.query(_ThemeRow))) == len(NAMES)


@pytest.mark.asyncio
async def test_show_picker_empty_names_stays_hidden() -> None:
    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        strip.show_picker((), current="")
        await pilot.pause()
        assert not strip.is_open
        assert strip.selected_name is None


@pytest.mark.asyncio
async def test_arrows_post_live_preview_for_each_move() -> None:
    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        strip.show_picker(NAMES, current="slate")
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        assert app.previewed == ["graphite", "carbon"]
        assert strip.selected_name == "carbon"
        await pilot.press("up")
        await pilot.pause()
        assert app.previewed == ["graphite", "carbon", "graphite"]


@pytest.mark.asyncio
async def test_clamped_ends_do_not_repost_preview() -> None:
    """Hammering past an edge previews nothing: the theme did not move,
    so a repaint notice would be noise."""
    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        strip.show_picker(NAMES, current="slate")
        await pilot.pause()
        for _ in range(3):
            await pilot.press("up")
        await pilot.pause()
        assert app.previewed == []
        assert strip.selected_name == "slate"


@pytest.mark.asyncio
async def test_enter_chooses_the_highlighted_theme() -> None:
    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        strip.show_picker(NAMES, current="slate")
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert app.chosen == ["graphite"]


@pytest.mark.asyncio
async def test_click_chooses_that_row_directly() -> None:
    """Mouse parity with the palette's "click runs any row": one click,
    no select-then-choose step."""
    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        strip.show_picker(NAMES, current="slate")
        await pilot.pause()
        await pilot.click("#theme-row-3")
        await pilot.pause()
        assert app.chosen == ["paper"]


@pytest.mark.asyncio
async def test_close_strip_posts_closed() -> None:
    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        strip.show_picker(NAMES, current="slate")
        await pilot.pause()
        strip.close_strip()
        await pilot.pause()
        assert not strip.is_open
        assert app.closed == 1


@pytest.mark.asyncio
async def test_row_swatch_renders_from_the_rows_own_theme() -> None:
    """The swatch paints the ROW's theme tokens (a tiny window into that
    theme), not the host app's live tokens."""
    from rich.console import Console

    app = ThemesHost()
    async with app.run_test() as pilot:
        strip = app.query_one(ThemeStrip)
        strip.show_picker(NAMES, current="slate")
        await pilot.pause()
        row = strip.query_one("#theme-row-1", _ThemeRow)  # graphite row
        assert row.theme_name == "graphite"
        console = Console(width=40)
        segments = list(console.render(row.render()))
        plain = "".join(segment.text for segment in segments)
        assert "graphite" in plain
        graphite_teal = THEME_TOKENS["graphite"]["teal"]
        swatch_colors = []
        for segment in segments:
            if segment.style is not None and segment.style.color is not None:
                swatch_colors.append(segment.style.color.get_truecolor().hex)
        assert graphite_teal in swatch_colors, "swatch cell must paint the row theme's teal token"


# -- single-source color rule ----------------------------------------------


def test_theme_strip_has_no_hex_literals() -> None:
    """Swatches read THEME_TOKENS at render time; the strip module itself
    must not smuggle hex values past tests/test_ui_themes.py's scan."""
    import inspect

    from amplifier_app_tui.ui import theme_strip

    source = inspect.getsource(theme_strip)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)
