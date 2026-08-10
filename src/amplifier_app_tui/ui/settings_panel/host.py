"""The standalone settings host: ``SettingsApp`` + ``run_settings_panel``.

This is the terminal entry point behind the bare ``settings`` / ``config`` /
``init`` CLI commands (WS3 Phase A). Unlike the in-session app
(:class:`ui.app.AmplifierApp`), this host is intentionally tiny: a title bar,
the :class:`~.panel.SettingsPanel`, and one save/discard/back review
:class:`ModalScreen` fed by the panel's redacted :func:`diff_settings`
output. Nothing here touches the network, spawns a session, or mounts a
bundle — it is a form over :mod:`kernel.settings_service`.

Exit protocol: Esc with no staged edits exits ``0`` immediately; Esc (or the
review's own choices) with staged edits routes through the review modal
first, so a staged change can never be silently dropped or silently saved.
``App.run()`` returns ``None`` on a bare ctrl+c quit, which
``run_settings_panel`` coerces to ``0``.
"""

from __future__ import annotations

from pathlib import Path

from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ..themes import DEFAULT_THEME, register_themes, theme_id
from ...kernel import setup
from ...kernel.bundle_admin import Scope, settings_paths
from ...kernel.config import SettingsPaths
from ...model import settings_schema
from ...product import TERMINAL_TITLE
from .panel import SettingsPanel


class _ReviewScreen(ModalScreen[str]):
    """Save/discard/back review of staged edits, values pre-redacted."""

    BINDINGS = [
        Binding("enter", "save", "enter save", show=False),
        Binding("d", "discard", "d discard", show=False),
        Binding("escape", "back", "esc back", show=False),
    ]

    DEFAULT_CSS = """
    _ReviewScreen {
        align: center middle;
    }
    _ReviewScreen #dialog {
        width: 76;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        background: $bg-chrome;
        border: solid $rule;
    }
    _ReviewScreen #review-title {
        text-style: bold;
        color: $bright;
        padding-bottom: 1;
    }
    _ReviewScreen #review-target {
        color: $dim;
        padding-top: 1;
    }
    _ReviewScreen #review-hints {
        color: $dim;
        padding-top: 1;
    }
    """

    def __init__(
        self, changes: tuple[settings_schema.SettingChange, ...], write_target: str
    ) -> None:
        super().__init__()
        self._changes = changes
        self._write_target = write_target

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Review staged settings changes", id="review-title")
            yield Static(self._changes_table(), id="review-changes")
            yield Static(f"writes → {self._write_target}", id="review-target")
            yield Static("enter save · d discard · esc back", id="review-hints")

    def _changes_table(self) -> Table:
        tokens = self.app.theme_variables
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(width=32, no_wrap=True, overflow="ellipsis")
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        action_color = {
            "added": tokens.get("green"),
            "changed": tokens.get("orange"),
            "removed": tokens.get("red"),
        }
        for change in self._changes:
            grid.add_row(
                Text(change.path, style=Style(color=tokens.get("fg"))),
                Text(change.old or "not set", style=Style(color=tokens.get("dim"))),
                Text(
                    change.new or "unset",
                    style=Style(color=action_color.get(change.action, tokens.get("fg"))),
                ),
            )
        return grid

    def action_save(self) -> None:
        self.dismiss("save")

    def action_discard(self) -> None:
        self.dismiss("discard")

    def action_back(self) -> None:
        self.dismiss("back")


class SettingsApp(App[int]):
    """Full-screen standalone settings editor over one scope's files."""

    CSS = """
    SettingsApp {
        background: $bg-page;
    }
    SettingsApp #title-bar {
        height: 1;
        padding: 0 1;
        background: $bg-chrome;
        color: $title-fg;
        text-style: bold;
    }
    """

    def __init__(
        self,
        *,
        paths: SettingsPaths,
        keys_path: Path,
        scope: Scope = "global",
        start_section: str | None = None,
    ) -> None:
        super().__init__()
        register_themes(self)  # before first stylesheet parse (themes.py NOTES)
        self.theme = theme_id(DEFAULT_THEME)
        self._panel = SettingsPanel(
            paths=paths,
            keys_path=keys_path,
            scope=scope,
            start_section=start_section,
            id="settings",
        )

    @property
    def panel(self) -> SettingsPanel:
        return self._panel

    def compose(self) -> ComposeResult:
        yield Static(f"{TERMINAL_TITLE} · settings", id="title-bar")
        yield self._panel

    # -- message handlers (messages bubble up from the panel) -----------

    def on_settings_panel_exit_requested(self) -> None:
        if self._panel.has_pending:
            self._push_review(exit_after=True)
        else:
            self.exit(0)

    def on_settings_panel_review_changes(self, message: SettingsPanel.ReviewChanges) -> None:
        self._open_review(changes=message.changes, exit_after=False)

    def _push_review(self, *, exit_after: bool) -> None:
        self._open_review(changes=self._panel.review_changes(), exit_after=exit_after)

    def _open_review(
        self,
        *,
        changes: tuple[settings_schema.SettingChange, ...],
        exit_after: bool,
    ) -> None:
        if not changes:
            if exit_after:
                self.exit(0)
            return

        def _resolve(result: str | None) -> None:
            if result == "save":
                self._panel.apply_pending()
                if exit_after and not self._panel.has_pending:
                    self.exit(0)
            elif result == "discard":
                self._panel.discard_pending()
                if exit_after:
                    self.exit(0)
            # "back" / dismissed: stay in the panel with edits intact.

        self.push_screen(_ReviewScreen(changes, self._panel.write_target_for_review()), _resolve)


def run_settings_panel(
    *,
    section: str | None = None,
    scope: Scope = "global",
    paths: SettingsPaths | None = None,
    keys_path: Path | None = None,
) -> int:
    """Run the full-screen settings panel; return a process exit code."""
    resolved_paths = paths or settings_paths(None, None)
    resolved_keys = keys_path or setup.keys_file()
    app = SettingsApp(
        paths=resolved_paths,
        keys_path=resolved_keys,
        scope=scope,
        start_section=section,
    )
    result = app.run()
    return 0 if result is None else result


__all__ = [
    "SettingsApp",
    "run_settings_panel",
]
