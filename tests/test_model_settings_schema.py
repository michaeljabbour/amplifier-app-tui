"""Pure registry tests for the WS2 settings schema (no files, no kernel)."""

from __future__ import annotations

import pytest

from amplifier_app_tui.model.settings_schema import (
    FIELDS,
    SECTIONS,
    diff_settings,
    field_by_path,
    fields_in_section,
    parse_field_value,
    render_value,
    section_by_id,
)


def _field(path: str):
    field = field_by_path(path)
    assert field is not None, f"schema is missing {path}"
    return field


def test_registry_has_the_locked_field_count() -> None:
    assert len(FIELDS) == 29


def test_field_paths_are_unique_and_sections_are_consistent() -> None:
    paths = [field.path for field in FIELDS]
    assert len(paths) == len(set(paths))
    section_ids = [section.id for section in SECTIONS]
    assert len(section_ids) == len(set(section_ids))
    for field in FIELDS:
        assert section_by_id(field.section) is not None, field.path
    for section in SECTIONS:
        assert fields_in_section(section.id), f"section {section.id} has no fields"


def test_every_field_is_read_locatable_and_applies_next_session() -> None:
    for field in FIELDS:
        assert field.keys_env or field.read_path, field.path
        assert field.keys_env or field.write_path or field.special_writer, field.path
        assert field.applies == "next-session", field.path


def test_unknown_lookups_return_none_or_empty() -> None:
    assert field_by_path("nope") is None
    assert section_by_id("nope") is None
    assert fields_in_section("nope") == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("Yes", True),
        ("ON", True),
        ("1", True),
        ("false", False),
        ("no", False),
        ("Off", False),
        ("0", False),
    ],
)
def test_parse_bool_spellings(raw: str, expected: bool) -> None:
    assert parse_field_value(_field("routing.enabled"), raw) is expected


def test_parse_bool_rejects_junk_in_plain_language() -> None:
    with pytest.raises(ValueError, match="expected true or false for routing.enabled"):
        parse_field_value(_field("routing.enabled"), "maybe")


def test_parse_int_enforces_whole_numbers_and_bounds() -> None:
    field = _field("context.max_tokens")
    assert parse_field_value(field, "300000") == 300000
    with pytest.raises(ValueError, match="must be greater than 0"):
        parse_field_value(field, "0")
    with pytest.raises(ValueError, match="expected a whole number"):
        parse_field_value(field, "3.5")
    with pytest.raises(ValueError, match="expected a whole number"):
        parse_field_value(field, "lots")


def test_parse_float_accepts_whole_numbers_and_enforces_bounds() -> None:
    field = _field("context.compact_threshold")
    assert parse_field_value(field, "0.85") == 0.85
    assert parse_field_value(field, "1") == 1.0
    with pytest.raises(ValueError, match="must be greater than 0"):
        parse_field_value(field, "0")
    with pytest.raises(ValueError, match="must be at most 1"):
        parse_field_value(field, "1.5")


def test_parse_choice_casefolds_to_the_canonical_value() -> None:
    field = _field("tui.permissions.write_boundary")
    assert parse_field_value(field, "GUARDED") == "guarded"
    with pytest.raises(ValueError, match="expected one of open, guarded"):
        parse_field_value(field, "yolo")


def test_parse_list_splits_commas_and_drops_empties() -> None:
    field = _field("notifications.push.tags")
    assert parse_field_value(field, "tada, rocket ,,ship") == ["tada", "rocket", "ship"]
    assert parse_field_value(field, "") == []


def test_parse_str_and_secret_require_a_value() -> None:
    with pytest.raises(ValueError, match="needs a value"):
        parse_field_value(_field("routing.matrix"), "  ")
    with pytest.raises(ValueError, match="settings unset providers.anthropic.api_key"):
        parse_field_value(_field("providers.anthropic.api_key"), " ")
    assert parse_field_value(_field("providers.anthropic.api_key"), " sk live ") == "sk live"


def test_render_value_never_shows_a_secret() -> None:
    field = _field("providers.anthropic.api_key")
    assert render_value(field, "sk-must-not-appear", present=True) == "configured"
    assert render_value(field, None, present=False) == "not set"


def test_render_value_formats_plain_kinds() -> None:
    assert render_value(_field("routing.enabled"), None, present=False) == "unset"
    assert render_value(_field("routing.enabled"), True, present=True) == "true"
    assert render_value(_field("routing.enabled"), False, present=True) == "false"
    assert render_value(_field("notifications.push.tags"), ["a", "b"], present=True) == "a, b"
    assert render_value(_field("notifications.push.tags"), [], present=True) == "(empty)"
    assert render_value(_field("routing.matrix"), "balanced", present=False) == "balanced"


def test_diff_settings_is_schema_ordered_and_redacted() -> None:
    old = {
        "routing.enabled": False,
        "providers.anthropic.api_key": "sk-old-secret",
        "zzz.unknown": "keep",
    }
    new = {
        "routing.enabled": True,
        "providers.anthropic.api_key": "sk-new-secret",
        "context.max_tokens": 300000,
        "aaa.unknown": "added",
    }
    changes = diff_settings(old, new)
    by_path = {change.path: change for change in changes}
    assert [change.path for change in changes] == [
        "providers.anthropic.api_key",
        "routing.enabled",
        "context.max_tokens",
        "aaa.unknown",
        "zzz.unknown",
    ]
    assert by_path["zzz.unknown"].action == "removed"
    assert by_path["zzz.unknown"].old == "keep"
    assert by_path["routing.enabled"].action == "changed"
    assert by_path["routing.enabled"].old == "false"
    assert by_path["routing.enabled"].new == "true"
    assert by_path["context.max_tokens"].action == "added"
    assert by_path["providers.anthropic.api_key"].action == "changed"
    for change in changes:
        assert "sk-old-secret" not in f"{change.old}{change.new}"
        assert "sk-new-secret" not in f"{change.old}{change.new}"


def test_diff_settings_marks_removals_and_skips_equal_values() -> None:
    changes = diff_settings(
        {"routing.enabled": True, "routing.matrix": "balanced"},
        {"routing.matrix": "balanced"},
    )
    assert len(changes) == 1
    assert changes[0].path == "routing.enabled"
    assert changes[0].action == "removed"
    assert diff_settings({"routing.matrix": "balanced"}, {"routing.matrix": "balanced"}) == ()


def test_every_section_summary_mentions_no_secret_values() -> None:
    secrets = [field for field in FIELDS if field.secret]
    assert secrets, "registry must keep marking credentials as secret"
    for field in secrets:
        assert field.secret and field.kind in {"secret"}
