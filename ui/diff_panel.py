"""Visor de parches Git con resaltado de líneas y selección de texto."""

from gi.repository import Gtk, Pango

from ui.files_panel import display_path, display_text


class DiffPanel(Gtk.Box):
    def __init__(self, on_details):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True, vexpand=True)
        self.add_css_class("diff-panel")
        self.set_size_request(280, -1)
        self.on_details = on_details
        self._error = None
        heading = Gtk.Box(spacing=12)
        title = Gtk.Label(label="CAMBIOS DEL ARCHIVO", xalign=0, hexpand=True)
        title.add_css_class("files-heading")
        self.spinner = Gtk.Spinner()
        heading.append(title)
        heading.append(self.spinner)
        self.append(heading)
        self.path_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE, selectable=True)
        self.path_label.add_css_class("section-title")
        self.append(self.path_label)
        self.comparison_label = Gtk.Label(xalign=0, wrap=True)
        self.comparison_label.add_css_class("secondary")
        self.append(self.comparison_label)
        self.message_label = Gtk.Label(xalign=0, wrap=True)
        self.message_label.add_css_class("notice")
        self.append(self.message_label)

        self.text_view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.NONE)
        self.text_view.add_css_class("diff-text")
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)
        self.buffer = self.text_view.get_buffer()
        self.buffer.create_tag("added", foreground="#245331", paragraph_background="#e6f3e2")
        self.buffer.create_tag("removed", foreground="#7a293d", paragraph_background="#fde1e3")
        self.buffer.create_tag("header", foreground="#47514b", paragraph_background="#fff0c4", weight=Pango.Weight.BOLD)
        self.scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=240)
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_child(self.text_view)
        self.append(self.scroll)
        self.details_button = Gtk.Button(label="Ver detalles de Git", halign=Gtk.Align.START)
        self.details_button.connect("clicked", lambda _button: self.on_details(self._error))
        self.append(self.details_button)
        legend = Gtk.Label(label="+ Añadido    − Eliminado    @@ Bloque de cambios", xalign=0, wrap=True)
        legend.add_css_class("secondary")
        self.append(legend)
        self.clear()

    def _reset(self):
        self._error = None
        self.details_button.set_visible(False)
        self.message_label.set_visible(False)
        self.buffer.set_text("")
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.scroll.get_vadjustment().set_value(0)
        self.scroll.get_hadjustment().set_value(0)

    def clear(self, message="Seleccioná un archivo para consultar sus cambios."):
        self._reset()
        self.path_label.set_text("Tu próxima revisión")
        self.path_label.set_tooltip_text(None)
        self.comparison_label.set_text(message)

    def show_loading(self, path, staged):
        self._reset()
        self.path_label.set_text(display_path(path))
        self.path_label.set_tooltip_text(display_path(path))
        self.comparison_label.set_text(
            "Preparado: cambios que irán al próximo commit" if staged else "Sin preparar: staging → carpeta de trabajo"
        )
        self.spinner.set_visible(True)
        self.spinner.start()

    def show_diff(self, diff):
        self.show_loading(diff.path, diff.staged)
        self.spinner.stop()
        self.spinner.set_visible(False)
        notices = [diff.message] if diff.message else []
        if diff.truncated:
            notices.append("Vista previa recortada: se muestran hasta 512 KiB o 5000 líneas. Consultá Git en la terminal para ver el diff completo.")
        self.message_label.set_text("\n\n".join(notices))
        self.message_label.set_visible(bool(notices))
        text = display_text(diff.text).replace("\0", "␀")
        self.buffer.set_text(text)
        offset = 0
        in_hunk = False
        for line in text.split("\n"):
            tag = None
            if line.startswith("diff --git "):
                in_hunk = False
            if line.startswith("@@"):
                in_hunk = True
                tag = "header"
            elif not in_hunk:
                tag = "header"
            elif line.startswith("+"):
                tag = "added"
            elif line.startswith("-"):
                tag = "removed"
            if tag:
                start = self.buffer.get_iter_at_offset(offset)
                end = self.buffer.get_iter_at_offset(offset + len(line))
                self.buffer.apply_tag_by_name(tag, start, end)
            offset += len(line) + 1

    def show_error(self, error):
        self._reset()
        self._error = error
        self.message_label.set_text(display_text(error))
        self.message_label.set_visible(True)
        self.details_button.set_visible(True)
