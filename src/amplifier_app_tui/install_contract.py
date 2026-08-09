"""One source-install contract shared by setup, repair, and update guidance.

The shell bootstrap itself lives in ``scripts/install.sh``.  Keeping its public URL,
the short public install command, and the exact fail-closed wrapper here prevents
the TUI from suggesting several subtly different floating ``uv tool install``
commands.  This module is dependency-free so both ``commands/`` and ``kernel/``
can import it without crossing the ADR-0007 layer boundary.
"""

from __future__ import annotations

import shlex

from .product import REPOSITORY_SLUG, REPOSITORY_URL

APP_REPO_URL = REPOSITORY_URL
APP_INSTALL_URI = f"git+{APP_REPO_URL}"
SOURCE_INSTALL_URL = f"https://raw.githubusercontent.com/{REPOSITORY_SLUG}/main/scripts/install.sh"

_PUBLIC_CURL_INSTALLER = f"curl -fsSL {SOURCE_INSTALL_URL}"
_CURL_INSTALLER = f"curl --proto '=https' --tlsv1.2 -fsSL {SOURCE_INSTALL_URL}"


def source_install_pipeline(*, launch: bool = False, ref: str | None = None) -> str:
    """The inner Bash pipeline, optionally targeting one resolved source revision."""
    launch_args = " --launch" if launch else ""
    ref_args = f" --ref {shlex.quote(ref)}" if ref else ""
    return f"{_CURL_INSTALLER} | bash -s --{launch_args}{ref_args}"


def source_install_command(*, launch: bool = False, ref: str | None = None) -> str:
    """Copy/paste command whose status preserves a failed bootstrap download."""
    return f'bash -o pipefail -c "{source_install_pipeline(launch=launch, ref=ref)}"'


def source_install_argv(*, launch: bool = False, ref: str | None = None) -> list[str]:
    """Argument vector for invoking the same contract without another shell parse."""
    return [
        "bash",
        "-o",
        "pipefail",
        "-c",
        source_install_pipeline(launch=launch, ref=ref),
    ]


PUBLIC_SOURCE_INSTALL_COMMAND = f"{_PUBLIC_CURL_INSTALLER} | bash"
HARDENED_SOURCE_INSTALL_COMMAND = source_install_command()
SOURCE_INSTALL_COMMAND = PUBLIC_SOURCE_INSTALL_COMMAND
SOURCE_INSTALL_LAUNCH_COMMAND = source_install_command(launch=True)


__all__ = [
    "APP_INSTALL_URI",
    "APP_REPO_URL",
    "HARDENED_SOURCE_INSTALL_COMMAND",
    "PUBLIC_SOURCE_INSTALL_COMMAND",
    "SOURCE_INSTALL_COMMAND",
    "SOURCE_INSTALL_LAUNCH_COMMAND",
    "SOURCE_INSTALL_URL",
    "source_install_argv",
    "source_install_command",
    "source_install_pipeline",
]
