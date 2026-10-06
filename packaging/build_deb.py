# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Crear un paquete binario .deb con dpkg-deb, sin instalarlo ni utilizar sudo."""

import argparse
import hashlib
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


PROJECT_DIR = Path(__file__).resolve().parent.parent
APP_ID = "org.gixsie.GixsiePy"
DEFAULT_VERSION = "0.1.0-1"
DEFAULT_MAINTAINER = "Mina (Lakhezis) <silvina@tocci.ar>"


def copy_file(source, target, mode=0o644):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(mode)


def build_deb(source, output_dir, *, version=DEFAULT_VERSION, maintainer=DEFAULT_MAINTAINER):
    if not re.fullmatch(r"[0-9][A-Za-z0-9.+:~\-]*", version):
        raise ValueError("La versión debe comenzar con un número y no contener espacios ni separadores de ruta.")
    if not maintainer.strip() or any(ord(char) < 32 for char in maintainer):
        raise ValueError("El nombre del mantenedor debe ocupar una sola línea.")
    dpkg_deb = shutil.which("dpkg-deb")
    if not dpkg_deb:
        raise ValueError("Falta dpkg-deb. En Debian se incluye en el paquete dpkg.")
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    if epoch < 0:
        raise ValueError("SOURCE_DATE_EPOCH no puede ser negativo.")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package = output_dir / f"gixsiepy_{version.split(':')[-1]}_all.deb"

    with tempfile.TemporaryDirectory(prefix="gixsie-deb-") as temporary:
        root = Path(temporary) / "package"
        app = root / "usr/share/gixsiepy"
        copy_file(source / "main.py", app / "main.py")
        for directory, pattern in (("git", "*.py"), ("ui", "*.py"), ("styles", "*.css"), ("assets", "*.svg")):
            for file in sorted((source / directory).glob(pattern)):
                copy_file(file, app / directory / file.name)
        launcher = root / "usr/bin/gixsiepy"
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text('#!/bin/sh\nexec /usr/bin/python3 -B /usr/share/gixsiepy/main.py "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
        template = (source / "packaging" / f"{APP_ID}.desktop.in").read_text(encoding="utf-8")
        desktop = root / "usr/share/applications" / f"{APP_ID}.desktop"
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text(template.replace("@EXEC@", "/usr/bin/gixsiepy"), encoding="utf-8")
        copy_file(source / "assets" / f"{APP_ID}.svg",
                  root / "usr/share/icons/hicolor/scalable/apps" / f"{APP_ID}.svg")
        documentation = root / "usr/share/doc/gixsiepy"
        copy_file(source / "README.md", documentation / "README.md")
        for file in sorted((source / "docs").glob("*.md")):
            copy_file(file, documentation / "docs" / file.name)
        copy_file(source / "assets" / f"{APP_ID}.svg", documentation / "assets" / f"{APP_ID}.svg")
        for name in ("LICENSE", "COPYRIGHT"):
            copy_file(source / name, documentation / name)
        (documentation / "copyright").write_text(
            (source / "COPYRIGHT").read_text(encoding="utf-8") + "\n"
            + (source / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")

        payload = sorted(path for path in root.rglob("*") if path.is_file())
        size = math.ceil(sum(path.stat().st_size for path in payload) / 1024)
        control_template = (source / "packaging/control.in").read_text(encoding="utf-8")
        control_dir = root / "DEBIAN"
        control_dir.mkdir()
        control = (control_template.replace("@VERSION@", version)
                   .replace("@MAINTAINER@", maintainer).replace("@SIZE@", str(size)))
        (control_dir / "control").write_text(control, encoding="utf-8")
        sums = "".join(f"{hashlib.md5(path.read_bytes()).hexdigest()}  {path.relative_to(root)}\n" for path in payload)
        (control_dir / "md5sums").write_text(sums, encoding="utf-8")
        # Fechas y propietarios estables, aunque quien construya el paquete no sea root.
        for path in root.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
            elif path != launcher:
                path.chmod(0o644)
            os.utime(path, (epoch, epoch))
        root.chmod(0o755)
        os.utime(root, (epoch, epoch))
        environment = os.environ.copy()
        environment["SOURCE_DATE_EPOCH"] = str(epoch)
        with tempfile.TemporaryDirectory(prefix=".gixsie-build-", dir=output_dir) as output:
            archive = Path(output) / package.name
            subprocess.run([dpkg_deb, "--root-owner-group", "-Zxz", "--build", str(root), str(archive)],
                           check=True, capture_output=True, text=True, env=environment)
            archive.chmod(0o644)
            archive.replace(package)
    checksum = hashlib.sha256(package.read_bytes()).hexdigest()
    package.with_suffix(".deb.sha256").write_text(f"{checksum}  {package.name}\n", encoding="utf-8")
    return package


def main():
    parser = argparse.ArgumentParser(description="Generar el paquete .deb de GixsiePy para Debian 13.")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Versión Debian, por ejemplo 0.1.0-1.")
    parser.add_argument("--maintainer", default=DEFAULT_MAINTAINER, help="Nombre y correo del mantenedor del paquete.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "dist", help="Carpeta para el .deb y su checksum.")
    args = parser.parse_args()
    try:
        package = build_deb(PROJECT_DIR, args.output_dir, version=args.version, maintainer=args.maintainer)
        print(f"Paquete creado: {package}\nPara instalar: sudo apt install {shlex.quote(str(package))}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(f"No se pudo crear el paquete: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
