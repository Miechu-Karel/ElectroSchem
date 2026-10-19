"""Cloud provider and ELS transfer tests; no real network calls are made."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from email.message import Message
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

from PySide6.QtCore import QSettings

from app.core.models import Project
from app.core.project_file import load_project_bytes, project_bytes
from app.core.settings import AppSettings, load_settings, save_settings
from app.services.cloud_storage import (
    CloudProjectFile, CloudStorageClient, CloudStorageError, _google_folder_id,
    _onedrive_share_id, _validate_els_name, _SafeRedirectHandler, PROVIDERS,
)


class ProjectTransferTests(unittest.TestCase):
    def test_project_roundtrip_in_memory(self):
        project = Project(name="Cloud roundtrip")
        restored = load_project_bytes(project_bytes(project))
        self.assertEqual(restored.to_dict(), project.to_dict())

    def test_cloud_filename_is_confined_to_leaf_els_name(self):
        self.assertEqual(_validate_els_name("../my-project"), "my-project.els")
        with self.assertRaises(CloudStorageError):
            _validate_els_name("bad\nname")


class CloudValidationTests(unittest.TestCase):
    def test_provider_folder_links_are_parsed_safely(self):
        self.assertEqual(_google_folder_id("https://drive.google.com/drive/folders/abc_DEF-123"), "abc_DEF-123")
        self.assertTrue(_onedrive_share_id("https://1drv.ms/f/example").startswith("u!"))
        self.assertEqual(PROVIDERS, {"google_drive", "onedrive"})

    def test_google_list_uses_folder_id_and_bearer_token(self):
        settings = AppSettings(cloud_provider="google_drive",
                               cloud_folder="https://drive.google.com/drive/folders/folder_123456",
                               cloud_tokens={"google_drive": {"access_token": "unit-test-token",
                                                               "expires_at": str(time.time() + 3600)}})
        with patch("app.services.cloud_storage._read_json", return_value={"files": [
                {"id": "file1", "name": "Blinker.els", "modifiedTime": "today"},
                {"id": "file2", "name": "notes.txt"}]}) as request:
            files = CloudStorageClient(settings).list_projects()
        self.assertEqual(files, [CloudProjectFile("file1", "Blinker.els", "today")])
        self.assertIn("folder_123456", request.call_args.args[0])
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer unit-test-token")

    def test_google_upload_places_package_in_selected_folder(self):
        settings = AppSettings(cloud_provider="google_drive", cloud_folder="folder_123456",
                               cloud_tokens={"google_drive": {"access_token": "unit-test-token",
                                                               "expires_at": str(time.time() + 3600)}})
        response = json.dumps({"id": "new-id", "name": "Cloud.els"}).encode()
        with patch("app.services.cloud_storage._read_url", return_value=(response, {})) as request:
            item = CloudStorageClient(settings).upload("Cloud", project_bytes(Project()))
        self.assertEqual(item, CloudProjectFile("new-id", "Cloud.els", ""))
        self.assertIn("uploadType=multipart", request.call_args.args[0])
        payload = request.call_args.args[3]
        self.assertIn(b'"parents":["folder_123456"]', payload)

    def test_large_google_upload_uses_resumable_session_without_forwarding_auth(self):
        settings = AppSettings(cloud_provider="google_drive", cloud_folder="folder_123456",
                               cloud_tokens={"google_drive": {"access_token": "unit-test-token",
                                                               "expires_at": str(time.time() + 3600)}})
        response = json.dumps({"id": "large-id", "name": "Large.els"}).encode()
        with patch("app.services.cloud_storage._read_url", side_effect=[
                (b"", {"Location": "https://upload.googleapis.com/session/abc"}), (response, {})]) as request:
            item = CloudStorageClient(settings).upload("Large", b"x" * 5_000_001)
        self.assertEqual(item.file_id, "large-id")
        self.assertIn("uploadType=resumable", request.call_args_list[0].args[0])
        self.assertEqual(request.call_args_list[1].args[1], "PUT")
        self.assertNotIn("Authorization", request.call_args_list[1].args[2])
        self.assertEqual(request.call_args_list[1].args[2]["Content-Range"], "bytes 0-5000000/5000001")

    def test_cross_host_redirect_does_not_forward_credentials(self):
        request = Request("https://graph.microsoft.com/content", headers={
            "Authorization": "Bearer private-token", "X-Private-Path": "private-path"})
        redirected = _SafeRedirectHandler().redirect_request(
            request, BytesIO(), 302, "Found", Message(), "https://download.example/file")
        self.assertNotIn("Authorization", redirected.headers)
        self.assertIn("x-private-path", {key.lower() for key in redirected.headers})
        self.assertIsNone(_SafeRedirectHandler().redirect_request(
            request, BytesIO(), 302, "Found", Message(), "http://download.example/file"))

class ProviderAdapterTests(unittest.TestCase):
    def token_settings(self, provider, **kwargs):
        return AppSettings(cloud_provider=provider,
                           cloud_tokens={provider: {"access_token": "unit-test-token",
                                                    "expires_at": str(time.time() + 3600)}}, **kwargs)

    def test_onedrive_shared_folder_and_project_listing(self):
        settings = self.token_settings("onedrive", cloud_folder="https://1drv.ms/f/example")
        folder = {"id": "folder-id", "folder": {"childCount": 0}, "parentReference": {"driveId": "drive-id"}}
        listing = {"value": [{"id": "project-id", "name": "Circuit.els", "lastModifiedDateTime": "today"},
                             {"id": "ignore", "name": "notes.txt"}]}
        with patch("app.services.cloud_storage._read_json", side_effect=[folder, listing]) as request:
            projects = CloudStorageClient(settings).list_projects()
        self.assertEqual(projects, [CloudProjectFile("project-id", "Circuit.els", "today")])
        self.assertIn("/shares/u%21", request.call_args_list[0].args[0])
        self.assertIn("/drives/drive-id/items/folder-id/children", request.call_args_list[1].args[0])
        self.assertEqual(request.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer unit-test-token")

class CloudSettingsTests(unittest.TestCase):
    def test_no_cloud_is_a_valid_choice_and_forces_local_default(self):
        with tempfile.TemporaryDirectory() as directory:
            store = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            settings = AppSettings(cloud_default_location="cloud", cloud_provider="none")
            save_settings(settings, store)
            restored = load_settings(store)
        self.assertEqual(restored.cloud_provider, "none")
        self.assertEqual(restored.cloud_default_location, "local")

    def test_cloud_secrets_are_encrypted_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            settings = AppSettings(
                cloud_default_location="cloud", cloud_provider="google_drive",
                cloud_folder="folder-id", google_drive_client_secret="test-cloud-secret",
                cloud_tokens={"google_drive": {"refresh_token": "test-refresh-token"}},
            )
            protected = []
            def fake_dpapi(data, *, decrypt=False):
                if decrypt:
                    return protected[0]
                protected.append(data)
                return b"protected-cloud-secret"
            with patch("app.core.settings._dpapi", side_effect=fake_dpapi):
                save_settings(settings, store)
                raw = str(store.value("cloud_secrets_dpapi"))
                self.assertNotIn("test-cloud-secret", raw)
                self.assertNotIn("test-refresh-token", raw)
                restored = load_settings(store)
            self.assertEqual(restored.cloud_default_location, "cloud")
            self.assertEqual(restored.cloud_provider, "google_drive")
            self.assertEqual(restored.google_drive_client_secret, "test-cloud-secret")
            self.assertEqual(restored.cloud_tokens["google_drive"]["refresh_token"], "test-refresh-token")

    def test_removed_provider_settings_migrate_to_no_cloud(self):
        with tempfile.TemporaryDirectory() as directory:
            store = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            store.setValue("cloud_provider", "dropbox")
            store.setValue("cloud_default_location", "cloud")
            store.setValue("dropbox_app_key", "legacy-key")
            restored = load_settings(store)
        self.assertEqual(restored.cloud_provider, "none")
        self.assertEqual(restored.cloud_default_location, "local")


if __name__ == "__main__":
    unittest.main()
