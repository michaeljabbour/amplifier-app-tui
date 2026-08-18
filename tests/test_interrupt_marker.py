"""Model-visible context marker for an accepted Esc interrupt.

The marker rides on a **user**-role message, and both halves of that are load
bearing. Not ``assistant``: an interrupt is a fact about the environment, not
something the model said, and persisted as assistant speech it becomes the
model's own last utterance -- a strong pattern to continue, so the next reply
parrots being interrupted and each interrupt appends another. Not ``system``
either: the Anthropic provider extracts system-role messages out of the
conversation into the single top-level system block, so one of these would
rewrite that block on every interrupt and bust its cache breakpoint.

If this assertion ever fails because the role changed back, read
``TURN_ABORTED_MARKER``'s docstring in amplifier-runtime before "fixing" it.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from amplifier_app_tui.kernel.git_yield import GitDiffSnapshot
from amplifier_app_tui.kernel.runtime import (
    TURN_ABORTED_MARKER,
    RealRuntime,
    restored_history,
)


@pytest.mark.asyncio
async def test_interrupt_appends_marker_before_end_of_turn_save() -> None:
    started = asyncio.Event()
    released = asyncio.Event()

    class Context:
        def __init__(self) -> None:
            self.messages: list[dict[str, str]] = []

        async def add_message(self, message: dict[str, str]) -> None:
            self.messages.append(message)

    context = Context()

    class Cancellation:
        def request_graceful(self) -> None:
            released.set()

    class Coordinator:
        cancellation = Cancellation()

        def get(self, capability: str):  # noqa: ANN201 - focused fake
            return context if capability == "context" else None

    class Session:
        async def execute(self, prompt: str) -> str:
            del prompt
            started.set()
            await released.wait()
            return ""

    class Saver:
        def __init__(self) -> None:
            self.saved_messages: list[dict[str, str]] = []

        async def maybe_save(self) -> bool:
            self.saved_messages = list(context.messages)
            return True

    runtime = RealRuntime()
    runtime._initialized = SimpleNamespace(
        session_id="session-id", coordinator=Coordinator(), session=Session()
    )
    runtime._saver = Saver()

    async def no_diff() -> GitDiffSnapshot:
        return GitDiffSnapshot(False)

    runtime._capture_diff = no_diff  # type: ignore[method-assign]

    turn = asyncio.create_task(runtime.submit("start a long task"))
    await started.wait()
    assert await runtime.interrupt()
    assert await turn == ""

    marker = {"role": "user", "content": TURN_ABORTED_MARKER}
    assert context.messages == [marker]
    assert runtime._saver.saved_messages == [marker]
    assert restored_history(context.messages) == ()
