"""Conversation inspection preserves the live view and bounds loaded history."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, OptionList, Static

from amplifier_app_tui.ui.history_navigation import HistoryNavigationScreen, copy_delegate_resume


class Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Input(value="Unsent draft", id="draft")
        yield Static("Live transcript remains here", id="live")


def saved(tmp_path: Path, count: int = 1000) -> Path:
    directory = tmp_path / "sessions" / "session"
    directory.mkdir(parents=True)
    with (directory / "ui-events.jsonl").open("w") as handle:
        for number in range(count):
            handle.write(
                json.dumps(
                    {
                        "event_id": f"event-{number}",
                        "session_id": "session",
                        "kind": "prompt_submit",
                        "prompt": f"Early saved turn {number}",
                    }
                )
                + "\n"
            )
    return directory


@pytest.mark.asyncio
async def test_unloaded_early_turn_and_paging_keep_live_draft_and_view(tmp_path: Path) -> None:
    directory = saved(tmp_path)
    app = Harness()
    async with app.run_test(size=(100, 35)) as pilot:
        original = app.screen
        draft = app.query_one("#draft", Input)
        screen = HistoryNavigationScreen(directory, "session")
        await app.push_screen(screen)
        await pilot.pause()
        await screen.workers.wait_for_complete()
        assert screen.query_one("#history-rows", OptionList).option_count == 25
        await pilot.press("enter")
        await screen.workers.wait_for_complete()
        assert "Early saved turn 0" in str(screen.query_one("#history-detail", Static).render())
        assert "Early saved turn 999" not in str(
            screen.query_one("#history-detail", Static).render()
        )
        cursor = screen.next_cursor
        await screen.load_page(cursor)
        assert len(screen.entries) == 25
        assert screen.entries[0]["event_id"] == "event-25"
        screen.dismiss(None)
        await pilot.pause()
        assert app.screen is original
        assert draft.value == "Unsent draft"
        assert "Live transcript remains here" in str(app.query_one("#live", Static).render())


@pytest.mark.asyncio
async def test_legacy_history_has_explicit_unavailable_state(tmp_path: Path) -> None:
    directory = saved(tmp_path, 0)
    (directory / "events.jsonl").write_text("{}\n")
    app = Harness()
    async with app.run_test(size=(80, 30)) as pilot:
        screen = HistoryNavigationScreen(directory, "session")
        await app.push_screen(screen)
        await pilot.pause()
        await screen.workers.wait_for_complete()
        assert "Navigation unavailable" in str(screen.query_one("#history-status", Static).render())
        assert screen.entries == []


def test_copy_resume_is_unavailable_without_live_capability() -> None:
    notices: list[str] = []
    copied: list[str] = []
    app = SimpleNamespace(
        adapter=SimpleNamespace(), show_notice=notices.append, copy_to_clipboard=copied.append
    )
    copy_delegate_resume(app, "unknown")
    assert not copied
    assert "does not advertise" in notices[0]


def test_copy_resume_rejects_foreign_parent_and_copies_known_child(tmp_path: Path) -> None:
    from amplifier_runtime.kernel.delegate_store import DelegateRecord, DelegateStore
    from amplifier_runtime.kernel.persistence import SessionStore

    directory = saved(tmp_path, 0)
    records = DelegateStore(SessionStore(directory.parent))
    records.save(
        DelegateRecord(
            session_id="child",
            parent_id="session",
            agent_name="researcher",
            project_dir=str(tmp_path),
            config={},
            overlay={},
            status="incomplete",
        )
    )
    notices: list[str] = []
    copied: list[str] = []
    coordinator = SimpleNamespace(get_capability=lambda name: lambda: None)
    adapter = SimpleNamespace(
        _runtime=SimpleNamespace(_initialized=SimpleNamespace(coordinator=coordinator)),
        session_dir=directory,
        session_id="other",
    )
    app: Any = SimpleNamespace(
        adapter=adapter, show_notice=notices.append, copy_to_clipboard=copied.append
    )
    copy_delegate_resume(app, "child")
    assert not copied
    adapter.session_id = "session"
    copy_delegate_resume(app, "child")
    assert copied == [
        "Resume delegate child from its saved checkpoint and continue its unfinished task."
    ]
    assert "Copied" in notices[-1]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["page", "window"])
async def test_storage_failure_is_visible_and_does_not_exit_app(
    tmp_path: Path, monkeypatch: Any, operation: str
) -> None:
    import sqlite3
    from amplifier_app_tui.ui import history_navigation

    directory = saved(tmp_path)
    app = Harness()
    async with app.run_test(size=(80, 30)) as pilot:
        screen = HistoryNavigationScreen(directory, "session")
        await app.push_screen(screen)
        await pilot.pause()
        await screen.workers.wait_for_complete()

        def failed(*args: Any, **kwargs: Any) -> Any:
            raise sqlite3.DatabaseError("private filesystem details")

        monkeypatch.setattr(
            history_navigation,
            "history_outline" if operation == "page" else "history_window",
            failed,
        )
        if operation == "page":
            await screen.load_page()
        else:
            await screen.show_entry(0)
        status = str(screen.query_one("#history-status", Static).render())
        assert "storage is unavailable" in status
        assert "private filesystem" not in status
        assert app.screen is screen


@pytest.mark.asyncio
async def test_repeated_requests_do_not_spawn_more_disk_reads_and_cancelled_waiter_recovers(
    tmp_path: Path,
) -> None:
    import asyncio
    import threading

    directory = saved(tmp_path)
    screen = HistoryNavigationScreen(directory, "session")
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def blocked(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(5)
        return {"entries": []}

    task = asyncio.create_task(screen._read(blocked))
    try:
        assert await asyncio.to_thread(started.wait, 5)
        for _ in range(5):
            assert await screen._read(blocked) is None
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await screen._read(blocked) is None
        assert calls == 1
    finally:
        release.set()
        if screen._read_task is not None:
            await screen._read_task
    assert await screen._read(lambda *args: {"entries": []}) == {"entries": []}
