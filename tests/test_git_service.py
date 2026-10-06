import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from git.git_service import MAX_DIFF_BYTES, MAX_DIFF_LINES, GitService, GitServiceError


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

    def commit_all(self, message="Cambios de prueba", cwd=None):
        self.git("add", "-A", cwd=cwd)
        self.git("-c", "user.name=Prueba", "-c", "user.email=prueba@example.test",
                 "-c", "commit.gpgSign=false", "commit", "-m", message, cwd=cwd)

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

    def test_clean_repository_has_no_changes(self):
        self.committed_repository()
        info = self.service.inspect_repository(self.folder)
        self.assertEqual(info.files, ())
        self.assertFalse(info.can_stage_all)

    def test_status_distinguishes_modified_deleted_added_and_untracked(self):
        self.committed_repository()
        (self.folder / "eliminado.txt").write_text("contenido", encoding="utf-8")
        self.commit_all()
        (self.folder / "eliminado.txt").unlink()
        (self.folder / "hola.txt").write_text("editado", encoding="utf-8")
        (self.folder / "nuevo.txt").write_text("nuevo", encoding="utf-8")
        (self.folder / "preparado.txt").write_text("preparado", encoding="utf-8")
        self.git("add", "--", "preparado.txt")
        info = self.service.inspect_repository(self.folder)
        codes = {file.path: (file.index_status, file.working_status) for file in info.files}
        self.assertEqual(codes, {
            "eliminado.txt": (".", "D"), "hola.txt": (".", "M"),
            "nuevo.txt": (".", "?"), "preparado.txt": ("A", "."),
        })
        self.assertEqual([file.path for file in info.staged_files], ["preparado.txt"])
        self.assertEqual(len(info.unstaged_files), 3)

    def test_stage_and_unstage_modified_file_preserve_local_content(self):
        self.committed_repository()
        file = self.folder / "hola.txt"
        file.write_text("nueva versión\n", encoding="utf-8")
        staged = self.service.stage_file(self.folder, "hola.txt")
        self.assertEqual(len(staged.staged_files), 1)
        self.assertEqual(staged.unstaged_files, ())
        self.assertEqual(self.git("show", ":hola.txt"), "nueva versión")
        unstaged = self.service.unstage_file(self.folder, "hola.txt")
        self.assertEqual(unstaged.staged_files, ())
        self.assertEqual(unstaged.unstaged_files[0].working_status, "M")
        self.assertEqual(file.read_text(encoding="utf-8"), "nueva versión\n")
        self.assertEqual(self.git("show", ":hola.txt"), "hola")

    def test_partially_staged_file_is_in_both_groups_and_can_be_staged_again(self):
        self.committed_repository()
        file = self.folder / "hola.txt"
        file.write_text("primera edición", encoding="utf-8")
        self.service.stage_file(self.folder, "hola.txt")
        file.write_text("segunda edición", encoding="utf-8")
        info = self.service.inspect_repository(self.folder)
        self.assertEqual(info.files[0].index_status, "M")
        self.assertEqual(info.files[0].working_status, "M")
        self.assertEqual(info.staged_files, info.unstaged_files)
        self.assertEqual(self.git("show", ":hola.txt"), "primera edición")
        self.service.stage_file(self.folder, "hola.txt")
        self.assertEqual(self.git("show", ":hola.txt"), "segunda edición")

    def test_unstage_before_first_commit_preserves_newer_working_copy(self):
        self.git("init")
        file = self.folder / "hola.txt"
        file.write_text("preparado", encoding="utf-8")
        self.service.stage_file(self.folder, "hola.txt")
        file.write_text("editado después", encoding="utf-8")
        info = self.service.unstage_file(self.folder, "hola.txt")
        self.assertEqual(info.staged_files, ())
        self.assertEqual(info.unstaged_files[0].working_status, "?")
        self.assertEqual(file.read_text(encoding="utf-8"), "editado después")
        self.assertEqual(self.git("ls-files"), "")

    def test_stage_and_unstage_deletion_does_not_recreate_file(self):
        self.committed_repository()
        file = self.folder / "hola.txt"
        file.unlink()
        info = self.service.stage_file(self.folder, "hola.txt")
        self.assertEqual(info.staged_files[0].index_status, "D")
        info = self.service.unstage_file(self.folder, "hola.txt")
        self.assertEqual(info.unstaged_files[0].working_status, "D")
        self.assertFalse(file.exists())

    def test_stage_all_includes_deletions_and_new_files_but_respects_gitignore(self):
        self.committed_repository()
        (self.folder / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        self.commit_all()
        (self.folder / "hola.txt").unlink()
        nested = self.folder / "documentos"
        nested.mkdir()
        (nested / "nuevo.txt").write_text("nuevo", encoding="utf-8")
        (self.folder / "ignorado.tmp").write_text("privado", encoding="utf-8")
        info = self.service.stage_all(nested)
        self.assertEqual(info.root_path, self.folder)
        self.assertEqual(info.selected_path, nested)
        self.assertEqual(info.unstaged_files, ())
        self.assertEqual({file.path for file in info.staged_files}, {"documentos/nuevo.txt", "hola.txt"})
        self.assertNotIn("ignorado.tmp", self.git("ls-files"))

    def test_literal_file_names_are_staged_one_at_a_time(self):
        self.git("init")
        names = ["*.txt", "[archivo].txt", "-opción.txt", ":(glob)*", "dos\nlíneas.txt", "retorno\r.txt"]
        for name in names:
            (self.folder / name).write_text(name, encoding="utf-8")
        for index, name in enumerate(names, start=1):
            with self.subTest(name=name):
                info = self.service.stage_file(self.folder, name)
                self.assertEqual({file.path for file in info.staged_files}, set(names[:index]))
        for name in names:
            with self.subTest(name=name):
                self.service.unstage_file(self.folder, name)
                self.assertEqual((self.folder / name).read_bytes(), name.encode("utf-8"))

    def test_filename_with_non_utf8_byte_can_be_staged(self):
        self.git("init")
        name = os.fsdecode(b"nombre-\xff.txt")
        (self.folder / name).write_bytes(b"contenido")
        info = self.service.stage_file(self.folder, name)
        self.assertEqual(info.staged_files[0].path, name)
        self.service.unstage_file(self.folder, name)
        self.assertEqual((self.folder / name).read_bytes(), b"contenido")

    def test_rename_unstage_restores_both_index_paths_and_keeps_working_rename(self):
        self.committed_repository()
        self.git("mv", "--", "hola.txt", "renombrado.txt")
        info = self.service.inspect_repository(self.folder)
        self.assertEqual(info.staged_files[0].index_status, "R")
        self.assertEqual(info.staged_files[0].original_path, "hola.txt")
        info = self.service.unstage_file(self.folder, "renombrado.txt")
        self.assertEqual(info.staged_files, ())
        self.assertEqual(self.git("ls-files"), "hola.txt")
        self.assertFalse((self.folder / "hola.txt").exists())
        self.assertEqual((self.folder / "renombrado.txt").read_text(encoding="utf-8"), "hola\n")

    def test_already_staged_rename_can_prepare_later_edits(self):
        self.committed_repository()
        self.git("mv", "--", "hola.txt", "renombrado.txt")
        (self.folder / "renombrado.txt").write_text("hola\nedición adicional\n", encoding="utf-8")
        info = self.service.stage_file(self.folder, "renombrado.txt")
        self.assertEqual(info.unstaged_files, ())
        self.assertEqual(self.git("show", ":renombrado.txt"), "hola\nedición adicional")

    def test_stale_or_outside_path_does_not_modify_index(self):
        self.committed_repository()
        before = self.git("ls-files", "--stage")
        for name in ("hola.txt", "../afuera.txt", str(self.folder / "hola.txt")):
            with self.subTest(name=name), self.assertRaises(GitServiceError):
                self.service.stage_file(self.folder, name)
        self.assertEqual(before, self.git("ls-files", "--stage"))

    def test_index_lock_error_is_visible_and_preserves_working_file(self):
        self.committed_repository()
        (self.folder / "hola.txt").write_text("editado", encoding="utf-8")
        (self.folder / ".git" / "index.lock").touch()
        with self.assertRaises(GitServiceError) as error:
            self.service.stage_file(self.folder, "hola.txt")
        self.assertIn("index.lock", error.exception.details)
        self.assertEqual((self.folder / "hola.txt").read_text(encoding="utf-8"), "editado")

    def test_merge_conflicts_are_visible_and_not_treated_as_prepared(self):
        self.committed_repository()
        self.git("checkout", "-b", "otra")
        (self.folder / "hola.txt").write_text("cambio de otra rama\n", encoding="utf-8")
        self.commit_all()
        self.git("checkout", "main")
        (self.folder / "hola.txt").write_text("cambio de main\n", encoding="utf-8")
        self.commit_all()
        with self.assertRaises(subprocess.CalledProcessError):
            self.git("-c", "user.name=Prueba", "-c", "user.email=prueba@example.test", "merge", "otra")
        info = self.service.inspect_repository(self.folder)
        self.assertTrue(info.unstaged_files[0].conflicted)
        self.assertEqual(info.staged_files, ())
        self.assertFalse(info.can_stage_all)
        original = (self.folder / "hola.txt").read_bytes()
        with self.assertRaises(GitServiceError):
            self.service.stage_all(self.folder)
        with self.assertRaises(GitServiceError):
            self.service.stage_file(self.folder, "hola.txt")
        self.assertEqual((self.folder / "hola.txt").read_bytes(), original)

    def test_submodule_working_changes_are_identified_and_not_silently_staged(self):
        self.committed_repository()
        source = self.base / "origen"
        source.mkdir()
        self.git("init", cwd=source)
        (source / "archivo.txt").write_text("contenido", encoding="utf-8")
        self.commit_all(cwd=source)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", str(source), "modulo")
        self.commit_all()
        (self.folder / "modulo" / "archivo.txt").write_text("modificado", encoding="utf-8")
        info = self.service.inspect_repository(self.folder)
        self.assertTrue(info.unstaged_files[0].submodule.startswith("S"))
        self.assertFalse(info.can_stage_all)
        with self.assertRaisesRegex(GitServiceError, "submódulos"):
            self.service.stage_all(self.folder)

    def test_root_with_carriage_return_is_preserved(self):
        folder = self.base / "carpeta\rfinal"
        folder.mkdir()
        self.assertEqual(self.service.initialize_repository(folder).root_path, folder)

    def test_unstaged_diff_shows_added_and_removed_lines_without_staging(self):
        self.committed_repository()
        (self.folder / "hola.txt").write_text("nueva línea\n", encoding="utf-8")
        diff = self.service.get_diff(self.folder, "hola.txt")
        self.assertIn("-hola\n", diff.text)
        self.assertIn("+nueva línea\n", diff.text)
        self.assertIn("@@", diff.text)
        self.assertFalse(diff.staged)
        self.assertFalse(diff.binary)
        self.assertEqual(self.git("show", ":hola.txt"), "hola")

    def test_staged_and_unstaged_diff_compare_the_correct_versions(self):
        self.committed_repository()
        file = self.folder / "hola.txt"
        file.write_text("primera edición\n", encoding="utf-8")
        self.service.stage_file(self.folder, "hola.txt")
        file.write_text("segunda edición\n", encoding="utf-8")
        staged = self.service.get_diff(self.folder, "hola.txt", staged=True)
        unstaged = self.service.get_diff(self.folder, "hola.txt")
        self.assertIn("-hola\n", staged.text)
        self.assertIn("+primera edición\n", staged.text)
        self.assertNotIn("segunda edición", staged.text)
        self.assertIn("-primera edición\n", unstaged.text)
        self.assertIn("+segunda edición\n", unstaged.text)
        self.assertEqual(self.git("show", ":hola.txt"), "primera edición")

    def test_untracked_diff_uses_git_without_creating_an_index_entry(self):
        self.git("init")
        file = self.folder / "nuevo.txt"
        file.write_text("hola\nsegunda línea\n", encoding="utf-8")
        diff = self.service.get_diff(self.folder, "nuevo.txt")
        self.assertIn("+segunda línea\n", diff.text)
        self.assertIn("new file mode", diff.text)
        self.assertEqual(self.git("ls-files"), "")
        self.assertEqual(file.read_text(encoding="utf-8"), "hola\nsegunda línea\n")

    def test_staged_new_file_diff_works_before_first_commit(self):
        self.git("init")
        (self.folder / "nuevo.txt").write_text("listo\n", encoding="utf-8")
        self.service.stage_file(self.folder, "nuevo.txt")
        diff = self.service.get_diff(self.folder, "nuevo.txt", staged=True)
        self.assertTrue(diff.staged)
        self.assertIn("+listo\n", diff.text)
        self.assertIn("/dev/null", diff.text)

    def test_deleted_file_diff_works_in_both_groups(self):
        self.committed_repository()
        file = self.folder / "hola.txt"
        file.unlink()
        diff = self.service.get_diff(self.folder, "hola.txt")
        self.assertIn("-hola\n", diff.text)
        self.service.stage_file(self.folder, "hola.txt")
        diff = self.service.get_diff(self.folder, "hola.txt", staged=True)
        self.assertIn("deleted file mode", diff.text)
        self.assertIn("-hola\n", diff.text)
        self.assertFalse(file.exists())

    def test_staged_rename_diff_includes_original_and_new_path(self):
        self.committed_repository()
        self.git("mv", "--", "hola.txt", "renombrado.txt")
        diff = self.service.get_diff(self.folder, "renombrado.txt", staged=True)
        self.assertIn("rename from hola.txt", diff.text)
        self.assertIn("rename to renombrado.txt", diff.text)

    def test_diff_reports_binary_files_for_new_and_staged_versions(self):
        self.git("init")
        (self.folder / "imagen.bin").write_bytes(b"\x00\xffcontenido\x00")
        diff = self.service.get_diff(self.folder, "imagen.bin")
        self.assertTrue(diff.binary)
        self.assertIn("binario", diff.message)
        self.service.stage_file(self.folder, "imagen.bin")
        self.assertTrue(self.service.get_diff(self.folder, "imagen.bin", staged=True).binary)

    def test_tracked_binary_diff_is_identified(self):
        self.committed_repository()
        (self.folder / "hola.txt").write_bytes(b"\x00datos binarios")
        self.assertTrue(self.service.get_diff(self.folder, "hola.txt").binary)

    def test_large_diff_is_limited_in_bytes_and_does_not_modify_file(self):
        self.git("init")
        data = b"x" * (MAX_DIFF_BYTES * 2)
        file = self.folder / "grande.txt"
        file.write_bytes(data)
        diff = self.service.get_diff(self.folder, "grande.txt")
        self.assertTrue(diff.truncated)
        self.assertLessEqual(len(diff.text.encode("utf-8")), MAX_DIFF_BYTES)
        self.assertEqual(file.read_bytes(), data)
        self.assertEqual(self.git("ls-files"), "")

    def test_large_diff_is_limited_in_lines(self):
        self.git("init")
        (self.folder / "lineas.txt").write_text("una línea\n" * (MAX_DIFF_LINES + 100), encoding="utf-8")
        diff = self.service.get_diff(self.folder, "lineas.txt")
        self.assertTrue(diff.truncated)
        self.assertLessEqual(diff.text.count("\n"), MAX_DIFF_LINES)

    def test_diff_handles_empty_files_and_missing_final_newline(self):
        self.git("init")
        (self.folder / "vacio.txt").touch()
        (self.folder / "sin-salto.txt").write_text("sin salto", encoding="utf-8")
        self.assertIn("new file mode", self.service.get_diff(self.folder, "vacio.txt").text)
        self.assertIn("No newline at end of file", self.service.get_diff(self.folder, "sin-salto.txt").text)

    def test_diff_paths_are_literal_and_accept_special_names(self):
        self.git("init")
        for name in ("*.txt", "-archivo.txt", "nombre\ncon salto.txt", os.fsdecode(b"nombre-\xff.txt")):
            (self.folder / name).write_text("mi contenido\n", encoding="utf-8")
            with self.subTest(name=name):
                diff = self.service.get_diff(self.folder, name)
                self.assertEqual(diff.path, name)
                self.assertIn("+mi contenido\n", diff.text)

    def test_diff_does_not_run_external_diff_or_textconv(self):
        self.committed_repository()
        marker = self.folder / "CONVERSOR_EJECUTADO"
        converter = self.base / "converter.sh"
        converter.write_text("#!/bin/sh\ntouch CONVERSOR_EJECUTADO\nprintf convertido\n", encoding="utf-8")
        converter.chmod(0o700)
        (self.folder / ".gitattributes").write_text("hola.txt diff=custom\n", encoding="utf-8")
        self.git("config", "diff.custom.textconv", str(converter))
        (self.folder / "hola.txt").write_text("texto nuevo\n", encoding="utf-8")
        with patch.dict(os.environ, {"GIT_EXTERNAL_DIFF": str(converter)}):
            diff = self.service.get_diff(self.folder, "hola.txt")
        self.assertIn("+texto nuevo\n", diff.text)
        self.assertFalse(marker.exists())

    def test_diff_rejects_stale_group_or_outside_path(self):
        self.committed_repository()
        (self.folder / "hola.txt").write_text("editado", encoding="utf-8")
        with self.assertRaisesRegex(GitServiceError, "versión"):
            self.service.get_diff(self.folder, "hola.txt", staged=True)
        with self.assertRaises(GitServiceError):
            self.service.get_diff(self.folder, "../afuera.txt")

    def test_diff_of_untracked_symlink_shows_target_without_reading_its_contents(self):
        self.git("init")
        outside = self.base / "afuera.txt"
        outside.write_text("contenido externo privado", encoding="utf-8")
        (self.folder / "enlace").symlink_to(outside)
        diff = self.service.get_diff(self.folder, "enlace")
        self.assertIn(str(outside), diff.text)
        self.assertNotIn("contenido externo privado", diff.text)

    def test_diff_of_file_mode_change_is_visible(self):
        self.committed_repository()
        (self.folder / "hola.txt").chmod(0o755)
        diff = self.service.get_diff(self.folder, "hola.txt")
        self.assertIn("old mode 100644", diff.text)
        self.assertIn("new mode 100755", diff.text)

    def test_untracked_diff_does_not_hide_git_errors_with_exit_code_one(self):
        self.git("init")
        file = self.folder / "nuevo.txt"
        file.write_text("contenido", encoding="utf-8")
        original_run = self.service._run

        def remove_before_diff(arguments, **kwargs):
            if arguments[0] == "diff":
                file.unlink()
            return original_run(arguments, **kwargs)

        with patch.object(self.service, "_run", side_effect=remove_before_diff):
            with self.assertRaises(GitServiceError) as error:
                self.service.get_diff(self.folder, "nuevo.txt")
        self.assertIn("Could not access", error.exception.details)


if __name__ == "__main__":
    unittest.main()
