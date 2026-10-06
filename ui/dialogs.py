# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Confirmaciones explícitas y errores con detalles consultables."""

from gi.repository import GLib, Gtk


def confirm_initialization(parent, folder, on_confirm, on_cancel):
    _confirm(
        parent, "¿Inicializar un repositorio Git?",
        (
            f"Carpeta: {folder}\n\n"
            "Se creará el repositorio en esta carpeta. "
            "Tus archivos se conservarán y todavía no se hará ningún commit."
        ),
        "Inicializar repositorio", on_confirm, on_cancel,
    )


def confirm_detached_commit(parent, on_confirm, on_cancel):
    _confirm(
        parent, "¿Crear un commit sin una rama activa?",
        "Estás en HEAD separado. El commit no quedará asociado a una rama. "
        "Para conservarlo al cambiar de posición, tendrás que crear una rama "
        "desde la terminal u otra herramienta.",
        "Hacer commit", on_confirm, on_cancel,
    )


def confirm_sync(parent, plan, on_confirm, on_cancel):
    if plan.operation == "pull":
        message = "¿Traer cambios del remoto (Pull)?"
        detail = (
            f"Desde: {plan.destination}\nRama local: {plan.local_branch}\n\n"
            "Se actualizarán los archivos y la rama mediante avance rápido. "
            "Si los historiales divergen, Git detendrá la operación."
        )
        accept = "Hacer Pull"
    else:
        message = "¿Enviar commits al remoto (Push)?"
        detail = (
            f"Rama local: {plan.local_branch}\nDestino: {plan.destination}\n\n"
            "Se publicarán los commits de esta rama, que podrían quedar visibles para otras personas."
        )
        if plan.set_upstream:
            detail += "\n\nEste primer Push establecerá el seguimiento (upstream) de la rama."
        accept = "Hacer Push"
    _confirm(parent, message, detail, accept, on_confirm, on_cancel)


def _confirm(parent, message, detail, accept_label, on_confirm, on_cancel):
    dialog = Gtk.AlertDialog(
        message=message, detail=detail, buttons=["Cancelar", accept_label],
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


def show_output(parent, details):
    show_error(
        parent, "La operación se completó. Esta es la salida original de Git.", details,
        title="Resultado de Git", heading="Detalles de la operación",
    )


def show_error(parent, message, details="", *, title="No se pudo completar la acción", heading="Revisemos qué pasó"):
    dialog = Gtk.Window(title=title, transient_for=parent, modal=True)
    dialog.set_default_size(510, 220)
    dialog.add_css_class("git-gui")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
    for side in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{side}")(24)
    heading_label = Gtk.Label(label=heading, xalign=0)
    heading_label.add_css_class("section-title")
    box.append(heading_label)
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
