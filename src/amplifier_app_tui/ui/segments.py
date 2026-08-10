"""Segment lists → Textual/Rich renderables, styled ONLY by theme tokens.

The transcript renderer (``ui/transcript.py``) produces lines of
:class:`~amplifier_app_tui.model.blocks.Segment` — plain data naming
DESIGN-SPEC §1 tokens. This module converts those segments into paintable
form without ever touching a color value:

- :func:`segment_style` / :func:`line_markup` / :func:`lines_markup` emit
  Textual *content markup* whose styles reference theme **variables**
  (``[bold $green]…[/]``). Textual resolves ``$green`` against the active
  theme's variables at paint time (our themes register every spec token as
  a variable — see ``ui/themes.py``), so a runtime theme switch is a
  repaint, not a rebuild (ADR-0007 resolution 11).
- :func:`to_rich_text` builds a ``rich.text.Text`` for callers that hold a
  resolved token→color mapping (``app.theme_variables``); the mapping is
  the only place a concrete color ever appears, and it comes from the
  theme, never from this module.
- :func:`line_plain` / :func:`lines_plain` are the style-free projections
  the golden tests assert exact glyph/label text against.
- :func:`escape_content` is the single home for escaping arbitrary
  user/model text before it is embedded in Textual markup — see its
  docstring for why ``textual.markup.escape`` itself is not safe enough.

No hex values appear here; ``tests/test_ui_themes.py`` enforces that
repo-wide.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from rich.style import Style
from rich.text import Text

from ..model.blocks import Segment

Line = tuple[Segment, ...]
"""One rendered transcript line: a run of styled segments."""

_UNESCAPED_BRACKET_RE = re.compile(r"(\\*)(\[)")
"""Any literal ``[``, with its run of preceding backslashes captured (so
they can be correctly doubled -- see :func:`escape_content`)."""


def escape_content(text: str) -> str:
    r"""Escape *text* so Textual can never parse any part of it as markup.

    ``textual.markup.escape`` (and ``rich.markup.escape``, which ships the
    exact same implementation) only escapes a ``[`` when a *matching* ``]``
    is present in the SAME string -- its regex is
    ``(\\*)(\[[a-z#/@][^[]*?])``, requiring the whole ``[tag...]`` span,
    closing bracket included, to be there. Content that opens a bracket
    with no same-string closing ``]`` -- e.g. a Graphviz/DOT attribute list
    wrapped across two source lines, where ``answer_spans`` turns each
    fenced-code *line* into its own :class:`Segment` (``node [style=...,``
    on one line, ``  shape=box];`` on the next) -- passes straight through
    UNESCAPED and crashes Textual's parser (``MarkupError: Expected markup
    value``) the moment that segment reaches a widget's ``update()``. This
    crashed transcript rendering for any resumed session whose answer
    quoted DOT/graphviz source, an unbalanced markdown/log fragment, or
    similar (S5-class isolation gap, caught here at the source instead).

    Textual's tokenizer only treats an unescaped ``[`` as special
    (``open_tag = r"(?<!\\)\["``) -- it never inspects what follows.
    Escaping EVERY ``[`` unconditionally is therefore always correct and
    always sufficient; a bare ``]`` outside an open tag is always literal
    and never needs escaping (Textual's own grammar has no rule that gives
    a lone ``]`` meaning outside of one). The backslash-doubling below (and
    the trailing-odd-backslash guard) mirror ``textual.markup.escape``
    exactly, so text that already contains literal backslashes keeps
    round-tripping the same way it does today.
    """

    def _double(match: re.Match[str]) -> str:
        backslashes = match.group(1)
        return f"{backslashes}{backslashes}\\["

    escaped = _UNESCAPED_BRACKET_RE.sub(_double, text)
    if escaped.endswith("\\") and not escaped.endswith("\\\\"):
        # A lone trailing backslash would otherwise escape the '[' of the
        # `[/]` (or `[link=...]`) tag callers append right after this text.
        escaped += "\\"
    return escaped


def segment_style(segment: Segment) -> str:
    """The Textual style string for a segment: ``bold italic $teal on $bg-tab``.

    Tokens are referenced by variable name (``$<token>``) — never by value.
    """
    parts: list[str] = []
    if segment.bold:
        parts.append("bold")
    if segment.italic:
        parts.append("italic")
    parts.append(f"${segment.style_token}")
    if segment.bg_token is not None:
        parts.append(f"on ${segment.bg_token}")
    return " ".join(parts)


def segment_markup(segment: Segment) -> str:
    """One segment as Textual content markup (text escaped, style by token).

    A segment carrying a ``link`` nests a ``[link="…"]`` tag so the terminal
    paints a real OSC 8 hyperlink (Textual emits the escape). The URL is
    QUOTED: an unquoted ``[link=https://…]`` breaks Textual's markup parser on
    the ``://`` ("Expected markup value") — which crashed transcript rendering
    (e.g. resuming a session whose answer contained a PR link). A stray ``"`` in
    the URL is escaped so the quoting itself can't be broken.
    """
    if not segment.text:
        return ""
    body = escape_content(segment.text)
    if segment.link:
        safe_link = segment.link.replace('"', "%22")
        body = f'[link="{safe_link}"]{body}[/link]'
    return f"[{segment_style(segment)}]{body}[/]"


def line_markup(line: Iterable[Segment]) -> str:
    """A whole line of segments as one markup string."""
    return "".join(segment_markup(segment) for segment in line)


def lines_markup(lines: Iterable[Iterable[Segment]]) -> str:
    """Multiple lines joined with newlines — the form widgets paint."""
    return "\n".join(line_markup(line) for line in lines)


def line_plain(line: Iterable[Segment]) -> str:
    """Style-free text of a line (what golden tests assert against)."""
    return "".join(segment.text for segment in line)


def lines_plain(lines: Iterable[Iterable[Segment]]) -> str:
    """Style-free text of many lines, newline-joined."""
    return "\n".join(line_plain(line) for line in lines)


def to_rich_text(line: Iterable[Segment], variables: Mapping[str, str] | None = None) -> Text:
    """A line as ``rich.text.Text``.

    ``variables`` maps token name → resolved color (pass
    ``app.theme_variables``); with ``None`` the Text carries structure but
    no colors (useful for width measurement and tests). Colors resolved
    this way still come exclusively from the theme.
    """
    text = Text()
    for segment in line:
        if not segment.text:
            continue
        color = variables.get(segment.style_token) if variables else None
        bgcolor = (
            variables.get(segment.bg_token) if variables and segment.bg_token is not None else None
        )
        text.append(
            segment.text,
            style=Style(
                color=color,
                bgcolor=bgcolor,
                bold=segment.bold or None,
                italic=segment.italic or None,
                link=segment.link,
            ),
        )
    return text


__all__ = [
    "Line",
    "escape_content",
    "line_markup",
    "line_plain",
    "lines_markup",
    "lines_plain",
    "segment_markup",
    "segment_style",
    "to_rich_text",
]
