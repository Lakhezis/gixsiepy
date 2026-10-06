# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Operaciones Git mediante el ejecutable instalado en el sistema."""

from dataclasses import dataclass, field
from contextlib import nullcontext
from datetime import datetime
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


MAX_DIFF_BYTES = 512 * 1024
MAX_DIFF_LINES = 5000
HISTORY_LIMIT = 50


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
class CommitInfo:
    short_hash: str
    message: str
    author: str
    authored_at: datetime


@dataclass(frozen=True)
class SyncPlan:
    operation: str
    root_path: Path
    local_branch: str
    remote: str
    remote_ref: str
    url: str = field(repr=False)
    set_upstream: bool = False

    @property
    def destination(self):
        return f"{self.remote}/{self.remote_ref.removeprefix('refs/heads/')}"


@dataclass(frozen=True)
class SyncResult:
    plan: SyncPlan
    details: str


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
    remotes: tuple[str, ...] = ()
    upstream_remote: str | None = None
    upstream_ref: str | None = None
    multiple_upstreams: bool = False

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

    @property
    def sync_problem(self):
        if not self.is_repository:
            return "Abrí o inicializá un repositorio."
        if not self.has_commits:
            return "Creá tu primer commit antes de sincronizar."
        if self.branch is None:
            return "La sincronización necesita una rama activa; estás en HEAD separado."
        if not self.remotes:
            return "No hay un remoto configurado. Agregalo desde la terminal y pulsá Actualizar."
        if len(self.remotes) != 1:
            return "La aplicación admite un único remoto para sincronizar. Este repositorio tiene varios."
        if any(file.conflicted for file in self.files):
            return "Resolvé los conflictos pendientes antes de sincronizar."
        if self.multiple_upstreams:
            return "La rama tiene varios destinos de seguimiento. Revisá su configuración en Git."
        if bool(self.upstream_remote) != bool(self.upstream_ref):
            return "El seguimiento de la rama está incompleto. Revisá su configuración en Git."
        if self.upstream_remote and self.upstream_remote != self.remotes[0]:
            return "El seguimiento no apunta al remoto disponible. Revisá su configuración en Git."
        if self.upstream_ref and not self.upstream_ref.startswith("refs/heads/"):
            return "El seguimiento debe apuntar a una rama del remoto. Revisá su configuración en Git."
        return None

    @property
    def pull_problem(self):
        if self.sync_problem:
            return self.sync_problem
        if not self.upstream_ref:
            return "La rama no tiene seguimiento. Hacé el primer Push o configurá su upstream desde la terminal."
        if self.files:
            return "Guardá los cambios pendientes en un commit antes de hacer Pull, incluidos los archivos nuevos."
        return None


