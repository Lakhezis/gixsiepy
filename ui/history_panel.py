"""Lista de commits recientes; solo representa los datos de GitService."""

from gi.repository import Gtk, Pango

from git.git_service import HISTORY_LIMIT
from ui.files_panel import display_text


class HistoryPanel(Gtk.Box):
    def __init__(self, *, on_details):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14, vexpand=True)
        self.add_css_class("history-panel")
        self.on_details = on_details
        self.commits = ()
        self._error = None
        heading = Gtk.Box(spacing=12)
        title = Gtk.Label(label="Historial de commits", xalign=0, hexpand=True)
        title.add_css_class("section-title")
        heading.append(title)
        self.count_label = Gtk.Label(label="0")
        self.count_label.add_css_class("file-count")
        heading.append(self.count_label)
        self.spinner = Gtk.Spinner()
        heading.append(self.spinner)
        self.append(heading)
        description = Gtk.Label(
            label=f"Hasta {HISTORY_LIMIT} commits desde tu posición actual (HEAD), del más reciente hacia atrás.",
            xalign=0, wrap=True,
        )
        description.add_css_class("secondary")
        self.append(description)
        self.message_label = Gtk.Label(xalign=0, wrap=True)
        self.message_label.add_css_class("notice")
        self.append(self.message_label)
        self.listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.listing.add_css_class("history-list")
        self.scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=240)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_child(self.listing)
        self.append(self.scroll)
        self.details_button = Gtk.Button(label="Ver detalles de Git", halign=Gtk.Align.START)
        self.details_button.connect("clicked", lambda _button: self.on_details(self._error))
        self.append(self.details_button)
        self.clear()

    def clear(self, message="Abrí Historial para consultar los commits recientes."):
        self.commits = ()
        self._error = None
        while (row := self.listing.get_row_at_index(0)) is not None:
            self.listing.remove(row)
        self.count_label.set_text("0")
        self.message_label.set_text(display_text(message))
        self.message_label.set_visible(bool(message))
        self.details_button.set_visible(False)
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.scroll.get_vadjustment().set_value(0)

    def show_loading(self):
        self.clear("Consultando los commits recientes…")
        self.spinner.set_visible(True)
        self.spinner.start()

    def show_history(self, commits):
        self.clear("" if commits else "Todavía no hay commits. Prepará archivos y creá tu primer commit en Cambios.")
        self.commits = tuple(commits)
        self.count_label.set_text(str(len(self.commits)))
        for commit in self.commits:
            self.listing.append(self._row(commit))

    def _row(self, commit):
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        heading = Gtk.Box(spacing=16)
        row.message_label = Gtk.Label(
            label=display_text(commit.message) or "(Sin mensaje)", xalign=0, hexpand=True,
            wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, lines=2,
            ellipsize=Pango.EllipsizeMode.END, selectable=True,
        )
        row.message_label.add_css_class("commit-title")
        row.message_label.set_tooltip_text(display_text(commit.message))
        heading.append(row.message_label)
        row.hash_label = Gtk.Label(label=commit.short_hash, selectable=True, valign=Gtk.Align.START)
        row.hash_label.add_css_class("commit-hash")
        row.hash_label.set_tooltip_text("Identificador corto del commit; podés seleccionarlo y copiarlo.")
        heading.append(row.hash_label)
        box.append(heading)
        metadata = Gtk.Box(spacing=16)
        row.author_label = Gtk.Label(
            label=display_text(commit.author) or "Autor sin nombre", xalign=0, hexpand=True,
            ellipsize=Pango.EllipsizeMode.MIDDLE, selectable=True,
        )
        row.author_label.add_css_class("secondary")
        row.author_label.set_tooltip_text(display_text(commit.author))
        metadata.append(row.author_label)
        row.date_label = Gtk.Label(label=commit.authored_at.strftime("%d/%m/%Y · %H:%M %z"), selectable=True)
        row.date_label.add_css_class("secondary")
        row.date_label.set_tooltip_text("Fecha del autor y zona horaria guardadas en el commit.")
        metadata.append(row.date_label)
        box.append(metadata)
        row.set_child(box)
        return row

    def show_error(self, error):
        self.clear(str(error))
        self._error = error
        self.details_button.set_visible(True)
