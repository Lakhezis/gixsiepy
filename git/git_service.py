"""Operaciones Git mediante el ejecutable instalado en el sistema."""

from dataclasses import dataclass
from contextlib import nullcontext
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


MAX_DIFF_BYTES = 512 * 1024
MAX_DIFF_LINES = 5000


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
class FileDiff:
    path: str
    staged: bool
    text: str = ""
    message: str = ""
    binary: bool = False
    truncated: bool = False


@dataclass(frozen=True)
class FileChange:
    path: str
    index_status: str = "."
    working_status: str = "."
    original_path: str | None = None
    submodule: str = "N..."
    conflicted: bool = False

    @property
    def is_staged(self):
        return self.index_status != "." and not self.conflicted

    @property
    def is_unstaged(self):
        return self.working_status != "." or self.conflicted

    @property
    def can_stage(self):
        return self.is_unstaged and not self.conflicted and not self.submodule.startswith("S")


@dataclass(frozen=True)
class RepositoryInfo:
    selected_path: Path
    root_path: Path | None = None
    branch: str | None = None
    head_short: str | None = None
    files: tuple[FileChange, ...] = ()

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

    @property
    def unstaged_files(self):
        return tuple(file for file in self.files if file.is_unstaged)

    @property
    def staged_files(self):
        return tuple(file for file in self.files if file.is_staged)

    @property
    def can_stage_all(self):
        return bool(self.unstaged_files) and all(file.can_stage for file in self.unstaged_files)

    @property
    def can_commit(self):
        return bool(self.staged_files) and not any(file.conflicted for file in self.files)


