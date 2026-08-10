"""The settings panel widget: every durable setting in one full-screen form.

One sidebar section list (the six schema sections plus a read-only
Maintenance section), one field list for the selected section, a search
filter, a staged-edit model, and a status bar. Edits NEVER write directly:
enter/``u`` stage changes in memory (``*`` marker + ``old → new`` in the
row), ``ctrl+s`` posts :class:`SettingsPanel.ReviewChanges` carrying the
redacted :func:`model.settings_schema.diff_settings` output for the host's
review modal, and only a confirmed review calls the kernel writers.

Secrets follow :func:`model.settings_schema.render_value` everywhere —
``configured`` / ``not set``, and the edit input masks typing for them;
a secret's value never appears in this module's renders, statuses, or
messages.

Esc, like every strip in this app, is never swallowed mid-gesture: it cancels
an open editor or search first, and only with nothing open does it post
:class:`SettingsPanel.ExitRequested` for the host to resolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import MountError
from textual.widgets import Input, Static

from ...kernel import settings_service
from ...kernel.bundle_admin import Scope, scope_file
from ...kernel.config import SettingsPaths
from ...model import settings_schema
from ...model.settings_schema import SettingsField
from .maintenance import MaintRowData, collect_maintenance

MAINTENANCE_SECTION_ID = "maintenance"
"""Synthetic sidebar section appended after the six schema sections."""

SCOPES: tuple[Scope, ...] = ("global", "project", "local")
SCOPE_NOTES: dict[Scope, str] = {
    "global": "default for this user",
    "project": "team-shared, committed",
    "local": "this machine only, gitignored",
}


@dataclass
class PendingEdit:
    """One staged, not-yet-written change to a field.

    ``raw`` feeds :func:`kernel.settings_service.set_value` verbatim (it
    re-parses and validates); ``parsed`` is for the review diff only.
    """

    op: Literal["set", "unset"]
    raw: str = ""
    parsed: Any = None


def _section_ids() -> tuple[str, ...]:
    return tuple(section.id for section in settings_schema.SECTIONS) + (MAINTENANCE_SECTION_ID,)


def _section_title(section_id: str) -> str:
    section = settings_schema.section_by_id(section_id)
    return section.title if section is not None else "Maintenance"


class SectionRow(Static):
    """One clickable sidebar section entry."""

    DEFAULT_CSS = """
    SectionRow {
        width: 100%;
        height: 1;
        padding: 0 1;
    }
    SectionRow.-selected {
        background: $bg-tab;
    }
    """

    def __init__(self, section_id: str, index: int) -> None:
        super().__init__(id=f"section-row-{index}")
        self.section_id = section_id
        self.index = index

    def render(self) -> Text:
        tokens = self.app.theme_variables
        selected = self.has_class("-selected")
        return Text.assemble(
            ("▸ " if selected else "  ", Style(color=tokens.get("green"))),
            (
                _section_title(self.section_id),
                Style(color=tokens.get("fg" if selected else "dim"), bold=selected),
            ),
        )

    def on_click(self) -> None:
        self.post_message(SettingsPanel.SectionChosen(self.section_id))


class FieldRow(Static):
    """One form row: marker, the field's help as its label, value, source.

    Pure display — the panel hands each row an ``EffectiveSetting`` plus any
    staged edit and owns all resolution and writes.
    """

    DEFAULT_CSS = """
    FieldRow {
        width: 100%;
        height: 1;
        padding: 0 1;
    }
    FieldRow.-selected {
        background: $bg-tab;
    }
    """

    def __init__(
        self,
        resolved: settings_service.EffectiveSetting,
        pending: PendingEdit | None,
        index: int,
    ) -> None:
        super().__init__(id=f"field-row-{index}")
        self.resolved = resolved
        self.pending = pending
        self.index = index

    @property
    def field(self) -> SettingsField:
        return self.resolved.field

    def update_data(
        self, resolved: settings_service.EffectiveSetting, pending: PendingEdit | None
    ) -> None:
        self.resolved = resolved
        self.pending = pending
        self.refresh()

    def _value_text(self, tokens) -> Text:  # noqa: ANN001 - theme token mapping
        current = self.resolved.display
        if self.pending is None:
            style = Style(color=tokens.get("fg" if self.resolved.present else "dim"))
            return Text(current, style=style)
        pending_style = Style(color=tokens.get("orange"))
        if self.pending.op == "unset":
            return Text.assemble(
                (current, Style(color=tokens.get("dim"))), (" → unset", pending_style)
            )
        staged = settings_schema.render_value(self.field, self.pending.parsed, True)
        return Text.assemble(
            (current, Style(color=tokens.get("dim"))), (f" → {staged}", pending_style)
        )

    def render(self) -> Table:
        tokens = self.app.theme_variables
        selected = self.has_class("-selected")
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(width=2, no_wrap=True)
        grid.add_column(width=26, no_wrap=True, overflow="ellipsis")
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        grid.add_column(width=12, no_wrap=True, justify="right")
        marker_color = tokens.get("orange") if self.pending is not None else tokens.get("green")
        marker = "*" if self.pending is not None else ("▸" if selected else " ")
        source = "env" if self.resolved.source == "env" else self.resolved.source
        grid.add_row(
            Text(marker, style=Style(color=marker_color)),
            Text(
                self.field.help,
                style=Style(color=tokens.get("fg" if selected else "dim"), bold=selected),
            ),
            self._value_text(tokens),
            Text(source, style=Style(color=tokens.get("dim"))),
        )
        return grid

    def on_click(self) -> None:
        self.post_message(SettingsPanel.FieldChosen(self.field.path))


class MaintRow(Static):
    """One read-only maintenance row: tone icon, label, value."""

    DEFAULT_CSS = """
    MaintRow {
        width: 100%;
        height: 1;
        padding: 0 1;
    }
    MaintRow.-selected {
        background: $bg-tab;
    }
    """

    def __init__(self, data: MaintRowData, index: int) -> None:
        super().__init__(id=f"maint-row-{index}")
        self.data = data
        self.index = index

    def render(self) -> Table:
        tokens = self.app.theme_variables
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(width=2, no_wrap=True)
        grid.add_column(width=26, no_wrap=True, overflow="ellipsis")
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        icon, color = {
            "ok": ("✔", tokens.get("green")),
            "warn": ("!", tokens.get("orange")),
        }.get(self.data.tone, ("·", tokens.get("dim")))
        grid.add_row(
            Text(icon, style=Style(color=color)),
            Text(self.data.label, style=Style(color=tokens.get("dim"))),
            Text(self.data.value, style=Style(color=tokens.get("fg"))),
        )
        return grid

    def on_click(self) -> None:
        self.post_message(SettingsPanel.FieldChosen(f"maintenance:{self.index}"))


class SettingsPanel(Vertical):
    """The full-screen settings form. Posts:

    - :class:`ReviewChanges` — ``ctrl+s`` with edits staged; carries the
      redacted, schema-ordered diff for the host's save/discard/back review.
    - :class:`ExitRequested` — Esc with nothing open; the host decides
      whether staged edits warrant a review first.
    - :class:`SectionChosen` / :class:`FieldChosen` — click parity rows.
    """

    can_focus = True

    DEFAULT_CSS = """
    SettingsPanel {
        background: $bg-page;
    }
    SettingsPanel #body {
        height: 1fr;
    }
    SettingsPanel #sidebar {
        width: 24;
        border-right: solid $rule;
        background: $bg-page;
        scrollbar-size-vertical: 1;
        scrollbar-color: $rule;
        scrollbar-background: $bg-page;
    }
    SettingsPanel #fields {
        width: 1fr;
        background: $bg-page;
        scrollbar-size-vertical: 1;
        scrollbar-color: $rule;
        scrollbar-background: $bg-page;
    }
    SettingsPanel #status {
        height: 1;
        padding: 0 1;
        background: $bg-chrome;
        color: $dim;
    }
    SettingsPanel #search, SettingsPanel #edit {
        display: none;
        height: 1;
        border: none;
        padding: 0 1;
        background: $bg-chrome;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "↑", show=False),
        Binding("down", "cursor_down", "↓", show=False),
        Binding("tab", "toggle_pane", "tab pane", show=False),
        Binding("left", "focus_sections", "← sections", show=False),
        Binding("right", "focus_fields", "→ fields", show=False),
        Binding("enter", "edit", "enter edit", show=False),
        Binding("u", "unset", "u unset", show=False),
        Binding("s", "cycle_scope", "s scope", show=False),
        Binding("slash", "search", "/ filter", show=False),
        Binding("ctrl+s", "save", "ctrl+s save", show=False),
        Binding("escape", "escape", "esc", show=False),
    ]

    class ReviewChanges(Message):
        """``ctrl+s`` with edits staged — review this redacted diff."""

        def __init__(self, changes: tuple[settings_schema.SettingChange, ...]) -> None:
            self.changes = changes
            super().__init__()

    class ExitRequested(Message):
        """Esc with no editor/search open (host decides what's next)."""

    class SectionChosen(Message):
        """Sidebar row clicked."""

        def __init__(self, section_id: str) -> None:
            self.section_id = section_id
            super().__init__()

    class FieldChosen(Message):
        """A field (or maintenance) row clicked — select it."""

        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__()

    def __init__(
        self,
        *,
        paths: SettingsPaths,
        keys_path: Path,
        scope: Scope = "global",
        start_section: str | None = None,
        id: str | None = None,  # noqa: A002 - Textual widget API
    ) -> None:
        super().__init__(id=id)
        self._paths = paths
        self._keys_path = keys_path
        self._scope: Scope = scope
        self._section_ids = _section_ids()
        self._section_index = (
            self._section_ids.index(start_section) if start_section in self._section_ids else 0
        )
        self._field_index = 0
        self._pane: Literal["sections", "fields"] = "fields"
        self._pending: dict[str, PendingEdit] = {}
        self._resolved: dict[str, settings_service.EffectiveSetting] = {}
        self._maintenance: tuple[MaintRowData, ...] = ()
        self._filter = ""
        self._editing: str | None = None
        self._message = ""

    # -- properties used by the host and tests -------------------------

    @property
    def scope(self) -> Scope:
        return self._scope

    @property
    def current_section(self) -> str:
        return self._section_ids[self._section_index]

    @property
    def pending(self) -> dict[str, PendingEdit]:
        return dict(self._pending)

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    @property
    def is_editing(self) -> bool:
        return self._editing is not None

    # -- layout ----------------------------------------------------------

    def compose(self):  # noqa: ANN202 - Textual ComposeResult
        with Horizontal(id="body"):
            yield VerticalScroll(id="sidebar")
            yield VerticalScroll(id="fields")
        yield Input(placeholder="filter settings…", id="search", compact=True)
        yield Input(id="edit", compact=True)
        yield Static(id="status")

    def on_mount(self) -> None:
        self._remount_sidebar()
        self._remount_fields()
        self._update_status()
        self.focus()

    # -- rendering -------------------------------------------------------

    def _remount_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar", VerticalScroll)

        async def _do() -> None:
            await sidebar.remove_children()
            await sidebar.mount(
                *(
                    SectionRow(section_id, index)
                    for index, section_id in enumerate(self._section_ids)
                )
            )
            self._apply_sidebar_selection()

        self.call_later(_do)

    def _visible_section_fields(self) -> tuple[SettingsField, ...]:
        fields = settings_schema.fields_in_section(self.current_section)
        if not self._filter:
            return fields
        needle = self._filter.casefold()
        return tuple(
            field
            for field in fields
            if needle in field.path.casefold() or needle in field.help.casefold()
        )

    def _remount_fields(self) -> None:
        container = self.query_one("#fields", VerticalScroll)
        section = self.current_section
        if section == MAINTENANCE_SECTION_ID:
            self._maintenance = collect_maintenance(self._keys_path.parent)
            rows: list[Static] = [
                MaintRow(data, index) for index, data in enumerate(self._maintenance)
            ]
        else:
            resolved = settings_service.resolve_section(self._paths, self._keys_path, section)
            self._resolved = {item.field.path: item for item in resolved}
            visible = self._visible_section_fields()
            rows = [
                FieldRow(self._resolved[field.path], self._pending.get(field.path), index)
                for index, field in enumerate(visible)
            ]
        self._field_index = min(self._field_index, max(len(rows) - 1, 0))

        async def _do() -> None:
            # A review-then-exit can tear the DOM down mid-repaint; a
            # cosmetic refresh must not outlive its widget.
            try:
                await container.remove_children()
                if rows:
                    await container.mount(*rows)
            except MountError:
                return
            self._apply_field_selection()
            self._update_status()

        self.call_later(_do)

    def _apply_sidebar_selection(self) -> None:
        for row in self.query(SectionRow):
            row.set_class(
                row.index == self._section_index and self._pane == "sections", "-selected"
            )
            if row.index == self._section_index:
                row.scroll_visible()

    def _apply_field_selection(self) -> None:
        selected_row: Static | None = None
        for row in self.query(FieldRow):
            on = row.index == self._field_index and self._pane == "fields"
            row.set_class(on, "-selected")
            if on:
                selected_row = row
        for row in self.query(MaintRow):
            on = row.index == self._field_index and self._pane == "fields"
            row.set_class(on, "-selected")
            if on:
                selected_row = row
        if selected_row is not None:
            selected_row.scroll_visible()

    # -- status bar --------------------------------------------------------

    def _write_target_line(self) -> str:
        return f"{self._scope} · {scope_file(self._paths, self._scope)}"

    def _update_status(self) -> None:
        status = self.query_one("#status", Static)
        if self._message:
            status.update(self._message)
            return
        if self._editing is not None:
            status.update("enter stage · esc cancel")
            return
        if self.current_section == MAINTENANCE_SECTION_ID:
            status.update("read-only · ↑↓ rows · tab sections · esc done")
            return
        rows = list(self.query(FieldRow))
        hint = ""
        if 0 <= self._field_index < len(rows):
            current = rows[self._field_index].field
            target = str(self._keys_path) if current.keys_env else self._write_target_line()
            hint = f"{current.path} · writes → {target}"
        staged = f" · {len(self._pending)} staged" if self._pending else ""
        status.update(f"{hint}{staged} · enter edit · u unset · s scope · / filter · ctrl+s save")

    def show_message(self, text: str) -> None:
        """Transient status message; cleared on the next cursor move."""
        self._message = text
        self._update_status()

    # -- editing -----------------------------------------------------------

    def _current_field_row(self) -> FieldRow | None:
        rows = list(self.query(FieldRow))
        if 0 <= self._field_index < len(rows):
            return rows[self._field_index]
        return None

    def _stage_set(self, field: SettingsField, raw: str) -> bool:
        try:
            parsed = settings_schema.parse_field_value(field, raw)
        except ValueError as error:
            self.show_message(str(error))
            return False
        edit = PendingEdit("set", raw=raw, parsed=parsed)
        resolved = self._resolved.get(field.path)
        if resolved is not None and resolved.present and resolved.value == parsed:
            self._pending.pop(field.path, None)
        else:
            self._pending[field.path] = edit
        row = self._current_field_row()
        if row is not None and row.field.path == field.path:
            row.update_data(row.resolved, self._pending.get(field.path))
        self._message = ""
        self._update_status()
        return True

    def _cycle_choice(
        self, field: SettingsField, resolved: settings_service.EffectiveSetting
    ) -> None:
        options = field.choices
        base = (
            self._pending[field.path].parsed
            if field.path in self._pending and self._pending[field.path].op == "set"
            else resolved.value
        )
        try:
            next_value = options[(options.index(base) + 1) % len(options)]
        except ValueError:
            next_value = options[0]
        self._stage_set(field, next_value)

    def _open_editor(self, row: FieldRow) -> None:
        field = row.field
        edit = self.query_one("#edit", Input)
        edit.password = field.secret
        edit.display = True
        pending = self._pending.get(field.path)
        if field.secret:
            edit.value = ""
            edit.placeholder = f"new value for {field.env_var or field.path} (masked)"
        else:
            current = (
                pending.raw
                if pending is not None and pending.op == "set"
                else settings_schema.render_value(field, row.resolved.value, row.resolved.present)
            )
            edit.value = "" if current == "unset" else current
            edit.placeholder = field.path
        self._editing = field.path
        edit.focus()
        self._update_status()

    def action_edit(self) -> None:
        if self._editing is not None:
            return
        row = self._current_field_row()
        if row is None:
            maint = list(self.query(MaintRow))
            if 0 <= self._field_index < len(maint):
                data = maint[self._field_index].data
                self.show_message(data.hint or "read-only — nothing to edit here")
            return
        field = row.field
        if field.kind == "bool":
            base: Any = (
                self._pending[field.path].parsed
                if field.path in self._pending and self._pending[field.path].op == "set"
                else row.resolved.value
            )
            self._stage_set(field, "false" if base else "true")
        elif field.kind == "choice":
            self._cycle_choice(field, row.resolved)
        else:
            self._open_editor(row)

    def action_unset(self) -> None:
        row = self._current_field_row()
        if row is None:
            return
        path = row.field.path
        if path in self._pending:
            self._pending.pop(path)
            row.update_data(row.resolved, None)
            self._message = ""
            self._update_status()
            return
        if not row.resolved.present:
            self.show_message(f"{path} is not set — nothing to unset")
            return
        self._pending[path] = PendingEdit("unset")
        row.update_data(row.resolved, self._pending[path])
        self._update_status()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "edit" and self._editing is not None:
            field = settings_schema.field_by_path(self._editing)
            if field is not None and self._stage_set(field, event.value):
                self._close_editor()
            return
        if event.input.id == "search":
            event.input.display = False
            self.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._filter = event.value
            self._field_index = 0
            self._remount_fields()

    def _close_editor(self) -> None:
        edit = self.query_one("#edit", Input)
        edit.display = False
        edit.value = ""
        self._editing = None
        self.focus()
        self._update_status()

    # -- review + save -------------------------------------------------------

    def review_changes(self) -> tuple[settings_schema.SettingChange, ...]:
        """The staged edits as a redacted diff against current state."""
        old: dict[str, Any] = {}
        for field in settings_schema.FIELDS:
            resolved = settings_service.resolve_field(self._paths, self._keys_path, field)
            if resolved.present:
                old[field.path] = resolved.value
        new = dict(old)
        for path, edit in self._pending.items():
            if edit.op == "unset":
                new.pop(path, None)
            else:
                new[path] = edit.parsed
        return settings_schema.diff_settings(old, new)

    def write_target_for_review(self) -> str:
        """One line for the review modal: where the confirmed changes land."""
        files = {scope_file(self._paths, self._scope)}
        if any(
            (field := settings_schema.field_by_path(path)) is not None and field.keys_env
            for path in self._pending
        ):
            files.add(self._keys_path)
        return f"{self._scope} · " + " and ".join(str(file) for file in sorted(files))

    def apply_pending(self) -> tuple[int, str]:
        """Persist staged edits in stage order; stop at the first failure.

        Returns ``(applied_count, message)``; the message is the last service
        reply (never echoes a secret — the writers pre-redact).
        """
        applied = 0
        message = ""
        for path, edit in list(self._pending.items()):
            if edit.op == "set":
                ok, message = settings_service.set_value(
                    self._paths, self._keys_path, path, edit.raw, self._scope
                )
            else:
                ok, message = settings_service.unset_value(
                    self._paths, self._keys_path, path, self._scope
                )
            if not ok:
                self.show_message(message)
                self._remount_fields()
                return applied, message
            applied += 1
            del self._pending[path]
        self._message = ""
        self._remount_fields()
        if applied:
            message = f"✓ saved {applied} change(s) · applies next session"
        self.show_message(message or "nothing to save")
        return applied, message

    def discard_pending(self) -> None:
        self._pending.clear()
        self._message = ""
        self._remount_fields()
        self.show_message("staged changes discarded")

    # -- key actions ---------------------------------------------------------

    def action_cursor_up(self) -> None:
        self._move(-1)

    def action_cursor_down(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        self._message = ""
        if self._editing is not None:
            return
        if self._pane == "sections":
            new = max(0, min(len(self._section_ids) - 1, self._section_index + delta))
            if new != self._section_index:
                self._section_index = new
                self._field_index = 0
                self._apply_sidebar_selection()
                self._remount_fields()
        else:
            count = len(list(self.query(FieldRow))) or len(list(self.query(MaintRow)))
            if count:
                self._field_index = max(0, min(count - 1, self._field_index + delta))
                self._apply_field_selection()
        self._update_status()

    def action_toggle_pane(self) -> None:
        self._pane = "fields" if self._pane == "sections" else "sections"
        self._apply_sidebar_selection()
        self._apply_field_selection()
        self._update_status()

    def action_focus_sections(self) -> None:
        self._pane = "sections"
        self._apply_sidebar_selection()
        self._apply_field_selection()

    def action_focus_fields(self) -> None:
        self._pane = "fields"
        self._apply_sidebar_selection()
        self._apply_field_selection()

    def action_cycle_scope(self) -> None:
        index = SCOPES.index(self._scope)
        self._scope = SCOPES[(index + 1) % len(SCOPES)]
        self.show_message(
            f"write scope → {self._scope} ({SCOPE_NOTES[self._scope]}) · "
            f"{scope_file(self._paths, self._scope)}"
        )

    def action_search(self) -> None:
        if self.current_section == MAINTENANCE_SECTION_ID:
            self.show_message("nothing to filter in Maintenance")
            return
        search = self.query_one("#search", Input)
        search.display = True
        search.focus()

    def action_save(self) -> None:
        if self._editing is not None:
            return
        if not self._pending:
            self.show_message("no staged changes — enter edit · u unset · esc done")
            return
        self.post_message(self.ReviewChanges(self.review_changes()))

    def action_escape(self) -> None:
        if self._editing is not None:
            self._close_editor()
            return
        search = self.query_one("#search", Input)
        if search.display:
            search.value = ""
            search.display = False
            self._filter = ""
            self._remount_fields()
            self.focus()
            return
        self.post_message(self.ExitRequested())

    # -- click parity ---------------------------------------------------------

    def on_settings_panel_section_chosen(self, message: SectionChosen) -> None:
        if message.section_id in self._section_ids:
            self._section_index = self._section_ids.index(message.section_id)
            self._field_index = 0
            self._pane = "fields"
            self._apply_sidebar_selection()
            self._remount_fields()
            self._update_status()

    def on_settings_panel_field_chosen(self, message: FieldChosen) -> None:
        if message.path.startswith("maintenance:"):
            try:
                self._field_index = int(message.path.split(":", 1)[1])
            except ValueError:
                return
        else:
            rows = list(self.query(FieldRow))
            for row in rows:
                if row.field.path == message.path:
                    self._field_index = row.index
                    break
        self._pane = "fields"
        self._apply_field_selection()
        self._update_status()


__all__ = [
    "MAINTENANCE_SECTION_ID",
    "SCOPES",
    "SCOPE_NOTES",
    "FieldRow",
    "MaintRow",
    "PendingEdit",
    "SectionRow",
    "SettingsPanel",
]
