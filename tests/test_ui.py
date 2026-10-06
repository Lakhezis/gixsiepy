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
                        and self.window._pending_diff is None)
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

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments], cwd=self.folder, check=True, capture_output=True, text=True,
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


if __name__ == "__main__":
    unittest.main()
