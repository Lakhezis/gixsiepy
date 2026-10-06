import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from git.git_service import GitService, GitServiceError


@unittest.skipUnless(shutil.which("git"), "Estas pruebas requieren Git instalado")
class GitServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gixsie-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.folder = self.base / "mi jardín con espacios"
        self.folder.mkdir()
        configuration = self.base / "gitconfig"
        configuration.write_text("[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        environment = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(configuration), "GIT_CONFIG_NOSYSTEM": "1",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.service = GitService()

    def git(self, *arguments, cwd=None):
        return subprocess.run(
            ["git", *arguments], cwd=cwd or self.folder, capture_output=True,
            text=True, check=True,
        ).stdout.strip()

    def committed_repository(self):
        self.git("init")
        (self.folder / "hola.txt").write_text("hola\n", encoding="utf-8")
        self.git("add", "--", "hola.txt")
        self.git("-c", "user.name=Prueba", "-c", "user.email=prueba@example.test",
                 "-c", "commit.gpgSign=false", "commit", "-m", "Primer commit")

    def test_inspection_does_not_initialize_a_folder(self):
        info = self.service.inspect_repository(self.folder)
        self.assertFalse(info.is_repository)
        self.assertEqual(info.name, self.folder.name)
        self.assertFalse((self.folder / ".git").exists())

    def test_initialization_preserves_files_and_respects_default_branch(self):
        original = self.folder / "hola.txt"
        original.write_text("Mi contenido", encoding="utf-8")
        info = self.service.initialize_repository(self.folder)
        self.assertTrue(info.is_repository)
        self.assertEqual(info.branch, "main")
        self.assertFalse(info.has_commits)
        self.assertEqual(original.read_text(encoding="utf-8"), "Mi contenido")
        self.assertEqual(self.git("ls-files"), "")

    def test_existing_repository_and_branch(self):
        self.committed_repository()
        info = self.service.inspect_repository(self.folder)
        self.assertEqual(info.root_path, self.folder)
        self.assertEqual(info.branch, "main")
        self.assertEqual(info.head_short, self.git("rev-parse", "--short", "HEAD"))

    def test_subfolder_opens_the_repository_root(self):
        self.git("init")
        nested = self.folder / "documentos" / "borradores"
        nested.mkdir(parents=True)
        info = self.service.inspect_repository(nested)
        self.assertEqual(info.root_path, self.folder)
        self.assertEqual(info.selected_path, nested)

    def test_detached_head_has_a_hash_and_no_branch(self):
        self.committed_repository()
        self.git("checkout", "--detach")
        info = self.service.inspect_repository(self.folder)
        self.assertIsNone(info.branch)
        self.assertTrue(info.has_commits)

    def test_worktree_with_git_file_is_detected(self):
        self.committed_repository()
        worktree = self.base / "otra carpeta"
        self.git("worktree", "add", "-b", "otra", str(worktree))
        self.assertTrue((worktree / ".git").is_file())
        info = self.service.inspect_repository(worktree)
        self.assertEqual(info.root_path, worktree)
        self.assertEqual(info.branch, "otra")

    def test_symbolic_link_resolves_to_real_folder(self):
        self.git("init")
        link = self.base / "enlace"
        link.symlink_to(self.folder, target_is_directory=True)
        self.assertEqual(self.service.inspect_repository(link).root_path, self.folder)

    def test_initialization_rechecks_an_existing_repository(self):
        self.committed_repository()
        before = self.git("rev-parse", "HEAD")
        with patch.object(self.service, "_run", wraps=self.service._run) as run:
            info = self.service.initialize_repository(self.folder)
        self.assertTrue(info.is_repository)
        self.assertEqual(before, self.git("rev-parse", "HEAD"))
        self.assertNotIn(["init"], [call.args[0] for call in run.call_args_list])

    def test_folder_name_is_not_executed_as_shell_code(self):
        folder = self.base / "flores; $(touch INYECCION)"
        folder.mkdir()
        self.assertTrue(self.service.initialize_repository(folder).is_repository)
        self.assertFalse((folder / "INYECCION").exists())
        self.assertFalse((self.base / "INYECCION").exists())

    def test_bare_repository_is_rejected(self):
        self.git("init", "--bare")
        with self.assertRaisesRegex(GitServiceError, "carpeta de trabajo"):
            self.service.initialize_repository(self.folder)

    def test_git_internal_directory_is_rejected(self):
        self.git("init")
        with self.assertRaisesRegex(GitServiceError, "carpeta de trabajo"):
            self.service.inspect_repository(self.folder / ".git")

    def test_nonexistent_folder_reports_a_friendly_error(self):
        with self.assertRaisesRegex(GitServiceError, "no existe"):
            self.service.inspect_repository(self.base / "ausente")

    def test_file_is_not_accepted_as_folder(self):
        file = self.folder / "archivo.txt"
        file.touch()
        with self.assertRaisesRegex(GitServiceError, "no un archivo"):
            self.service.inspect_repository(file)

    def test_missing_git_is_reported_without_modifying_folder(self):
        with patch("git.git_service.shutil.which", return_value=None):
            with self.assertRaisesRegex(GitServiceError, "Git no está instalado"):
                self.service.initialize_repository(self.folder)
        self.assertFalse((self.folder / ".git").exists())

    def test_inherited_repository_variables_do_not_redirect_git(self):
        with patch.dict(os.environ, {
            "GIT_DIR": str(self.base / "incorrecto"),
            "GIT_WORK_TREE": str(self.base / "incorrecto"),
            "GIT_INDEX_FILE": str(self.base / "incorrecto"),
        }):
            info = self.service.initialize_repository(self.folder)
        self.assertEqual(info.root_path, self.folder)
        self.assertFalse((self.base / "incorrecto").exists())

    def test_security_error_is_not_treated_as_non_repository(self):
        failed = subprocess.CompletedProcess(
            ["git", "rev-parse", "--is-inside-work-tree"], 128,
            stdout="", stderr="fatal: detected dubious ownership in repository\n",
        )
        version = subprocess.CompletedProcess(["git", "--version"], 0, stdout="git version", stderr="")
        with patch("git.git_service.subprocess.run", side_effect=[version, failed]) as run:
            with self.assertRaisesRegex(GitServiceError, "no confía") as error:
                self.service.initialize_repository(self.folder)
        self.assertIn("dubious ownership", error.exception.details)
        self.assertEqual(run.call_count, 2)

    def test_permission_error_keeps_original_git_message(self):
        failed = subprocess.CompletedProcess(["git"], 128, stdout="", stderr="fatal: Permission denied")
        with patch("git.git_service.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(GitServiceError, "permiso") as error:
                self.service.inspect_repository(self.folder)
        self.assertEqual(error.exception.returncode, 128)
        self.assertIn("Permission denied", error.exception.details)

    def test_timeout_is_reported_as_an_error(self):
        with patch("git.git_service.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            with self.assertRaisesRegex(GitServiceError, "tardó demasiado"):
                self.service.inspect_repository(self.folder)


if __name__ == "__main__":
    unittest.main()
