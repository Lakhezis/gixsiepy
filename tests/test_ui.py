"""Pruebas gráficas opcionales. Requieren una sesión de escritorio disponible."""

import os
from pathlib import Path
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
        self.folder = Path(self.temporary.name)
        configuration = self.folder / "config"
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
        self.pump_until(lambda: not self.window.tasks.busy)
        for window in list(self.Gtk.Window.get_toplevels()):
            window.destroy()
        self.window.tasks.close()
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


if __name__ == "__main__":
    unittest.main()
