"""Tests for ui/timeline_strip.py + its app wiring (item 3b): the ctrl+g
idle film strip -- live-scrubbing turn navigation with theme-picker
semantics (enter keeps the scroll, esc returns to the tail)."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from amplifier_app_tui.ui.app import TuiApp
from amplifier_app_tui.ui.demo_wiring import DemoRuntimeAdapter
from amplifier_app_tui.ui.themes import DEFAULT_THEME, register_themes, theme_id
from amplifier_app_tui.ui.timeline_strip import (
    TimelineEntry,
    TimelineStrip,
    snippet_of,
)

from .test_flow_helpers import SIZE, seed_done, type_text, wait_for


class TimelineHost(App[None]):
    """Minimal host app: spec themes + recorded strip messages."""

    def __init__(self) -> None:
        super().__init__()
        register_themes(self)
        self.theme = theme_id(DEFAULT_THEME)
        self.moved: list[str] = []
        self.closed: list[bool] = []
        self.typed: list[str] = []

    def compose(self) -> ComposeResult:
        yield TimelineStrip(id="timeline-strip")

    def on_timeline_strip_moved(self, message: TimelineStrip.Moved) -> None:
        self.moved.append(message.block_id)

    def on_timeline_strip_closed(self, message: TimelineStrip.Closed) -> None:
        self.closed.append(message.kept)

    def on_timeline_strip_type_through(self, message: TimelineStrip.TypeThrough) -> None:
        self.typed.append(message.character)


def _entries(n: int) -> tuple[TimelineEntry, ...]:
    return tuple(TimelineEntry(f"rule-{i}", i + 1, f"prompt {i + 1}") for i in range(n))


def test_snippet_of_first_line_collapsed_and_ellipsized() -> None:
    assert snippet_of("add fuzzy recall") == "add fuzzy recall"
    assert snippet_of("first line\nsecond line") == "first line"
    assert snippet_of("   \n  ") == "(blank prompt)"
    long = "x" * 60
    assert snippet_of(long).endswith("…")
    assert len(snippet_of(long)) == 40


@pytest.mark.asyncio
async def test_empty_list_keeps_the_strip_hidden() -> None:
    app = TimelineHost()
    async with app.run_test(size=SIZE) as pilot:
        strip = app.query_one(TimelineStrip)
        strip.show_entries(())
        await pilot.pause()
        assert not strip.display


@pytest.mark.asyncio
async def test_show_opens_on_the_newest_turn() -> None:
    app = TimelineHost()
    async with app.run_test(size=SIZE) as pilot:
        strip = app.query_one(TimelineStrip)
        strip.show_entries(_entries(3))
        await pilot.pause()
        assert strip.display
        assert strip.index == 2
        assert strip.label_text == 'timeline · turn 3/3 · "prompt 3"'
        assert app.moved == [], "the opening position is the tail -- nothing scrubbed yet"


@pytest.mark.asyncio
async def test_nav_scrubs_live_and_clamps_at_both_ends() -> None:
    app = TimelineHost()
    async with app.run_test(size=SIZE) as pilot:
        strip = app.query_one(TimelineStrip)
        strip.show_entries(_entries(3))
        await pilot.pause()
        for _ in range(5):
            strip.nav(1)
        assert strip.index == 2
        assert app.moved == [], "clamped at the newest turn -- no phantom moves"
        strip.nav(-1)
        strip.nav(-1)
        strip.nav(-1)  # clamp at the oldest
        await pilot.pause()  # Moved messages post async
        assert strip.index == 0
        assert app.moved == ["rule-1", "rule-0"]
        assert strip.label_text == 'timeline · turn 1/3 · "prompt 1"'


@pytest.mark.asyncio
async def test_keep_and_esc_post_distinct_closed_outcomes() -> None:
    app = TimelineHost()
    async with app.run_test(size=SIZE) as pilot:
        strip = app.query_one(TimelineStrip)
        strip.show_entries(_entries(2))
        await pilot.pause()
        strip.keep()
        await pilot.pause()
        assert not strip.display
        strip.show_entries(_entries(2))
        await pilot.pause()
        strip.close_strip()
        await pilot.pause()
        assert app.closed == [True, False]


@pytest.mark.asyncio
async def test_printable_keys_feed_through_for_the_composer() -> None:
    app = TimelineHost()
    async with app.run_test(size=SIZE) as pilot:
        strip = app.query_one(TimelineStrip)
        strip.show_entries(_entries(2))
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        assert app.typed == ["x"]
        assert strip.display, "typing must not close the strip"


# -- app wiring (the real TuiApp over the demo runtime) --------------------------


def _prompts(app: TuiApp) -> list[str]:
    return [b.text for b in app.transcript.blocks if b.kind == "user_line"]


@pytest.mark.asyncio
async def test_ctrl_g_idle_opens_the_strip_and_ctrl_g_again_closes_it() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        assert not app.timeline_strip.display
        await pilot.press("ctrl+g")
        await pilot.pause()
        assert app.timeline_strip.display
        assert app.footer_bar.state.context == "timeline"
        # The newest turn is selected; its label carries the seed prompt.
        assert app.timeline_strip.current is not None
        assert app.timeline_strip.current.snippet == snippet_of(_prompts(app)[-1])
        await pilot.press("ctrl+g")  # toggle-close idiom
        await pilot.pause()
        assert not app.timeline_strip.display
        assert app.footer_bar.state.context == "idle"


@pytest.mark.asyncio
async def test_scrub_moves_the_transcript_and_esc_returns_to_the_tail() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await type_text(pilot, "second turn")
        await pilot.press("enter")
        assert await wait_for(
            pilot, lambda: sum(b.kind == "turn_rule" for b in app.transcript.blocks) >= 2
        )
        visits: list[str] = []
        tail_jumps: list[bool] = []
        original = app.transcript.scroll_block_visible
        app.transcript.scroll_block_visible = lambda block_id, *, top=False: (  # type: ignore[method-assign]
            visits.append(block_id),
            original(block_id, top=top),
        )[1]
        original_end = app.transcript.scroll_end
        app.transcript.scroll_end = lambda **kwargs: (  # type: ignore[method-assign]
            tail_jumps.append(True),
            original_end(**kwargs),
        )[1]
        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        entries = app.timeline_strip.entries
        assert len(entries) == 2
        assert visits == [entries[0].block_id], "scrubbing targets the older turn's rule"
        # Esc closes AND reverts the scroll to the tail (nothing moved for
        # a pure look-around).
        await pilot.press("escape")
        await pilot.pause()
        assert not app.timeline_strip.display
        assert app.footer_bar.state.context == "idle"
        assert tail_jumps, "esc returned the transcript to the tail"


@pytest.mark.asyncio
async def test_enter_keeps_the_landed_scroll_position() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await type_text(pilot, "second turn")
        await pilot.press("enter")
        assert await wait_for(
            pilot, lambda: sum(b.kind == "turn_rule" for b in app.transcript.blocks) >= 2
        )
        visits: list[str] = []
        tail_jumps: list[bool] = []
        original = app.transcript.scroll_block_visible
        app.transcript.scroll_block_visible = lambda block_id, *, top=False: (  # type: ignore[method-assign]
            visits.append(block_id),
            original(block_id, top=top),
        )[1]
        original_end = app.transcript.scroll_end
        app.transcript.scroll_end = lambda **kwargs: (  # type: ignore[method-assign]
            tail_jumps.append(True),
            original_end(**kwargs),
        )[1]
        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert visits, "the cursor scrubbed to an older turn"
        await pilot.press("enter")
        await pilot.pause()
        assert not app.timeline_strip.display
        assert app.footer_bar.state.context == "idle"
        assert not tail_jumps, "enter keeps the landed position -- no tail return"


@pytest.mark.asyncio
async def test_typing_at_the_strip_lands_in_the_composer() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await pilot.press("ctrl+g")
        await pilot.pause()
        await type_text(pilot, "hi")
        await pilot.pause()
        assert app.composer.text == "hi"
        assert app.timeline_strip.display


@pytest.mark.asyncio
async def test_esc_orders_a_live_palette_before_the_strip() -> None:
    app = TuiApp(DemoRuntimeAdapter(instant=True))
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await pilot.press("ctrl+g")
        await pilot.pause()
        await type_text(pilot, "/")
        await pilot.pause()
        assert app.palette.filter_text is not None
        assert app.timeline_strip.display
        await pilot.press("escape")
        await pilot.pause()
        assert app.palette.filter_text is None, "the stateful palette closes first"
        assert app.timeline_strip.display
        await pilot.press("escape")
        await pilot.pause()
        assert not app.timeline_strip.display


@pytest.mark.asyncio
async def test_ctrl_g_with_no_turns_notices_instead_of_opening() -> None:
    async def _fake_clear_context() -> tuple[bool, int]:
        return (True, 4)

    app = TuiApp(DemoRuntimeAdapter(instant=True))
    app.adapter.clear_context = _fake_clear_context
    async with app.run_test(size=SIZE) as pilot:
        await seed_done(pilot, app)
        await type_text(pilot, "/clear")
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: not app.transcript.blocks)
        await pilot.press("ctrl+g")
        assert await wait_for(
            pilot, lambda: app.notice_slot.current == "no turns yet · nothing to scrub"
        )
        assert not app.timeline_strip.display
