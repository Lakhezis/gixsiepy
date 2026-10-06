"""Pruebas gráficas opcionales. Requieren una sesión de escritorio disponible."""

import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("GIXSIE_RUN_UI_TESTS") == "1", "Pruebas gráficas opcionales")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk, Gio, GLib, Gtk
        from main import PROJECT_DIR, load_styles
        from ui.window import MainWindow

        cls.GLib, cls.Gtk, cls.Gio = GLib, Gtk, Gio
        if not Gtk.init_check():
            raise unittest.SkipTest("No hay una sesión gráfica disponible")
        cls.project_dir = PROJECT_DIR
        cls.window_class = MainWindow
        cls.application = Gtk.Application(
            application_id="org.gixsie.Tests", flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        cls.application.register(None)
        cls.provider = load_styles(Gdk.Display.get_default())

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gixsie-ui-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / "repositorio"
        self.folder.mkdir()
        configuration = Path(self.temporary.name) / "config"
        configuration.write_text("[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        environment = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(configuration), "GIT_CONFIG_NOSYSTEM": "1",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.window = self.window_class(self.application, self.project_dir)
        self.window.present()
        self.pump_until(lambda: self.window.get_mapped())

    def tearDown(self):
        self.pump_until(lambda: not self.window.tasks.busy and not self.window.diff_tasks.busy
                        and self.window._pending_diff is None and self.window._pending_history is None)
        for window in list(self.Gtk.Window.get_toplevels()):
            window.destroy()
        self.window.tasks.close()
        self.window.diff_tasks.close()
        self.pump()

    def pump(self):
        context = self.GLib.MainContext.default()
        while context.pending():
            context.iteration(False)

    def pump_until(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while not condition():
            self.pump()
            if time.monotonic() > deadline:
                self.fail("La interfaz no completó la acción a tiempo")
            time.sleep(0.005)
        self.pump()

    def open_folder(self):
        self.window.open_repository(self.folder)
        self.pump_until(lambda: not self.window.tasks.busy)

    def wait_for_diff(self):
        self.pump_until(lambda: not self.window.diff_tasks.busy and self.window._pending_diff is None)

    def wait_for_history(self):
        self.pump_until(lambda: not self.window.diff_tasks.busy and self.window._pending_history is None)

    def open_history(self):
        self.window.views.set_visible_child_name("history")
        self.wait_for_history()

    def diff_text(self):
        buffer = self.window.diff_panel.buffer
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def create_repository(self):
        self.window.service.initialize_repository(self.folder)

    def prepare_commit(self):
        self.create_repository()
        self.git("config", "user.name", "Prueba")
        self.git("config", "user.email", "prueba@example.test")
        (self.folder / "a.txt").write_text("preparado\n", encoding="utf-8")
        self.window.service.stage_file(self.folder, "a.txt")
        self.open_folder()

    def prepare_sync_repository(self, *, published=False):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        remote = Path(self.temporary.name) / "remoto.git"
        self.git("init", "--bare", str(remote))
        self.git("remote", "add", "origin", str(remote))
        if published:
            self.git("push", "-u", "origin", "main")
        self.open_folder()
        return remote

    def git(self, *arguments, cwd=None):
        return subprocess.run(
            ["git", *arguments], cwd=cwd or self.folder, check=True, capture_output=True, text=True,
        ).stdout.strip()

    def test_welcome_and_css_render_without_parsing_errors(self):
        provider = self.Gtk.CssProvider()
        errors = []
        provider.connect("parsing-error", lambda _provider, _section, error: errors.append(error))
        provider.load_from_path(str(self.project_dir / "styles" / "style.css"))
        self.assertEqual(errors, [])
        self.assertEqual(self.window.stack.get_visible_child_name(), "welcome")
        self.assertFalse(self.window.init_button.get_visible())
        self.assertFalse(self.window.refresh_button.get_sensitive())
        self.assertTrue(self.window.open_button.get_sensitive())

    def test_opening_a_new_folder_offers_initialization_without_creating_git(self):
        self.open_folder()
        self.assertFalse((self.folder / ".git").exists())
        self.assertTrue(self.window.init_button.get_visible())
        self.assertTrue(self.window.init_button.get_sensitive())
        self.assertEqual(self.window.branch_label.get_text(), "Sin repositorio Git")

    def test_initialization_waits_for_confirmation_and_cancel_does_not_write(self):
        self.open_folder()
        with patch("ui.window.confirm_initialization") as confirm:
            self.window.init_button.emit("clicked")
            self.window.init_button.emit("clicked")
            self.assertEqual(confirm.call_count, 1)
            self.assertFalse(self.window.init_button.get_sensitive())
            self.assertFalse((self.folder / ".git").exists())
            confirm.call_args.args[3]()
        self.assertFalse((self.folder / ".git").exists())
        self.assertTrue(self.window.init_button.get_sensitive())

    def test_confirmed_initialization_updates_the_window(self):
        self.open_folder()
        with patch("ui.window.confirm_initialization") as confirm:
            self.window.init_button.emit("clicked")
            confirm.call_args.args[2]()
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertTrue((self.folder / ".git").exists())
        self.assertEqual(self.window.branch_label.get_text(), "Rama · main")
        self.assertFalse(self.window.init_button.get_visible())
        self.assertIn("Todavía no hay commits", self.window.notice_label.get_text())
        self.assertEqual(self.window.status_label.get_text(), "Repositorio inicializado correctamente.")

    def test_real_confirmation_dialog_can_be_cancelled(self):
        self.open_folder()
        self.window.init_button.emit("clicked")
        self.pump_until(lambda: len(list(self.Gtk.Window.get_toplevels())) > 1)

        def find_cancel(widget):
            if isinstance(widget, self.Gtk.Button) and widget.get_label() == "Cancelar":
                return widget
            child = widget.get_first_child()
            while child:
                button = find_cancel(child)
                if button:
                    return button
                child = child.get_next_sibling()
            return None

        dialog = next(window for window in self.Gtk.Window.get_toplevels() if window is not self.window)
        cancel = find_cancel(dialog)
        self.assertIsNotNone(cancel)
        cancel.emit("clicked")
        self.pump_until(lambda: not self.window._dialog_pending)
        self.assertFalse((self.folder / ".git").exists())
        self.assertTrue(self.window.init_button.get_sensitive())

    def test_folder_picker_cancellation_preserves_the_current_view(self):
        from unittest.mock import Mock
        error = self.GLib.Error.new_literal(
            self.Gtk.dialog_error_quark(), "Selección cancelada", self.Gtk.DialogError.DISMISSED,
        )
        picker = Mock()
        picker.select_folder_finish.side_effect = error
        self.window._dialog_pending = True
        self.window._folder_selected(picker, None)
        self.assertIsNone(self.window.repository)
        self.assertEqual(self.window.stack.get_visible_child_name(), "welcome")
        self.assertTrue(self.window.open_button.get_sensitive())

    def test_folder_button_launches_picker_and_disables_duplicate_action(self):
        with patch("ui.window.Gtk.FileDialog") as dialog_class:
            self.window.open_button.emit("clicked")
            picker = dialog_class.return_value
            self.assertTrue(self.window._dialog_pending)
            self.assertFalse(self.window.open_button.get_sensitive())
            picker.select_folder.assert_called_once()
            self.window._dialog_pending = False
            self.window._update_actions()

    def test_native_folder_picker_cancellation_returns_to_the_window(self):
        dialog = self.Gtk.FileDialog(title="Prueba del selector de carpeta")
        cancellation = self.Gio.Cancellable()
        self.window._dialog_pending = True
        self.window._update_actions()
        dialog.select_folder(self.window, cancellation, self.window._folder_selected)
        self.GLib.timeout_add(1000, lambda: cancellation.cancel() or self.GLib.SOURCE_REMOVE)
        self.pump_until(lambda: not self.window._dialog_pending)
        self.assertEqual(self.window.stack.get_visible_child_name(), "welcome")
        self.assertTrue(self.window.open_button.get_sensitive())
        self.assertIn("cancelada", self.window.status_label.get_text())

    def test_application_entry_point_activates_a_window(self):
        from main import GitGuiApplication
        application = GitGuiApplication()
        application.set_flags(self.Gio.ApplicationFlags.NON_UNIQUE)
        application.register(None)
        application.activate()
        self.pump_until(lambda: application.window is not None and application.window.get_mapped())
        self.assertEqual(application.window.stack.get_visible_child_name(), "welcome")
        application.window.close()

    def test_worker_keeps_main_loop_responsive_and_prevents_duplicate_operations(self):
        release = threading.Event()
        original = self.window.service.inspect_repository

        def slow_inspect(path):
            if not release.wait(timeout=3):
                raise RuntimeError("La prueba no liberó el trabajador")
            return original(path)

        with patch.object(self.window.service, "inspect_repository", side_effect=slow_inspect) as inspect:
            self.window.open_repository(self.folder)
            self.window.open_repository(self.folder)
            try:
                self.assertFalse(self.window.open_button.get_sensitive())
                ticks = []
                self.GLib.idle_add(lambda: ticks.append("GTK responde") or self.GLib.SOURCE_REMOVE)
                self.pump_until(lambda: bool(ticks))
                self.assertTrue(self.window.tasks.busy)
                self.assertTrue(self.window._on_close_request(self.window))
            finally:
                release.set()
            self.pump_until(lambda: not self.window.tasks.busy)
            self.assertEqual(inspect.call_count, 1)
        self.assertTrue(self.window.open_button.get_sensitive())

    def test_error_details_can_be_opened(self):
        from git.git_service import GitServiceError
        self.window._show_failure(GitServiceError("Sin acceso", stderr="Permission denied", returncode=128))
        self.pump()
        dialogs = [window for window in self.Gtk.Window.get_toplevels() if window is not self.window]
        self.assertEqual(len(dialogs), 1)
        self.assertEqual(self.window.status_label.get_text(), "Sin acceso")
        box = dialogs[0].get_child()
        child = box.get_first_child()
        while child and not isinstance(child, self.Gtk.Expander):
            child = child.get_next_sibling()
        self.assertIsNotNone(child)
        child.set_expanded(True)
        buffer = child.get_child().get_child().get_buffer()
        self.assertIn("Permission denied", buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False))

    def test_clean_repository_disables_all_staging_buttons(self):
        self.create_repository()
        self.open_folder()
        panel = self.window.files_panel
        self.assertTrue(panel.get_visible())
        self.assertEqual(panel.changes_count.get_text(), "0")
        self.assertEqual(panel.staged_count.get_text(), "0")
        self.assertFalse(panel.stage_button.get_sensitive())
        self.assertFalse(panel.unstage_button.get_sensitive())
        self.assertFalse(panel.stage_all_button.get_sensitive())

    def test_selecting_a_file_enables_stage_without_preparing_it(self):
        self.create_repository()
        (self.folder / "nuevo.txt").write_text("contenido", encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        self.assertFalse(panel.stage_button.get_sensitive())
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        self.assertTrue(panel.stage_button.get_sensitive())
        self.assertEqual(panel.selected_file.path, "nuevo.txt")
        self.assertEqual(self.git("ls-files"), "")

    def test_stage_and_unstage_buttons_update_both_groups_and_prevent_double_click(self):
        self.create_repository()
        file = self.folder / "a.txt"
        file.write_text("contenido", encoding="utf-8")
        (self.folder / "b.txt").write_text("otro", encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        with patch.object(self.window.service, "stage_file", wraps=self.window.service.stage_file) as stage:
            panel.stage_button.emit("clicked")
            panel.stage_button.emit("clicked")
            self.assertFalse(panel.stage_all_button.get_sensitive())
            self.pump_until(lambda: not self.window.tasks.busy)
            self.assertEqual(stage.call_count, 1)
        self.assertEqual(panel.changes_count.get_text(), "1")
        self.assertEqual(panel.staged_count.get_text(), "1")
        self.assertEqual(panel.selected_group, "staged")
        self.assertEqual(self.git("ls-files"), "a.txt")
        self.assertIn("Archivo preparado", self.window.status_label.get_text())
        panel.unstage_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.changes_count.get_text(), "2")
        self.assertEqual(panel.staged_count.get_text(), "0")
        self.assertEqual(panel.selected_group, "changes")
        self.assertEqual(file.read_text(encoding="utf-8"), "contenido")
        self.assertIn("conservaron", self.window.status_label.get_text())

    def test_prepare_all_automatically_refreshes_lists(self):
        self.create_repository()
        for name in ("a.txt", "b.txt"):
            (self.folder / name).write_text(name, encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        panel.stage_all_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.changes_count.get_text(), "0")
        self.assertEqual(panel.staged_count.get_text(), "2")
        self.assertFalse(panel.stage_all_button.get_sensitive())
        self.assertEqual(self.git("ls-files"), "a.txt\nb.txt")

    def test_partial_staging_shows_file_in_both_groups_with_one_selection(self):
        self.create_repository()
        file = self.folder / "a.txt"
        file.write_text("preparado", encoding="utf-8")
        self.window.service.stage_file(self.folder, "a.txt")
        file.write_text("otra edición", encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        self.assertEqual(panel.changes_count.get_text(), "1")
        self.assertEqual(panel.staged_count.get_text(), "1")
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        self.assertTrue(panel.stage_button.get_sensitive())
        panel.staged_list.select_row(panel.staged_list.get_row_at_index(0))
        self.assertIsNone(panel.changes_list.get_selected_row())
        self.assertTrue(panel.unstage_button.get_sensitive())
        self.assertFalse(panel.stage_button.get_sensitive())
        self.assertEqual(self.git("show", ":a.txt"), "preparado")

    def test_refresh_keeps_selection_and_switching_repository_clears_it(self):
        self.create_repository()
        (self.folder / "a.txt").write_text("contenido", encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        self.window.refresh_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.selected_file.path, "a.txt")
        other = Path(self.temporary.name) / "otra carpeta"
        other.mkdir()
        self.window.service.initialize_repository(other)
        (other / "a.txt").write_text("otro repositorio", encoding="utf-8")
        self.window.open_repository(other)
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertIsNone(panel.selected_file)
        self.assertFalse(panel.stage_button.get_sensitive())

    def test_failed_stage_refreshes_external_changes_and_keeps_git_error_visible(self):
        self.create_repository()
        file = self.folder / "a.txt"
        file.write_text("contenido", encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        file.unlink()
        panel.stage_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.changes_count.get_text(), "0")
        self.assertFalse(panel.stage_button.get_sensitive())
        self.assertIn("ya no aparece", self.window.status_label.get_text())

    def test_unusual_filename_renders_and_stages_its_original_path(self):
        self.create_repository()
        name = os.fsdecode(b"nombre-\xff\r\n.txt")
        (self.folder / name).write_bytes(b"contenido")
        self.open_folder()
        panel = self.window.files_panel
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        panel.stage_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.selected_file.path, name)
        self.assertEqual(panel.staged_count.get_text(), "1")

    def test_diff_selection_displays_new_file_and_applies_line_tags(self):
        self.create_repository()
        (self.folder / "nuevo.txt").write_text("primera línea\n+++contenido\n", encoding="utf-8")
        self.open_folder()
        self.window.files_panel.changes_list.select_row(self.window.files_panel.changes_list.get_row_at_index(0))
        self.wait_for_diff()
        text = self.diff_text()
        self.assertIn("+primera línea\n", text)
        self.assertEqual(self.window.diff_panel.path_label.get_text(), "nuevo.txt")
        buffer = self.window.diff_panel.buffer
        for fragment, expected_tag in (("+++ b/", "header"), ("+primera línea", "added"), ("++++contenido", "added")):
            with self.subTest(fragment=fragment):
                offset = text.index(fragment)
                tags = [tag.props.name for tag in buffer.get_iter_at_offset(offset).get_tags()]
                self.assertIn(expected_tag, tags)
        self.assertEqual(self.git("ls-files"), "")
        self.assertTrue(self.window.diff_panel.text_view.get_monospace())
        self.assertFalse(self.window.diff_panel.text_view.get_editable())

    def test_diff_selection_distinguishes_staged_from_local_edits(self):
        self.create_repository()
        file = self.folder / "a.txt"
        file.write_text("versión preparada\n", encoding="utf-8")
        self.window.service.stage_file(self.folder, "a.txt")
        file.write_text("versión local\n", encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        self.wait_for_diff()
        text = self.diff_text()
        self.assertIn("-versión preparada\n", text)
        self.assertIn("+versión local\n", text)
        removed = self.window.diff_panel.buffer.get_iter_at_offset(text.index("-versión preparada"))
        self.assertIn("removed", [tag.props.name for tag in removed.get_tags()])
        self.assertIn("Sin preparar", self.window.diff_panel.comparison_label.get_text())
        panel.staged_list.select_row(panel.staged_list.get_row_at_index(0))
        self.wait_for_diff()
        self.assertIn("+versión preparada\n", self.diff_text())
        self.assertNotIn("versión local", self.diff_text())
        self.assertIn("Preparado", self.window.diff_panel.comparison_label.get_text())

    def test_diff_refreshes_after_stage_unstage_and_manual_update(self):
        self.create_repository()
        file = self.folder / "a.txt"
        file.write_text("primera edición\n", encoding="utf-8")
        self.open_folder()
        panel = self.window.files_panel
        panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
        self.wait_for_diff()
        panel.stage_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_diff()
        self.assertIn("Preparado", self.window.diff_panel.comparison_label.get_text())
        self.assertIn("+primera edición\n", self.diff_text())
        panel.unstage_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_diff()
        self.assertIn("Sin preparar", self.window.diff_panel.comparison_label.get_text())
        file.write_text("segunda edición\n", encoding="utf-8")
        self.window.refresh_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_diff()
        self.assertIn("+segunda edición\n", self.diff_text())
        self.assertNotIn("+primera edición\n", self.diff_text())

    def test_diff_of_binary_file_has_a_readable_explanation(self):
        self.create_repository()
        (self.folder / "imagen.bin").write_bytes(b"\0\xffdatos")
        self.open_folder()
        self.window.files_panel.changes_list.select_row(self.window.files_panel.changes_list.get_row_at_index(0))
        self.wait_for_diff()
        self.assertTrue(self.window.diff_panel.message_label.get_visible())
        self.assertIn("binario", self.window.diff_panel.message_label.get_text())

    def test_large_diff_displays_a_truncation_notice(self):
        self.create_repository()
        (self.folder / "grande.txt").write_text("una línea\n" * 5100, encoding="utf-8")
        self.open_folder()
        self.window.files_panel.changes_list.select_row(self.window.files_panel.changes_list.get_row_at_index(0))
        self.wait_for_diff()
        self.assertIn("recortada", self.window.diff_panel.message_label.get_text())
        self.assertLessEqual(self.window.diff_panel.buffer.get_line_count(), 5001)

    def test_fast_selection_keeps_gtk_responsive_and_discards_older_diff(self):
        from git.git_service import FileDiff
        self.create_repository()
        for name in ("a.txt", "b.txt", "c.txt"):
            (self.folder / name).write_text(name, encoding="utf-8")
        self.open_folder()
        release = threading.Event()
        started = threading.Event()

        def delayed_diff(_root, path, *, staged):
            if path == "a.txt":
                started.set()
                release.wait(timeout=3)
            return FileDiff(path, staged, text=f"+Contenido de {path}\n")

        with patch.object(self.window.service, "get_diff", side_effect=delayed_diff) as read:
            panel = self.window.files_panel
            panel.changes_list.select_row(panel.changes_list.get_row_at_index(0))
            self.pump_until(started.is_set)
            try:
                panel.changes_list.select_row(panel.changes_list.get_row_at_index(1))
                panel.changes_list.select_row(panel.changes_list.get_row_at_index(2))
                self.assertTrue(panel.changes_list.get_sensitive())
                self.assertTrue(panel.stage_button.get_sensitive())
                self.assertEqual(self.diff_text(), "")
                self.assertEqual(self.window.diff_panel.path_label.get_text(), "c.txt")
            finally:
                release.set()
            self.wait_for_diff()
            self.assertIn("Contenido de c.txt", self.diff_text())
            self.assertNotIn("Contenido de a.txt", self.diff_text())
            self.assertEqual([call.args[1] for call in read.call_args_list], ["a.txt", "c.txt"])

    def test_switching_repository_discards_a_diff_still_loading(self):
        from git.git_service import FileDiff
        self.create_repository()
        (self.folder / "a.txt").write_text("contenido", encoding="utf-8")
        self.open_folder()
        other = Path(self.temporary.name) / "otro repo"
        other.mkdir()
        self.window.service.initialize_repository(other)
        release = threading.Event()
        started = threading.Event()

        def delayed_diff(*args, **kwargs):
            started.set()
            release.wait(timeout=3)
            return FileDiff("a.txt", False, text="+Repositorio anterior\n")

        with patch.object(self.window.service, "get_diff", side_effect=delayed_diff):
            self.window.files_panel.changes_list.select_row(self.window.files_panel.changes_list.get_row_at_index(0))
            self.pump_until(started.is_set)
            try:
                self.window.open_repository(other)
                self.pump_until(lambda: not self.window.tasks.busy)
            finally:
                release.set()
            self.wait_for_diff()
        self.assertEqual(self.diff_text(), "")
        self.assertIsNone(self.window.files_panel.selected_file)

    def test_diff_error_offers_original_git_details(self):
        from git.git_service import GitServiceError
        self.create_repository()
        (self.folder / "a.txt").write_text("contenido", encoding="utf-8")
        self.open_folder()
        error = GitServiceError("No se pudo leer el diff", stderr="Git original error", returncode=128)
        with patch.object(self.window.service, "get_diff", side_effect=error):
            self.window.files_panel.changes_list.select_row(self.window.files_panel.changes_list.get_row_at_index(0))
            self.wait_for_diff()
        self.assertEqual(self.window.diff_panel.message_label.get_text(), str(error))
        self.assertTrue(self.window.diff_panel.details_button.get_visible())
        with patch.object(self.window.diff_panel, "on_details") as details:
            self.window.diff_panel.details_button.emit("clicked")
            details.assert_called_once_with(error)

    def test_commit_button_requires_message_and_prepared_files(self):
        panel = self.window.commit_panel
        self.assertFalse(panel.message_view.get_accepts_tab())
        self.assertFalse(panel.message_view.get_monospace())
        self.assertFalse(panel.commit_button.get_sensitive())
        self.assertFalse(panel.message_view.get_sensitive())
        self.create_repository()
        (self.folder / "a.txt").write_text("nuevo", encoding="utf-8")
        self.open_folder()
        panel.buffer.set_text("Mensaje sin staging")
        self.assertFalse(panel.commit_button.get_sensitive())
        self.window.files_panel.stage_all_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertTrue(panel.commit_button.get_sensitive())
        panel.buffer.set_text(" \n\t ")
        self.assertFalse(panel.commit_button.get_sensitive())
        panel.buffer.set_text("Mensaje")
        self.assertTrue(panel.commit_button.get_sensitive())
        self.window.files_panel.staged_list.select_row(self.window.files_panel.staged_list.get_row_at_index(0))
        self.window.files_panel.unstage_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertFalse(panel.commit_button.get_sensitive())

    def test_successful_commit_clears_message_refreshes_files_and_diff(self):
        self.prepare_commit()
        (self.folder / "a.txt").write_text("edición posterior\n", encoding="utf-8")
        self.open_folder()
        files = self.window.files_panel
        files.staged_list.select_row(files.staged_list.get_row_at_index(0))
        self.wait_for_diff()
        panel = self.window.commit_panel
        panel.buffer.set_text("Primero\n\nExplicación 🌸")
        panel.commit_button.emit("clicked")
        panel.commit_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_diff()
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
        self.assertEqual(self.git("log", "-1", "--format=%B"), "Primero\n\nExplicación 🌸")
        self.assertEqual(panel.message, "")
        self.assertFalse(panel.commit_button.get_sensitive())
        self.assertEqual(files.staged_count.get_text(), "0")
        self.assertEqual(files.changes_count.get_text(), "1")
        self.assertEqual(files.selected_group, "changes")
        self.assertIn("+edición posterior", self.diff_text())
        self.assertIn("Commit creado correctamente", self.window.status_label.get_text())
        self.assertFalse(self.window.notice_label.get_visible())

    def test_slow_commit_keeps_gtk_responsive_and_blocks_duplicate_actions(self):
        self.prepare_commit()
        panel = self.window.commit_panel
        panel.buffer.set_text("Un solo commit")
        original = self.window.service.commit
        started, release = threading.Event(), threading.Event()

        def delayed(*args, **kwargs):
            started.set()
            if not release.wait(5):
                raise RuntimeError("La prueba no liberó el trabajador")
            return original(*args, **kwargs)

        with patch.object(self.window.service, "commit", side_effect=delayed) as commit:
            try:
                panel.commit_button.emit("clicked")
                self.pump_until(started.is_set)
                responsive = []
                self.GLib.idle_add(lambda: responsive.append(True) and False)
                self.pump_until(lambda: bool(responsive))
                self.assertFalse(panel.commit_button.get_sensitive())
                self.assertFalse(panel.message_view.get_sensitive())
                self.assertFalse(self.window.open_button.get_sensitive())
                self.assertFalse(self.window.files_panel.stage_all_button.get_sensitive())
                self.assertTrue(self.window._on_close_request(self.window))
                panel.commit_button.emit("clicked")
                self.assertEqual(commit.call_count, 1)
            finally:
                release.set()
            self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
        self.assertTrue(panel.message_view.get_sensitive())

    def test_rejected_commit_keeps_draft_and_git_details_for_retry(self):
        self.prepare_commit()
        hook = self.folder / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nprintf 'Hook rechazó el commit\\n' >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o700)
        panel = self.window.commit_panel
        panel.buffer.set_text("Conservar mi mensaje")
        with patch("ui.window.show_error") as show:
            panel.commit_button.emit("clicked")
            self.pump_until(lambda: not self.window.tasks.busy)
            self.assertIn("Hook rechazó", show.call_args.args[2])
        self.assertEqual(panel.message, "Conservar mi mensaje")
        self.assertTrue(panel.commit_button.get_sensitive())
        self.assertEqual(self.window.files_panel.staged_count.get_text(), "1")
        self.assertIn("Git no pudo", self.window.status_label.get_text())
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        panel.commit_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.message, "")
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")

    def test_commit_revalidates_external_unstage_and_keeps_message(self):
        self.prepare_commit()
        panel = self.window.commit_panel
        panel.buffer.set_text("Conservar")
        self.window.service.unstage_file(self.folder, "a.txt")
        with patch("ui.window.show_error"):
            panel.commit_button.emit("clicked")
            self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.message, "Conservar")
        self.assertFalse(panel.commit_button.get_sensitive())
        self.assertEqual(self.window.files_panel.staged_count.get_text(), "0")
        self.assertIn("Prepará", self.window.status_label.get_text())

    def test_refresh_failure_after_commit_reports_success_and_clears_message(self):
        from git.git_service import GitServiceError
        self.prepare_commit()
        panel = self.window.commit_panel
        panel.buffer.set_text("Commit real")
        original_commit = self.window.service.commit
        original_inspect = self.window.service.inspect_repository
        committed = []

        def create(*args, **kwargs):
            output = original_commit(*args, **kwargs)
            committed.append(True)
            return output

        def inspect(*args):
            if committed:
                raise GitServiceError("Error de lectura", stderr="Detalle del error al actualizar")
            return original_inspect(*args)

        with patch.object(self.window.service, "commit", side_effect=create), \
                patch.object(self.window.service, "inspect_repository", side_effect=inspect), \
                patch("ui.window.show_error") as show:
            panel.commit_button.emit("clicked")
            self.pump_until(lambda: not self.window.tasks.busy)
            self.assertIn("El commit se creó", show.call_args.args[1])
            self.assertIn("Detalle del error", show.call_args.args[2])
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
        self.assertEqual(panel.message, "")
        self.assertFalse(panel.commit_button.get_sensitive())
        self.window.refresh_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(self.window.files_panel.staged_count.get_text(), "0")

    def test_refresh_preserves_draft_and_opening_another_repository_clears_it(self):
        self.prepare_commit()
        panel = self.window.commit_panel
        panel.buffer.set_text("Borrador de este repositorio")
        self.window.refresh_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.message, "Borrador de este repositorio")
        other = Path(self.temporary.name) / "otro repositorio"
        other.mkdir()
        self.window.service.initialize_repository(other)
        self.window.open_repository(other)
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(panel.message, "")

    def test_detached_commit_can_be_cancelled_or_explicitly_confirmed(self):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Primero")
        self.git("checkout", "--detach")
        (self.folder / "a.txt").write_text("otro", encoding="utf-8")
        self.window.service.stage_all(self.folder)
        self.open_folder()
        panel = self.window.commit_panel
        panel.buffer.set_text("Sin rama")
        with patch("ui.window.confirm_detached_commit") as confirm:
            panel.commit_button.emit("clicked")
            panel.commit_button.emit("clicked")
            self.assertEqual(confirm.call_count, 1)
            self.assertFalse(panel.commit_button.get_sensitive())
            confirm.call_args.args[2]()
            self.assertEqual(panel.message, "Sin rama")
            self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
            panel.commit_button.emit("clicked")
            confirm.call_args.args[1]()
        self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "2")
        self.assertEqual(panel.message, "")

    def test_conflicts_disable_commit_even_when_other_files_are_prepared(self):
        from dataclasses import replace
        from git.git_service import FileChange
        self.prepare_commit()
        panel = self.window.commit_panel
        panel.buffer.set_text("No guardar conflictos")
        info = self.window.repository
        self.window._repository_loaded(replace(
            info, files=(*info.files, FileChange("conflicto.txt", "U", "U", conflicted=True)),
        ))
        self.assertFalse(panel.commit_button.get_sensitive())
        self.assertIn("conflictos", panel.help_label.get_text())
        with patch.object(self.window.service, "commit") as commit:
            panel.commit_button.emit("clicked")
            commit.assert_not_called()

    def test_sync_buttons_explain_missing_repository_remote_upstream_and_pending_changes(self):
        self.assertFalse(self.window.pull_button.get_sensitive())
        self.assertFalse(self.window.push_button.get_sensitive())
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        self.open_folder()
        self.assertFalse(self.window.push_button.get_sensitive())
        self.assertIn("remoto", self.window.push_button.get_tooltip_text())
        self.git("remote", "add", "origin", str(Path(self.temporary.name) / "remoto.git"))
        self.open_folder()
        self.assertTrue(self.window.push_button.get_sensitive())
        self.assertFalse(self.window.pull_button.get_sensitive())
        self.assertIn("seguimiento", self.window.pull_button.get_tooltip_text())
        self.git("config", "branch.main.remote", "origin")
        self.git("config", "branch.main.merge", "refs/heads/main")
        (self.folder / "nuevo.txt").write_text("pendiente", encoding="utf-8")
        self.open_folder()
        self.assertFalse(self.window.pull_button.get_sensitive())
        self.assertIn("pendientes", self.window.pull_button.get_tooltip_text())
        self.assertTrue(self.window.push_button.get_sensitive())

    def test_first_push_waits_for_confirmation_and_cancel_preserves_repository(self):
        remote = self.prepare_sync_repository()
        self.window.commit_panel.buffer.set_text("Borrador")
        with patch("ui.window.confirm_sync") as confirm:
            self.window.push_button.emit("clicked")
            self.window.push_button.emit("clicked")
            self.pump_until(lambda: self.window._dialog_pending)
            self.assertEqual(confirm.call_count, 1)
            plan = confirm.call_args.args[1]
            self.assertTrue(plan.set_upstream)
            self.assertEqual(plan.destination, "origin/main")
            self.assertFalse(self.window.push_button.get_sensitive())
            self.assertFalse(self.window.open_button.get_sensitive())
            self.assertEqual(self.git("for-each-ref", cwd=remote), "")
            confirm.call_args.args[3]()
        self.assertTrue(self.window.push_button.get_sensitive())
        self.assertEqual(self.window.commit_panel.message, "Borrador")
        self.assertIsNone(self.window.repository.upstream_ref)
        self.assertIn("cancelado", self.window.status_label.get_text())
        self.assertEqual(self.git("for-each-ref", cwd=remote), "")

    def test_confirmed_push_updates_upstream_and_exposes_successful_git_output(self):
        remote = self.prepare_sync_repository()
        self.open_history()
        self.window.commit_panel.buffer.set_text("Borrador")
        with patch("ui.window.confirm_sync") as confirm:
            self.window.push_button.emit("clicked")
            self.pump_until(lambda: self.window._dialog_pending)
            confirm.call_args.args[2]()
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_history()
        self.assertEqual(self.window.views.get_visible_child_name(), "history")
        self.assertEqual(len(self.window.history_panel.commits), 1)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=remote), self.git("rev-parse", "HEAD"))
        self.assertEqual(self.window.repository.upstream_ref, "refs/heads/main")
        self.assertIn("origin/main", self.window.remote_label.get_text())
        self.assertTrue(self.window.pull_button.get_sensitive())
        self.assertEqual(self.window.commit_panel.message, "Borrador")
        self.assertIn("Push completado", self.window.status_label.get_text())
        self.assertTrue(self.window.sync_details_button.get_visible())
        with patch("ui.window.show_output") as show:
            self.window.sync_details_button.emit("clicked")
            self.assertIn("main", show.call_args.args[1])

    def test_confirmed_pull_refreshes_branch_files_and_preserves_commit_draft(self):
        remote = self.prepare_sync_repository(published=True)
        self.open_history()
        other = Path(self.temporary.name) / "otro equipo"
        self.git("clone", str(remote), str(other))
        (other / "a.txt").write_text("actualizado por pull\n", encoding="utf-8")
        self.git("add", "-A", cwd=other)
        self.git("-c", "user.name=Prueba", "-c", "user.email=prueba@example.test",
                 "-c", "commit.gpgSign=false", "commit", "-m", "Remoto", cwd=other)
        self.git("push", cwd=other)
        self.window.commit_panel.buffer.set_text("Borrador")
        before = self.window.repository.head_short
        with patch("ui.window.confirm_sync") as confirm:
            self.window.pull_button.emit("clicked")
            self.pump_until(lambda: self.window._dialog_pending)
            self.assertEqual(confirm.call_args.args[1].operation, "pull")
            self.assertEqual((self.folder / "a.txt").read_text(encoding="utf-8"), "preparado\n")
            confirm.call_args.args[2]()
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_history()
        self.assertEqual(self.window.views.get_visible_child_name(), "history")
        self.assertEqual(self.window.history_panel.commits[0].message, "Remoto")
        self.assertEqual(len(self.window.history_panel.commits), 2)
        self.assertNotEqual(before, self.window.repository.head_short)
        self.assertEqual((self.folder / "a.txt").read_text(encoding="utf-8"), "actualizado por pull\n")
        self.assertEqual(self.window.repository.files, ())
        self.assertEqual(self.window.commit_panel.message, "Borrador")
        self.assertIn("Pull completado", self.window.status_label.get_text())
        self.assertIn("Fast-forward", self.window._last_sync.details)

    def test_slow_sync_keeps_gtk_responsive_and_prevents_duplicate_operations(self):
        remote = self.prepare_sync_repository()
        original = self.window.service.sync
        started, release = threading.Event(), threading.Event()

        def delayed(*args):
            started.set()
            if not release.wait(5):
                raise RuntimeError("La prueba no liberó el trabajador")
            return original(*args)

        with patch.object(self.window.service, "sync", side_effect=delayed) as sync, \
                patch("ui.window.confirm_sync") as confirm:
            try:
                self.window.push_button.emit("clicked")
                self.pump_until(lambda: self.window._dialog_pending)
                confirm.call_args.args[2]()
                self.pump_until(started.is_set)
                responsive = []
                self.GLib.idle_add(lambda: responsive.append(True) and False)
                self.pump_until(lambda: bool(responsive))
                for button in (self.window.pull_button, self.window.push_button,
                               self.window.refresh_button, self.window.open_button):
                    self.assertFalse(button.get_sensitive())
                self.assertFalse(self.window.commit_panel.message_view.get_sensitive())
                self.assertTrue(self.window._on_close_request(self.window))
                self.window.push_button.emit("clicked")
                self.window.pull_button.emit("clicked")
                self.assertEqual(sync.call_count, 1)
            finally:
                release.set()
            self.pump_until(lambda: not self.window.tasks.busy)
        self.assertEqual(self.git("rev-list", "--count", "HEAD", cwd=remote), "1")

    def test_failed_push_keeps_draft_and_displays_remote_hook_error(self):
        remote = self.prepare_sync_repository()
        hook = remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nprintf 'Rechazado por el servidor\\n' >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o700)
        self.window.commit_panel.buffer.set_text("Conservar")
        with patch("ui.window.confirm_sync") as confirm, patch("ui.window.show_error") as show:
            self.window.push_button.emit("clicked")
            self.pump_until(lambda: self.window._dialog_pending)
            confirm.call_args.args[2]()
            self.pump_until(lambda: not self.window.tasks.busy)
            self.assertIn("Push", show.call_args.args[1])
            self.assertIn("Rechazado por el servidor", show.call_args.args[2])
        self.assertEqual(self.window.commit_panel.message, "Conservar")
        self.assertEqual(self.git("for-each-ref", cwd=remote), "")
        self.assertIsNone(self.window.repository.upstream_ref)
        self.assertTrue(self.window.push_button.get_sensitive())
        self.assertFalse(self.window.sync_details_button.get_visible())

    def test_changed_remote_after_confirmation_does_not_publish(self):
        remote = self.prepare_sync_repository()
        with patch("ui.window.confirm_sync") as confirm, patch("ui.window.show_error") as show:
            self.window.push_button.emit("clicked")
            self.pump_until(lambda: self.window._dialog_pending)
            self.git("remote", "set-url", "origin", str(Path(self.temporary.name) / "otro.git"))
            confirm.call_args.args[2]()
            self.pump_until(lambda: not self.window.tasks.busy)
            self.assertIn("cambiaron", show.call_args.args[1])
        self.assertEqual(self.git("for-each-ref", cwd=remote), "")

    def test_successful_push_with_refresh_failure_is_not_reported_as_failed_push(self):
        from git.git_service import GitServiceError
        remote = self.prepare_sync_repository()
        original_sync = self.window.service.sync
        original_inspect = self.window.service.inspect_repository
        completed = []

        def sync(*args):
            result = original_sync(*args)
            completed.append(True)
            return result

        def inspect(*args):
            if completed:
                raise GitServiceError("No se puede consultar", stderr="Error al actualizar")
            return original_inspect(*args)

        with patch.object(self.window.service, "sync", side_effect=sync), \
                patch.object(self.window.service, "inspect_repository", side_effect=inspect), \
                patch("ui.window.confirm_sync") as confirm, patch("ui.window.show_error") as show:
            self.window.push_button.emit("clicked")
            self.pump_until(lambda: self.window._dialog_pending)
            confirm.call_args.args[2]()
            self.pump_until(lambda: not self.window.tasks.busy)
            self.assertIn("Push se completó", show.call_args.args[1])
            self.assertIn("Error al actualizar", show.call_args.args[2])
        self.assertEqual(self.git("rev-list", "--count", "HEAD", cwd=remote), "1")
        self.assertTrue(self.window.sync_details_button.get_visible())
        self.assertIn("main", self.window._last_sync.details)

    def test_history_tabs_are_available_only_for_repositories_and_open_without_writing(self):
        self.assertFalse(self.window.view_switcher.get_visible())
        self.open_folder()
        self.assertFalse(self.window.view_switcher.get_visible())
        self.create_repository()
        self.open_folder()
        self.assertTrue(self.window.view_switcher.get_visible())
        self.assertEqual(self.window.views.get_visible_child_name(), "changes")
        self.assertIs(self.window.view_switcher.get_stack(), self.window.views)

        def has_history_label(widget):
            if isinstance(widget, self.Gtk.Label) and widget.get_text() == "Historial":
                return True
            child = widget.get_first_child()
            while child:
                if has_history_label(child):
                    return True
                child = child.get_next_sibling()
            return False

        button = self.window.view_switcher.get_first_child()
        while button and not has_history_label(button):
            button = button.get_next_sibling()
        self.assertIsNotNone(button)
        button.emit("clicked")
        self.wait_for_history()
        self.assertEqual(self.window.views.get_visible_child_name(), "history")
        self.assertEqual(self.window.history_panel.count_label.get_text(), "0")
        self.assertIn("Todavía no hay commits", self.window.history_panel.message_label.get_text())
        self.assertFalse(self.window.history_panel.spinner.get_spinning())
        self.assertEqual(self.git("ls-files"), "")

    def test_history_rows_show_literal_message_author_date_and_selectable_hash(self):
        self.prepare_commit()
        self.git("config", "user.name", "Ana & Jardín 🌸")
        with patch.dict(os.environ, {"GIT_AUTHOR_DATE": "2025-06-01T15:30:00-03:00"}):
            self.window.service.commit(self.folder, "<b>Flores & plantas 🌸</b>\n\nExplicación")
        self.open_folder()
        self.open_history()
        panel = self.window.history_panel
        row = panel.listing.get_row_at_index(0)
        self.assertEqual(row.message_label.get_text(), "<b>Flores & plantas 🌸</b>")
        self.assertFalse(row.message_label.get_use_markup())
        self.assertEqual(row.author_label.get_text(), "Ana & Jardín 🌸")
        self.assertEqual(row.date_label.get_text(), "01/06/2025 · 15:30 -0300")
        self.assertEqual(row.hash_label.get_text(), self.git("rev-parse", "--short=7", "HEAD"))
        self.assertTrue(row.hash_label.get_selectable())
        self.assertFalse(row.get_activatable())
        self.assertFalse(row.get_selectable())
        self.assertFalse(panel.message_label.get_visible())
        self.assertEqual(panel.count_label.get_text(), "1")

    def test_switching_views_preserves_staged_selection_diff_and_commit_draft(self):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        (self.folder / "a.txt").write_text("versión preparada\n", encoding="utf-8")
        self.window.service.stage_file(self.folder, "a.txt")
        (self.folder / "a.txt").write_text("edición posterior\n", encoding="utf-8")
        self.open_folder()
        files = self.window.files_panel
        files.staged_list.select_row(files.staged_list.get_row_at_index(0))
        self.wait_for_diff()
        self.window.commit_panel.buffer.set_text("Conservar borrador")
        before = self.git("ls-files", "--stage")
        with patch.object(self.window.service, "get_history", wraps=self.window.service.get_history) as history:
            self.open_history()
            self.window.views.set_visible_child_name("changes")
            self.wait_for_diff()
            self.assertIn("+versión preparada", self.diff_text())
            self.assertEqual(files.selected_file.path, "a.txt")
            self.assertEqual(files.selected_group, "staged")
            self.assertEqual(self.window.commit_panel.message, "Conservar borrador")
            self.open_history()
            self.assertEqual(history.call_count, 1)
        self.assertEqual(self.git("ls-files", "--stage"), before)

    def test_first_commit_invalidates_cached_empty_history(self):
        self.prepare_commit()
        self.open_history()
        self.assertEqual(self.window.history_panel.commits, ())
        self.window.views.set_visible_child_name("changes")
        self.window.commit_panel.buffer.set_text("Mi primer commit")
        self.window.commit_panel.commit_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.open_history()
        self.assertEqual(self.window.history_panel.commits[0].message, "Mi primer commit")
        self.assertEqual(self.window.history_panel.count_label.get_text(), "1")

    def test_manual_refresh_updates_visible_history_after_external_commit(self):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        self.open_folder()
        self.open_history()
        self.git("commit", "--allow-empty", "-m", "Creado desde la terminal")
        self.window.refresh_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_history()
        self.assertEqual(self.window.views.get_visible_child_name(), "history")
        self.assertEqual(self.window.history_panel.commits[0].message, "Creado desde la terminal")
        self.assertEqual(len(self.window.history_panel.commits), 2)

    def test_slow_history_keeps_gtk_responsive_and_coalesces_fast_view_switches(self):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        self.open_folder()
        original = self.window.service.get_history
        started, release = threading.Event(), threading.Event()
        reads = []

        def delayed(root):
            reads.append(root)
            if len(reads) == 1:
                started.set()
                if not release.wait(5):
                    raise RuntimeError("La prueba no liberó el lector")
            return original(root)

        with patch.object(self.window.service, "get_history", side_effect=delayed):
            try:
                self.window.views.set_visible_child_name("history")
                self.pump_until(started.is_set)
                self.assertTrue(self.window.history_panel.spinner.get_spinning())
                responsive = []
                self.GLib.idle_add(lambda: responsive.append(True) and False)
                self.pump_until(lambda: bool(responsive))
                self.assertTrue(self.window.open_button.get_sensitive())
                self.assertTrue(self.window.refresh_button.get_sensitive())
                for _index in range(3):
                    self.window.views.set_visible_child_name("changes")
                    self.window.views.set_visible_child_name("history")
            finally:
                release.set()
            self.wait_for_history()
        self.assertEqual(len(reads), 2)
        self.assertEqual(self.window.history_panel.count_label.get_text(), "1")
        self.assertFalse(self.window.history_panel.spinner.get_spinning())

    def test_switching_repository_discards_history_still_loading(self):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Del repositorio anterior")
        self.open_folder()
        other = Path(self.temporary.name) / "otra carpeta"
        other.mkdir()
        self.window.service.initialize_repository(other)
        self.git("config", "user.name", "Otro autor", cwd=other)
        self.git("config", "user.email", "otro@example.test", cwd=other)
        (other / "otro.txt").write_text("otro", encoding="utf-8")
        self.window.service.stage_all(other)
        self.window.service.commit(other, "Del repositorio nuevo")
        original = self.window.service.get_history
        started, release = threading.Event(), threading.Event()

        def delayed(root):
            commits = original(root)
            if root == self.folder:
                started.set()
                if not release.wait(5):
                    raise RuntimeError("La prueba no liberó el lector")
            return commits

        with patch.object(self.window.service, "get_history", side_effect=delayed):
            try:
                self.window.views.set_visible_child_name("history")
                self.pump_until(started.is_set)
                self.window.open_repository(other)
                self.pump_until(lambda: not self.window.tasks.busy)
                self.assertEqual(self.window.views.get_visible_child_name(), "changes")
                self.assertEqual(self.window.history_panel.commits, ())
                self.window.views.set_visible_child_name("history")
            finally:
                release.set()
            self.wait_for_history()
        self.assertEqual([commit.message for commit in self.window.history_panel.commits], ["Del repositorio nuevo"])
        self.assertEqual(self.window.history_panel.listing.get_row_at_index(0).author_label.get_text(), "Otro autor")

    def test_refresh_discards_an_old_history_read_and_reloads_new_commits(self):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        self.open_folder()
        original = self.window.service.get_history
        started, release = threading.Event(), threading.Event()
        reads = []

        def delayed(root):
            commits = original(root)
            reads.append(root)
            if len(reads) == 1:
                started.set()
                if not release.wait(5):
                    raise RuntimeError("La prueba no liberó el lector")
            return commits

        with patch.object(self.window.service, "get_history", side_effect=delayed):
            try:
                self.window.views.set_visible_child_name("history")
                self.pump_until(started.is_set)
                self.git("commit", "--allow-empty", "-m", "Nuevo commit externo")
                self.window.refresh_button.emit("clicked")
                self.pump_until(lambda: not self.window.tasks.busy)
            finally:
                release.set()
            self.wait_for_history()
        self.assertEqual(len(reads), 2)
        self.assertEqual(len(self.window.history_panel.commits), 2)
        self.assertEqual(self.window.history_panel.commits[0].message, "Nuevo commit externo")

    def test_history_error_exposes_git_details_and_manual_refresh_can_retry(self):
        from git.git_service import GitServiceError
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        self.open_folder()
        error = GitServiceError("No se pudo leer el historial", stderr="fatal: bad object HEAD", returncode=128)
        with patch.object(self.window.service, "get_history", side_effect=error):
            self.open_history()
        panel = self.window.history_panel
        self.assertIn("No se pudo leer", panel.message_label.get_text())
        self.assertTrue(panel.details_button.get_visible())
        self.assertFalse(panel.spinner.get_spinning())
        with patch.object(panel, "on_details") as details:
            panel.details_button.emit("clicked")
            details.assert_called_once_with(error)
        self.window.refresh_button.emit("clicked")
        self.pump_until(lambda: not self.window.tasks.busy)
        self.wait_for_history()
        self.assertFalse(panel.details_button.get_visible())
        self.assertEqual(len(panel.commits), 1)

    def test_closing_during_history_read_does_not_update_destroyed_window(self):
        self.prepare_commit()
        self.window.service.commit(self.folder, "Inicial")
        self.open_folder()
        original = self.window.service.get_history
        started, release = threading.Event(), threading.Event()

        def delayed(root):
            started.set()
            if not release.wait(5):
                raise RuntimeError("La prueba no liberó el lector")
            return original(root)

        with patch.object(self.window.service, "get_history", side_effect=delayed), \
                patch.object(self.window.history_panel, "show_history") as render:
            try:
                self.window.views.set_visible_child_name("history")
                self.pump_until(started.is_set)
                self.window.close()
                self.pump()
                self.assertTrue(self.window._closed)
            finally:
                release.set()
            self.wait_for_history()
            render.assert_not_called()


if __name__ == "__main__":
    unittest.main()
