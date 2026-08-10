"""Full-screen settings panel (WS3): every durable setting in one form.

The terminal entry point is :func:`run_settings_panel`; the in-package
pieces are :class:`SettingsApp` (host + review modal), :class:`SettingsPanel`
(the form widget), and :func:`collect_maintenance` (read-only maintenance
rows). Edits are staged, reviewed as a redacted diff, and only then written
through :mod:`kernel.settings_service`.
"""

from .host import SettingsApp, run_settings_panel
from .maintenance import MaintRowData, collect_maintenance
from .panel import MAINTENANCE_SECTION_ID, PendingEdit, SettingsPanel

__all__ = [
    "MAINTENANCE_SECTION_ID",
    "MaintRowData",
    "PendingEdit",
    "SettingsApp",
    "SettingsPanel",
    "collect_maintenance",
    "run_settings_panel",
]
