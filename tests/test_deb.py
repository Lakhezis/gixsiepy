# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Verificar paquetes .deb sin instalar archivos en el sistema."""

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parent.parent
# Cargar el script por su ruta evita confundirlo con el paquete de Python llamado packaging.
spec = importlib.util.spec_from_file_location("gixsie_deb", PROJECT_DIR / "packaging/build_deb.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
APP_ID, DEFAULT_VERSION, build_deb = builder.APP_ID, builder.DEFAULT_VERSION, builder.build_deb


@unittest.skipUnless(shutil.which("dpkg-deb"), "Estas pruebas requieren dpkg-deb")
class DebTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gixsie-deb-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.package = build_deb(PROJECT_DIR, self.base / "salida con espacios")

    def extract(self):
        root = self.base / "extraído"
        subprocess.run(["dpkg-deb", "--raw-extract", str(self.package), str(root)],
                       check=True, capture_output=True)
        return root

    def test_metadata_declares_application_architecture_and_dependencies(self):
        result = subprocess.run(["dpkg-deb", "--field", str(self.package)],
                                check=True, capture_output=True, text=True).stdout
        for field in ("Package: gixsiepy", f"Version: {DEFAULT_VERSION}", "Architecture: all",
                      "python3 (>= 3.10)", "python3-gi", "gir1.2-gtk-4.0 (>= 4.10)", "git",
                      "Suggests: fonts-quicksand"):
            self.assertIn(field, result)

    def test_payload_has_code_resources_launcher_menu_and_documentation_only(self):
        root = self.extract()
        app = root / "usr/share/gixsiepy"
        self.assertEqual((app / "main.py").read_bytes(), (PROJECT_DIR / "main.py").read_bytes())
        for directory in ("git", "ui", "styles", "assets"):
            self.assertTrue((app / directory).is_dir())
        documentation = root / "usr/share/doc/gixsiepy"
        for relative in ("README.md", "docs/USAGE.md", "docs/DEVELOPMENT.md", f"assets/{APP_ID}.svg",
                         "LICENSE", "COPYRIGHT"):
            self.assertEqual((documentation / relative).read_bytes(), (PROJECT_DIR / relative).read_bytes())
        copyright_notice = (documentation / "copyright").read_text(encoding="utf-8")
        self.assertIn("SPDX-License-Identifier: GPL-3.0-or-later", copyright_notice)
        self.assertIn("Copyright (C) 2026 GixsiePy contributors", copyright_notice)
        self.assertIn((PROJECT_DIR / "LICENSE").read_text(encoding="utf-8"), copyright_notice)
        self.assertTrue((root / "usr/share/icons/hicolor/scalable/apps" / f"{APP_ID}.svg").is_file())
        for name in (".git", ".venv", "__pycache__", "tests", "install.py", "packaging", "dist"):
            self.assertFalse(list(app.rglob(name)), name)
        launcher = root / "usr/bin/gixsiepy"
        self.assertEqual(launcher.stat().st_mode & 0o777, 0o755)
        self.assertIn('exec /usr/bin/python3 -B /usr/share/gixsiepy/main.py "$@"', launcher.read_text())
        desktop = root / "usr/share/applications" / f"{APP_ID}.desktop"
        self.assertIn("Exec=/usr/bin/gixsiepy", desktop.read_text())
        self.assertIn(f"Icon={APP_ID}", desktop.read_text())
        self.assertEqual(sorted(path.name for path in (root / "DEBIAN").iterdir()), ["control", "md5sums"])

    def test_archive_has_root_ownership_normal_permissions_and_no_system_configuration(self):
        data = subprocess.run(["dpkg-deb", "--fsys-tarfile", str(self.package)],
                              check=True, capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive.getmembers():
                with self.subTest(path=member.name):
                    self.assertEqual((member.uid, member.gid), (0, 0))
                    self.assertIn(member.mode, (0o644, 0o755))
                    self.assertFalse(member.issym())
                    self.assertTrue(member.name in (".", "./", "./usr") or member.name.startswith("./usr/"))

    def test_checksums_match_every_payload_file(self):
        root = self.extract()
        checksums = (root / "DEBIAN/md5sums").read_text().splitlines()
        self.assertEqual(len(checksums), len([file for file in (root / "usr").rglob("*") if file.is_file()]))
        for line in checksums:
            checksum, name = line.split("  ", 1)
            self.assertEqual(hashlib.md5((root / name).read_bytes()).hexdigest(), checksum)
        checksum_file = self.package.with_suffix(".deb.sha256")
        self.assertEqual(checksum_file.read_text().split()[0], hashlib.sha256(self.package.read_bytes()).hexdigest())

    def test_build_is_reproducible_and_supports_custom_version_and_maintainer(self):
        with patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "1750000000"}):
            first = build_deb(PROJECT_DIR, self.base / "primero", version="0.2.0-2", maintainer="Ana <ana@example.test>")
            second = build_deb(PROJECT_DIR, self.base / "segundo", version="0.2.0-2", maintainer="Ana <ana@example.test>")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(first.name, "gixsiepy_0.2.0-2_all.deb")
        result = subprocess.run(["dpkg-deb", "--field", str(first), "Maintainer"],
                                check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "Ana <ana@example.test>")

    def test_invalid_metadata_and_missing_tool_do_not_replace_existing_package(self):
        before = self.package.read_bytes()
        for version in ("../0.1", "0.1\nDepends: otra", "--opción", "", "1/otra"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                build_deb(PROJECT_DIR, self.package.parent, version=version)
        with self.assertRaises(ValueError):
            build_deb(PROJECT_DIR, self.package.parent, maintainer="Ana\nDepends: otra")
        with patch.object(builder.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "dpkg-deb"):
                build_deb(PROJECT_DIR, self.package.parent)
        self.assertEqual(self.package.read_bytes(), before)

    @unittest.skipUnless(shutil.which("desktop-file-validate"), "Validación adicional opcional")
    def test_desktop_file_passes_freedesktop_validation(self):
        root = self.extract()
        result = subprocess.run(["desktop-file-validate", str(root / "usr/share/applications" / f"{APP_ID}.desktop")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(os.environ.get("GIXSIE_RUN_UI_TESTS") == "1", "Prueba gráfica opcional")
    def test_extracted_package_opens_gtk_and_reads_a_repository(self):
        root = self.extract()
        app = root / "usr/share/gixsiepy"
        script = """
import sys
import time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from main import APPLICATION_ID, PROJECT_DIR, GitGuiApplication
from gi.repository import Gdk, Gio, GLib, Gtk
assert PROJECT_DIR == Path(sys.argv[1])
application = GitGuiApplication()
application.set_application_id('org.gixsie.DebTests')
application.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
application.register(None)
application.activate()
context = GLib.MainContext.default()
def wait(condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)
    assert condition()
wait(lambda: application.window.get_mapped())
assert Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).has_icon(APPLICATION_ID)
folder = Path(sys.argv[2]) / 'repositorio'
folder.mkdir()
application.window.service.initialize_repository(folder)
application.window.open_repository(folder)
wait(lambda: not application.window.tasks.busy)
assert application.window.repository.is_repository
application.window.views.set_visible_child_name('history')
wait(lambda: not application.window.diff_tasks.busy and application.window._pending_history is None)
assert application.window.history_panel.count_label.get_text() == '0'
application.window.close()
application.quit()
"""
        result = subprocess.run(["/usr/bin/python3", "-B", "-c", script, str(app), str(self.base)],
                                cwd=self.base, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(list(app.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
