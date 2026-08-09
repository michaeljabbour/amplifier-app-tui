"""Theme picker overlay strip: a live-preview, keep-or-revert theme chooser.

Docked above the composer like every other picker in this app
(:class:`~.sessions_strip.SessionsStrip`,
:class:`~.palette.PaletteStrip`) -- never a ``ModalScreen``. Bare
``/theme`` opens it; ``/theme <name>`` still jumps directly. Moving the
highlight posts :class:`ThemeStrip.PreviewTheme` so the app repaints the
whole UI in the highlighted theme live (a real repaint, not a mock);
enter keeps the highlighted theme (:class:`ThemeChosen`); a click on any
row chooses that row directly (mouse parity with the palette's "click
runs any row"). Esc is never a local binding here -- it bubbles to the
app, which resolves it through ``keymap.ESC_CHAIN`` and reverts to the
theme that was active when the picker opened.

Row swatches are drawn from each theme's own tokens, read out of
:data:`~.themes.THEME_TOKENS` at render time -- no hex literals in this
module (``tests/test_ui_themes.py`` enforces the single-source rule).
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from .themes import THEME_TOKENS

SWATCH_BG_TOKEN = "bg-term"
"""Token the row swatch paints its cells on (the theme's own terminal
surface, so the swatch reads as a tiny window into that theme)."""

SWATCH_TOKENS = ("bg-tab", "teal", "orange")
"""Tokens sampled as swatch cells, in order: the theme's highlight
surface plus its two most recognizable accents."""


class _ThemeRow(Static):
    """One clickable theme row: current marker + live swatch + name."""

    DEFAULT_CSS = """
    _ThemeRow {
        width: 100%;
        height: 1;
        padding: 0 2;
    }
    _ThemeRow.-selected {
        background: $bg-tab;
    }
    """

    def __init__(self, theme_name: str, index: int, *, current: bool) -> None:
        super().__init__(id=f"theme-row-{index}")
        self.theme_name = theme_name
        self.index = index
        self.current = current

    def render(self) -> Table:
        tokens = self.app.theme_variables
        swatch_tokens = THEME_TOKENS.get(self.theme_name, {})
        selected = self.has_class("-selected")
        if swatch_tokens:
            swatch_bg = swatch_tokens[SWATCH_BG_TOKEN]
            swatch = Text.assemble(
                *(
                    ("\u2588", Style(color=swatch_tokens[token], bgcolor=swatch_bg))
                    for token in SWATCH_TOKENS
                )
            )
        else:
            swatch = Text(" ")
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(width=2, no_wrap=True)
        grid.add_column(width=len(SWATCH_TOKENS) + 1, no_wrap=True)
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        grid.add_row(
            Text("\u25b8" if self.current else " ", style=Style(color=tokens.get("green"))),
            swatch,
            Text(
                self.theme_name,
                style=Style(color=tokens.get("fg" if selected else "dim"), bold=self.current),
            ),
        )
        return grid

    def on_click(self) -> None:
        """Click parity: any row chooses immediately -- no separate
        select-then-choose step (mirrors ``PaletteStrip``)."""
        self.post_message(ThemeStrip.ThemeChosen(self.theme_name))


class ThemeStrip(VerticalScroll):
    """The live-preview theme picker strip.

    Open with :meth:`show_picker`. Posts:

    - :class:`PreviewTheme` -- the highlight MOVED to a different theme;
      the app switches ``App.theme`` immediately so the preview is the
      real repaint.
    - :class:`ThemeChosen` -- enter on the highlight, or a click on any
      row; the app keeps that theme.
    - :class:`Closed` -- :meth:`close_strip` ran (Esc itself is resolved
      by the app via ``keymap.ESC_CHAIN``, where the same close also
      reverts the preview -- never a local binding here, matching every
      other picker strip).
    """

    can_focus = True

    DEFAULT_CSS = """
    ThemeStrip {
        display: none;
        width: 100%;
        height: auto;
        max-height: 8;
        border-top: solid $rule;
        background: $bg-page;
        padding: 0;
        scrollbar-size-vertical: 1;
        /* All UI color comes from the §1 tokens -- never Textual-derived. */
        scrollbar-color: $rule;
        scrollbar-color-hover: $dim;
        scrollbar-color-active: $dim;
        scrollbar-background: $bg-page;
        scrollbar-background-hover: $bg-page;
        scrollbar-background-active: $bg-page;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "\u2191\u2193 preview", show=False),
        Binding("down", "cursor_down", "\u2191\u2193 preview", show=False),
        Binding("enter", "choose", "enter keep", show=False),
        # No local escape binding: Esc must bubble to the app so it
        # resolves via keymap.ESC_CHAIN (matches PaletteStrip/SessionsStrip).
    ]

    class PreviewTheme(Message):
        """The highlight moved to a different theme -- preview it live."""

        def __init__(self, name: str) -> None:
            self.name = name
            super().__init__()

    class ThemeChosen(Message):
        """Keep the highlighted (or clicked) theme."""

        def __init__(self, name: str) -> None:
            self.name = name
            super().__init__()

    class Closed(Message):
        """:meth:`close_strip` ran."""

    def __init__(self, *, id: str | None = None) -> None:  # noqa: A002 - Textual widget API
        super().__init__(id=id)
        self._names: tuple[str, ...] = ()
        self._current: str = ""
        self._selected = 0

    # -- public API ----------------------------------------------------

    @property
    def is_open(self) -> bool:
        return bool(self.display)

    @property
    def names(self) -> tuple[str, ...]:
        """Currently displayed theme names, in row order."""
        return self._names

    @property
    def selected_name(self) -> str | None:
        if not self._names:
            return None
        return self._names[self._selected]

    def show_picker(self, names: Sequence[str], *, current: str = "") -> None:
        """Open the picker on *names*, highlighting *current*.

        An empty sequence keeps the strip hidden (mirrors
        ``SessionsStrip.show_sessions`` on an empty roster; the app shows
        a notice instead).
        """
        self._names = tuple(names)
        self._current = current
        self._selected = self._names.index(current) if current in self._names else 0
        if not self._names:
            self.display = False
            return
        self.display = True
        # remove_children is asynchronous: await it before remounting so
        # rebuilt rows never collide with the ids of outgoing ones
        # (mirrors SessionsStrip._remount_rows).
        self.call_later(self._remount_rows)
        self.focus()

    def close_strip(self) -> None:
        self.display = False
        self.post_message(self.Closed())

    def move_selection(self, delta: int) -> None:
        """Move the highlight by *delta* (clamped) and preview it live."""
        if not self._names:
            return
        new = max(0, min(len(self._names) - 1, self._selected + delta))
        if new == self._selected:
            return
        self._selected = new
        self._apply_selection()
        self.post_message(self.PreviewTheme(self._names[new]))

    def choose_selected(self) -> None:
        """Post :class:`ThemeChosen` for the highlighted row."""
        name = self.selected_name
        if name is not None:
            self.post_message(self.ThemeChosen(name))

    # -- key actions ----------------------------------------------------

    def action_cursor_up(self) -> None:
        self.move_selection(-1)

    def action_cursor_down(self) -> None:
        self.move_selection(1)

    def action_choose(self) -> None:
        self.choose_selected()

    # -- internals -------------------------------------------------------

    async def _remount_rows(self) -> None:
        await self.remove_children()
        if not self._names:
            return
        rows = [
            _ThemeRow(name, index, current=name == self._current)
            for index, name in enumerate(self._names)
        ]
        await self.mount(*rows)
        self._apply_selection()

    def _apply_selection(self) -> None:
        rows = list(self.query(_ThemeRow))
        for row in rows:
            row.set_class(row.index == self._selected, "-selected")
        if 0 <= self._selected < len(rows):
            rows[self._selected].scroll_visible()


__all__ = [
    "SWATCH_BG_TOKEN",
    "SWATCH_TOKENS",
    "ThemeStrip",
]
