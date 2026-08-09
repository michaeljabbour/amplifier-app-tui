"""The durable ``config`` control center and its scriptable read surfaces."""

from __future__ import annotations

import json
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
    assert "config" in result.output


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


def test_config_routes_number_to_existing_provider_console(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        main_mod,
        "_provider_console",
        lambda scope: calls.append(scope) or scope,
    )

    result = CliRunner().invoke(main, ["config"], input="1\nq\nq\n")

    assert result.exit_code == 0, result.output
    assert calls == ["global"]
    assert "Amplifier control center" in result.output
    assert "Configuration complete" in result.output


def test_config_accepts_action_name_and_recovers_from_invalid_choice(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        main_mod,
        "_routing_console",
        lambda scope: calls.append(scope) or scope,
    )

    result = CliRunner().invoke(main, ["config"], input="wat\nmodels and routing\nq\nq\n")

    assert result.exit_code == 0, result.output
    assert "Choose 1-7" in result.output
    assert calls == ["global"]


def test_config_quit_writes_nothing(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: True)
    result = CliRunner().invoke(main, ["config"], input="q\n")
    assert result.exit_code == 0, result.output
    assert not (isolated_config / "settings.yaml").exists()
    assert "Configuration complete" in result.output
    assert f"Write target: global · {isolated_config / 'settings.yaml'}" in result.output


def test_init_no_flags_enters_provider_first_control_center(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_control_center(*, scope: str, start: str) -> int:
        captured.update(scope=scope, start=start)
        return 0

    monkeypatch.setattr(main_mod, "_run_config_control_center", fake_control_center)
    monkeypatch.setattr(main_mod, "_is_interactive_terminal", lambda: True)
    result = CliRunner().invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert captured == {"scope": "global", "start": "providers"}


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
