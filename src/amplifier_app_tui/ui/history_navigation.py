"""Bounded conversation inspection, separate from the live transcript reducer."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from amplifier_runtime.kernel.history_navigation import history_outline, history_window
from amplifier_runtime.kernel.persistence import SessionStore
from filelock import Timeout
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Label, OptionList, Static


class HistoryNavigationScreen(Screen[None]):
    """One outline page and one conversation window; closing restores the live view."""

    DEFAULT_CSS = """
    HistoryNavigationScreen { background: $surface; padding: 1 2; }
    #history-title { height: 2; text-style: bold; }
    #history-status { height: 2; color: $text-muted; }
    #history-rows { height: 40%; border: solid $accent; }
    #history-detail-scroll { height: 1fr; border: solid $primary; padding: 0 1; }
    #history-detail { height: auto; }
    #history-actions { height: 3; }
    #history-actions Button { margin-right: 1; }
    """

    def __init__(self, session_dir: Path, session_id: str) -> None:
        super().__init__()
        self.store = SessionStore(session_dir.parent)
        self.session_id = session_id
        self.entries: list[dict[str, Any]] = []
        self.generation: str | None = None
        self.next_cursor: str | None = None
        self._request = 0
        self._read_task: asyncio.Task[Any] | None = None

    def compose(self) -> ComposeResult:
        yield Label("Conversation outline", id="history-title")
        yield Static("Loading saved conversation…", id="history-status", markup=False)
        yield OptionList(id="history-rows")
        with VerticalScroll(id="history-detail-scroll"):
            yield Static(
                "Select a prompt or completed answer. Tool detail stays in the live transcript.",
                id="history-detail",
                markup=False,
            )
        with Horizontal(id="history-actions"):
            yield Button("First page", id="history-first")
            yield Button("Next page", id="history-next", disabled=True)
            yield Button("Return to session", id="history-close", variant="primary")

    def on_mount(self) -> None:
        self.run_worker(self.load_page(), group="history")

    async def _read(self, reader: Any, **kwargs: Any) -> dict[str, Any] | None:
        """Keep one disk operation alive even if its UI waiter is cancelled."""
        if self._read_task is not None and not self._read_task.done():
            if self.is_mounted:
                self.query_one("#history-status", Static).update(
                    "History is still loading; wait before selecting another page."
                )
            return None
        task = asyncio.create_task(asyncio.to_thread(reader, self.store, self.session_id, **kwargs))
        self._read_task = task
        # A dismissed screen can cancel the waiter while the thread finishes.
        # Retrieve failures even when that waiter no longer exists.
        task.add_done_callback(
            lambda completed: completed.exception() if not completed.cancelled() else None
        )
        return await asyncio.shield(task)

    async def load_page(self, cursor: str | None = None) -> None:
        if self._read_task is not None and not self._read_task.done():
            return
        self._request += 1
        request = self._request
        try:
            result = await self._read(history_outline, cursor=cursor, limit=25)
        except (sqlite3.Error, Timeout, OSError):
            if self.is_mounted:
                self.query_one("#history-status", Static).update(
                    "History storage is unavailable. Retry, or return to the session for ordinary history."
                )
            return
        except ValueError as error:
            if request == self._request and self.is_mounted:
                self.query_one("#history-status", Static).update(
                    f"Navigation unavailable: {error}. Return to the session for ordinary history."
                )
            return
        if result is None or request != self._request or not self.is_mounted:
            return
        self.entries = result["entries"]
        self.generation = result["generation"]
        self.next_cursor = result["next_cursor"]
        rows = self.query_one("#history-rows", OptionList)
        rows.clear_options()
        from rich.text import Text

        rows.add_options(
            [
                Text(
                    ("You: " if entry["kind"] == "prompt_submit" else "Answer: ") + entry["preview"]
                )
                for entry in self.entries
            ]
        )
        self.query_one("#history-next", Button).disabled = self.next_cursor is None
        self.query_one("#history-status", Static).update(
            f"{len(self.entries)} saved conversation entries · select to inspect · live session unchanged"
        )
        rows.highlighted = 0 if self.entries else None
        rows.focus()

    async def show_entry(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        if self._read_task is not None and not self._read_task.done():
            return
        self._request += 1
        request = self._request
        try:
            result = await self._read(
                history_window,
                event_id=self.entries[index]["event_id"],
                generation=self.generation,
                before=1,
                after=1,
            )
        except (sqlite3.Error, Timeout, OSError):
            if self.is_mounted:
                self.query_one("#history-status", Static).update(
                    "History storage is unavailable. Retry, or return to the session for ordinary history."
                )
            return
        except ValueError as error:
            if request == self._request and self.is_mounted:
                self.query_one("#history-status", Static).update(
                    f"Cannot open entry: {error}. First page refreshes the outline."
                )
            return
        if result is None or request != self._request or not self.is_mounted:
            return
        text = "\n\n".join(
            ("You\n" + record["prompt"])
            if record["kind"] == "prompt_submit"
            else ("Answer\n" + record["response"])
            for record in result["records"]
        )
        self.query_one("#history-detail", Static).update(text)
        self.query_one("#history-detail-scroll", VerticalScroll).scroll_home(animate=False)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.run_worker(self.show_entry(event.option_index), group="history")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "history-close":
            self.dismiss(None)
        elif event.button.id == "history-first":
            self.run_worker(self.load_page(), group="history")
        elif event.button.id == "history-next" and self.next_cursor:
            self.run_worker(self.load_page(self.next_cursor), group="history")


def open_history(app: Any) -> None:
    """Inspect the connected local session without loading its full transcript."""
    directory = app.adapter.session_dir
    session_id = app.adapter.session_id
    if directory is None or not session_id:
        app.show_notice("Conversation outline needs a saved local session.")
        return
    app.push_screen(HistoryNavigationScreen(directory, session_id))


def copy_delegate_resume(app: Any, child_id: str) -> None:
    """Copy a verified child-resume instruction when the live runtime supports it."""
    from amplifier_runtime.kernel.delegate_store import DelegateStore

    runtime = getattr(app.adapter, "_runtime", None)
    initialized = getattr(runtime, "_initialized", None)
    coordinator = getattr(initialized, "coordinator", None)
    if coordinator is None or not callable(coordinator.get_capability("session.resume")):
        app.show_notice("This session does not advertise delegate recovery.")
        return
    directory = app.adapter.session_dir
    if not child_id or directory is None:
        app.show_notice("Usage: /delegate-resume <child-session-id>")
        return
    try:
        record = DelegateStore(SessionStore(directory.parent)).load(
            child_id, app.adapter.session_id
        )
    except (ValueError, OSError, PermissionError) as error:
        app.show_notice(f"Delegate recovery unavailable: {error}")
        return
    text = f"Resume delegate {record.session_id} from its saved checkpoint and continue its unfinished task."
    app.copy_to_clipboard(text)
    app.show_notice(
        "Copied delegate-resume instruction. Paste it into this parent session to request recovery."
    )
