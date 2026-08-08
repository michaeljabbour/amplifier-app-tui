"""Turn-film-strip scrubber (item 3b): a navigation-only sibling of the
rewind picker, opened by ctrl+g while IDLE (the same chord toggles the
thinking peek while a turn runs -- the keymap table holds both claims on
disjoint contexts, so the chord can never mean two things at once).

``‹ timeline · turn 2/5 · "add fuzzy recall" › [enter keep] [esc back]``

- ``↑``/``←`` / ``↓``/``→`` move the cursor, clamped at both ends
  (rewind-picker idiom, no wrap). Every move posts :class:`Moved` so the
  app scrubs the transcript live -- same live-preview contract as the
  theme picker.
- ``enter`` keeps the landed scroll position (posts ``Closed(kept=True)``).
- ``esc`` posts ``Closed(kept=False)`` via the app's ESC_CHAIN (no local
  escape binding, exactly like :class:`RewindStrip`); the app returns the
  transcript to the tail, so a pure look-around never moves anything.
- Printable keys post :class:`TypeThrough` and land in the composer
  (mockup ground truth: typing is never swallowed by an open strip).

The strip is pure navigation: it never touches checkpoints, the ledger,
or session state (that is rewind's job), so it needs no restore scope.
"""

from __future__ import annotations

from collections.abc import Sequence

from textual import events
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from ..model.blocks import GLYPH_REWIND_LEFT, GLYPH_REWIND_RIGHT

KEEP_HINT = "enter keep"
BACK_HINT = "esc back"

_SNIPPET_MAX_CHARS = 40


