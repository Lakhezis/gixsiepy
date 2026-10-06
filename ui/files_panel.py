# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Listas de archivos y acciones de staging, sin ejecutar comandos Git."""

from gi.repository import Gtk, Pango


STATUS_NAMES = {
    "M": "Modificado", "A": "Añadido", "D": "Eliminado", "?": "Sin seguimiento",
    "R": "Renombrado", "C": "Copiado", "T": "Cambio de tipo", "U": "Conflicto",
}


def display_text(value):
    return str(value).encode("utf-8", errors="replace").decode("utf-8")


def display_path(path):
    return display_text(path).replace("\n", "⏎").replace("\r", "␍").replace("\t", "⇥")


class FilesPanel(Gtk.Box):
    def __init__(self, *, on_stage, on_unstage, on_stage_all, on_select):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.on_stage = on_stage
        self.on_unstage = on_unstage
        self.on_stage_all = on_stage_all
        self.on_select = on_select
        self.repository = None
        self.selected_file = None
        self.selected_group = None
        self._blocked = False
        self._updating = False
        groups = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.append(groups)

        changes, self.changes_list, self.changes_count = self._group(
            "CAMBIOS", "Cambios que todavía no están preparados (Stage).",
            "No hay cambios sin preparar.", "changes",
        )
        self.stage_button = Gtk.Button(label="Preparar archivo (Stage)")
        self.stage_button.add_css_class("primary-button")
        self.stage_button.connect("clicked", self._stage_selected)
        self.stage_all_button = Gtk.Button(label="Preparar todos los cambios")
        self.stage_all_button.connect("clicked", self._stage_all)
        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        actions.append(self.stage_button)
        actions.append(self.stage_all_button)
        changes.append(actions)
        groups.append(changes)

        staged, self.staged_list, self.staged_count = self._group(
            "PREPARADOS PARA COMMIT", "Versiones que se incluirán en el próximo commit.",
            "Todavía no hay archivos preparados.", "staged",
        )
        self.unstage_button = Gtk.Button(label="Quitar de staging (Unstage)", halign=Gtk.Align.START)
        self.unstage_button.connect("clicked", self._unstage_selected)
        staged.append(self.unstage_button)
        groups.append(staged)
        self._update_actions()

    def _group(self, title, description, empty_message, name):
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True)
        group.add_css_class("files-group")
        group.add_css_class(f"{name}-group")
        heading = Gtk.Box(spacing=12)
        label = Gtk.Label(label=title, xalign=0, hexpand=True, wrap=True)
        label.add_css_class("files-heading")
        count = Gtk.Label(label="0")
        count.add_css_class("file-count")
        heading.append(label)
        heading.append(count)
        group.append(heading)
        help_label = Gtk.Label(label=description, xalign=0, wrap=True)
        help_label.add_css_class("secondary")
        group.append(help_label)
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, activate_on_single_click=False)
        listing.add_css_class("files-list")
        placeholder = Gtk.Label(label=empty_message, wrap=True)
        placeholder.add_css_class("empty-files")
        listing.set_placeholder(placeholder)
        listing.connect("row-selected", self._selected, name)
        scroll = Gtk.ScrolledWindow(min_content_height=90, max_content_height=150)
        scroll.set_propagate_natural_height(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(listing)
        group.append(scroll)
        return group, listing, count

    def _row(self, file, group):
        code = "U" if file.conflicted else (file.working_status if group == "changes" else file.index_status)
        row = Gtk.ListBoxRow(activatable=False)
        row.file_change = file
        line = Gtk.Box(spacing=12)
        badge = Gtk.Label(label=code, width_chars=2)
        badge.add_css_class("file-state")
        badge.add_css_class({"M": "state-modified", "A": "state-added", "D": "state-deleted",
                             "?": "state-new", "U": "state-conflict"}.get(code, "state-modified"))
        line.append(badge)
        path = file.path
        if file.original_path and code in ("R", "C"):
            path = f"{file.original_path} → {file.path}"
        name = Gtk.Label(label=display_path(path), xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        line.append(name)
        status = STATUS_NAMES.get(code, code)
        if file.submodule.startswith("S"):
            status += " · Submódulo"
        description = Gtk.Label(label=status)
        description.add_css_class("secondary")
        line.append(description)
        row.set_tooltip_text(display_path(path) + "\n" + status)
        row.set_child(line)
        return row

    def set_repository(self, info):
        same_root = self.repository and self.repository.root_path == info.root_path
        previous = (self.selected_file.path, self.selected_group) if same_root and self.selected_file else None
        self.repository = info
        self._updating = True
        self.selected_file = None
        self.selected_group = None
        candidates = {}
        for group, listing, count, files in (
            ("changes", self.changes_list, self.changes_count, info.unstaged_files),
            ("staged", self.staged_list, self.staged_count, info.staged_files),
        ):
            while (row := listing.get_row_at_index(0)) is not None:
                listing.remove(row)
            count.set_text(str(len(files)))
            for file in files:
                row = self._row(file, group)
                listing.append(row)
                candidates[(file.path, group)] = (listing, row)
        if previous:
            selected = candidates.get(previous)
            if selected is None:
                other = "staged" if previous[1] == "changes" else "changes"
                selected = candidates.get((previous[0], other))
            if selected:
                selected[0].select_row(selected[1])
                self.selected_file = selected[1].file_change
                self.selected_group = "changes" if selected[0] is self.changes_list else "staged"
                if previous[1] != self.selected_group:
                    selected[1].grab_focus()
        self._updating = False
        self._update_actions()

    def _selected(self, listing, row, group):
        if self._updating:
            return
        if row is None and group != self.selected_group:
            return
        self._updating = True
        if row:
            other = self.staged_list if listing is self.changes_list else self.changes_list
            other.unselect_all()
            row.grab_focus()
        self.selected_file = row.file_change if row else None
        self.selected_group = group if row else None
        self._updating = False
        self._update_actions()
        self.on_select(self.selected_file, self.selected_group)

    def set_blocked(self, blocked):
        self._blocked = blocked
        self.changes_list.set_sensitive(not blocked)
        self.staged_list.set_sensitive(not blocked)
        self._update_actions()

    def _update_actions(self):
        file = self.selected_file
        self.stage_button.set_sensitive(
            not self._blocked and file is not None and self.selected_group == "changes" and file.can_stage
        )
        self.unstage_button.set_sensitive(
            not self._blocked and file is not None and self.selected_group == "staged" and file.is_staged
        )
        self.stage_all_button.set_sensitive(
            not self._blocked and self.repository is not None and self.repository.can_stage_all
        )

    def _stage_selected(self, _button):
        if self.stage_button.get_sensitive():
            self.on_stage(self.selected_file.path)

    def _unstage_selected(self, _button):
        if self.unstage_button.get_sensitive():
            self.on_unstage(self.selected_file.path)

    def _stage_all(self, _button):
        if self.stage_all_button.get_sensitive():
            self.on_stage_all()
