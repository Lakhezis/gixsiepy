"""Operaciones Git mediante el ejecutable instalado en el sistema."""

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess


class GitServiceError(Exception):
    def __init__(self, message, *, command=(), stdout="", stderr="", returncode=None):
        super().__init__(message)
        self.command = tuple(command)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    @property
    def details(self):
        lines = []
        if self.command:
            lines.append(f"Comando: {shlex.join(self.command)}")
        if self.returncode is not None:
            lines.append(f"Código de salida: {self.returncode}")
        if self.stderr.strip():
            lines.append(self.stderr.strip())
        if self.stdout.strip():
            lines.append(self.stdout.strip())
        return "\n\n".join(lines)


@dataclass(frozen=True)
class RepositoryInfo:
    selected_path: Path
    root_path: Path | None = None
    branch: str | None = None
    head_short: str | None = None

    @property
    def is_repository(self):
        return self.root_path is not None

    @property
    def name(self):
        path = self.root_path or self.selected_path
        return path.name or str(path)

    @property
    def has_commits(self):
        return self.head_short is not None


class GitService:
    def __init__(self, timeout=30):
        self.timeout = timeout

    def _run(self, arguments, *, cwd=None, accepted_codes=(0,)):
        executable = shutil.which("git")
        if executable is None:
            raise GitServiceError(
                "Git no está instalado o no está disponible en PATH. "
                "Instalalo con: sudo apt install git"
            )
        command = [executable, "--no-pager", "--literal-pathspecs", *arguments]
        environment = os.environ.copy()
        # Una variable de otra sesión no debe redirigir la carpeta elegida.
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
            environment.pop(key, None)
        environment["LC_ALL"] = "C"
        environment["GIT_TERMINAL_PROMPT"] = "0"
        try:
            result = subprocess.run(
                command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8",
                errors="surrogateescape", timeout=self.timeout, shell=False,
            )
        except FileNotFoundError as error:
            raise GitServiceError(
                "No se pudo ejecutar Git. Comprobá que Git esté instalado "
                "y que la carpeta siga existiendo.", command=command, stderr=str(error),
            ) from error
        except subprocess.TimeoutExpired as error:
            raise GitServiceError(
                "Git tardó demasiado en responder. Revisá la carpeta y volvé a intentar.",
                command=command, stderr=str(error),
            ) from error
        except OSError as error:
            raise GitServiceError(
                "No se pudo acceder a la carpeta o ejecutar Git. Revisá los permisos.",
                command=command, stderr=str(error),
            ) from error
        if result.returncode not in accepted_codes:
            raise self._command_error(result)
        return result

    @staticmethod
    def _command_error(result):
        if "dubious ownership" in result.stderr:
            message = (
                "Git no confía en el propietario de esta carpeta. "
                "Revisá su propiedad y la configuración de seguridad de Git."
            )
        elif "Permission denied" in result.stderr:
            message = "Git no tiene permiso para acceder al repositorio. Revisá los permisos."
        else:
            message = "Git no pudo completar la operación. Podés consultar su mensaje en los detalles."
        return GitServiceError(
            message, command=result.args, stdout=result.stdout,
            stderr=result.stderr, returncode=result.returncode,
        )

    @staticmethod
    def _folder(path):
        try:
            folder = Path(path).expanduser().resolve(strict=True)
            if not folder.is_dir():
                raise GitServiceError("Seleccioná una carpeta, no un archivo.")
            return folder
        except OSError as error:
            raise GitServiceError(
                "La carpeta no existe o no se puede acceder a ella.", stderr=str(error),
            ) from error

    def inspect_repository(self, path):
        folder = self._folder(path)
        self._run(["--version"])
        result = self._run(
            ["rev-parse", "--is-inside-work-tree"], cwd=folder, accepted_codes=(0, 128),
        )
        if result.returncode != 0:
            # Otros errores (permisos, repositorio roto, seguridad) no autorizan init.
            if "not a git repository" in result.stderr:
                return RepositoryInfo(selected_path=folder)
            raise self._command_error(result)
        if result.stdout.strip() != "true":
            raise GitServiceError(
                "Esta carpeta no es una carpeta de trabajo Git. "
                "Abrí la carpeta donde editás los archivos del repositorio."
            )
        root = self._run(["rev-parse", "--show-toplevel"], cwd=folder)
        root_path = Path(root.stdout.removesuffix("\n"))
        branch = self._run(
            ["symbolic-ref", "--quiet", "--short", "HEAD"],
            cwd=root_path, accepted_codes=(0, 1),
        )
        head = self._run(
            ["rev-parse", "--verify", "--quiet", "--short", "HEAD"],
            cwd=root_path, accepted_codes=(0, 1),
        )
        return RepositoryInfo(
            selected_path=folder, root_path=root_path,
            branch=branch.stdout.strip() if branch.returncode == 0 else None,
            head_short=head.stdout.strip() if head.returncode == 0 else None,
        )

    def initialize_repository(self, path):
        """Invocar solamente después de la confirmación explícita en la UI."""
        info = self.inspect_repository(path)
        # Revalidar: otra aplicación pudo inicializar la carpeta mientras tanto.
        if info.is_repository:
            return info
        self._run(["init"], cwd=info.selected_path)
        return self.inspect_repository(info.selected_path)
