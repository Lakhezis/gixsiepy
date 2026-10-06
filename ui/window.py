"""Ventana y coordinación de la primera etapa: abrir e inicializar repositorios."""

from pathlib import Path
import traceback

from gi.repository import Gio, GLib, Gtk, Pango

from git.git_service import GitService, GitServiceError
from ui.dialogs import confirm_initialization, show_error
from ui.tasks import TaskRunner


def display_text(value):
    # GTK necesita UTF-8 válido; la ruta real del servicio conserva sus bytes.
    return str(value).encode("utf-8", errors="replace").decode("utf-8")


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application, project_dir):
        super().__init__(application=application, title="Gixsie · Git a tu ritmo")
        self.set_default_size(960, 700)
        self.set_size_request(640, 480)
        self.add_css_class("git-gui")
        self.service = GitService()
        self.tasks = TaskRunner()
        self.repository = None
        self._dialog_pending = False
        self._closed = False
        self.connect("close-request", self._on_close_request)
        self.connect("destroy", lambda _window: self.tasks.close())

        header = Gtk.HeaderBar()
        title = Gtk.Label(label="gixsie")
        title.add_css_class("app-title")
        header.set_title_widget(title)
        self.open_button = Gtk.Button(label="Abrir carpeta…")
        self.open_button.connect("clicked", self._choose_folder)
        header.pack_start(self.open_button)
        self.refresh_button = Gtk.Button(label="↻ Actualizar", sensitive=False)
        self.refresh_button.connect("clicked", self._refresh)
        header.pack_end(self.refresh_button)
        self.set_titlebar(header)

        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        for side in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{side}")(32)

        self.stack = Gtk.Stack(vexpand=True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        welcome = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        welcome.add_css_class("card")
        welcome.set_valign(Gtk.Align.CENTER)
        flowers = Gtk.Picture.new_for_filename(str(Path(project_dir) / "assets" / "flower-pattern.svg"))
        flowers.set_size_request(-1, 130)
        flowers.set_can_shrink(True)
        flowers.set_content_fit(Gtk.ContentFit.CONTAIN)
        flowers.set_can_target(False)
        welcome.append(flowers)
        greeting = Gtk.Label(label="Un lugar amable para tus cambios")
        greeting.add_css_class("hero-title")
        greeting.set_wrap(True)
        welcome.append(greeting)
        intro = Gtk.Label(
            label="Abrí una carpeta para conocer su repositorio Git.\n"
                  "Si todavía no tiene uno, podés crearlo cuando quieras.",
            wrap=True, justify=Gtk.Justification.CENTER,
        )
        intro.add_css_class("secondary")
        welcome.append(intro)
        self.welcome_open_button = Gtk.Button(label="Elegir una carpeta", halign=Gtk.Align.CENTER)
        self.welcome_open_button.add_css_class("primary-button")
        self.welcome_open_button.connect("clicked", self._choose_folder)
        welcome.append(self.welcome_open_button)
        self.stack.add_named(welcome, "welcome")

        repo_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20, valign=Gtk.Align.CENTER)
        repo_card.add_css_class("card")
        heading = Gtk.Label(label="TU CARPETA", xalign=0)
        heading.add_css_class("eyebrow")
        repo_card.append(heading)
        self.name_label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.name_label.add_css_class("hero-title")
        repo_card.append(self.name_label)
        self.path_label = Gtk.Label(xalign=0, selectable=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        self.path_label.add_css_class("secondary")
        repo_card.append(self.path_label)
        self.branch_label = Gtk.Label(xalign=0, wrap=True, halign=Gtk.Align.START)
        self.branch_label.add_css_class("branch-badge")
        repo_card.append(self.branch_label)
        self.description_label = Gtk.Label(xalign=0, wrap=True)
        repo_card.append(self.description_label)
        self.notice_label = Gtk.Label(xalign=0, wrap=True)
        self.notice_label.add_css_class("notice")
        repo_card.append(self.notice_label)
        self.init_button = Gtk.Button(label="Inicializar repositorio", halign=Gtk.Align.START)
        self.init_button.add_css_class("primary-button")
        self.init_button.connect("clicked", self._confirm_init)
        repo_card.append(self.init_button)
        self.stack.add_named(repo_card, "repository")
        content.append(self.stack)
        scroll.set_child(content)
        layout.append(scroll)

        status = Gtk.Box(spacing=12)
        status.add_css_class("status-bar")
        self.spinner = Gtk.Spinner()
        status.append(self.spinner)
        self.status_label = Gtk.Label(label="Elegí una carpeta para comenzar.", xalign=0, wrap=True, hexpand=True)
        status.append(self.status_label)
        layout.append(status)
        self.set_child(layout)
        self._update_actions()

    def _set_status(self, message, error=False):
        self.status_label.set_text(display_text(message))
        if error:
            self.status_label.add_css_class("status-error")
        else:
            self.status_label.remove_css_class("status-error")

    def _update_actions(self):
        blocked = self.tasks.busy or self._dialog_pending
        self.open_button.set_sensitive(not blocked)
        self.welcome_open_button.set_sensitive(not blocked)
        self.refresh_button.set_sensitive(not blocked and self.repository is not None)
        self.init_button.set_sensitive(
            not blocked and self.repository is not None and not self.repository.is_repository
        )
        self.init_button.set_visible(self.repository is not None and not self.repository.is_repository)
        self.spinner.set_visible(self.tasks.busy)
        self.spinner.set_spinning(self.tasks.busy)

    def _choose_folder(self, _button):
        if self.tasks.busy or self._dialog_pending:
            return
        self._dialog_pending = True
        self._update_actions()
        dialog = Gtk.FileDialog(title="Elegí una carpeta o repositorio", accept_label="Abrir", modal=True)
        if self.repository:
            dialog.set_initial_folder(Gio.File.new_for_path(str(self.repository.selected_path)))
        dialog.select_folder(self, None, self._folder_selected)

    def _folder_selected(self, dialog, result):
        self._dialog_pending = False
        self._update_actions()
        if self._closed:
            return
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error as error:
            if error.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED) or error.matches(
                Gtk.dialog_error_quark(), Gtk.DialogError.CANCELLED
            ):
                self._set_status("Selección cancelada. Podés abrir una carpeta cuando quieras.")
            else:
                self._show_failure(error)
            return
        path = folder.get_path()
        if path is None:
            self._show_failure(GitServiceError("Seleccioná una carpeta local para trabajar con Git."))
            return
        self.open_repository(path)

    def open_repository(self, path):
        self._start_task(
            lambda: self.service.inspect_repository(path),
            self._repository_loaded, "Comprobando la carpeta y su repositorio…",
        )

    def _refresh(self, _button):
        if self.repository:
            self.open_repository(self.repository.selected_path)

    def _start_task(self, operation, on_success, message):
        if self._closed or self._dialog_pending:
            return
        def succeeded(value):
            self._update_actions()
            on_success(value)

        def failed(error):
            self._update_actions()
            self._show_failure(error)

        if self.tasks.submit(operation, succeeded, failed):
            self._set_status(message)
            self._update_actions()

    def _repository_loaded(self, info, initialized=False):
        self.repository = info
        self.name_label.set_text(display_text(info.name))
        path = info.root_path or info.selected_path
        self.path_label.set_text(display_text(path))
        self.path_label.set_tooltip_text(display_text(path))
        self.stack.set_visible_child_name("repository")
        if info.is_repository:
            branch = f"Rama · {info.branch}" if info.branch else f"HEAD separado · {info.head_short}"
            self.branch_label.set_text(display_text(branch))
            self.description_label.set_text("Tu repositorio Git está abierto.")
            notices = []
            if info.selected_path != info.root_path:
                notices.append("Elegiste una subcarpeta. Estamos usando la raíz del repositorio.")
            if not info.has_commits:
                notices.append("Todavía no hay commits. La rama ya está lista para tu primer commit.")
            if info.branch is None:
                notices.append("Estás consultando un commit concreto, sin una rama activa (HEAD separado).")
            self.notice_label.set_text("\n\n".join(notices))
            self.notice_label.set_visible(bool(notices))
            self._set_status("Repositorio inicializado correctamente." if initialized else "Repositorio actualizado.")
        else:
            self.branch_label.set_text("Sin repositorio Git")
            self.description_label.set_text(
                "Esta carpeta todavía no pertenece a un repositorio Git. "
                "Podés inicializar uno para empezar a guardar el historial de tus archivos."
            )
            self.notice_label.set_text("Inicializar crea el repositorio; tus archivos se conservan.")
            self.notice_label.set_visible(True)
            self._set_status("Carpeta abierta. Vos decidís si querés inicializar Git.")
        self._update_actions()

    def _confirm_init(self, _button):
        if self.tasks.busy or self._dialog_pending or not self.repository or self.repository.is_repository:
            return
        path = self.repository.selected_path
        self._dialog_pending = True
        self._update_actions()

        def confirmed():
            self._dialog_pending = False
            self._start_task(
                lambda: self.service.initialize_repository(path),
                lambda info: self._repository_loaded(info, initialized=True),
                "Inicializando el repositorio…",
            )

        def cancelled():
            self._dialog_pending = False
            self._update_actions()
            self._set_status("Inicialización cancelada. No se realizaron cambios.")

        confirm_initialization(self, display_text(path), confirmed, cancelled)

    def _show_failure(self, error):
        if isinstance(error, GitServiceError):
            message, details = str(error), error.details
        else:
            traceback.print_exception(error)
            message = "No se pudo completar la acción. Consultá los detalles y volvé a intentar."
            details = str(error)
        self._set_status(message, error=True)
        show_error(self, display_text(message), display_text(details))

    def _on_close_request(self, _window):
        if self.tasks.busy:
            self._set_status("Esperá a que termine la operación antes de cerrar la aplicación.")
            return True
        self._closed = True
        self.tasks.close()
        return False
