"""Preserve incomplete orchestrator endings across upstream status drift.

The pinned streaming loop emits ``provider:request(max_reached=True)`` when
its iteration/token cap is exhausted, then asks the model for a progress
summary. Upstream currently labels any non-empty summary as success. This
root-session hook keeps the earlier mechanical stop signal authoritative so
the UI cannot present partial work as a completed answer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from amplifier_core import HookResult


class CompletionIntegrityTracker:
    """Downgrade max-reached completion payloads to ``incomplete``."""

    def __init__(self) -> None:
        self._max_reached: set[str] = set()

    async def handle_event(self, event: str, data: dict[str, Any]) -> HookResult:
        payload = data or {}
        session_id = str(payload.get("session_id") or "")
        if event == "provider:request" and bool(payload.get("max_reached")):
            self._max_reached.add(session_id)
        elif event == "orchestrator:complete":
            if session_id in self._max_reached:
                payload["status"] = "incomplete"
            self._max_reached.discard(session_id)
        return HookResult(action="continue")

    def register_hooks(self, hooks: Any, *, priority: int = 100) -> Callable[[], None]:
        unregisters = [
            hooks.register(
                event,
                self.handle_event,
                priority=priority,
                name=f"tui-completion-integrity-{event.replace(':', '-')}",
            )
            for event in ("provider:request", "orchestrator:complete")
        ]

        def unregister_all() -> None:
            for unregister in reversed(unregisters):
                if callable(unregister):
                    unregister()

        return unregister_all


__all__ = ["CompletionIntegrityTracker"]
