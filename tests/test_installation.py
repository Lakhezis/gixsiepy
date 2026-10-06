# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Instalación, actualización y desinstalación aisladas en carpetas temporales."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import install


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gixsie-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.paths = install.InstallPaths(self.base / "datos", self.base / "bin")
        self.source = install.SOURCE_DIR

    def install(self):
        install.install(self.source, self.paths)

    def test_install_copies_only_application_files_and_executable_launcher(self):
        self.install()
        root = self.paths.app_dir
        for relative in ("main.py", "install.py", "git/__init__.py", "git/git_service.py",
                         "ui/__init__.py", "ui/history_panel.py", "styles/style.css",
                         "assets/flower-pattern.svg", f"assets/{install.APP_ID}.svg", "README.md",
                         "docs/USAGE.md", "docs/DEVELOPMENT.md", "LICENSE", "COPYRIGHT"):
            self.assertEqual((root / relative).read_bytes(), (self.source / relative).read_bytes())
        self.assertFalse((root / ".git").exists())
        self.assertFalse((root / "tests").exists())
        self.assertFalse(list(root.rglob("__pycache__")))
        self.assertTrue(os.access(self.paths.launcher, os.X_OK))
        self.assertEqual(self.paths.desktop.stat().st_mode & 0o777, 0o644)
        help_result = subprocess.run([str(self.paths.launcher), "--help"], cwd=self.base,
                                     capture_output=True, text=True, timeout=10)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("help", help_result.stdout.lower())
        self.assertFalse(list(root.rglob("__pycache__")))

    @unittest.skipUnless(shutil.which("desktop-file-validate"), "Validación opcional de freedesktop")
    def test_desktop_entry_is_valid(self):
        self.install()
        result = subprocess.run(["desktop-file-validate", str(self.paths.desktop)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_desktop_and_launcher_handle_spaces_unicode_and_special_characters(self):
        import gi
        from gi.repository import Gio

        self.paths = install.InstallPaths(self.base / 'mi jardín 100% " $ ` \\', self.base / "mis programas")
        self.install()
        desktop = Gio.DesktopAppInfo.new_from_filename(str(self.paths.desktop))
        self.assertIsNotNone(desktop)
        self.assertEqual(desktop.get_name(), "GixsiePy")
        self.assertEqual(desktop.get_executable(), "/usr/bin/python3")
        self.assertEqual(desktop.get_icon().to_string(), install.APP_ID)
        # Gio interpreta los escapes de Exec, incluidos los porcentajes, al lanzar.
        environment = Gio.AppLaunchContext()
        environment.setenv("GIXSIE_INSTALL_TEST_OUTPUT", str(self.base / "arranque.txt"))
        (self.paths.app_dir / "main.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "Path(os.environ['GIXSIE_INSTALL_TEST_OUTPUT']).write_text(str(Path(__file__).resolve()))\n",
            encoding="utf-8",
        )
        import time
        desktop.launch([], environment)
        deadline = time.monotonic() + 5
        output = self.base / "arranque.txt"
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(output.exists(), "El archivo .desktop no pudo iniciar la copia instalada")
        self.assertEqual(output.read_text(), str(self.paths.app_dir / "main.py"))
        with patch.dict(os.environ, {"GIXSIE_INSTALL_TEST_OUTPUT": str(output)}):
            subprocess.run([str(self.paths.launcher)], cwd=self.base, check=True, timeout=5)
        self.assertEqual(output.read_text(), str(self.paths.app_dir / "main.py"))

    def test_reinstall_updates_the_copy_and_can_run_from_installed_directory(self):
        self.install()
        self.install()
        source = self.base / "código nuevo"
        shutil.copytree(self.paths.app_dir, source)
        (source / "styles/style.css").write_text("/* actualización */\n", encoding="utf-8")
        install.install(source, self.paths)
        self.assertEqual((self.paths.app_dir / "styles/style.css").read_text(), "/* actualización */\n")
        install.install(self.paths.app_dir, self.paths)

    def test_uninstall_removes_owned_files_and_preserves_unrelated_files(self):
        self.install()
        other_app = self.paths.desktop.parent / "otra.desktop"
        other_app.write_text("otra aplicación", encoding="utf-8")
        user_file = self.paths.app_dir / "nota personal.txt"
        user_file.write_text("conservar", encoding="utf-8")
        install.uninstall(self.paths)
        self.assertTrue(other_app.exists())
        self.assertTrue(user_file.exists())
        for file in (self.paths.desktop, self.paths.icon, self.paths.launcher, self.paths.manifest,
                     self.paths.app_dir / "main.py"):
            self.assertFalse(file.exists())

    def test_uninstall_leaves_no_application_directory_when_there_are_no_extra_files(self):
        self.install()
        install.uninstall(self.paths)
        self.assertFalse(self.paths.app_dir.exists())

    def test_modified_installed_files_block_update_and_uninstall_before_any_changes(self):
        self.install()
        self.paths.launcher.write_text("mi lanzador personalizado", encoding="utf-8")
        before = (self.paths.app_dir / "main.py").read_bytes()
        for operation in (self.install, lambda: install.uninstall(self.paths)):
            with self.subTest(operation=operation), self.assertRaises(install.InstallationError):
                operation()
            self.assertEqual(self.paths.launcher.read_text(), "mi lanzador personalizado")
            self.assertEqual((self.paths.app_dir / "main.py").read_bytes(), before)
            self.assertTrue(self.paths.manifest.exists())

    def test_existing_unowned_launcher_is_not_overwritten(self):
        self.paths.bin_dir.mkdir()
        self.paths.launcher.write_text("archivo ajeno", encoding="utf-8")
        with self.assertRaises(install.InstallationError):
            self.install()
        self.assertEqual(self.paths.launcher.read_text(), "archivo ajeno")
        self.assertFalse(self.paths.app_dir.exists())

    def test_symlinked_application_directory_or_resource_folder_is_not_followed(self):
        outside = self.base / "fuera"
        outside.mkdir()
        self.paths.data_dir.mkdir()
        self.paths.app_dir.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(install.InstallationError):
            self.install()
        self.paths.app_dir.unlink()
        self.install()
        shutil.rmtree(self.paths.app_dir / "assets")
        (self.paths.app_dir / "assets").symlink_to(outside, target_is_directory=True)
        for operation in (self.install, lambda: install.uninstall(self.paths)):
            with self.subTest(operation=operation), self.assertRaises(install.InstallationError):
                operation()
        self.assertEqual(list(outside.iterdir()), [])

    def test_corrupt_or_outside_manifest_does_not_delete_other_files(self):
        import json

        self.install()
        outside = self.base / "repositorio.txt"
        outside.write_text("no borrar", encoding="utf-8")
        manifest = json.loads(self.paths.manifest.read_text())
        manifest["files"][str(outside)] = install.digest(outside.read_bytes())
        self.paths.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(install.InstallationError):
            install.uninstall(self.paths)
        self.assertTrue(outside.exists())
        self.assertTrue(self.paths.launcher.exists())
        self.paths.manifest.write_text("{", encoding="utf-8")
        with self.assertRaises(install.InstallationError):
            self.install()

    def test_failed_write_rolls_back_files_already_updated(self):
        self.install()
        source = self.base / "código nuevo"
        shutil.copytree(self.paths.app_dir, source)
        (source / "main.py").write_text("# nueva versión\n", encoding="utf-8")
        before = (self.paths.app_dir / "main.py").read_bytes()
        original_write = install.write_file

        def fail_once(path, *args):
            if path == self.paths.desktop:
                raise OSError("sin espacio")
            original_write(path, *args)

        with patch.object(install, "write_file", side_effect=fail_once):
            with self.assertRaises(OSError):
                install.install(source, self.paths)
        self.assertEqual((self.paths.app_dir / "main.py").read_bytes(), before)
        install.uninstall(self.paths)

    def test_failed_first_install_can_be_retried_without_leftover_files(self):
        original_write = install.write_file

        def fail_once(path, *args):
            if path == self.paths.desktop:
                raise OSError("sin espacio")
            original_write(path, *args)

        with patch.object(install, "write_file", side_effect=fail_once):
            with self.assertRaises(OSError):
                self.install()
        self.assertFalse(self.paths.app_dir.exists())
        self.install()
        install.uninstall(self.paths)

    def test_update_removes_only_obsolete_registered_files(self):
        old_source = self.base / "versión anterior"
        shutil.copytree(self.source / "ui", old_source / "ui")
        for relative in ("main.py", "install.py", "README.md", "LICENSE", "COPYRIGHT",
                         "git", "styles", "assets", "packaging"):
            origin = self.source / relative
            if origin.is_dir():
                shutil.copytree(origin, old_source / relative)
            else:
                shutil.copyfile(origin, old_source / relative)
        (old_source / "ui/old_panel.py").write_text("# anterior\n", encoding="utf-8")
        install.install(old_source, self.paths)
        unrelated = self.paths.app_dir / "ui/my_notes.py"
        unrelated.write_text("# conservar\n", encoding="utf-8")
        self.install()
        self.assertFalse((self.paths.app_dir / "ui/old_panel.py").exists())
        self.assertTrue(unrelated.exists())
        install.uninstall(self.paths)
        self.assertTrue(unrelated.exists())

    def test_xdg_default_relative_and_custom_absolute_directory(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": ""}):
            self.assertEqual(install.user_paths().data_dir, Path.home() / ".local/share")
        with patch.dict(os.environ, {"XDG_DATA_HOME": "ruta-relativa"}):
            self.assertEqual(install.user_paths().data_dir, Path.home() / ".local/share")
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.base)}):
            self.assertEqual(install.user_paths().data_dir, self.base)

    def test_missing_git_is_explained_without_installing_files(self):
        with patch("install.shutil.which", return_value=None):
            with self.assertRaisesRegex(install.InstallationError, "sudo apt install git"):
                install.check_dependencies()
        self.assertFalse(self.paths.app_dir.exists())

    def test_relative_and_control_character_destinations_are_rejected(self):
        for data_dir in (Path("relativa"), self.base / "salto\nde línea", self.base / ".." / "otra"):
            with self.subTest(data_dir=data_dir), self.assertRaises(install.InstallationError):
                install.install(self.source, install.InstallPaths(data_dir, self.paths.bin_dir))

    @unittest.skipUnless(os.environ.get("GIXSIE_RUN_UI_TESTS") == "1", "Prueba gráfica opcional")
    def test_installed_copy_opens_a_gtk_window_from_another_directory(self):
        self.install()
        # Un proceso nuevo evita que imports de la carpeta de desarrollo oculten archivos faltantes.
        script = """
import sys
import time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from main import APPLICATION_ID, PROJECT_DIR, GitGuiApplication
from gi.repository import Gdk, Gio, GLib, Gtk
assert PROJECT_DIR == Path(sys.argv[1])
application = GitGuiApplication()
application.set_application_id('org.gixsie.InstalledTests')
application.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
application.register(None)
application.activate()
context = GLib.MainContext.default()
deadline = time.monotonic() + 5
while not application.window.get_mapped() and time.monotonic() < deadline:
    while context.pending():
        context.iteration(False)
    time.sleep(0.01)
assert application.window.get_mapped()
assert application.window.stack.get_visible_child_name() == 'welcome'
assert Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).has_icon(APPLICATION_ID)
assert Gtk.Window.get_default_icon_name() == APPLICATION_ID
folder = Path(sys.argv[2]) / 'repositorio'
folder.mkdir()
application.window.service.initialize_repository(folder)
application.window.open_repository(folder)
deadline = time.monotonic() + 5
while application.window.tasks.busy and time.monotonic() < deadline:
    while context.pending():
        context.iteration(False)
    time.sleep(0.01)
assert application.window.repository.is_repository
assert application.window.view_switcher.get_visible()
application.window.close()
application.quit()
"""
        result = subprocess.run(["/usr/bin/python3", "-B", "-c", script,
                                 str(self.paths.app_dir), str(self.base)], cwd=self.base,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(list(self.paths.app_dir.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