class TimelineEntry:
    """One jump target: a turn-rule block plus its prompt snippet."""

    __slots__ = ("block_id", "turn", "snippet")

    def __init__(self, block_id: str, turn: int, snippet: str) -> None:
        self.block_id = block_id
        self.turn = turn
        self.snippet = snippet

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TimelineEntry) and (self.block_id, self.turn, self.snippet) == (
            other.block_id,
            other.turn,
            other.snippet,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"TimelineEntry({self.block_id!r}, {self.turn}, {self.snippet!r})"


def snippet_of(text: str, *, max_chars: int = _SNIPPET_MAX_CHARS) -> str:
    """First line of *text*, collapsed whitespace, ellipsized -- the row label."""
    snippet = " ".join(text.splitlines()[:1]).strip()
    if not snippet:
        return "(blank prompt)"
    if len(snippet) > max_chars:
        snippet = snippet[: max_chars - 1].rstrip() + "…"
    return snippet


def timeline_line(entry: TimelineEntry, total: int) -> str:
    """``timeline · turn 2/5 · "add fuzzy recall"`` -- the strip's center text."""
    return f'timeline · turn {entry.turn}/{total} · "{entry.snippet}"'


class TimelineStrip(Horizontal):
    """The timeline scrubber strip. Open with :meth:`show_entries`; posts

    - :class:`Moved` -- cursor moved (scrub the transcript to this block).
    - :class:`Closed` -- enter keep / esc back (``kept`` says which).
    - :class:`TypeThrough` -- printable key for the composer.
    """

    can_focus = True

    DEFAULT_CSS = """
    TimelineStrip {
        display: none;
        width: 100%;
        height: auto;
        border-top: solid $rule;
        padding: 0 2;
        color: $teal;
    }
    TimelineStrip > Static {
        width: auto;
        height: 1;
        color: $teal;
        margin-right: 1;
    }
    TimelineStrip #timeline-keep {
        color: $bright;
        background: $bg-tab;
        padding: 0 1;
    }
    TimelineStrip #timeline-back {
        color: $dimmer;
    }
    """

    BINDINGS = [
        Binding("up", "prev", "↑↓", show=False),
        Binding("left", "prev", "↑↓", show=False),
        Binding("down", "next", "↑↓", show=False),
        Binding("right", "next", "↑↓", show=False),
        Binding("enter", "keep", "enter keep", show=False),
        # No local escape binding: Esc bubbles to the app and resolves via
        # keymap.ESC_CHAIN (lane-focus/palette still close first) --
        # the rewind picker's exact contract, which this strip mirrors.
    ]

    class Moved(Message):
        """The cursor moved to *block_id* (scrub the transcript live)."""

        def __init__(self, block_id: str) -> None:
            self.block_id = block_id
            super().__init__()

    class Closed(Message):
        """Enter keep (``kept=True``) / esc back (``kept=False``)."""

        def __init__(self, *, kept: bool) -> None:
            self.kept = kept
            super().__init__()

    class TypeThrough(Message):
        """A printable key pressed while the strip held focus (to composer)."""

        def __init__(self, character: str) -> None:
            self.character = character
            super().__init__()

    def __init__(self, *, id: str | None = None) -> None:  # noqa: A002
        super().__init__(id=id)
        self._entries: tuple[TimelineEntry, ...] = ()
        self._index = 0

    def compose(self):
        yield Static(GLYPH_REWIND_LEFT, id="timeline-prev")
        yield Static("", id="timeline-label")
        yield Static(GLYPH_REWIND_RIGHT, id="timeline-next")
        yield Static(KEEP_HINT, id="timeline-keep")
        yield Static(BACK_HINT, id="timeline-back")

    # -- public API ----------------------------------------------------

    @property
    def entries(self) -> tuple[TimelineEntry, ...]:
        return self._entries

    @property
    def index(self) -> int:
        return self._index

    @property
    def current(self) -> TimelineEntry | None:
        if not self._entries:
            return None
        return self._entries[self._index]

    @property
    def label_text(self) -> str:
        current = self.current
        return timeline_line(current, len(self._entries)) if current is not None else ""

    def show_entries(self, entries: Sequence[TimelineEntry], index: int | None = None) -> None:
        """Open on *entries* (newest turn selected by default -- the scrub
        starts from where you are, the tail). An empty list keeps the
        strip hidden (the app shows the ``no turns yet`` notice instead).
        Unlike :meth:`RewindStrip.show_checkpoints` no :class:`Moved` is
        posted for the opening position: the tail already shows it."""
        self._entries = tuple(entries)
        if not self._entries:
            self.display = False
            return
        last = len(self._entries) - 1
        self._index = last if index is None else max(0, min(last, index))
        self._refresh_label()
        self.display = True
        self.focus()

    def nav(self, delta: int) -> None:
        """Move the cursor by *delta*, clamped at both ends, and scrub."""
        if not self._entries:
            return
        new_index = max(0, min(len(self._entries) - 1, self._index + delta))
        if new_index == self._index:
            return
        self._index = new_index
        self._refresh_label()
        current = self.current
        if current is not None:
            self.post_message(self.Moved(current.block_id))

    def keep(self) -> None:
        """Keep the landed scroll position and close."""
        self.display = False
        self.post_message(self.Closed(kept=True))

    def close_strip(self) -> None:
        """Esc path (ESC_CHAIN): close and ask for the scroll to revert."""
        self.display = False
        self.post_message(self.Closed(kept=False))

    # -- key actions ----------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Printable keys pass through to the composer (the strip never
        swallows typing, the rewind picker's mockup contract)."""
        if event.is_printable and event.character:
            event.stop()
            event.prevent_default()
            self.post_message(self.TypeThrough(event.character))

    def action_prev(self) -> None:
        self.nav(-1)

    def action_next(self) -> None:
        self.nav(1)

    def action_keep(self) -> None:
        self.keep()

    # -- clicks ----------------------------------------------------------

    def on_click(self, event: events.Click) -> None:
        widget = event.widget
        if widget is None or widget.id is None:
            return
        if widget.id == "timeline-prev":
            self.nav(-1)
        elif widget.id == "timeline-next":
            self.nav(1)
        elif widget.id == "timeline-keep":
            self.keep()
        elif widget.id == "timeline-back":
            self.close_strip()

    # -- internals -------------------------------------------------------

    def _refresh_label(self) -> None:
        if self.is_mounted:
            self.query_one("#timeline-label", Static).update(self.label_text)


__all__ = [
    "BACK_HINT",
    "KEEP_HINT",
    "TimelineEntry",
    "TimelineStrip",
    "snippet_of",
    "timeline_line",
]
