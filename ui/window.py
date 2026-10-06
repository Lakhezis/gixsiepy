"""Ventana y coordinación de los repositorios y sus archivos."""

from pathlib import Path
import traceback

from gi.repository import Gio, GLib, Gtk, Pango

from git.git_service import GitService, GitServiceError
from ui.dialogs import confirm_detached_commit, confirm_initialization, show_error
from ui.commit_panel import CommitPanel
from ui.diff_panel import DiffPanel
from ui.files_panel import FilesPanel, STATUS_NAMES, display_path, display_text
from ui.tasks import TaskRunner


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application, project_dir):
        super().__init__(application=application, title="Gixsie · Git a tu ritmo")
        self.set_default_size(1120, 800)
        self.set_size_request(760, 540)
        self.add_css_class("git-gui")
        self.service = GitService()
        self.tasks = TaskRunner()
        self.diff_tasks = TaskRunner()
        self._diff_generation = 0
        self._pending_diff = None
        self.repository = None
        self._dialog_pending = False
        self._closed = False
        self.connect("close-request", self._on_close_request)
        self.connect("destroy", self._on_destroy)

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
            getattr(content, f"set_margin_{side}")(24)

        self.stack = Gtk.Stack(vexpand=True)
        self.stack.set_vhomogeneous(False)
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
        self.repo_card = repo_card
        repo_card.add_css_class("card")
        heading = Gtk.Label(label="TU CARPETA", xalign=0)
        self.folder_heading = heading
        heading.add_css_class("eyebrow")
        repo_card.append(heading)
        self.name_label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.name_label.add_css_class("hero-title")
        repository_heading = Gtk.Box(spacing=20)
        self.name_label.set_hexpand(True)
        repository_heading.append(self.name_label)
        repo_card.append(repository_heading)
        self.path_label = Gtk.Label(xalign=0, selectable=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        self.path_label.add_css_class("secondary")
        repo_card.append(self.path_label)
        self.branch_label = Gtk.Label(xalign=0, wrap=True, halign=Gtk.Align.START)
        self.branch_label.add_css_class("branch-badge")
        repository_heading.append(self.branch_label)
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
        self.files_panel = FilesPanel(
            on_stage=self._stage_file, on_unstage=self._unstage_file,
            on_stage_all=self._stage_all, on_select=self._file_selected,
        )
        self.files_panel.set_visible(False)
        files_scroll = Gtk.ScrolledWindow(min_content_width=290, min_content_height=160, vexpand=True)
        files_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        files_scroll.set_child(self.files_panel)
        self.diff_panel = DiffPanel(on_details=self._show_failure)
        self.commit_panel = CommitPanel(on_commit=self._commit)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        sidebar.append(files_scroll)
        sidebar.append(self.commit_panel)
        self.workspace = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        self.workspace.set_start_child(sidebar)
        self.workspace.set_end_child(self.diff_panel)
        self.workspace.set_position(350)
        self.workspace.set_resize_start_child(False)
        self.workspace.set_shrink_start_child(False)
        self.workspace.set_shrink_end_child(False)
        self.workspace.set_visible(False)
        content.append(self.workspace)
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
        self.files_panel.set_blocked(blocked)
        self.commit_panel.set_blocked(blocked)
        self._start_pending_diff()

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

    def _start_task(self, operation, on_success, message, on_error=None):
        if self._closed or self._dialog_pending:
            return
        def succeeded(value):
            self._update_actions()
            on_success(value)

        def failed(error):
            self._update_actions()
            if on_error:
                on_error(error)
            else:
                self._show_failure(error)

        if self.tasks.submit(operation, succeeded, failed):
            self._invalidate_diff("Actualizando el repositorio…")
            self._set_status(message)
            self._update_actions()

    def _repository_loaded(self, info, initialized=False):
        self.repository = info
        self.name_label.set_text(display_text(info.name))
        path = info.root_path or info.selected_path
        self.path_label.set_text(display_text(path))
        self.path_label.set_tooltip_text(display_text(path))
        self.stack.set_visible_child_name("repository")
        self.stack.set_vexpand(not info.is_repository)
        self.repo_card.set_valign(Gtk.Align.FILL if info.is_repository else Gtk.Align.CENTER)
        self.repo_card.set_spacing(10 if info.is_repository else 20)
        if info.is_repository:
            self.repo_card.add_css_class("repository-summary")
        else:
            self.repo_card.remove_css_class("repository-summary")
        self.description_label.set_visible(not info.is_repository)
        self.folder_heading.set_visible(not info.is_repository)
        self.files_panel.set_visible(info.is_repository)
        self.workspace.set_visible(info.is_repository)
        self.files_panel.set_repository(info)
        self.commit_panel.set_repository(info)
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
            if any(file.conflicted for file in info.files):
                notices.append("Hay conflictos. Revisalos y resolvelos con otra herramienta antes de prepararlos.")
            if any(file.submodule.startswith("S") and file.is_unstaged for file in info.files):
                notices.append("Los cambios en submódulos se preparan dentro de su propio repositorio.")
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
        self._request_diff(self.files_panel.selected_file, self.files_panel.selected_group)

    def _file_selected(self, file, group):
        self._request_diff(file, group)
        if file is None:
            return
        code = "U" if file.conflicted else (file.working_status if group == "changes" else file.index_status)
        area = "sin preparar" if group == "changes" else "preparado para commit"
        self._set_status(f"{display_path(file.path)} · {STATUS_NAMES.get(code, code)} · {area}")

    def _invalidate_diff(self, message="Seleccioná un archivo para consultar sus cambios."):
        self._diff_generation += 1
        self._pending_diff = None
        self.diff_panel.clear(message)

    def _request_diff(self, file, group):
        self._invalidate_diff()
        if file is None or not self.repository or not self.repository.is_repository:
            return
        staged = group == "staged"
        self._pending_diff = (self._diff_generation, self.repository.root_path, file.path, staged)
        self.diff_panel.show_loading(file.path, staged)
        self._start_pending_diff()

    def _start_pending_diff(self):
        if (self._closed or self.tasks.busy or self._dialog_pending or
                self.diff_tasks.busy or self._pending_diff is None):
            return
        generation, root, path, staged = self._pending_diff
        self._pending_diff = None

        def completed(diff):
            if generation == self._diff_generation:
                self.diff_panel.show_diff(diff)
            self._start_pending_diff()

        def failed(error):
            if generation == self._diff_generation:
                self.diff_panel.show_error(error)
                self._set_status(str(error), error=True)
            self._start_pending_diff()

        self.diff_tasks.submit(
            lambda: self.service.get_diff(root, path, staged=staged), completed, failed,
        )

    def _change_staging(self, operation, success_message):
        if not self.repository or not self.repository.is_repository:
            return
        path = self.repository.selected_path

        def updated(info):
            self._repository_loaded(info)
            self._set_status(success_message)

        def failed(error):
            self._show_failure(error)

            def refreshed(info):
                self._repository_loaded(info)
                self._set_status(str(error), error=True)

            self._start_task(
                lambda: self.service.inspect_repository(path), refreshed,
                "Comprobando el estado después del error…",
                on_error=lambda _refresh_error: self._set_status(str(error), error=True),
            )

        self._start_task(
            lambda: operation(path), updated, "Actualizando los archivos preparados…", on_error=failed,
        )

    def _stage_file(self, file_path):
        self._change_staging(
            lambda path: self.service.stage_file(path, file_path),
            f"Archivo preparado (Stage): {display_path(file_path)}",
        )

    def _unstage_file(self, file_path):
        self._change_staging(
            lambda path: self.service.unstage_file(path, file_path),
            f"Archivo quitado de staging. Tus cambios se conservaron: {display_path(file_path)}",
        )

    def _stage_all(self):
        self._change_staging(self.service.stage_all, "Todos los cambios quedaron preparados para commit.")

    def _commit(self, message):
        if (self.tasks.busy or self._dialog_pending or not self.repository or
                not self.repository.can_commit or not message.strip()):
            return
        path = self.repository.selected_path

        def execute(allow_detached=False):
            self._dialog_pending = False

            def committed(_output):
                # El commit ya existe aunque una consulta posterior a Git falle.
                self.commit_panel.clear_message()

                def refreshed(info):
                    self._repository_loaded(info)
                    self._set_status(f"Commit creado correctamente · {info.head_short}")

                def refresh_failed(error):
                    self._show_failure(GitServiceError(
                        "El commit se creó, pero no se pudo actualizar la vista. Pulsá Actualizar.",
                        stderr=error.details if isinstance(error, GitServiceError) else str(error),
                    ))

                self._start_task(
                    lambda: self.service.inspect_repository(path), refreshed,
                    "Commit creado. Actualizando el repositorio…", on_error=refresh_failed,
                )

            def failed(error):
                self._show_failure(error)

                def refreshed(info):
                    self._repository_loaded(info)
                    self._set_status(str(error), error=True)

                self._start_task(
                    lambda: self.service.inspect_repository(path), refreshed,
                    "Comprobando el estado después del error…",
                    on_error=lambda _error: self._set_status(str(error), error=True),
                )

            self._start_task(
                lambda: self.service.commit(path, message, allow_detached=allow_detached),
                committed, "Creando el commit…", on_error=failed,
            )

        if self.repository.branch is None:
            self._dialog_pending = True
            self._update_actions()

            def cancelled():
                self._dialog_pending = False
                self._update_actions()
                self._set_status("Commit cancelado. El mensaje y los archivos preparados se conservaron.")

            confirm_detached_commit(self, lambda: execute(True), cancelled)
        else:
            execute()

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
        self.diff_tasks.close()
        return False

    def _on_destroy(self, _window):
        self._closed = True
        self.tasks.close()
        self.diff_tasks.close()
