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
- :func:`append_closing_tag` safely appends a ``[/...]`` closing tag after
  already-escaped content — see its docstring for why plain string
  concatenation of a closing tag isn't always safe.

No hex values appear here; ``tests/test_ui_themes.py`` enforces that
repo-wide.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from rich.style import Style
from rich.text import Text

from ..model.blocks import Segment

Line = tuple[Segment, ...]
"""One rendered transcript line: a run of styled segments."""


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

    That was PR #241's fix, and it was correct as far as it went -- but it
    modeled Textual's unescaping as PARITY-based (like a Python/Rich string
    literal: a run of backslashes before ``[`` is "escaped" if odd, doubled
    to stay "unescaped" if even). Textual does not work that way. Its real
    tokenizer (``textual/markup.py``) decides whether a ``[`` opens a tag
    with a SINGLE-CHARACTER negative lookbehind -- ``open_tag = r"(?<!\\)\["``
    -- which only ever asks "is the ONE character right before this ``[``
    a backslash?". It never counts a run, so ANY number of backslashes
    (1, 2, 100 -- odd or even, doesn't matter) immediately before ``[``
    is equally enough to hide it from being parsed as a tag. Once hidden,
    Textual's unescape step (``token.value.replace("\\[", "[")``) then
    removes exactly ONE backslash from in front of that ``[`` -- again
    regardless of how many preceded it.

    So to round-trip a literal run of N backslashes immediately followed by
    ``[``, the emitted markup needs exactly N+1 backslashes then ``[``: the
    original N pass through untouched (the tokenizer's one-character check
    never looks at them), and the extra one is what makes the ``[`` itself
    "invisible" to the tokenizer, then gets consumed by the unescape step
    leaving the ``[`` as a literal character. PR #241's ``2N+1`` (doubling
    the run) only coincides with the correct ``N+1`` when N is 0 -- which is
    exactly why the (all backslash-free) tests it shipped with passed, and
    why real backslash-bearing content (a shell/Makefile line continuation,
    an already-escaped bracket, LaTeX) silently corrupted: an extra,
    unwanted backslash (or a leaked literal ``[/]``) appeared in rendered
    output that was never in the model's answer.

    The fix below needs no run-length bookkeeping at all: inserting exactly
    one backslash immediately before EVERY ``[`` -- independent of whatever
    backslashes (if any) already precede it -- produces precisely the N+1
    pattern above for every N, because the pre-existing N are left alone
    and the tokenizer's check only ever cares about the one character
    adjacent to the bracket. A bare ``]`` outside an open tag is always
    literal and never needs escaping (Textual's grammar has no rule that
    gives a lone ``]`` meaning outside of one).

    A trailing run of backslashes at the very END of *text* (not before a
    ``[`` at all -- there's nothing after them here) is left untouched:
    Textual's unescape only ever touches the literal substring ``\\[``, so
    a backslash with no ``[`` after it is inert. It only becomes dangerous
    once a caller concatenates a ``[...]`` tag directly after this
    function's return value -- see :func:`append_closing_tag`, which is
    where that case is actually handled.
    """
    return text.replace("[", "\\[")


def append_closing_tag(escaped: str, closing_tag: str) -> str:
    r"""Append *closing_tag* (e.g. ``"[/]"``, ``"[/link]"``) after *escaped*.

    *escaped* must already be the output of :func:`escape_content` (or of
    this function itself, for nesting -- see :func:`segment_markup`'s
    ``link`` branch). Plain string concatenation (``escaped + closing_tag``)
    is unsafe in exactly one case: if *escaped* ends in one or more literal
    backslashes, the FIRST character of *closing_tag* is always ``[``, and
    that ``[`` would now sit immediately after a backslash -- which hides
    it from Textual's tokenizer (see :func:`escape_content`'s docstring)
    exactly like an internal escaped bracket. Except here the ``[`` was
    never meant to be hidden: it's real markup, meant to close the span.
    Once hidden, it's swept into plain text and Textual's unescape step
    (``replace("\\[", "[")``) eats one of the trailing backslashes,
    producing exactly the observed corruption -- e.g. ``echo hello \``
    rendering as ``echo hello \[/]`` (the tag leaks as literal text AND
    the backslash count is wrong).

    There is no way to fix this by adding more backslashes: Textual's
    lookbehind only ever checks the ONE character immediately before
    ``[``, so no count (odd or even) of backslashes there ever lets that
    ``[`` be recognized as a real tag -- recognition and "leave N literal
    backslashes in the plain output right before a real tag" are mutually
    exclusive. So instead we move the closing tag to sit BEFORE the
    trailing backslash run rather than after it, then re-append the run
    (raw, unescaped) after the now-safely-placed tag. With nothing left
    between the run and the following text, the backslashes are inert
    again (see :func:`escape_content`) and the tag is correctly recognized
    and closes the span.

    Trade-off, stated plainly: the trailing backslash run itself ends up
    just outside the span it would otherwise be the tail of (rendered in
    whatever style follows, rather than this span's style/link). That's a
    cosmetic detail confined to the literal trailing-backslash character(s)
    of a segment; the alternative -- corrupting the actual text content --
    is the bug this function exists to close. Content correctness wins.
    """
    stripped = escaped.rstrip("\\")
    trailing_backslashes = escaped[len(stripped) :]
    return stripped + closing_tag + trailing_backslashes


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
        body = f'[link="{safe_link}"]{append_closing_tag(body, "[/link]")}'
    return f"[{segment_style(segment)}]{append_closing_tag(body, '[/]')}"


def line_markup(line: Iterable[Segment]) -> str:
    r"""A whole line of segments as one markup string.

    Naively joining each segment's OWN ``segment_markup()`` output
    (``"".join(segment_markup(s) for s in line)``) reopens the hazard
    :func:`append_closing_tag` closes for a single segment: that helper
    only ever protects a segment's own closing tag, because it knows
    nothing follows it. Here, a DIFFERENT segment's OPENING tag -- also a
    literal ``[...]`` -- can immediately follow one segment's text with no
    separator, and it is just as vulnerable to a trailing backslash run as
    a closing tag is (Textual's tokenizer doesn't distinguish "opening" vs
    "closing" -- see :func:`escape_content`'s docstring; a ``[`` is a
    ``[`` either way).

    Rather than relocate such a run past its own segment's closing tag
    (which would strand it there, immediately before the NEXT segment's
    opening ``[``), a segment whose text ends in a raw backslash run hands
    that run off to the FRONT of the next segment's text instead. It's
    still 100% correct there -- backslashes at the very start of a
    segment's text are just as inert as anywhere else not adjacent to a
    ``[`` -- and it keeps `.plain`'s character order exactly right (the
    carried-over backslashes still land between the two segments' own
    text, exactly where they belong). Only the line's LAST segment (where
    nothing follows) falls back to :func:`segment_markup`'s own handling.
    """
    segments = list(line)
    if not segments:
        return ""
    carry = ""
    pieces: list[str] = []
    last_index = len(segments) - 1
    for index, segment in enumerate(segments):
        text = carry + segment.text
        carry = ""
        if index != last_index:
            stripped = text.rstrip("\\")
            carry = text[len(stripped) :]
            text = stripped
        if text != segment.text:
            segment = segment.model_copy(update={"text": text})
        pieces.append(segment_markup(segment))
    if carry:
        pieces.append(carry)
    return "".join(pieces)


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
    "append_closing_tag",
    "escape_content",
    "line_markup",
    "line_plain",
    "lines_markup",
    "lines_plain",
    "segment_markup",
    "segment_style",
    "to_rich_text",
]
