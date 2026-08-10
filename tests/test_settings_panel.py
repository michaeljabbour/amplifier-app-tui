"""Pilot tests for the WS3 settings panel (``ui/settings_panel/``).

These drive the real :class:`SettingsApp` over tmp scope files: staged
edits, the redacted review modal, click parity, search, scope cycling, and
the exit protocol. Keys.env-backed fields resolve through the REAL process
environment when no ``environ`` is injected (the panel never injects one),
so every test runs with the provider variables scrubbed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from textual.widgets import Input, Static

from amplifier_app_tui.kernel import setup
from amplifier_app_tui.kernel.bundle_admin import read_scope, write_scope
from amplifier_app_tui.kernel.config import SettingsPaths
from amplifier_app_tui.ui.settings_panel.host import SettingsApp, _ReviewScreen
from amplifier_app_tui.ui.settings_panel.panel import FieldRow, MaintRow, SectionRow

_PROVIDER_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GITHUB_TOKEN",
    "AMPLIFIER_NTFY_TOPIC",
)


@pytest.fixture(autouse=True)
def _isolate_provider_env(monkeypatch: pytest.MonkeyPatch):
    """The panel's resolver reads ``os.environ`` for keys.env-backed fields."""
    for name in _PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield
    # setup.write_key mirrors writes into os.environ — never leak them onward.
    for name in _PROVIDER_ENV_VARS:
        os.environ.pop(name, None)


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


def _status(app: SettingsApp) -> str:
    return str(app.query_one("#status", Static).render())


def _field_rows(app: SettingsApp) -> list[FieldRow]:
    return list(app.query_one("#settings").query(FieldRow))


# -- boot + deep links -------------------------------------------------------


@pytest.mark.asyncio
async def test_boot_lists_sections_and_provider_fields(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.panel
        assert panel.current_section == "providers"
        # Six schema sections plus the synthetic Maintenance section.
        assert [row.section_id for row in panel.query(SectionRow)] == [
            "providers",
            "models-routing",
            "bundles",
            "directory-access",
            "notifications",
            "behavior",
            "maintenance",
        ]
        assert len(_field_rows(app)) == 7
        assert not panel.has_pending
        # Status names the current field and where an edit would land.
        assert "providers.anthropic.api_key" in _status(app)
        assert str(keys) in _status(app)


@pytest.mark.asyncio
async def test_deep_link_start_section(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="notifications")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.panel.current_section == "notifications"
        assert len(_field_rows(app)) == 7


@pytest.mark.asyncio
async def test_unknown_start_section_falls_back_to_providers(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="bogus")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.panel.current_section == "providers"


# -- navigation + click parity ------------------------------------------------


@pytest.mark.asyncio
async def test_tab_and_arrows_move_between_sections(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("tab")  # sections pane
        await pilot.press("down")
        await pilot.pause()
        assert app.panel.current_section == "models-routing"
        assert len(_field_rows(app)) == 2  # routing.matrix + routing.enabled
        await pilot.press("down")
        await pilot.pause()
        assert app.panel.current_section == "bundles"
        await pilot.press("up")
        await pilot.press("up")
        await pilot.pause()
        assert app.panel.current_section == "providers"


@pytest.mark.asyncio
async def test_click_section_row_switches_section(locations) -> None:
    """Sidebar clicks post SectionChosen — parity with arrow navigation."""
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#section-row-4")
        await pilot.pause()
        assert app.panel.current_section == "notifications"
        assert len(_field_rows(app)) == 7


@pytest.mark.asyncio
async def test_click_field_row_selects_it(locations) -> None:
    """Field clicks post FieldChosen — one click selects, no double-step."""
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#field-row-2")
        await pilot.pause()
        assert "providers.azure-openai.api_key" in _status(app)


# -- maintenance section ------------------------------------------------------


@pytest.mark.asyncio
async def test_maintenance_section_is_read_only(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="maintenance")
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.panel
        rows = list(panel.query(MaintRow))
        # version, three offline doctor checks, reset preview, change trail
        assert len(rows) >= 5
        assert not _field_rows(app)
        assert "read-only" in _status(app)
        # enter never edits a maintenance row — it names the terminal command.
        await pilot.press("enter")
        await pilot.pause()
        assert not panel.is_editing
        assert not panel.has_pending
        assert "update" in _status(app)


@pytest.mark.asyncio
async def test_click_maintenance_row_selects_it(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="maintenance")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#maint-row-2")
        await pilot.pause()
        assert app.panel.current_section == "maintenance"
        assert not app.panel.has_pending


# -- editing ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bool_toggle_stages_and_review_save_writes_global_scope(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="notifications")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")  # notifications.suppress: bool, unset -> true
        await pilot.pause()
        panel = app.panel
        pending = panel.pending
        assert pending["notifications.suppress"].op == "set"
        assert pending["notifications.suppress"].parsed is True
        assert "*" not in _status(app)  # marker lives on the row, not the status
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, _ReviewScreen)
        (change,) = app.screen._changes
        assert (change.path, change.action, change.old, change.new) == (
            "notifications.suppress",
            "added",
            "unset",
            "true",
        )
        await pilot.press("enter")  # review: save
        await pilot.pause()
        assert not isinstance(app.screen, _ReviewScreen)
        assert not panel.has_pending
        assert read_scope(paths.global_settings) == {
            "config": {"notifications": {"suppress": True}}
        }
        assert "saved 1 change" in _status(app)


@pytest.mark.asyncio
async def test_enter_cycles_choice_fields(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="directory-access")
    async with app.run_test() as pilot:
        await pilot.pause()
        # write_boundary defaults to "open" — one enter stages "guarded".
        await pilot.press("enter")
        await pilot.pause()
        assert app.panel.pending["tui.permissions.write_boundary"].parsed == "guarded"
        await pilot.press("enter")  # cycles back around
        await pilot.pause()
        assert app.panel.pending["tui.permissions.write_boundary"].parsed == "open"


@pytest.mark.asyncio
async def test_secret_edit_masks_input_and_saves_redacted(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.panel
        await pilot.press("enter")  # providers.anthropic.api_key: secret editor
        await pilot.pause()
        edit = app.query_one("#edit", Input)
        assert panel.is_editing
        assert edit.password is True
        assert edit.value == ""
        edit.value = "sk-test-hunter2"
        await pilot.press("enter")
        await pilot.pause()
        assert not panel.is_editing
        assert "sk-test-hunter2" not in _status(app)
        # The review carries redacted values only.
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, _ReviewScreen)
        (change,) = app.screen._changes
        assert (change.path, change.action, change.old, change.new) == (
            "providers.anthropic.api_key",
            "added",
            "not set",
            "configured",
        )
        await pilot.press("enter")  # save
        await pilot.pause()
        assert setup.read_keys(keys)["ANTHROPIC_API_KEY"] == "sk-test-hunter2"
        # …but the secret never touches the status bar or the change log.
        assert "hunter2" not in _status(app)
        log_text = (keys.parent / "settings-changes.jsonl").read_text(encoding="utf-8")
        assert "hunter2" not in log_text
        assert "configured" in log_text


@pytest.mark.asyncio
async def test_unset_stages_removal_and_save_clears_the_scope(locations) -> None:
    paths, keys = locations
    write_scope(paths.global_settings, {"context": {"max_tokens": 200}})
    app = SettingsApp(paths=paths, keys_path=keys, start_section="behavior")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "context.max_tokens" in _status(app)
        await pilot.press("u")
        await pilot.pause()
        assert app.panel.pending["context.max_tokens"].op == "unset"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, _ReviewScreen)
        (change,) = app.screen._changes
        assert (change.path, change.action, change.old, change.new) == (
            "context.max_tokens",
            "removed",
            "200",
            "unset",
        )
        await pilot.press("enter")
        await pilot.pause()
        # The last key left the scope empty — an empty scope unlinks its file.
        assert not paths.global_settings.exists()


