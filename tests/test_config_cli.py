"""``config`` (hidden panel alias) and ``settings`` CLI wiring contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from click.testing import CliRunner
import pytest

import amplifier_app_tui.main as main_mod
from amplifier_app_tui.main import main


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "amp-home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("AMPLIFIER_HOME", str(home))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(project)
    return home


def test_config_help_explains_session_config_distinction() -> None:
    result = CliRunner().invoke(main, ["config", "--help"])
    assert result.exit_code == 0
    assert "durable app setup" in result.output
    assert "in-session /config" in result.output
    assert "show" in result.output
    assert "paths" in result.output


def test_root_help_groups_commands_by_job() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    for heading in (
        "Start and return",
        "Configure and maintain",
        "Direct configuration",
        "Automation and advanced",
    ):
        assert heading in result.output
    assert re.search(r"^\s+settings\s", result.output, re.MULTILINE)
    # `config` keeps working as a compatibility alias but stays out of help.
    assert not re.search(r"^\s+config\s", result.output, re.MULTILINE)


def test_config_without_tty_fails_fast_with_script_alternatives(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: False)
    result = CliRunner().invoke(main, ["config"])
    assert result.exit_code == 2
    assert "interactive config needs a terminal" in result.output
    assert "config show --json" in result.output
    assert "provider add --help" in result.output


def test_config_show_json_is_redacted_and_stable(isolated_config: Path) -> None:
    secret = "sk-must-not-appear"
    (isolated_config / "keys.env").write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["config", "show", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema"] == "amplifier-app-tui/config/v1"
    assert payload["command"] == "amplifier-tui"
    assert payload["bundle"] == "tui"
    assert payload["provider"] is None
    assert secret not in result.output
    assert "ANTHROPIC_API_KEY" not in result.output


def test_config_paths_json_names_locations_without_reading_secrets(
    isolated_config: Path,
) -> None:
    result = CliRunner().invoke(main, ["config", "paths", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema"] == "amplifier-app-tui/config-paths/v1"
    assert payload["global_settings"] == str(isolated_config / "settings.yaml")
    assert payload["keys"] == str(isolated_config / "keys.env")
    assert "project_settings" in payload
    assert "local_settings" in payload


def _capture_panel(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    def fake_panel(*, section: str | None = None, scope: str = "global") -> int:
        captured.update(section=section, scope=scope)
        return 0

    monkeypatch.setattr(main_mod, "_run_settings_panel", fake_panel)
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: True)
    return captured


def test_config_without_args_opens_the_settings_panel(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bare `config` is the hidden alias: stderr pointer, then the panel."""
    captured = _capture_panel(monkeypatch)
    result = CliRunner().invoke(main, ["config", "--scope", "project"])
    assert result.exit_code == 0, result.output
    assert captured == {"section": None, "scope": "project"}
    assert "opens the settings panel" in result.output
    assert not (isolated_config / "settings.yaml").exists()


def test_settings_without_args_opens_the_panel(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _capture_panel(monkeypatch)
    result = CliRunner().invoke(main, ["settings"])
    assert result.exit_code == 0, result.output
    assert captured == {"section": None, "scope": "global"}
    assert not (isolated_config / "settings.yaml").exists()


def test_settings_section_deep_link(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_panel(monkeypatch)
    result = CliRunner().invoke(main, ["settings", "notifications"])
    assert result.exit_code == 0, result.output
    assert captured == {"section": "notifications", "scope": "global"}

    result = CliRunner().invoke(main, ["settings", "providers", "--scope", "local"])
    assert result.exit_code == 0, result.output
    assert captured == {"section": "providers", "scope": "local"}


def test_settings_unknown_section_errors(isolated_config: Path) -> None:
    result = CliRunner().invoke(main, ["settings", "bogus"])
    assert result.exit_code == 2
    assert "No such command" in result.output


def test_settings_section_without_tty_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: False)
    result = CliRunner().invoke(main, ["settings", "behavior"])
    assert result.exit_code == 2
    assert "the settings panel needs a terminal" in result.output
    assert "settings get" in result.output


def test_settings_without_tty_points_at_scriptable_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: False)
    result = CliRunner().invoke(main, ["settings"])
    assert result.exit_code == 2
    assert "the settings panel needs a terminal" in result.output
    assert "settings get" in result.output
    assert "settings set" in result.output
    assert "config show --json" in result.output


def test_init_no_flags_opens_the_panel_at_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_panel(monkeypatch)
    result = CliRunner().invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert captured == {"section": "providers", "scope": "global"}


def test_init_without_tty_fails_fast_with_automation_alternatives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: False)
    result = CliRunner().invoke(main, ["init"])
    assert result.exit_code == 2
    assert "guided init needs a terminal" in result.output
    assert "init --provider <type> --help" in result.output
    assert "config show --json" in result.output


def test_flagged_init_without_tty_requires_noninteractive_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: False)
    result = CliRunner().invoke(main, ["init", "--provider", "anthropic"])
    assert result.exit_code == 2
    assert "requires `--yes` or `--from-env`" in result.output


def test_provider_add_without_tty_fails_before_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: False)
    result = CliRunner().invoke(main, ["provider", "add", "anthropic"])
    assert result.exit_code == 2
    assert "interactive provider setup needs a terminal" in result.output


def test_routing_manage_without_tty_points_to_direct_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: False)
    result = CliRunner().invoke(main, ["routing", "manage"])
    assert result.exit_code == 2
    assert "interactive routing management needs a terminal" in result.output
    assert "routing use <name>" in result.output


def test_conflicting_write_scope_flags_fail_loud(isolated_config: Path) -> None:
    result = CliRunner().invoke(main, ["bundle", "clear", "--project", "--local"])
    assert result.exit_code == 2
    assert "choose exactly one write scope" in result.output
