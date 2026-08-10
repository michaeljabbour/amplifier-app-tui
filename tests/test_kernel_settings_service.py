"""Kernel tests for the settings service: merge-mirroring, redaction, writes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amplifier_app_tui.kernel import notify_admin, settings_service, setup
from amplifier_app_tui.kernel.bundle_admin import read_scope, write_scope
from amplifier_app_tui.kernel.config import SettingsPaths
from amplifier_app_tui.model import settings_schema


@pytest.fixture
def locations(tmp_path: Path) -> tuple[SettingsPaths, Path]:
    home = tmp_path / "home"
    project = tmp_path / "project"
    (project / ".amplifier").mkdir(parents=True)
    home.mkdir()
    paths = SettingsPaths(
        global_settings=home / "settings.yaml",
        project_settings=project / ".amplifier" / "settings.yaml",
        local_settings=project / ".amplifier" / "settings.local.yaml",
    )
    return paths, home / "keys.env"


def _resolve(paths: SettingsPaths, keys: Path, dotted: str, **kwargs):
    resolved = settings_service.resolve_path(paths, keys, dotted, **kwargs)
    assert resolved is not None, dotted
    return resolved


def test_unset_field_resolves_to_the_schema_default(locations) -> None:
    paths, keys = locations
    resolved = _resolve(paths, keys, "routing.matrix")
    assert resolved.value == "balanced"
    assert resolved.present is False
    assert resolved.source == "default"
    assert resolved.source_file is None
    assert _resolve(paths, keys, "routing.enabled").value is None
    assert _resolve(paths, keys, "routing.enabled").display == "unset"


def test_local_beats_project_beats_global(locations) -> None:
    paths, keys = locations
    write_scope(paths.global_settings, {"context": {"max_tokens": 100}})
    write_scope(paths.project_settings, {"context": {"max_tokens": 200}})
    write_scope(paths.local_settings, {"context": {"max_tokens": 300}})
    resolved = _resolve(paths, keys, "context.max_tokens")
    assert (resolved.value, resolved.source) == (300, "local")
    assert resolved.source_file == paths.local_settings
    paths.local_settings.unlink()
    assert _resolve(paths, keys, "context.max_tokens").source == "project"
    paths.project_settings.unlink()
    assert _resolve(paths, keys, "context.max_tokens").value == 100


def test_namespaced_value_beats_legacy_within_one_scope(locations) -> None:
    paths, keys = locations
    write_scope(
        paths.project_settings,
        {"bundle": {"active": "legacy-one"}, "tui": {"bundle": {"active": "canonical-one"}}},
    )
    resolved = _resolve(paths, keys, "tui.bundle.active")
    assert (resolved.value, resolved.source) == ("canonical-one", "project")


def test_legacy_value_still_resolves_when_no_namespaced_value_exists(locations) -> None:
    paths, keys = locations
    write_scope(paths.project_settings, {"bundle": {"active": "legacy-one"}})
    assert _resolve(paths, keys, "tui.bundle.active").value == "legacy-one"


def test_null_tombstone_in_a_more_specific_scope_masks_less_specific_ones(locations) -> None:
    paths, keys = locations
    write_scope(paths.global_settings, {"bundle": {"active": "global-legacy"}})
    write_scope(paths.local_settings, {"tui": {"bundle": {"active": None}}})
    resolved = _resolve(paths, keys, "tui.bundle.active")
    assert resolved.present is False
    assert resolved.source == "default"
    assert resolved.value == "tui"


def test_junk_intermediate_masks_the_subtree_from_less_specific_scopes(locations) -> None:
    paths, keys = locations
    write_scope(paths.global_settings, {"context": {"max_tokens": 100}})
    write_scope(paths.local_settings, {"context": "not-a-dict"})
    resolved = _resolve(paths, keys, "context.max_tokens")
    assert resolved.present is False
    assert resolved.source == "default"


def test_junk_leaf_resolves_to_default_not_the_junk(locations) -> None:
    paths, keys = locations
    write_scope(paths.project_settings, {"context": {"compact_threshold": 7.5}})
    resolved = _resolve(paths, keys, "context.compact_threshold")
    assert resolved.present is False
    assert resolved.source == "default"
    write_scope(paths.project_settings, {"tui": {"permissions": {"write_boundary": "yolo"}}})
    assert _resolve(paths, keys, "tui.permissions.write_boundary").value == "open"


def test_stored_numbers_coerce_the_way_the_runtime_tolerates(locations) -> None:
    paths, keys = locations
    write_scope(paths.local_settings, {"context": {"compact_threshold": 1, "auto_compact": 1}})
    resolved = _resolve(paths, keys, "context.compact_threshold")
    assert (resolved.value, resolved.present) == (1.0, True)
    # The runtime requires real bools; a stored 1 reads as the default.
    assert _resolve(paths, keys, "context.auto_compact").present is False


def test_env_beats_keys_env_and_empty_env_is_ignored(locations) -> None:
    paths, keys = locations
    keys.write_text("ANTHROPIC_API_KEY=sk-from-file\n", encoding="utf-8")
    resolved = _resolve(
        paths, keys, "providers.anthropic.api_key", environ={"ANTHROPIC_API_KEY": "sk-from-env"}
    )
    assert (resolved.value, resolved.source) == ("sk-from-env", "env")
    resolved = _resolve(paths, keys, "providers.anthropic.api_key", environ={})
    assert (resolved.value, resolved.source) == ("sk-from-file", "keys.env")
    assert resolved.source_file == keys
    resolved = _resolve(
        paths, keys, "providers.anthropic.api_key", environ={"ANTHROPIC_API_KEY": "  "}
    )
    assert resolved.source == "keys.env"


def test_unset_secret_resolves_to_not_set(locations) -> None:
    paths, keys = locations
    resolved = _resolve(paths, keys, "providers.anthropic.api_key", environ={})
    assert (resolved.value, resolved.present, resolved.display) == (None, False, "not set")


def test_set_secret_goes_to_keys_env_and_is_redacted_everywhere(locations) -> None:
    paths, keys = locations
    secret = "sk-ant-must-not-appear-12345"
    ok, message = settings_service.set_value(
        paths, keys, "providers.anthropic.api_key", secret, "global"
    )
    assert ok, message
    assert secret not in message
    assert "value not shown" in message
    assert secret in keys.read_text(encoding="utf-8")
    for scope_file in paths.in_merge_order():
        assert not scope_file.exists() or secret not in scope_file.read_text(encoding="utf-8")
    log_text = (keys.parent / "settings-changes.jsonl").read_text(encoding="utf-8")
    assert secret not in log_text
    record = json.loads(log_text.splitlines()[-1])
    assert record["op"] == "set"
    assert record["path"] == "providers.anthropic.api_key"
    assert record["value"] == "configured"


def test_set_and_unset_round_trip_through_a_scope_file(locations) -> None:
    paths, keys = locations
    ok, message = settings_service.set_value(paths, keys, "context.max_tokens", "250000", "local")
    assert ok, message
    assert read_scope(paths.local_settings)["context"]["max_tokens"] == 250000
    resolved = _resolve(paths, keys, "context.max_tokens")
    assert (resolved.value, resolved.source) == (250000, "local")
    ok, message = settings_service.unset_value(paths, keys, "context.max_tokens", "local")
    assert ok, message
    # Removing the last key prunes empty containers and unlinks the file.
    assert not paths.local_settings.exists()
    assert _resolve(paths, keys, "context.max_tokens").present is False


def test_unset_of_an_absent_value_is_an_idempotent_success(locations) -> None:
    paths, keys = locations
    ok, message = settings_service.unset_value(paths, keys, "context.max_tokens", "project")
    assert ok
    assert "nothing to do" in message
    ok, message = settings_service.unset_value(paths, keys, "providers.openai.api_key", "global")
    assert ok
    assert "nothing to do" in message


def test_unknown_paths_fail_with_a_pointer_to_the_listing(locations) -> None:
    paths, keys = locations
    ok, message = settings_service.set_value(paths, keys, "bogus.path", "1", "global")
    assert not ok
    assert "unknown setting 'bogus.path'" in message
    ok, message = settings_service.unset_value(paths, keys, "bogus.path", "global")
    assert not ok
    assert "settings get" in message
    assert settings_service.resolve_path(paths, keys, "bogus.path") is None


def test_invalid_values_fail_before_any_write(locations) -> None:
    paths, keys = locations
    ok, message = settings_service.set_value(
        paths, keys, "context.compact_threshold", "9", "global"
    )
    assert not ok
    assert "must be at most 1" in message
    assert not paths.global_settings.exists()


def test_routing_matrix_uses_the_routing_admin_write_path(locations) -> None:
    paths, keys = locations
    ok, message = settings_service.set_value(paths, keys, "routing.matrix", "quality", "project")
    assert ok, message
    assert read_scope(paths.project_settings)["routing"]["matrix"] == "quality"
    assert "routing.matrix = quality" in message


def test_active_bundle_uses_the_bundle_admin_write_and_clear_paths(locations) -> None:
    paths, keys = locations
    ok, _ = settings_service.set_value(paths, keys, "tui.bundle.active", "dev-bundle", "project")
    assert ok
    data = read_scope(paths.project_settings)
    assert data["tui"]["bundle"]["active"] == "dev-bundle"
    resolved = _resolve(paths, keys, "tui.bundle.active")
    assert (resolved.value, resolved.source) == ("dev-bundle", "project")
    ok, message = settings_service.unset_value(paths, keys, "tui.bundle.active", "project")
    assert ok, message
    assert _resolve(paths, keys, "tui.bundle.active").value == "tui"


def test_notification_write_paths_match_notify_admin_known_keys() -> None:
    schema_by_suffix = {
        field.path.removeprefix("notifications."): field
        for field in settings_schema.fields_in_section("notifications")
    }
    # notify_admin calls the secret just "topic"; the schema nests it under push.
    aliases = {"topic": "push.topic"}
    for spec in notify_admin.KNOWN_KEYS:
        field = schema_by_suffix[aliases.get(spec.dotted, spec.dotted)]
        if spec.settings_path is None:
            assert field.keys_env, f"{field.path} must persist to keys.env like notify"
            assert field.env_var == notify_admin.NTFY_TOPIC_ENV
            continue
        assert field.write_path == ("config", "notifications", *spec.settings_path), field.path


def test_write_failures_come_back_as_messages_not_exceptions(
    locations, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, keys = locations

    def _boom(*args, **kwargs) -> None:
        raise OSError("disk on fire")

    # settings_service bound write_scope by name at import; patch its binding.
    monkeypatch.setattr(settings_service, "write_scope", _boom)
    ok, message = settings_service.set_value(paths, keys, "context.max_tokens", "10", "local")
    assert not ok
    assert "could not write context.max_tokens to the local scope" in message
    assert "disk on fire" in message
    monkeypatch.undo()

    monkeypatch.setattr(setup, "write_key", _boom)
    ok, message = settings_service.set_value(
        paths, keys, "providers.anthropic.api_key", "sk-x", "global"
    )
    assert not ok
    assert "could not write" in message
    assert "sk-x" not in message


def test_remove_key_is_line_preserving_and_idempotent(locations) -> None:
    _, keys = locations
    keys.write_text(
        "# comment\nANTHROPIC_API_KEY=sk-one\nOPENAI_API_KEY=sk-two\n", encoding="utf-8"
    )
    assert setup.remove_key(keys, "ANTHROPIC_API_KEY", update_environ=False) is True
    remaining = keys.read_text(encoding="utf-8")
    assert "sk-one" not in remaining
    assert "# comment" in remaining
    assert "OPENAI_API_KEY=sk-two" in remaining
    assert setup.remove_key(keys, "ANTHROPIC_API_KEY", update_environ=False) is False
    assert oct(keys.stat().st_mode & 0o777) == "0o600"


def test_change_log_records_sets_and_unsets_redacted(locations) -> None:
    paths, keys = locations
    home = keys.parent
    assert settings_service.recent_changes(home) == []
    settings_service.set_value(paths, keys, "context.max_tokens", "123", "local")
    settings_service.set_value(paths, keys, "notifications.push.topic", "secret-topic", "global")
    settings_service.unset_value(paths, keys, "context.max_tokens", "local")
    records = settings_service.recent_changes(home)
    assert [(r["op"], r["path"]) for r in records] == [
        ("set", "context.max_tokens"),
        ("set", "notifications.push.topic"),
        ("unset", "context.max_tokens"),
    ]
    assert records[0]["value"] == "123"
    assert records[1]["value"] == "configured"
    assert "secret-topic" not in json.dumps(records)
    assert all("at" in record and "scope" in record and "file" in record for record in records)
    assert [r["path"] for r in settings_service.recent_changes(home, limit=1)] == [
        "context.max_tokens"
    ]


def test_no_stray_tmp_files_after_writes(locations) -> None:
    paths, keys = locations
    settings_service.set_value(paths, keys, "routing.enabled", "true", "local")
    settings_service.unset_value(paths, keys, "routing.enabled", "local")
    assert list(paths.local_settings.parent.glob("*.tmp")) == []
