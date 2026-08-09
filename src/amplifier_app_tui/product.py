"""Stable product identity shared by the CLI, runtime, and documentation.

The executable, distribution, repository, on-screen brand, and persisted
protocol identifiers are deliberately *not* derived from one another.  They
have different compatibility contracts.  Keeping the user-facing names here
still makes a future rename an explicit, reviewable edit instead of a search
through hundreds of help strings.

Do not use these values for stored schema/kind identifiers such as
``amplifier-tui/session-export/v1``.  Those are durable data contracts and must
survive a display or executable rename.
"""

from __future__ import annotations

DISPLAY_NAME = "Amplifier TUI"
"""Long product name used in install, diagnostics, and contributor surfaces."""

BRAND_NAME = "Amplifier"
"""Short human-facing brand used by the full-screen app."""

TERMINAL_TITLE = "amplifier"
"""Lower-case title used in the TUI chrome."""

EXECUTABLE_NAME = "amplifier-tui"
"""Installed console script.  ADR-0008 keeps this distinct from ``amplifier``."""

DISTRIBUTION_NAME = "amplifier-app-tui"
"""Python distribution / ``uv tool`` package name."""

REPOSITORY_SLUG = "michaeljabbour/amplifier-app-tui"
REPOSITORY_URL = f"https://github.com/{REPOSITORY_SLUG}"


def command(*parts: str) -> str:
    """Return a display-ready command using the canonical executable name."""

    suffix = " ".join(part.strip() for part in parts if part.strip())
    return f"{EXECUTABLE_NAME} {suffix}" if suffix else EXECUTABLE_NAME


__all__ = [
    "BRAND_NAME",
    "DISPLAY_NAME",
    "DISTRIBUTION_NAME",
    "EXECUTABLE_NAME",
    "REPOSITORY_SLUG",
    "REPOSITORY_URL",
    "TERMINAL_TITLE",
    "command",
]