class GitService:
    def __init__(self, timeout=30):
        self.timeout = timeout

    def _run(self, arguments, *, cwd=None, accepted_codes=(0,), stdout_limit=None):
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
            # Un diff grande se almacena temporalmente en disco, no entero en memoria.
            with (tempfile.TemporaryFile() if stdout_limit is not None else nullcontext()) as output:
                result = subprocess.run(
                    command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                    stdout=output if output is not None else subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=self.timeout, shell=False,
                )
                result.stdout_truncated = False
                if output is not None:
                    output.seek(0)
                    data = output.read(stdout_limit + 1)
                    result.stdout = data[:stdout_limit]
                    result.stdout_truncated = len(data) > stdout_limit
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
        # Decodificar sin universal-newlines: \r y \n pueden ser parte de una ruta.
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="surrogateescape")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="surrogateescape")
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
        elif "Author identity unknown" in result.stderr or "unable to auto-detect email address" in result.stderr:
            message = (
                "Git necesita tu nombre y correo para crear commits. "
                "Configurá user.name y user.email en Git y volvé a intentar."
            )
        elif "failed to sign" in result.stderr or "gpg failed" in result.stderr:
            message = (
                "Git no pudo firmar el commit. Revisá tu configuración de firma "
                "y el acceso a tu clave antes de volver a intentar."
            )
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
        status = self._run(
            ["--no-optional-locks", "status", "--porcelain=v2", "--branch", "-z",
             "--untracked-files=all", "--renames", "--ignore-submodules=none"],
            cwd=root_path,
        )
        return RepositoryInfo(
            selected_path=folder, root_path=root_path,
            branch=branch.stdout.strip() if branch.returncode == 0 else None,
            head_short=head.stdout.strip() if head.returncode == 0 else None,
            files=self._parse_status(status.stdout),
        )

    @staticmethod
    def _parse_status(output):
        files = []
        records = iter(output.split("\0"))
        try:
            for record in records:
                if not record or record.startswith(("# ", "! ")):
                    continue
                if record.startswith("? "):
                    files.append(FileChange(path=record[2:], working_status="?"))
                    continue
                kind = record[0]
                field_count = {"1": 8, "2": 9, "u": 10}[kind]
                fields = record.split(" ", field_count)
                if len(fields) != field_count + 1 or len(fields[1]) != 2:
                    raise ValueError("Registro Git incompleto")
                original_path = next(records) if kind == "2" else None
                if not fields[-1] or original_path == "":
                    raise ValueError("Ruta Git vacía")
                files.append(FileChange(
                    path=fields[-1], index_status=fields[1][0], working_status=fields[1][1],
                    submodule=fields[2], original_path=original_path, conflicted=kind == "u",
                ))
        except (KeyError, ValueError, StopIteration) as error:
            raise GitServiceError(
                "No se pudo interpretar el estado del repositorio. Probá actualizarlo.",
                stdout=output,
            ) from error
        return tuple(sorted(files, key=lambda file: (file.path.casefold(), file.path)))

    def _working_repository(self, path):
        info = self.inspect_repository(path)
        if not info.is_repository:
            raise GitServiceError("Abrí o inicializá un repositorio para realizar esta acción.")
        return info

    @staticmethod
    def _current_file(info, path):
        # Usar exclusivamente una ruta exacta que Git acaba de informar.
        for file in info.files:
            if file.path == path:
                return file
        raise GitServiceError("El archivo ya no aparece entre los cambios. Actualizá el repositorio.")

    def stage_file(self, repository_path, file_path):
        info = self._working_repository(repository_path)
        file = self._current_file(info, file_path)
        if not file.can_stage:
            raise GitServiceError(
                "Este archivo no se puede preparar desde esta vista. "
                "Los conflictos y los cambios internos de submódulos requieren otra herramienta."
            )
        paths = [file.path]
        if file.working_status == "R" and file.original_path:
            paths.insert(0, file.original_path)
        self._run(["add", "-A", "--", *paths], cwd=info.root_path)
        return self.inspect_repository(repository_path)

    def get_diff(self, repository_path, file_path, *, staged=False):
        info = self._working_repository(repository_path)
        file = self._current_file(info, file_path)
        if file.conflicted:
            return FileDiff(file.path, staged, message="Este archivo tiene conflictos. Resolvelos con otra herramienta.")
        if (staged and not file.is_staged) or (not staged and not file.is_unstaged):
            raise GitServiceError("Esta versión del archivo ya no tiene cambios. Actualizá el repositorio.")
        options = [
            "diff", "--patch", "--no-color", "--no-ext-diff", "--no-textconv",
            "--no-relative", "--src-prefix=a/", "--dst-prefix=b/", "--unified=3",
        ]
        if file.working_status == "?" and not staged:
            if file.path.endswith("/"):
                return FileDiff(file.path, staged, message="Esta entrada es otro repositorio. Abrí su carpeta para ver sus archivos.")
            arguments = [*options, "--no-index", "--", "/dev/null", file.path]
            accepted_codes = (0, 1)  # --no-index usa 1 para indicar diferencias.
        else:
            paths = [file.path]
            code = file.index_status if staged else file.working_status
            if code in ("R", "C") and file.original_path:
                paths.insert(0, file.original_path)
            arguments = [*options, *(["--cached"] if staged else []), "--", *paths]
            accepted_codes = (0,)
        result = self._run(
            arguments, cwd=info.root_path, accepted_codes=accepted_codes, stdout_limit=MAX_DIFF_BYTES,
        )
        if result.stderr.startswith(("error:", "fatal:")):
            raise self._command_error(result)
        text = result.stdout
        binary = any(line.startswith(("Binary files ", "GIT binary patch")) for line in text.split("\n"))
        truncated = result.stdout_truncated
        lines = text.split("\n")
        if len(lines) - int(text.endswith("\n")) > MAX_DIFF_LINES:
            text = "\n".join(lines[:MAX_DIFF_LINES]) + "\n"
            truncated = True
        message = ""
        if binary:
            message = "Git detectó un archivo binario. Sus cambios no se pueden mostrar como líneas de texto."
        elif not text:
            message = "No hay diferencias de texto para esta selección. El archivo puede estar vacío o haber cambiado desde la última actualización."
        return FileDiff(file.path, staged, text=text, message=message, binary=binary, truncated=truncated)

    def unstage_file(self, repository_path, file_path):
        info = self._working_repository(repository_path)
        file = self._current_file(info, file_path)
        if not file.is_staged:
            raise GitServiceError("Este archivo no tiene cambios preparados para commit.")
        paths = [file.path]
        if file.index_status == "R" and file.original_path:
            paths.insert(0, file.original_path)
        if info.has_commits:
            self._run(["restore", "--staged", "--", *paths], cwd=info.root_path)
        else:
            # Sin HEAD, quitar únicamente la entrada del índice; nunca el archivo.
            self._run(["update-index", "--force-remove", "--", *paths], cwd=info.root_path)
        return self.inspect_repository(repository_path)

    def stage_all(self, repository_path):
        info = self._working_repository(repository_path)
        if not info.unstaged_files:
            return info
        if not info.can_stage_all:
            raise GitServiceError(
                "Hay conflictos o cambios en submódulos. Revisalos con otra herramienta "
                "antes de preparar todos los cambios. Podés preparar los demás archivos uno a uno."
            )
        self._run(["add", "-A"], cwd=info.root_path)
        return self.inspect_repository(repository_path)

    def commit(self, repository_path, message, *, allow_detached=False):
        """Crear el commit; la actualización posterior se realiza por separado."""
        if not message.strip():
            raise GitServiceError("Escribí un mensaje para explicar los cambios del commit.")
        if "\0" in message:
            raise GitServiceError("El mensaje contiene un carácter nulo que Git no puede recibir.")
        info = self._working_repository(repository_path)
        if any(file.conflicted for file in info.files):
            raise GitServiceError("Hay conflictos pendientes. Resolvelos antes de hacer un commit.")
        if not info.staged_files:
            raise GitServiceError("Prepará al menos un archivo (Stage) antes de hacer un commit.")
        if info.branch is None and not allow_detached:
            raise GitServiceError("El repositorio tiene HEAD separado. Confirmá antes de crear un commit sin rama.")
        # Sin -a: guardar solo el índice. Conservar líneas del mensaje que empiezan por #.
        result = self._run(
            ["commit", "--cleanup=whitespace", "-m", message.strip()], cwd=info.root_path,
        )
        return result.stdout

    def initialize_repository(self, path):
        """Invocar solamente después de la confirmación explícita en la UI."""
        info = self.inspect_repository(path)
        # Revalidar: otra aplicación pudo inicializar la carpeta mientras tanto.
        if info.is_repository:
            return info
        self._run(["init"], cwd=info.selected_path)
        return self.inspect_repository(info.selected_path)
