"""Confirmaciones explícitas y errores con detalles consultables."""

from gi.repository import GLib, Gtk


def confirm_initialization(parent, folder, on_confirm, on_cancel):
    dialog = Gtk.AlertDialog(
        message="¿Inicializar un repositorio Git?",
        detail=(
            f"Carpeta: {folder}\n\n"
            "Se creará el repositorio en esta carpeta. "
            "Tus archivos se conservarán y todavía no se hará ningún commit."
        ),
        buttons=["Cancelar", "Inicializar repositorio"],
        cancel_button=0, default_button=0, modal=True,
    )

    def finished(source, result):
        try:
            accepted = source.choose_finish(result) == 1
        except GLib.Error:
            accepted = False
        if accepted:
            on_confirm()
        else:
            on_cancel()

    dialog.choose(parent, None, finished)


def show_error(parent, message, details=""):
    dialog = Gtk.Window(title="No se pudo completar la acción", transient_for=parent, modal=True)
    dialog.set_default_size(510, 220)
    dialog.add_css_class("git-gui")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
    for side in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{side}")(24)
    title = Gtk.Label(label="Revisemos qué pasó", xalign=0)
    title.add_css_class("section-title")
    box.append(title)
    label = Gtk.Label(label=message, wrap=True, xalign=0, selectable=True)
    label.set_max_width_chars(65)
    box.append(label)
    if details:
        expander = Gtk.Expander(label="Detalles de Git")
        scroll = Gtk.ScrolledWindow(min_content_height=140, max_content_height=280)
        scroll.set_propagate_natural_height(True)
        text = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        text.get_buffer().set_text(details)
        text.set_left_margin(12)
        text.set_right_margin(12)
        text.set_top_margin(12)
        text.set_bottom_margin(12)
        scroll.set_child(text)
        expander.set_child(scroll)
        box.append(expander)
    close = Gtk.Button(label="Entendido", halign=Gtk.Align.END)
    close.add_css_class("primary-button")
    close.connect("clicked", lambda _button: dialog.close())
    box.append(close)
    dialog.set_child(box)
    dialog.present()
