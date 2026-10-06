# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Instalación para el usuario actual, sin paquetes de pip ni permisos de administrador."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile


APP_ID = "org.gixsie.GixsiePy"
SOURCE_DIR = Path(__file__).resolve().parent
MANIFEST_NAME = ".installation.json"


class InstallationError(Exception):
    pass


@dataclass(frozen=True)
class InstallPaths:
    data_dir: Path
    bin_dir: Path

    @property
    def app_dir(self):
        return self.data_dir / "gixsiepy"

    @property
    def desktop(self):
        return self.data_dir / "applications" / f"{APP_ID}.desktop"

    @property
    def icon(self):
        return self.data_dir / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"

    @property
    def launcher(self):
        return self.bin_dir / "gixsiepy"

    @property
    def manifest(self):
        return self.app_dir / MANIFEST_NAME


def user_paths():
    home = Path.home()
    data_dir = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    if not data_dir.is_absolute():
        data_dir = home / ".local/share"
    return InstallPaths(data_dir, home / ".local/bin")


def check_dependencies():
    if not shutil.which("git"):
        raise InstallationError("Falta Git. Instalalo con: sudo apt install git")
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
    except (ImportError, ValueError) as error:
        raise InstallationError(
            "Falta GTK4 o PyGObject. Ejecutá: sudo apt install python3-gi gir1.2-gtk-4.0\n"
            "Después usá /usr/bin/python3 install.py."
        ) from error
    if (Gtk.get_major_version(), Gtk.get_minor_version()) < (4, 10):
        raise InstallationError("GixsiePy necesita GTK 4.10 o posterior.")


def desktop_argument(value):
    # Exec tiene sus propias reglas: primero comillas, luego escapes del archivo .desktop.
    quoted = "".join("\\" + char if char in '\\"`$' else char for char in str(value))
    return '"' + quoted.replace("\\", "\\\\").replace("%", "%%") + '"'


def installation_files(source, paths):
    for path in (paths.data_dir, paths.bin_dir):
        if not path.is_absolute() or ".." in path.parts or any(ord(char) < 32 for char in str(path)):
            raise InstallationError("Las rutas de instalación deben ser absolutas y sin caracteres de control.")
    files = {}
    relative_files = [Path(name) for name in ("main.py", "install.py", "README.md", "LICENSE", "COPYRIGHT")]
    relative_files.append(Path("packaging") / f"{APP_ID}.desktop.in")
    for directory, pattern in (("git", "*.py"), ("ui", "*.py"), ("styles", "*.css"), ("assets", "*.svg"), ("docs", "*.md")):
        relative_files.extend(sorted((source / directory).glob(pattern)))
    for relative in relative_files:
        if relative.is_absolute():
            relative = relative.relative_to(source)
        files[paths.app_dir / relative] = ((source / relative).read_bytes(), 0o644)
    main_path = paths.app_dir / "main.py"
    template = (source / "packaging" / f"{APP_ID}.desktop.in").read_text(encoding="utf-8")
    command = f"/usr/bin/python3 -B {desktop_argument(main_path)}"
    files[paths.desktop] = (template.replace("@EXEC@", command).encode("utf-8"), 0o644)
    launcher = f'#!/bin/sh\nexec /usr/bin/python3 -B {shlex.quote(str(main_path))} "$@"\n'
    files[paths.launcher] = (launcher.encode("utf-8"), 0o755)
    files[paths.icon] = ((source / "assets" / f"{APP_ID}.svg").read_bytes(), 0o644)
    return files


def digest(content):
    return hashlib.sha256(content).hexdigest()


def allowed_path(path, paths):
    if path in (paths.desktop, paths.icon, paths.launcher):
        return True
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(paths.app_dir):
        return False
    relative = path.relative_to(paths.app_dir)
    if str(relative) in ("main.py", "install.py", "README.md", "LICENSE", "COPYRIGHT", f"packaging/{APP_ID}.desktop.in"):
        return True
    return (len(relative.parts) == 2 and relative.parts[0] in ("git", "ui", "styles", "assets", "docs")
            and relative.suffix in (".py", ".css", ".svg", ".md"))


