"""Which-key overlay: the f1 cheat sheet, rendered from the keymap itself.

Docked above the composer like every other overlay in this app
(:class:`~.theme_strip.ThemeStrip`, :class:`~.palette.PaletteStrip`) --
never a ``ModalScreen``. ``f1`` toggles it (the keymap's ``show_keys``
action); Esc closes it through ``keymap.ESC_CHAIN``'s first entry: the
overlay is read-only chrome, so dismissing it must win over every
state-changing esc resolution beneath it. Both the toggle and Esc stay
with the app, matching the other strips (never a local binding here).

Every body row comes from :func:`keymap.help_rows` -- the same table
that drives the real bindings AND the ``/keys`` transcript reference --
plus one context line read live from :data:`keymap.FOOTER_HINTS`, so the
contents track the keymap automatically and can never drift. The overlay
never takes the composer's focus: typing keeps reaching the draft while
help is open.
"""

from __future__ import annotations

from rich.console import Group
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.message import Message
from textual.widgets import Static

from . import keymap

TWO_COLUMN_MIN_WIDTH = 90
"""Below this terminal width the body renders one reference column."""

MAX_HEIGHT = 16
"""Display cap; past it the region scrolls (overflow-y: auto below)."""


class KeysOverlay(Static):
    """The f1 which-key overlay strip.

    Open/refresh with :meth:`show`; close with :meth:`close` (Esc itself
    is resolved by the app via ``keymap.ESC_CHAIN`` -- never a local
    binding, matching every other overlay strip). Posts:

    - :class:`Closed` -- :meth:`close` ran.
    """

    can_focus = False  # read-only chrome: the composer keeps the keyboard

    DEFAULT_CSS = """
    KeysOverlay {
        display: none;
        width: 100%;
        height: auto;
        max-height: 16;
        border-top: solid $rule;
        background: $bg-page;
        padding: 0 2;
        overflow-y: auto;
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

    class Closed(Message):
        """:meth:`close` ran."""

    def __init__(self, *, id: str | None = None) -> None:  # noqa: A002 - Textual widget API
        super().__init__(id=id)
        # NOT ``self._context``: MessagePump._context is a bound method on
        # every Textual widget; shadowing it strands the message loop (the
        # app hangs on startup before the first paint).
        self._shown_context: keymap.Context = "idle"

    # -- public API -----------------------------------------------------

    @property
    def is_open(self) -> bool:
        return bool(self.display)

    @property
    def context(self) -> keymap.Context:
        """The UI context the currently displayed rows were built for."""
        return self._shown_context

    def show(self, context: keymap.Context) -> None:
        """Open the overlay, or rebuild it in place for a NEW context
        (the app re-shows on every footer refresh so the context line
        tracks e.g. a turn starting while help is pinned)."""
        self._shown_context = context
        self.update(self._build(context))
        self.display = True

    def close(self) -> None:
        self.display = False
        self.post_message(self.Closed())

    # -- internals --------------------------------------------------------

    def _build(self, context: keymap.Context) -> Group:
        tokens = self.app.theme_variables
        header = Text.assemble(
            ("· ", Style(color=tokens.get("blue"))),
            ("Keys", Style(color=tokens.get("bright"), bold=True)),
            (
                "  keys that work right now · esc/f1 closes",
                Style(color=tokens.get("dimmer")),
            ),
        )
        hint = "" if context == "idle" else keymap.FOOTER_HINTS.get(context, "")
        parts: list[Text | Table] = [header]
        if hint:
            parts.append(
                Text.assemble(
                    (f"  {context}: ", Style(color=tokens.get("teal"))),
                    (hint, Style(color=tokens.get("dim"))),
                )
            )
        parts.append(self._body_grid(tokens))
        return Group(*parts)

    def _body_grid(self, tokens: dict[str, str]) -> Table:
        rows = keymap.help_rows()
        label_width = max(len(label) for label, _ in rows)

        def row_cells(label: str, description: str) -> tuple[Text, Text]:
            return (
                Text(
                    f"{label.ljust(label_width)} " if label else " " * (label_width + 1),
                    style=Style(color=tokens.get("teal")),
                ),
                Text(
                    description,
                    style=Style(color=tokens.get("dim")),
                    no_wrap=True,
                    overflow="ellipsis",
                ),
            )

        grid = Table.grid(expand=True, padding=(0, 1))
        # The widget has no width of its own while display:none, so read
        # the SCREEN width; first open must not fall into the narrow
        # single-column layout on a wide terminal.
        if self.screen.size.width < TWO_COLUMN_MIN_WIDTH:
            grid.add_column(no_wrap=True)
            grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
            for label, description in rows:
                grid.add_row(*row_cells(label, description))
        else:
            for _ in range(2):
                grid.add_column(no_wrap=True)
                grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
            half = (len(rows) + 1) // 2
            left, right = rows[:half], rows[half:]
            for index in range(half):
                l_label, l_desc = left[index]
                r_label, r_desc = right[index] if index < len(right) else ("", "")
                grid.add_row(*row_cells(l_label, l_desc), *row_cells(r_label, r_desc))
        return grid


__all__ = [
    "MAX_HEIGHT",
    "TWO_COLUMN_MIN_WIDTH",
    "KeysOverlay",
]
