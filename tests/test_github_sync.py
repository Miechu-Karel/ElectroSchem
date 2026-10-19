"""GitHub sync safety and UI wiring without network access."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.settings import AppSettings, load_settings, save_settings
from app.services.github_sync import GitHubSync, GitHubSyncError, validate_branch, validate_github_remote
from app.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])
GIT_AVAILABLE = shutil.which("git") is not None


@unittest.skipUnless(GIT_AVAILABLE, "Git is not installed")
class GitHubSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.remote = "https://github.com/example/electroschem.git"
        self._git("init", "-b", "main")
        self._git("config", "user.name", "ElectroSchem Test")
        self._git("config", "user.email", "test@example.invalid")
        self._git("remote", "add", "origin", self.remote)
        (self.root / "Project.els").write_text("first", encoding="utf-8")
        (self.root / "notes.txt").write_text("leave untouched", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "initial")

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_save_commit_contains_only_saved_els_file(self):
        (self.root / "Project.els").write_text("old staged version", encoding="utf-8")
        self._git("add", "--", "Project.els")
        (self.root / "Project.els").write_text("second", encoding="utf-8")
        (self.root / "notes.txt").write_text("user edit not committed", encoding="utf-8")
        sync = GitHubSync(self.root, self.remote, "main")

        self.assertEqual(sync.commit_file(self.root / "Project.els", "Test project"), "committed")
        changed_paths = self._git("show", "--pretty=format:", "--name-only", "HEAD").splitlines()
        self.assertEqual(changed_paths, ["Project.els"])
        self.assertEqual(self._git("show", "HEAD:Project.els"), "second")
        subject = self._git("log", "-1", "--format=%s")
        self.assertTrue(subject.startswith("Project.els "))
        self.assertRegex(subject, r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}$")
        self.assertEqual((self.root / "notes.txt").read_text(encoding="utf-8"), "user edit not committed")

    def test_new_project_file_is_added_and_committed(self):
        new_file = self.root / "NewProject.els"
        new_file.write_text("new", encoding="utf-8")
        sync = GitHubSync(self.root, self.remote, "main")
        self.assertEqual(sync.commit_file(new_file, "New project"), "committed")
        self.assertEqual(self._git("show", "HEAD:NewProject.els"), "new")

    def test_every_save_creates_a_commit_even_when_unchanged(self):
        sync = GitHubSync(self.root, self.remote, "main")
        before = int(self._git("rev-list", "--count", "HEAD"))
        self.assertEqual(sync.commit_file(self.root / "Project.els", "Test project"), "committed")
        self.assertEqual(int(self._git("rev-list", "--count", "HEAD")), before + 1)

    def test_manual_push_targets_the_entire_configured_branch_ref(self):
        client = GitHubSync(self.root, self.remote, "main")
        client._ensure_origin_and_branch = lambda: self.root
        with patch.object(client, "_run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            client.push()
        run.assert_called_once_with(["push", "origin", "main"])

    def test_remote_and_branch_validation(self):
        self.assertEqual(validate_github_remote(self.remote), self.remote)
        self.assertEqual(validate_branch("feature/alpha-4"), "feature/alpha-4")
        with self.assertRaises(GitHubSyncError):
            validate_github_remote("https://example.com/user/repo")
        with self.assertRaises(GitHubSyncError):
            validate_branch("../main")

    def test_file_outside_repository_is_not_committed(self):
        outside = Path(self.temp.name) / "outside.els"
        outside.write_text("local", encoding="utf-8")
        sync = GitHubSync(self.root, self.remote, "main")
        self.assertEqual(sync.commit_file(outside, "Outside"), "outside-repository")


class GitHubSettingsAndUiTests(unittest.TestCase):
    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            expected = AppSettings(cloud_provider="github",
                                   github_repository_url="https://github.com/example/repo.git",
                                   github_branch="release/1.4")
            save_settings(expected, store)
            actual = load_settings(store)
        self.assertEqual(actual.github_repository_url, expected.github_repository_url)
        self.assertEqual(actual.github_branch, expected.github_branch)
        self.assertEqual(actual.cloud_provider, "github")

    def test_github_menu_has_manual_pull_and_push(self):
        window = MainWindow(AppSettings(cloud_provider="github"), start_setup=False)
        try:
            self.assertTrue(window.github_menu.menuAction().isVisible())
            self.assertEqual([action.text() for action in window.github_menu.actions()],
                             ["Pull from GitHub", "Push to GitHub"])
        finally:
            window.close()
            window.deleteLater()
            APP.processEvents()

    def test_successful_local_save_queues_a_project_commit(self):
        settings = AppSettings(cloud_provider="github",
                               github_repository_url="https://github.com/example/repo.git")
        window = MainWindow(settings, start_setup=False)
        try:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "Circuit.els"
                with patch.object(window, "_start_next_github_operation"):
                    self.assertTrue(window._write_project(target))
                self.assertEqual(window._github_queue,
                                 [("commit", str(target), window.project.name)])
        finally:
            window._saved_state = window.project.to_dict()
            window.close()
            window.deleteLater()
            APP.processEvents()

    def test_startup_pull_runs_as_queued_background_operation(self):
        settings = AppSettings(cloud_provider="github",
                               github_repository_url="https://github.com/example/repo.git")
        window = MainWindow(settings, start_setup=False)
        try:
            with patch("app.ui.main_window.QThreadPool.globalInstance") as pool, \
                    patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
                pool.return_value.start.side_effect = lambda worker: worker.signals.finished.emit(
                    "startup_pull", "Already up to date.", None)
                window._queue_github_operation("startup_pull")
                APP.processEvents()
            self.assertFalse(window._github_busy)
            self.assertIsNone(window._github_progress)
            self.assertIn("pull", window.statusBar().currentMessage().lower())
        finally:
            window.close()
            window.deleteLater()
            APP.processEvents()

    def test_selected_github_provider_schedules_pull_on_every_start(self):
        settings = AppSettings(cloud_provider="github",
                               github_repository_url="https://github.com/example/repo.git",
                               github_branch="release/1.4")
        with patch("app.ui.main_window.QTimer.singleShot") as schedule, \
                patch.object(MainWindow, "_queue_github_operation") as queue:
            window = MainWindow(settings, start_setup=False)
            try:
                schedule.assert_called_once()
                callback = schedule.call_args.args[1]
                callback()
                queue.assert_called_once_with("startup_pull")
            finally:
                window.close()
                window.deleteLater()
                APP.processEvents()

    def test_github_provider_routes_default_cloud_actions_to_local_clone(self):
        settings = AppSettings(cloud_provider="github", cloud_default_location="cloud",
                               github_repository_url="https://github.com/example/repo.git")
        window = MainWindow(settings, start_setup=False)
        try:
            with patch.object(window, "open_project") as open_local:
                window.open_default_location()
                open_local.assert_called_once_with()
            with patch.object(window, "save_github_project", return_value=True) as save_github:
                self.assertTrue(window.save_default_location())
                save_github.assert_called_once_with()
        finally:
            window._saved_state = window.project.to_dict()
            window.close()
            window.deleteLater()
            APP.processEvents()


if __name__ == "__main__":
    unittest.main()