def installed_files(paths):
    if any(path.is_symlink() for path in (paths.app_dir, paths.manifest,
            *(paths.app_dir / name for name in ("git", "ui", "styles", "assets", "docs", "packaging")))):
        raise InstallationError("La instalación no puede reemplazar enlaces simbólicos.")
    if paths.app_dir.exists() and not paths.app_dir.is_dir():
        raise InstallationError(f"La ruta de instalación ya existe y no es una carpeta: {paths.app_dir}")
    if not paths.manifest.exists():
        if paths.app_dir.exists() and any(paths.app_dir.iterdir()):
            raise InstallationError(f"La carpeta ya contiene archivos ajenos a esta instalación: {paths.app_dir}")
        return {}
    try:
        manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        if manifest["application"] != APP_ID or manifest["format"] != 1:
            raise ValueError("Identificación de instalación inválida")
        files = {Path(name): checksum for name, checksum in manifest["files"].items()}
        if any(not allowed_path(path, paths) or not isinstance(checksum, str) for path, checksum in files.items()):
            raise ValueError("Archivo fuera de la instalación")
        return files
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise InstallationError("No se pudo leer el registro de instalación; no se modificó ningún archivo.") from error


def check_existing(files, owned):
    for path in files:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise InstallationError(f"No se puede reemplazar este archivo o enlace: {path}")
        if path.exists() and (path not in owned or digest(path.read_bytes()) != owned[path]):
            raise InstallationError(f"El archivo ya existe o fue modificado fuera del instalador: {path}\n"
                                    "Conservá una copia y movelo antes de continuar.")


def write_file(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reemplazo atómico: una interrupción no deja un archivo escrito a medias.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(content)
            temporary.flush()
            temporary_path.chmod(mode)
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def remove_empty_app_directories(paths):
    # Solo se quitan carpetas vacías de la aplicación; nunca carpetas compartidas del usuario.
    for directory in ("git", "ui", "styles", "assets", "docs", "packaging", ""):
        try:
            (paths.app_dir / directory).rmdir()
        except OSError:
            pass


def install(source, paths):
    files = installation_files(source, paths)
    owned = installed_files(paths)
    check_existing(set(files) | set(owned), owned)
    manifest = {"application": APP_ID, "format": 1,
                "files": {str(path): digest(content) for path, (content, _mode) in files.items()}}
    for obsolete in set(owned) - set(files):
        files[obsolete] = (None, 0)
    files[paths.manifest] = (json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8") + b"\n", 0o644)
    before = {path: (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None for path in files}
    written = []
    try:
        for path, (content, mode) in files.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                write_file(path, content, mode)
            written.append(path)
    except OSError:
        for path in reversed(written):
            if before[path] is None:
                path.unlink(missing_ok=True)
            else:
                write_file(path, *before[path])
        remove_empty_app_directories(paths)
        raise


def uninstall(paths):
    owned = installed_files(paths)
    if not owned:
        raise InstallationError("No se encontró una instalación de GixsiePy para este usuario.")
    check_existing(owned, owned)
    for path in owned:
        path.unlink(missing_ok=True)
    paths.manifest.unlink()
    remove_empty_app_directories(paths)


def main():
    parser = argparse.ArgumentParser(description="Instalar GixsiePy para el usuario actual, sin sudo.")
    parser.add_argument("--uninstall", action="store_true", help="Quitar los archivos instalados de GixsiePy.")
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise InstallationError("Ejecutá este instalador como tu usuario habitual, sin sudo.")
        paths = user_paths()
        if args.uninstall:
            uninstall(paths)
            print("GixsiePy desinstalada. Tus repositorios permanecen intactos.")
        else:
            check_dependencies()
            install(SOURCE_DIR, paths)
            print(f"GixsiePy instalada en {paths.app_dir}\n"
                  f"Buscá GixsiePy en el menú de aplicaciones.\n"
                  f"También podés ejecutar: {shlex.quote(str(paths.launcher))}\n"
                  "Para actualizarla, volvé a ejecutar este instalador con el código nuevo.")
        return 0
    except (InstallationError, OSError) as error:
        print(f"No se pudo completar la operación: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
