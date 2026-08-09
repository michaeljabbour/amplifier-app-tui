from __future__ import annotations

import pytest

from amplifier_app_tui.kernel.completion_integrity import CompletionIntegrityTracker


@pytest.mark.asyncio
async def test_max_reached_forces_incomplete_completion() -> None:
    tracker = CompletionIntegrityTracker()
    await tracker.handle_event("provider:request", {"session_id": "root", "max_reached": True})
    completion = {"session_id": "root", "status": "success"}
    await tracker.handle_event("orchestrator:complete", completion)
    assert completion["status"] == "incomplete"


@pytest.mark.asyncio
async def test_normal_completion_stays_success() -> None:
    tracker = CompletionIntegrityTracker()
    completion = {"session_id": "root", "status": "success"}
    await tracker.handle_event("orchestrator:complete", completion)
    assert completion["status"] == "success"
