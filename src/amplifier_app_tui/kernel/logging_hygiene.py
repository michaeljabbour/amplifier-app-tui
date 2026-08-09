"""Process-local logging hygiene for noisy optional integrations."""

from __future__ import annotations

import logging
import threading


class _OncePerMessageFilter(logging.Filter):
    """Allow the first instance of each rendered log message per process."""

    def __init__(self) -> None:
        super().__init__()
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        with self._lock:
            if message in self._seen:
                return False
            self._seen.add(message)
        return True


_installed = False


def install_runtime_log_filters() -> None:
    """Install idempotent filters for warnings repeated by every child mount.

    Invalid user skills remain visible once and remain nonfatal. Delegated
    child sessions mount ``tool-skills`` again, so without this process-local
    filter the same actionable warning can flood the terminal many times.
    """
    global _installed
    if _installed:
        return
    logging.getLogger("amplifier_module_tool_skills.discovery").addFilter(_OncePerMessageFilter())
    _installed = True


__all__ = ["install_runtime_log_filters"]
