# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Mensaje y validación visual del commit, sin ejecutar Git."""

from gi.repository import Gtk


class CommitPanel(Gtk.Box):
    def __init__(self, *, on_commit):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("commit-panel")
        self.on_commit = on_commit
        self.repository = None
        self._blocked = False
        heading = Gtk.Label(label="GUARDAR CAMBIOS (COMMIT)", xalign=0)
        heading.add_css_class("files-heading")
        self.append(heading)
        self.message_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.message_view.set_accepts_tab(False)
        self.message_view.set_tooltip_text("Mensaje del commit: describí qué cambió y por qué.")
        for side in ("top", "bottom", "left", "right"):
            getattr(self.message_view, f"set_{side}_margin")(10)
        self.buffer = self.message_view.get_buffer()
        self.buffer.connect("changed", lambda _buffer: self._update_actions())
        scroll = Gtk.ScrolledWindow(min_content_height=65)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.message_view)
        scroll.add_css_class("commit-message")
        self.append(scroll)
        footer = Gtk.Box(spacing=12)
        self.help_label = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self.help_label.add_css_class("secondary")
        footer.append(self.help_label)
        self.commit_button = Gtk.Button(label="Hacer commit", valign=Gtk.Align.CENTER)
        self.commit_button.add_css_class("primary-button")
        self.commit_button.connect("clicked", self._commit)
        footer.append(self.commit_button)
        self.append(footer)
        self._update_actions()

    @property
    def message(self):
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def clear_message(self):
        self.buffer.set_text("")

    def set_repository(self, info):
        if self.repository and self.repository.root_path != info.root_path:
            self.clear_message()
        self.repository = info
        self._update_actions()

    def set_blocked(self, blocked):
        self._blocked = blocked
        self._update_actions()

    def _update_actions(self):
        info = self.repository
        ready = info is not None and info.is_repository and info.can_commit
        message = self.message
        self.commit_button.set_sensitive(
            not self._blocked and ready and bool(message.strip()) and "\0" not in message
        )
        self.message_view.set_sensitive(not self._blocked and info is not None and info.is_repository)
        if info and any(file.conflicted for file in info.files):
            help_text = "Resolvé los conflictos antes de hacer un commit."
        elif not ready:
            help_text = "Prepará archivos y escribí qué cambió."
        elif not message.strip():
            help_text = "Escribí un mensaje para tus cambios preparados."
        else:
            count = len(info.staged_files)
            help_text = "Se guardará 1 archivo preparado." if count == 1 else f"Se guardarán {count} archivos preparados."
        self.help_label.set_text(help_text)

    def _commit(self, _button):
        if self.commit_button.get_sensitive():
            self.on_commit(self.message)
