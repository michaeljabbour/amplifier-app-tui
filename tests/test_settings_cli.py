"""The scriptable ``settings get|set|unset`` trio against isolated tmp scopes."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
import pytest

from amplifier_app_tui.main import main


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "amp-home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("AMPLIFIER_HOME", str(home))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # Ambient secrets from the dev shell (or a prior in-process write_key)
    # must not change what these tests resolve.
    monkeypatch.delenv("AMPLIFIER_NTFY_TOPIC", raising=False)
    monkeypatch.chdir(project)
    return home


def test_settings_group_help_lists_the_trio(isolated_config: Path) -> None:
    for args in (["settings"], ["settings", "--help"]):
        result = CliRunner().invoke(main, args)
        assert result.exit_code == 0, result.output
        for verb in ("get", "set", "unset"):
            assert verb in result.output


def test_root_help_offers_settings_under_configure_and_maintain(isolated_config: Path) -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "settings" in result.output


def test_settings_get_bare_lists_sections(isolated_config: Path) -> None:
    result = CliRunner().invoke(main, ["settings", "get"])
    assert result.exit_code == 0, result.output
    for section in ("providers", "models-routing", "bundles", "notifications", "behavior"):
        assert section in result.output


def test_settings_get_section_lists_fields_with_sources(isolated_config: Path) -> None:
    result = CliRunner().invoke(main, ["settings", "get", "notifications"])
    assert result.exit_code == 0, result.output
    assert "notifications.suppress = unset" in result.output
    assert "notifications.push.topic = not set" in result.output
    assert "source:" in result.output


def test_settings_get_unknown_target_fails_with_a_pointer(isolated_config: Path) -> None:
    result = CliRunner().invoke(main, ["settings", "get", "bogus.path"])
    assert result.exit_code == 1
    assert "unknown setting or section 'bogus.path'" in result.output


def test_settings_set_get_unset_round_trip(isolated_config: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["settings", "set", "--project", "context.max_tokens", "12345"])
    assert result.exit_code == 0, result.output
    assert "✓ Set context.max_tokens = 12345" in result.output
    assert "project" in result.output

    result = runner.invoke(main, ["settings", "get", "context.max_tokens"])
    assert result.exit_code == 0, result.output
    assert "12345" in result.output
    assert "source: project" in result.output

    result = runner.invoke(main, ["settings", "unset", "--project", "context.max_tokens"])
    assert result.exit_code == 0, result.output
    assert "✓ Unset context.max_tokens" in result.output

    result = runner.invoke(main, ["settings", "get", "context.max_tokens"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("unset")
    assert "source: default" in result.output

    # Unsetting an already-absent value is an idempotent success.
    result = runner.invoke(main, ["settings", "unset", "--project", "context.max_tokens"])
    assert result.exit_code == 0, result.output
    assert "nothing to do" in result.output


def test_settings_set_conflicting_scope_flags_is_a_usage_error(isolated_config: Path) -> None:
    result = CliRunner().invoke(
        main, ["settings", "set", "--global", "--project", "routing.enabled", "true"]
    )
    assert result.exit_code == 2
    assert "choose exactly one write scope" in result.output


def test_settings_set_invalid_value_is_a_plain_language_usage_error(
    isolated_config: Path,
) -> None:
    result = CliRunner().invoke(main, ["settings", "set", "context.compact_threshold", "5"])
    assert result.exit_code == 2
    assert "context.compact_threshold must be at most 1" in result.output
    # Nothing was written for a rejected value.
    assert not (isolated_config / "settings.yaml").exists()


def test_settings_set_and_unset_unknown_paths_are_usage_errors(isolated_config: Path) -> None:
    for args in (
        ["settings", "set", "bogus.path", "1"],
        ["settings", "unset", "bogus.path"],
    ):
        result = CliRunner().invoke(main, args)
        assert result.exit_code == 2, args
        assert "unknown setting 'bogus.path'" in result.output


def test_settings_secrets_round_trip_through_keys_env_without_echo(
    isolated_config: Path,
) -> None:
    secret = "sk-ant-must-not-appear-12345"
    runner = CliRunner()
    result = runner.invoke(main, ["settings", "set", "providers.anthropic.api_key", secret])
    assert result.exit_code == 0, result.output
    assert "value not shown" in result.output
    assert secret not in result.output
    assert secret in (isolated_config / "keys.env").read_text(encoding="utf-8")

    result = runner.invoke(main, ["settings", "get", "providers.anthropic.api_key"])
    assert result.exit_code == 0, result.output
    assert "configured" in result.output
    assert secret not in result.output

    result = runner.invoke(main, ["settings", "get", "providers"])
    assert result.exit_code == 0, result.output
    assert "providers.anthropic.api_key = configured" in result.output
    assert secret not in result.output

    result = runner.invoke(main, ["settings", "unset", "providers.anthropic.api_key"])
    assert result.exit_code == 0, result.output
    assert secret not in result.output
    assert secret not in (isolated_config / "keys.env").read_text(encoding="utf-8")

    # The change log exists, and the secret never touched it.
    log = isolated_config / "settings-changes.jsonl"
    assert log.exists()
    assert secret not in log.read_text(encoding="utf-8")


def test_settings_set_choice_and_defaults_render(isolated_config: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["settings", "set", "--local", "tui.permissions.write_boundary", "guarded"]
    )
    assert result.exit_code == 0, result.output
    assert (Path.cwd() / ".amplifier" / "settings.local.yaml").exists()
    result = runner.invoke(main, ["settings", "get", "tui.permissions.write_boundary"])
    assert result.exit_code == 0, result.output
    assert "guarded" in result.output
    assert "source: local" in result.output


def test_settings_set_routing_matrix_round_trip(isolated_config: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["settings", "set", "--project", "routing.matrix", "quality"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(main, ["settings", "get", "routing.matrix"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("quality")
    assert "source: project" in result.output
    # config show keeps reading the same value through the service.
    result = runner.invoke(main, ["config", "show", "--json"])
    assert result.exit_code == 0, result.output
    assert '"routing": "quality"' in result.output
