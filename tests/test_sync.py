"""Pull y push reales contra repositorios bare locales; no requieren Internet."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from git.git_service import GitService, GitServiceError


@unittest.skipUnless(shutil.which("git"), "Estas pruebas requieren Git instalado")
class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gixsie-sync-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.folder = self.base / "mi jardín"
        self.folder.mkdir()
        configuration = self.base / "config"
        configuration.write_text(
            "[init]\n\tdefaultBranch = main\n[user]\n\tname = Prueba\n"
            "\temail = prueba@example.test\n[commit]\n\tgpgSign = false\n", encoding="utf-8",
        )
        environment = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(configuration), "GIT_CONFIG_NOSYSTEM": "1",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.service = GitService()
        self.remote = self.base / "remoto con espacios.git"
        self.git("init", "--bare", str(self.remote), cwd=self.base)
        self.git("init")
        self.git("remote", "add", "origin", str(self.remote))
        (self.folder / "archivo.txt").write_text("inicial\n", encoding="utf-8")
        self.commit("Inicial")

    def git(self, *arguments, cwd=None):
        return subprocess.run(
            ["git", *arguments], cwd=cwd or self.folder, capture_output=True, text=True, check=True,
        ).stdout.strip()

    def commit(self, message, *, cwd=None):
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-m", message, cwd=cwd)

    def publish(self):
        self.git("push", "--set-upstream", "origin", "main")

    def remote_change(self):
        other = self.base / "otro equipo"
        self.git("clone", str(self.remote), str(other), cwd=self.base)
        (other / "archivo.txt").write_text("cambio remoto\n", encoding="utf-8")
        self.commit("Desde otro equipo", cwd=other)
        self.git("push", cwd=other)
        return other

    def sync(self, operation):
        return self.service.sync(self.folder, self.service.prepare_sync(self.folder, operation))

    def test_first_push_publishes_current_branch_and_sets_upstream(self):
        (self.folder / "sin preparar.txt").write_text("pendiente", encoding="utf-8")
        plan = self.service.prepare_sync(self.folder, "push")
        self.assertTrue(plan.set_upstream)
        self.assertEqual(plan.destination, "origin/main")
        result = self.service.sync(self.folder, plan)
        self.assertIn("git", result.details)
        self.assertIn("main", result.details)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.remote), self.git("rev-parse", "HEAD"))
        info = self.service.inspect_repository(self.folder)
        self.assertEqual(info.upstream_remote, "origin")
        self.assertEqual(info.upstream_ref, "refs/heads/main")
        self.assertIsNotNone(info.pull_problem)
        self.assertEqual(info.unstaged_files[0].path, "sin preparar.txt")
        self.assertEqual(self.git("ls-tree", "--name-only", "HEAD", cwd=self.remote), "archivo.txt")

    def test_pull_fast_forwards_and_updates_files_without_merge_or_rebase(self):
        self.publish()
        other = self.remote_change()
        self.git("config", "pull.rebase", "true")
        self.git("config", "branch.main.rebase", "true")
        self.git("config", "pull.ff", "false")
        result = self.sync("pull")
        self.assertEqual(self.git("rev-parse", "HEAD"), self.git("rev-parse", "HEAD", cwd=other))
        self.assertEqual((self.folder / "archivo.txt").read_text(encoding="utf-8"), "cambio remoto\n")
        self.assertIn("Fast-forward", result.details)
        self.assertEqual(self.service.inspect_repository(self.folder).files, ())
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "2")

    def test_repeated_pull_and_push_report_already_synchronized(self):
        self.publish()
        self.assertIn("Already up to date", self.sync("pull").details)
        self.assertIn("Everything up-to-date", self.sync("push").details)

    def test_no_remote_disables_sync_and_does_not_contact_any_server(self):
        self.git("remote", "remove", "origin")
        info = self.service.inspect_repository(self.folder)
        self.assertIn("No hay un remoto", info.sync_problem)
        for operation in ("pull", "push"):
            with self.subTest(operation=operation), self.assertRaisesRegex(GitServiceError, "remoto"):
                self.service.prepare_sync(self.folder, operation)

    def test_no_upstream_allows_first_push_but_explains_disabled_pull(self):
        info = self.service.inspect_repository(self.folder)
        self.assertIsNone(info.sync_problem)
        self.assertIn("seguimiento", info.pull_problem)
        with self.assertRaisesRegex(GitServiceError, "seguimiento"):
            self.service.prepare_sync(self.folder, "pull")

    def test_dirty_pull_rejected_for_tracked_staged_and_untracked_changes(self):
        self.publish()
        for state in ("modificado", "preparado", "nuevo"):
            with self.subTest(state=state):
                name = "nuevo.txt" if state == "nuevo" else "archivo.txt"
                file = self.folder / name
                file.write_text(state, encoding="utf-8")
                if state == "preparado":
                    self.git("add", "--", name)
                before = self.git("rev-parse", "HEAD")
                with self.assertRaisesRegex(GitServiceError, "pendientes"):
                    self.service.prepare_sync(self.folder, "pull")
                self.assertEqual(file.read_text(encoding="utf-8"), state)
                self.assertEqual(before, self.git("rev-parse", "HEAD"))
                self.commit(state)
                self.git("push")

    def test_divergent_pull_preserves_local_commits_and_shows_git_error(self):
        self.publish()
        self.remote_change()
        (self.folder / "local.txt").write_text("cambio local", encoding="utf-8")
        self.commit("Desde este equipo")
        before = self.git("rev-parse", "HEAD")
        self.git("config", "pull.rebase", "true")
        self.git("config", "merge.autoStash", "true")
        with self.assertRaises(GitServiceError) as error:
            self.sync("pull")
        self.assertIn("divergen", str(error.exception))
        self.assertIn("Not possible to fast-forward", error.exception.stderr)
        self.assertEqual(before, self.git("rev-parse", "HEAD"))
        self.assertFalse((self.folder / ".git" / "MERGE_HEAD").exists())
        self.assertFalse((self.folder / ".git" / "rebase-merge").exists())

    def test_rejected_push_does_not_overwrite_remote_history(self):
        self.publish()
        other = self.remote_change()
        (self.folder / "local.txt").write_text("local", encoding="utf-8")
        self.commit("Local")
        self.git("config", "remote.origin.mirror", "true")
        self.git("config", "remote.origin.push", "+refs/heads/*:refs/heads/*")
        before = self.git("rev-parse", "HEAD", cwd=self.remote)
        with self.assertRaises(GitServiceError) as error:
            self.sync("push")
        self.assertIn("remoto tiene cambios", str(error.exception))
        self.assertIn("rejected", error.exception.stderr)
        self.assertEqual(before, self.git("rev-parse", "HEAD", cwd=self.remote))
        self.assertEqual(before, self.git("rev-parse", "HEAD", cwd=other))

    def test_explicit_push_ignores_mirror_force_refspecs_matching_and_extra_tags(self):
        self.publish()
        self.git("branch", "otra")
        self.git("tag", "-a", "v1", "-m", "Tag de prueba")
        self.git("config", "remote.origin.mirror", "true")
        self.git("config", "remote.origin.push", "+refs/heads/*:refs/heads/*")
        self.git("config", "push.default", "matching")
        self.git("config", "push.followTags", "true")
        (self.folder / "archivo.txt").write_text("segundo", encoding="utf-8")
        self.commit("Segundo")
        self.sync("push")
        self.assertEqual(self.git("for-each-ref", "--format=%(refname)", cwd=self.remote), "refs/heads/main")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.remote), self.git("rev-parse", "HEAD"))

    def test_upstream_with_a_different_name_is_used_for_push_and_pull(self):
        self.git("push", "-u", "origin", "main:desarrollo")
        info = self.service.inspect_repository(self.folder)
        self.assertEqual(info.upstream_ref, "refs/heads/desarrollo")
        self.assertEqual(self.service.prepare_sync(self.folder, "push").destination, "origin/desarrollo")
        (self.folder / "archivo.txt").write_text("local actualizado", encoding="utf-8")
        self.commit("Actualizado")
        self.sync("push")
        self.assertEqual(self.git("rev-parse", "desarrollo", cwd=self.remote), self.git("rev-parse", "HEAD"))
        self.assertEqual(self.git("for-each-ref", "--format=%(refname)", cwd=self.remote), "refs/heads/desarrollo")
        other = self.base / "otra rama"
        self.git("clone", "-b", "desarrollo", str(self.remote), str(other), cwd=self.base)
        (other / "archivo.txt").write_text("desde desarrollo", encoding="utf-8")
        self.commit("Remoto", cwd=other)
        self.git("push", cwd=other)
        self.sync("pull")
        self.assertEqual((self.folder / "archivo.txt").read_text(encoding="utf-8"), "desde desarrollo")

    def test_branch_and_remote_names_are_literal_arguments(self):
        self.git("branch", "-m", "jardín/$(touch_INYECTADO)")
        self.git("remote", "rename", "origin", "flores")
        self.sync("push")
        self.assertEqual(self.git("for-each-ref", "--format=%(refname)", cwd=self.remote), "refs/heads/jardín/$(touch_INYECTADO)")
        self.assertFalse((self.folder / "INYECTADO").exists())

    def test_multiple_remotes_or_merge_targets_are_rejected(self):
        self.publish()
        self.git("config", "--add", "branch.main.merge", "refs/heads/otra")
        with self.assertRaisesRegex(GitServiceError, "varios destinos"):
            self.service.prepare_sync(self.folder, "push")
        self.git("config", "--unset-all", "branch.main.merge")
        self.git("config", "branch.main.merge", "refs/heads/main")
        self.git("remote", "add", "otro", str(self.remote))
        with self.assertRaisesRegex(GitServiceError, "único remoto"):
            self.service.prepare_sync(self.folder, "pull")

    def test_multiple_push_urls_are_rejected_before_publishing(self):
        second = self.base / "segundo.git"
        self.git("init", "--bare", str(second), cwd=self.base)
        self.git("config", "--add", "remote.origin.pushurl", str(self.remote))
        self.git("config", "--add", "remote.origin.pushurl", str(second))
        with self.assertRaisesRegex(GitServiceError, "única dirección"):
            self.service.prepare_sync(self.folder, "push")
        for remote in (self.remote, second):
            self.assertEqual(self.git("for-each-ref", cwd=remote), "")

    def test_changed_destination_or_branch_after_confirmation_requires_new_confirmation(self):
        plan = self.service.prepare_sync(self.folder, "push")
        self.git("remote", "set-url", "origin", str(self.base / "otro.git"))
        with self.assertRaisesRegex(GitServiceError, "cambiaron"):
            self.service.sync(self.folder, plan)
        self.git("remote", "set-url", "origin", str(self.remote))
        self.git("switch", "-c", "otra")
        with self.assertRaisesRegex(GitServiceError, "cambiaron"):
            self.service.sync(self.folder, plan)
        self.assertEqual(self.git("for-each-ref", cwd=self.remote), "")

    def test_external_edit_after_pull_confirmation_prevents_pull(self):
        self.publish()
        plan = self.service.prepare_sync(self.folder, "pull")
        (self.folder / "archivo.txt").write_text("no perder", encoding="utf-8")
        with self.assertRaisesRegex(GitServiceError, "pendientes"):
            self.service.sync(self.folder, plan)
        self.assertEqual((self.folder / "archivo.txt").read_text(encoding="utf-8"), "no perder")

    def test_pull_preserves_ignored_files_that_collide_with_remote_files(self):
        (self.folder / ".gitignore").write_text("privado.txt\n", encoding="utf-8")
        self.commit("Ignorar archivo privado")
        self.publish()
        (self.folder / "privado.txt").write_text("contenido local privado", encoding="utf-8")
        other = self.base / "otro equipo"
        self.git("clone", str(self.remote), str(other), cwd=self.base)
        (other / "privado.txt").write_text("archivo del remoto", encoding="utf-8")
        self.git("add", "-f", "privado.txt", cwd=other)
        self.commit("Publicar archivo", cwd=other)
        self.git("push", cwd=other)
        before = self.git("rev-parse", "HEAD")
        with self.assertRaises(GitServiceError) as error:
            self.sync("pull")
        self.assertIn("sobrescritos", str(error.exception))
        self.assertEqual((self.folder / "privado.txt").read_text(encoding="utf-8"), "contenido local privado")
        self.assertEqual(self.git("rev-parse", "HEAD"), before)

    def test_pull_overrides_squash_merge_options_for_a_real_fast_forward(self):
        self.publish()
        other = self.remote_change()
        self.git("config", "branch.main.mergeOptions", "--squash")
        self.sync("pull")
        self.assertEqual(self.git("rev-parse", "HEAD"), self.git("rev-parse", "HEAD", cwd=other))
        self.assertEqual(self.git("config", "branch.main.mergeOptions"), "--squash")
        self.assertEqual(self.service.inspect_repository(self.folder).files, ())

    def test_invalid_or_local_upstream_is_rejected(self):
        self.publish()
        self.git("config", "branch.main.remote", ".")
        with self.assertRaisesRegex(GitServiceError, "seguimiento"):
            self.service.prepare_sync(self.folder, "push")
        self.git("config", "branch.main.remote", "origin")
        self.git("config", "branch.main.merge", "refs/tags/v1")
        with self.assertRaisesRegex(GitServiceError, "rama del remoto"):
            self.service.prepare_sync(self.folder, "push")
        self.git("config", "branch.main.merge", "refs/heads/*")
        with self.assertRaises(GitServiceError):
            self.service.prepare_sync(self.folder, "push")

    def test_missing_remote_branch_has_readable_error_and_original_output(self):
        self.publish()
        self.git("config", "branch.main.merge", "refs/heads/inexistente")
        with self.assertRaises(GitServiceError) as error:
            self.sync("pull")
        self.assertIn("no existe", str(error.exception))
        self.assertIn("couldn't find remote ref", error.exception.stderr)

    def test_detached_or_unborn_branch_cannot_sync(self):
        self.git("checkout", "--detach")
        with self.assertRaisesRegex(GitServiceError, "rama activa"):
            self.service.prepare_sync(self.folder, "push")
        empty = self.base / "nuevo"
        empty.mkdir()
        self.git("init", cwd=empty)
        self.git("remote", "add", "origin", str(self.remote), cwd=empty)
        with self.assertRaisesRegex(GitServiceError, "primer commit"):
            self.service.prepare_sync(empty, "push")

    def test_missing_remote_path_keeps_original_git_error(self):
        self.git("remote", "set-url", "origin", str(self.base / "inexistente.git"))
        with self.assertRaises(GitServiceError) as error:
            self.sync("push")
        self.assertIn("Push", str(error.exception))
        self.assertIn("does not appear to be a git repository", error.exception.stderr)

    def test_authentication_and_connection_errors_have_explanation_and_details(self):
        plan = self.service.prepare_sync(self.folder, "push")
        original_run = self.service._run
        for stderr, explanation in (
            ("Permission denied (publickey).", "autenticar"),
            ("fatal: Authentication failed", "autenticar"),
            ("Could not resolve host: example.test", "conectar"),
            ("fatal: unable to access URL: The requested URL returned error: 403", "autenticar"),
            ("Host key verification failed.", "identidad del servidor"),
        ):
            def fail_network(arguments, **kwargs):
                if kwargs.get("network"):
                    raise GitServiceError("Original", command=("git", *arguments), stderr=stderr, returncode=128)
                return original_run(arguments, **kwargs)
            with self.subTest(stderr=stderr), patch.object(self.service, "_run", side_effect=fail_network):
                with self.assertRaises(GitServiceError) as error:
                    self.service.sync(self.folder, plan)
                self.assertIn(explanation, str(error.exception))
                self.assertEqual(error.exception.stderr, stderr)
                self.assertEqual(error.exception.returncode, 128)

    def test_rejected_first_push_explains_that_tracking_must_be_configured(self):
        self.publish()
        self.remote_change()
        self.git("config", "--unset", "branch.main.remote")
        self.git("config", "--unset", "branch.main.merge")
        (self.folder / "local.txt").write_text("local", encoding="utf-8")
        self.commit("Local")
        with self.assertRaisesRegex(GitServiceError, "Configurá el seguimiento"):
            self.sync("push")
        self.assertIsNone(self.service.inspect_repository(self.folder).upstream_ref)

    def test_network_timeout_preserves_partial_git_output(self):
        error = subprocess.TimeoutExpired(["git", "push"], 120, output=b"salida parcial", stderr=b"detalle parcial")
        with patch.object(self.service, "_config_values", return_value=()), \
                patch("git.git_service.subprocess.run", side_effect=error):
            with self.assertRaises(GitServiceError) as raised:
                self.service._run(["push"], cwd=self.folder, network=True)
        self.assertIn("comprobá", str(raised.exception))
        self.assertIn("salida parcial", raised.exception.details)
        self.assertIn("detalle parcial", raised.exception.details)

    def test_network_uses_extended_timeout_and_keeps_existing_ssh_configuration(self):
        result = subprocess.CompletedProcess(["git", "push"], 0, stdout=b"ok", stderr=b"")
        with patch.dict(os.environ, {"GIT_SSH_COMMAND": "ssh -F /ruta/config"}), \
                patch("git.git_service.subprocess.run", return_value=result) as run:
            self.service._run(["push"], network=True)
        self.assertEqual(run.call_args.kwargs["timeout"], 120)
        self.assertEqual(run.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(run.call_args.kwargs["env"]["GIT_SSH_COMMAND"], "ssh -F /ruta/config")
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_network_keeps_core_ssh_command_and_defaults_to_batch_mode_otherwise(self):
        environment = os.environ.copy()
        environment.pop("GIT_SSH", None)
        environment.pop("GIT_SSH_COMMAND", None)
        actual_run = subprocess.run

        def simulate_network(command, **kwargs):
            if "config" in command:
                return actual_run(command, **kwargs)
            return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

        with patch.dict(os.environ, environment, clear=True):
            self.git("config", "core.sshCommand", "ssh -i /ruta/clave")
            with patch("git.git_service.subprocess.run", side_effect=simulate_network) as run:
                self.service._run(["push"], cwd=self.folder, network=True)
                self.assertNotIn("GIT_SSH_COMMAND", run.call_args.kwargs["env"])
            self.git("config", "--unset", "core.sshCommand")
            with patch("git.git_service.subprocess.run", side_effect=simulate_network) as run:
                self.service._run(["push"], cwd=self.folder, network=True)
                self.assertEqual(run.call_args.kwargs["env"]["GIT_SSH_COMMAND"], "ssh -o BatchMode=yes")


if __name__ == "__main__":
    unittest.main()
