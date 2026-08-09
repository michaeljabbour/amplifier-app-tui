from __future__ import annotations

import logging

from amplifier_app_tui.kernel.logging_hygiene import _OncePerMessageFilter


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord("skills", logging.WARNING, __file__, 1, message, (), None)


def test_once_per_message_filter_keeps_first_actionable_warning_only() -> None:
    warning_filter = _OncePerMessageFilter()
    first = _record("Invalid YAML in /tmp/skill/SKILL.md")
    repeated = _record("Invalid YAML in /tmp/skill/SKILL.md")
    different = _record("Skill name does not match directory")

    assert warning_filter.filter(first) is True
    assert warning_filter.filter(repeated) is False
    assert warning_filter.filter(different) is True
