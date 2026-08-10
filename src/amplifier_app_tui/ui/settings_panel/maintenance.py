"""Read-only rows behind the settings panel's Maintenance section.

Everything here is offline and side-effect-free: the installed-version
identity comes from the distribution's own metadata, only the three doctor
checks that never touch the network run, the reset row is a dry-run preview
against the safe default categories (cache/registry — secrets never in
scope), and the change trail is the service's pre-redacted JSONL log. Rows
that correspond to a real action carry a ``hint`` naming the exact terminal
command instead of pretending the panel ran it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ...commands import doctor
from ...kernel import reset, settings_service, updater
from ...product import EXECUTABLE_NAME

Tone = Literal["ok", "warn", "info"]
"""Row accent: green check, orange finding, or plain dim information."""

RECENT_CHANGES_LIMIT = 5


@dataclass(frozen=True)
class MaintRowData:
    """One read-only maintenance row: label, value, accent, terminal hint."""

    id: str
    label: str
    value: str
    tone: Tone = "info"
    hint: str = ""


def _reset_preview(home: Path) -> MaintRowData:
    """Dry-run the safe-default reset so the panel can show what WOULD clear."""
    try:
        report = reset.run_reset(home, set(reset.DEFAULT_CATEGORIES), dry_run=True)
    except reset.ResetError as error:
        return MaintRowData("reset", "Safe reset preview", str(error), tone="warn")
    value = (
        f"would clear {len(report.removed)} cache/registry path(s), "
        f"keep {len(report.preserved)} (keys and settings never touched)"
    )
    return MaintRowData(
        "reset",
        "Safe reset preview",
        value,
        hint=f"run in terminal: `{EXECUTABLE_NAME} reset --dry-run`",
    )


def collect_maintenance(home: Path) -> tuple[MaintRowData, ...]:
    """Every maintenance row, oldest concerns first; never raises."""
    rows: list[MaintRowData] = [
        MaintRowData(
            "version",
            "Installed version",
            updater.app_identity().label(),
            hint=f"check for an app update: `{EXECUTABLE_NAME} update`",
        )
    ]

    # Offline doctor subset: the checks that never spawn a subprocess, read
    # another machine's state, or contact a provider.
    for check in (
        doctor.check_install(),
        doctor.check_path(),
        doctor.check_platform(*doctor.detect_platform()),
    ):
        rows.append(
            MaintRowData(
                f"doctor-{check.name}",
                f"Doctor · {check.name.replace('_', ' ')}",
                check.message,
                tone="ok" if check.ok else "warn",
                hint="" if check.ok else f"full diagnosis: `{EXECUTABLE_NAME} doctor`",
            )
        )

    rows.append(_reset_preview(home))

    records = settings_service.recent_changes(home, limit=RECENT_CHANGES_LIMIT)
    if not records:
        rows.append(MaintRowData("changes", "Recent settings changes", "none recorded yet"))
    for record in reversed(records):  # newest first on screen
        rows.append(
            MaintRowData(
                "change",
                str(record.get("at", "?")),
                (
                    f"{record.get('op', '?')} {record.get('path', '?')} = "
                    f"{record.get('value', '?')} ({record.get('scope', '?')})"
                ),
            )
        )
    return tuple(rows)


__all__ = [
    "RECENT_CHANGES_LIMIT",
    "MaintRowData",
    "Tone",
    "collect_maintenance",
]