class GitService:
    def __init__(self, timeout=30, network_timeout=120):
        self.timeout = timeout
        self.network_timeout = network_timeout

    def _run(self, arguments, *, cwd=None, accepted_codes=(0,), stdout_limit=None, network=False):
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
        if (network and not any(key in environment for key in ("GIT_SSH", "GIT_SSH_COMMAND"))
                and not self._config_values(cwd, "core.sshCommand")):
            environment["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
        try:
            # Un diff grande se almacena temporalmente en disco, no entero en memoria.
            with (tempfile.TemporaryFile() if stdout_limit is not None else nullcontext()) as output:
                result = subprocess.run(
                    command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                    stdout=output if output is not None else subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=self.network_timeout if network else self.timeout,
                    shell=False,
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
                "Git tardó demasiado en responder. Actualizá y comprobá el estado antes de volver a intentar.",
                command=command,
                stdout=(error.stdout or b"").decode("utf-8", errors="surrogateescape"),
                stderr=(error.stderr or b"").decode("utf-8", errors="surrogateescape") or str(error),
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
        remotes = self._run(["remote"], cwd=root_path).stdout.splitlines()
        branch_name = branch.stdout.strip() if branch.returncode == 0 else None
        upstream_remotes = self._config_values(root_path, f"branch.{branch_name}.remote") if branch_name else ()
        upstream_refs = self._config_values(root_path, f"branch.{branch_name}.merge") if branch_name else ()
        return RepositoryInfo(
            selected_path=folder, root_path=root_path,
            branch=branch_name,
            head_short=head.stdout.strip() if head.returncode == 0 else None,
            files=self._parse_status(status.stdout),
            remotes=tuple(remotes),
            upstream_remote=upstream_remotes[0] if len(upstream_remotes) == 1 else None,
            upstream_ref=upstream_refs[0] if len(upstream_refs) == 1 else None,
            multiple_upstreams=len(upstream_remotes) > 1 or len(upstream_refs) > 1,
        )

    def _config_values(self, root, key):
        result = self._run(["config", "-z", "--get-all", key], cwd=root, accepted_codes=(0, 1))
        return tuple(result.stdout.removesuffix("\0").split("\0")) if result.returncode == 0 else ()

    def get_history(self, repository_path):
        info = self._working_repository(repository_path)
        if not info.has_commits:
            return ()
        result = self._run([
            "log", f"--max-count={HISTORY_LIMIT}", "--topo-order", "--abbrev=7",
            "--no-color", "--no-decorate", "--no-notes", "--no-show-signature", "--no-patch",
            "--encoding=UTF-8", "-z", "--format=%h%x00%s%x00%an%x00%aI", "HEAD", "--",
        ], cwd=info.root_path)
        fields = result.stdout.removesuffix("\0").split("\0") if result.stdout else []
        try:
            if len(fields) % 4:
                raise ValueError("Registro de commit incompleto")
            commits = []
            for offset in range(0, len(fields), 4):
                short_hash, message, author, date = fields[offset:offset + 4]
                if not short_hash or any(char not in "0123456789abcdef" for char in short_hash):
                    raise ValueError("Hash de commit inválido")
                commits.append(CommitInfo(short_hash, message, author, datetime.fromisoformat(date)))
            return tuple(commits)
        except ValueError as error:
            raise GitServiceError(
                "No se pudo interpretar el historial. Probá actualizar el repositorio.",
                command=result.args, stdout=result.stdout,
            ) from error

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

    def prepare_sync(self, repository_path, operation):
        """Consultar el destino sin conectarse; la UI lo muestra antes de confirmar."""
        if operation not in ("pull", "push"):
            raise ValueError("Operación de sincronización desconocida")
        info = self._working_repository(repository_path)
        problem = info.pull_problem if operation == "pull" else info.sync_problem
        if problem:
            raise GitServiceError(problem)
        remote = info.remotes[0]
        remote_ref = info.upstream_ref or f"refs/heads/{info.branch}"
        self._run(["check-ref-format", remote_ref], cwd=info.root_path)
        urls = self._run(
            ["remote", "get-url", *(["--push"] if operation == "push" else []), "--all", "--", remote],
            cwd=info.root_path,
        ).stdout.splitlines()
        if len(urls) != 1 or not urls[0]:
            raise GitServiceError("El remoto debe tener una única dirección para esta operación. Revisá sus URLs en Git.")
        return SyncPlan(
            operation, info.root_path, info.branch, remote, remote_ref, urls[0],
            set_upstream=operation == "push" and info.upstream_ref is None,
        )

    def sync(self, repository_path, plan):
        """Ejecutar exclusivamente el destino que el usuario acaba de confirmar."""
        if self.prepare_sync(repository_path, plan.operation) != plan:
            raise GitServiceError("La rama o el destino cambiaron. Actualizá y confirmá la operación nuevamente.")
        if plan.operation == "pull":
            arguments = [
                # Restringir el merge heredado y proteger archivos locales ignorados.
                "-c", f"branch.{plan.local_branch}.mergeOptions=--no-overwrite-ignore",
                "pull", "--ff-only", "--no-rebase", "--no-autostash", "--no-recurse-submodules",
                "--no-all", "--no-prune",
                "--", plan.remote, plan.remote_ref,
            ]
        else:
            arguments = [
                # mirror se lee después de los flags en Git; anularlo solo en esta ejecución.
                "-c", f"remote.{plan.remote}.mirror=false",
                "push", "--no-force", "--no-mirror", "--no-follow-tags", "--no-prune",
                "--recurse-submodules=no", *(["--set-upstream"] if plan.set_upstream else []),
                "--", plan.remote, f"refs/heads/{plan.local_branch}:{plan.remote_ref}",
            ]
        try:
            result = self._run(arguments, cwd=plan.root_path, network=True)
        except GitServiceError as error:
            raise self._sync_error(plan, error) from error
        return SyncResult(plan, GitServiceError(
            "", command=result.args, stdout=result.stdout, stderr=result.stderr, returncode=result.returncode,
        ).details)

    @staticmethod
    def _sync_error(plan, error):
        operation = plan.operation
        output = error.stderr.lower()
        if "tardó demasiado" in str(error):
            message = str(error)
        elif "host key verification failed" in output:
            message = "SSH no pudo verificar la identidad del servidor. Comprobala desde la terminal antes de volver a intentar."
        elif any(text in output for text in (
            "authentication failed", "permission denied", "could not read username", "could not read password",
            "terminal prompts disabled", "returned error: 401", "returned error: 403",
        )):
            message = "Git no pudo autenticarte. Revisá el agente SSH, tus permisos o el gestor de credenciales de Git."
        elif any(text in output for text in ("could not resolve", "couldn't resolve", "failed to connect", "unable to access", "connection refused")):
            message = "No se pudo conectar con el remoto. Revisá la conexión y la dirección configurada en Git."
        elif operation == "pull" and any(text in output for text in ("not possible to fast-forward", "diverging branches")):
            message = "Las ramas local y remota divergen. Pull no puede avanzar directamente; resolvé la divergencia desde otra herramienta."
        elif operation == "push" and any(text in output for text in ("non-fast-forward", "fetch first")):
            if plan.set_upstream:
                message = "El remoto tiene cambios que tu rama no incluye. Configurá el seguimiento y revisá ambos historiales desde otra herramienta antes de enviar."
            else:
                message = "El remoto tiene cambios que tu rama no incluye. Hacé Pull antes de intentar Push; si divergen, resolvelo desde otra herramienta."
        elif "couldn't find remote ref" in output:
            message = "La rama de seguimiento no existe en el remoto. Revisá su nombre o publicala con Push."
        elif "would be overwritten" in output:
            message = "Git encontró archivos locales que serían sobrescritos. Guardá una copia y revisá los archivos indicados antes de hacer Pull."
        else:
            message = f"Git no pudo completar {operation.capitalize()}. Consultá su mensaje original en los detalles."
        return GitServiceError(
            message, command=error.command, stdout=error.stdout, stderr=error.stderr, returncode=error.returncode,
        )

    def initialize_repository(self, path):
        """Invocar solamente después de la confirmación explícita en la UI."""
        info = self.inspect_repository(path)
        # Revalidar: otra aplicación pudo inicializar la carpeta mientras tanto.
        if info.is_repository:
            return info
        self._run(["init"], cwd=info.selected_path)
        return self.inspect_repository(info.selected_path)
