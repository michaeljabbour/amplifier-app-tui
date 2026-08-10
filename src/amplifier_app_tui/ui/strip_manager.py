"""StripManager: the overlay-strip open/close/type-through surface (ADR-0007 seam).

The palette / lanes / rewind / timeline / sessions / queued / theme / keys
overlay message handlers used to live directly on
:class:`~amplifier_app_tui.ui.app.TuiApp`; this controller owns them as a
single-purpose unit so the composition root stays a thin shell (ADR-0007's
<500-line budget). Textual resolves message handlers by method name on the
App class, so the app keeps thin ``on_*`` delegating methods; the bodies
below are the verbatim historical implementations with only the host
reference indirected (``self`` -> ``self._app``).

The manager drives the app through a direct app reference (constructed with
the app, like :class:`~amplifier_app_tui.ui.session_ops_controller.SessionOpsController`);
state ownership stays on the app (``self._app.transcript`` and friends).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..model.blocks import Answer
from . import app_support
from .keys_overlay import KeysOverlay
from .lanes_panel import LanesPanel
from .palette import PaletteStrip
from .queued_strip import QueuedStrip
from .rewind_strip import RewindStrip
from .session_ops_view import resume_command_for, session_detail_spans
from .sessions_strip import ResumeSessionRequest, SessionsStrip
from .theme_strip import ThemeStrip
from .themes import THEME_NAME_PREFIX, THEME_TOKENS, theme_id
from .timeline_strip import TimelineStrip

if TYPE_CHECKING:
    from .app import TuiApp


class StripManager:
    """Overlay-strip message handlers and openers (ADR-0007 seam).

    Owns the palette, lanes, rewind, timeline, sessions, queued, theme, and
    keys-overlay strip logic. Behavior is identical to the app's prior inline
    handlers; only the app reference is indirected.
    """

    def __init__(self, app: TuiApp) -> None:
        self._app = app

    # -- palette ------------------------------------------------------------

    def palette_command_run(self, message: PaletteStrip.CommandRun) -> None:
        app = self._app
        message.stop()
        app.composer.clear()
        app.palette.apply_filter(None)
        app._commands.run(message.command.name, app._ctx)
        app._note_command_use(message.command.name)
        app.composer.focus_input()
        app._refresh_footer()

    def palette_closed(self, message: PaletteStrip.Closed) -> None:
        app = self._app
        message.stop()
        app.close_palette()

    # -- lanes --------------------------------------------------------------

    def lanes_focus_lane(self, message: LanesPanel.FocusLane) -> None:
        app = self._app
        message.stop()
        blocks = app.adapter.lane_blocks(message.name, message.session_id, app.allocator)
        if blocks is None:
            # Real sessions have no scripted lane logs — the reducer
            # accumulates each child's diverted events into a focus
            # transcript instead (DESIGN-SPEC §8).
            blocks = app.reducer.lane_transcript(message.session_id or message.name)
        if blocks is None:
            app.show_notice(f"no transcript for lane · {message.name}")
            return
        # The panel stays open while a lane is focused (mockup focusLane
        # never touches lanesOpen); its row snaps to the focused lane.
        app.lanes_panel.set_focused(message.name)
        # Esc must resolve via ESC_CHAIN (lane_focus first, lanes later),
        # so the keyboard returns to the composer, not the panel.
        app.composer.focus_input()
        if not app._lane_focus_intro_shown:
            # First-ever focus transition (S6 AC4): a transient notice
            # announcing the exit path, not a permanent tutorial overlay —
            # never repeats once the user has seen it.
            app._lane_focus_intro_shown = True
            app.show_notice(app_support.LANE_FOCUS_INTRO_NOTICE)
        app.run_worker(
            app.transcript.focus_lane(message.session_id or message.name, blocks),
            exclusive=False,
        )

    def lanes_type_through(self, message: LanesPanel.TypeThrough) -> None:
        # Mockup: the composer input keeps focus while lanesOpen — a
        # printable key typed "at" the panel lands in the composer ("/"
        # opens the palette via the composer's normal edit path) and the
        # keyboard returns to the composer for the rest of the typing.
        app = self._app
        message.stop()
        app.composer.focus_input()
        app.composer.insert_text(message.character)

    def lanes_closed(self, message: LanesPanel.Closed) -> None:
        app = self._app
        message.stop()
        app._restore_keyboard()
        app._refresh_footer()

    # -- rewind -------------------------------------------------------------

    def rewind_fork_requested(self, message: RewindStrip.ForkRequested) -> None:
        app = self._app
        message.stop()
        # The strip hid itself on fork; hand the keyboard back NOW — the
        # approval bar while one is open (it owns the keyboard, spec §7,
        # so Esc still means Deny for a fork parked behind a pending
        # approval), the composer otherwise. A fork-chip click must not
        # strand focus on the hidden strip (spec §12).
        app._restore_keyboard()
        app._refresh_footer()
        app_support.handle_restore(app, message.checkpoint_id, message.scope)

    def rewind_type_through(self, message: RewindStrip.TypeThrough) -> None:
        # Mockup: the composer input keeps focus while rewindOpen — a
        # printable key typed "at" the strip lands in the composer ("/"
        # opens the palette live-filtered, §5) and the keyboard returns
        # to the composer for the rest of the typing.
        app = self._app
        message.stop()
        app.composer.focus_input()
        app.composer.insert_text(message.character)

    def rewind_closed(self, message: RewindStrip.Closed) -> None:
        app = self._app
        message.stop()
        app._restore_keyboard()
        app._refresh_footer()

    # -- timeline -----------------------------------------------------------

    def timeline_moved(self, message: TimelineStrip.Moved) -> None:
        """Cursor move scrubs the transcript live (theme-picker preview idiom)."""
        app = self._app
        message.stop()
        app.transcript.scroll_block_visible(message.block_id, top=True)

    def timeline_type_through(self, message: TimelineStrip.TypeThrough) -> None:
        # Same mockup contract as the rewind picker: printable keys typed
        # at the strip land in the composer ("/" opens the palette live).
        app = self._app
        message.stop()
        app.composer.focus_input()
        app.composer.insert_text(message.character)

    def timeline_closed(self, message: TimelineStrip.Closed) -> None:
        """Enter keeps the landed scroll position; esc returns to the tail --
        a pure look-around must not move anything (theme-picker revert idiom)."""
        app = self._app
        message.stop()
        if not message.kept:
            app.transcript.scroll_end(animate=False, immediate=True)
        app._restore_keyboard()
        app._refresh_footer()

    # -- sessions -----------------------------------------------------------

    def sessions_session_activated(self, message: SessionsStrip.SessionActivated) -> None:
        """A session row was activated (Enter or click) -- S2 gap 1 + 2:
        show its full-id detail (``r``/the trailing glyph is the distinct
        resume action), and
        best-effort copy the full id via the app's existing clipboard
        helper (OSC 52 + OS tool where available; the detail block below
        is the reliable fallback -- terminal clipboard access is
        environment-dependent)."""
        app = self._app
        message.stop()
        summary = next(
            (s for s in app.sessions_strip.summaries if s.session_id == message.session_id),
            None,
        )
        app.sessions_strip.close_strip()
        app._restore_keyboard()
        app._refresh_footer()
        if summary is None:
            return
        app.copy_to_clipboard(summary.session_id)
        app.append_block(Answer(id=app.allocator.next_id(), spans=session_detail_spans(summary)))

    def sessions_resume_requested(self, message: SessionsStrip.ResumeRequested) -> None:
        """``r``, or a click on a row's resume glyph -- Samuel S2 AC4.

        Close the picker, reject rows the canonical resume resolver also
        considers unresumable, then exit with a typed request. Textual's
        shutdown completes (including adapter cleanup) before ``_launch_tui``
        constructs the selected session's fresh runtime. The exact CLI
        command is copied as a fallback, but the key action itself resumes.
        """
        app = self._app
        message.stop()
        summary = next(
            (s for s in app.sessions_strip.summaries if s.session_id == message.session_id),
            None,
        )
        app.sessions_strip.close_strip()
        app._restore_keyboard()
        app._refresh_footer()
        if summary is None:
            return
        from ..kernel.session_manager import RESUMABLE_STATES

        if summary.state not in RESUMABLE_STATES:
            state = summary.state.replace("_", " ")
            app.show_notice(f"cannot resume · session is {state} · enter opens details")
            return
        app.copy_to_clipboard(resume_command_for(summary))
        app.exit(ResumeSessionRequest(summary.session_id))

    def sessions_closed(self, message: SessionsStrip.Closed) -> None:
        app = self._app
        message.stop()
        app._restore_keyboard()
        app._refresh_footer()

    # -- queued -------------------------------------------------------------

    def queued_recall_requested(self, message: QueuedStrip.RecallRequested) -> None:
        message.stop()
        app_support.recall_queued_message(self._app)

    # -- rewind / theme pickers ---------------------------------------------

    def open_rewind_strip(self, index: int | None) -> None:
        app = self._app
        if app.session_ops.context_operation_pending:
            app.show_notice(
                f"{app.session_ops.context_operation_label} in progress · rewind unavailable"
            )
            return
        checkpoints = app.ledger.checkpoints
        if not checkpoints:
            app.show_notice("no rewind checkpoints yet")
            return
        app.rewind.show_checkpoints(checkpoints, index)
        if app.approval_bar is not None:
            app.approval_bar.focus()  # approval owns the keyboard (spec §7)
        app._refresh_footer()

    def open_theme_picker(self) -> None:
        """Bare ``/theme``: open the live-preview theme picker.

        Records the active theme so Esc reverts to it; arrow keys preview
        each theme as a real repaint and enter keeps the highlight.
        """
        app = self._app
        current = app.theme.removeprefix(THEME_NAME_PREFIX)
        app._theme_picker_revert = current
        app.theme_strip.show_picker(tuple(THEME_TOKENS), current=current)
        app._refresh_footer()

    def theme_preview_theme(self, message: ThemeStrip.PreviewTheme) -> None:
        """Live preview: repaint in the highlighted theme (no notice --
        nothing is kept or reverted yet)."""
        app = self._app
        message.stop()
        if message.name in THEME_TOKENS:
            app.theme = theme_id(message.name)

    def theme_theme_chosen(self, message: ThemeStrip.ThemeChosen) -> None:
        """Enter/click keeps the theme: clear the revert marker BEFORE
        closing so the Closed handler doesn't restore the opening theme."""
        app = self._app
        message.stop()
        name = message.name
        app._theme_picker_revert = None
        app.theme_strip.close_strip()
        app._restore_keyboard()
        app._refresh_footer()
        if name in THEME_TOKENS:
            app.theme = theme_id(name)
            app.show_notice(f"theme {name}")

    def theme_closed(self, message: ThemeStrip.Closed) -> None:
        """Esc close reverts the preview to the opening theme (the marker
        is already None when the close followed a keep, so that path
        collapses to just focus/refresh)."""
        app = self._app
        message.stop()
        revert = app._theme_picker_revert
        app._theme_picker_revert = None
        if revert is not None and revert in THEME_TOKENS:
            app.theme = theme_id(revert)
        app._restore_keyboard()
        app._refresh_footer()

    # -- keys overlay ---------------------------------------------------------

    def keys_overlay_closed(self, message: KeysOverlay.Closed) -> None:
        """F1/Esc close returns footer hints to the underlying context."""
        app = self._app
        message.stop()
        app._refresh_footer()


__all__ = ["StripManager"]
