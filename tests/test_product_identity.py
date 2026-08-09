"""The rename-ready product identity stays aligned with shipped entry points."""

from __future__ import annotations

from pathlib import Path
import re
import tomllib

from click.testing import CliRunner

from amplifier_app_tui.commands import doctor
from amplifier_app_tui.install_contract import APP_REPO_URL, SOURCE_INSTALL_URL
from amplifier_app_tui.kernel import session_factory, updater
from amplifier_app_tui.main import main
from amplifier_app_tui.product import (
    DISPLAY_NAME,
    DISTRIBUTION_NAME,
    EXECUTABLE_NAME,
    REPOSITORY_SLUG,
    REPOSITORY_URL,
    TERMINAL_TITLE,
)
from amplifier_app_tui.ui import chrome

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_product_identity_matches_package_and_console_script() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["name"] == DISTRIBUTION_NAME
    assert pyproject["project"]["scripts"] == {EXECUTABLE_NAME: "amplifier_app_tui.main:main"}


def test_product_identity_drives_runtime_surfaces() -> None:
    assert doctor.PACKAGE_NAME == DISTRIBUTION_NAME
    assert doctor.EXECUTABLE_NAME == EXECUTABLE_NAME
    assert updater.APP_PACKAGE == DISTRIBUTION_NAME
    assert session_factory.APPLICATION_HOST == DISPLAY_NAME
    assert chrome.APP_TITLE_NAME == TERMINAL_TITLE


def test_product_identity_drives_repository_and_installer_contract() -> None:
    assert APP_REPO_URL == REPOSITORY_URL
    assert REPOSITORY_SLUG in SOURCE_INSTALL_URL

    installer = (REPO_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    command_match = re.search(r'^APP_COMMAND="([^"]+)"$', installer, re.MULTILINE)
    display_match = re.search(r'^APP_DISPLAY_NAME="([^"]+)"$', installer, re.MULTILINE)
    repository_match = re.search(r'^REPO_URL_DEFAULT="([^"]+)"$', installer, re.MULTILINE)
    assert command_match is not None
    assert display_match is not None
    assert repository_match is not None
    assert command_match.group(1) == EXECUTABLE_NAME
    assert display_match.group(1) == DISPLAY_NAME
    assert repository_match.group(1) == f"{REPOSITORY_URL}.git"


def test_user_facing_hints_follow_actual_invocation_name() -> None:
    result = CliRunner().invoke(main, ["version"], prog_name="amplifier")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0].startswith("amplifier ")

    flag = CliRunner().invoke(main, ["--version"], prog_name="amplifier")
    assert flag.exit_code == 0, flag.output
    assert flag.output.startswith("amplifier, version ")