@pytest.mark.asyncio
async def test_unset_on_an_absent_field_reports_nothing_to_unset(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="behavior")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("down")  # context.auto_compact — unset
        await pilot.press("u")
        await pilot.pause()
        assert not app.panel.has_pending
        assert "nothing to unset" in _status(app)


@pytest.mark.asyncio
async def test_invalid_input_keeps_the_editor_open_with_an_error(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="behavior")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")  # context.max_tokens editor
        await pilot.pause()
        app.query_one("#edit", Input).value = "abc"
        await pilot.press("enter")
        await pilot.pause()
        assert app.panel.is_editing  # rejected — the editor stays open
        assert not app.panel.has_pending
        assert "expected a whole number" in _status(app)
        await pilot.press("escape")
        await pilot.pause()
        assert not app.panel.is_editing


# -- scope, search ------------------------------------------------------------


@pytest.mark.asyncio
async def test_scope_cycle_rotates_and_reports_the_target(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.panel
        assert panel.scope == "global"
        await pilot.press("s")
        await pilot.pause()
        assert panel.scope == "project"
        assert "project" in _status(app)
        assert str(paths.project_settings) in _status(app)
        await pilot.press("s")
        await pilot.pause()
        assert panel.scope == "local"
        await pilot.press("s")
        await pilot.pause()
        assert panel.scope == "global"


@pytest.mark.asyncio
async def test_search_filter_narrows_rows_and_escape_restores(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="notifications")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        search = app.query_one("#search", Input)
        assert search.display
        await pilot.press(*"topic")
        await pilot.pause()
        rows = _field_rows(app)
        assert len(rows) == 1
        assert rows[0].field.path == "notifications.push.topic"
        await pilot.press("escape")  # cancels the search, never the panel
        await pilot.pause()
        assert not search.display
        assert len(_field_rows(app)) == 7


# -- save / exit protocol -----------------------------------------------------


@pytest.mark.asyncio
async def test_ctrls_without_staged_edits_does_not_open_the_review(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert not isinstance(app.screen, _ReviewScreen)
        assert "no staged changes" in _status(app)


@pytest.mark.asyncio
async def test_escape_with_nothing_staged_exits_zero(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
    assert app.return_value == 0


@pytest.mark.asyncio
async def test_escape_with_staged_edits_reviews_and_discard_writes_nothing(
    locations,
) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="notifications")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")  # stage notifications.suppress = true
        await pilot.pause()
        await pilot.press("escape")  # staged edits route through the review
        await pilot.pause()
        assert isinstance(app.screen, _ReviewScreen)
        await pilot.press("d")  # discard + exit
    assert app.return_value == 0
    assert read_scope(paths.global_settings) == {}
    assert not keys.exists()


@pytest.mark.asyncio
async def test_review_back_keeps_the_staged_edits(locations) -> None:
    paths, keys = locations
    app = SettingsApp(paths=paths, keys_path=keys, start_section="notifications")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, _ReviewScreen)
        await pilot.press("escape")  # back to the panel, edits intact
        await pilot.pause()
        assert not isinstance(app.screen, _ReviewScreen)
        assert app.panel.has_pending
        assert read_scope(paths.global_settings) == {}
