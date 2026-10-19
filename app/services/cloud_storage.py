"""Direct project-file access for configured cloud providers.

The module deliberately keeps credentials out of project files. OAuth tokens
are held by AppSettings and encrypted with Windows DPAPI by settings.py.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
from pathlib import PurePosixPath
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse, parse_qs
from urllib.request import HTTPRedirectHandler, Request, build_opener
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from hashlib import sha256


MAX_PROJECT_BYTES = 20_000_000
TIMEOUT_SECONDS = 20
PROVIDERS = {"google_drive", "onedrive"}


class CloudStorageError(RuntimeError):
    """A safe-to-display cloud storage error without raw provider payloads."""


_ERROR_TRANSLATIONS = {
    "Cloud authorization failed. Reconnect the selected provider.": "Autoryzacja chmury nie powiodła się. Połącz ponownie wybranego dostawcę.",
    "The cloud folder or project file was not found.": "Nie znaleziono folderu lub pliku projektu w chmurze.",
    "The cloud provider reported a file conflict.": "Dostawca chmury zgłosił konflikt pliku.",
    "Could not connect to the cloud provider. Check the Internet connection.": "Nie można połączyć się z chmurą. Sprawdź połączenie internetowe.",
    "The cloud provider returned an invalid response.": "Dostawca chmury zwrócił niepoprawną odpowiedź.",
    "Choose a supported cloud provider in Settings → Cloud.": "Wybierz obsługiwanego dostawcę w Ustawienia → Chmura.",
    "Choose a supported cloud provider.": "Wybierz obsługiwanego dostawcę chmury.",
    "Connect your cloud account in Settings → Cloud first.": "Najpierw połącz konto w Ustawienia → Chmura.",
    "Could not refresh the cloud authorization. Reconnect the provider.": "Nie udało się odświeżyć autoryzacji. Połącz ponownie dostawcę.",
    "Enter a Google Drive folder link or folder ID.": "Wpisz link do folderu Google Drive lub jego ID.",
    "Enter a OneDrive HTTPS sharing link.": "Wpisz link udostępniania OneDrive HTTPS.",
    "The OneDrive link must point to a folder you can edit.": "Link OneDrive musi prowadzić do folderu, w którym masz uprawnienia edycji.",
    "Cloud sign-in timed out. Try connecting again.": "Logowanie do chmury przekroczyło limit czasu. Spróbuj ponownie.",
    "Cloud sign-in was cancelled or rejected.": "Logowanie do chmury anulowano lub odrzucono.",
    "Enter a project file name.": "Wpisz nazwę pliku projektu.",
    "The project file name is invalid.": "Nazwa pliku projektu jest niepoprawna.",
    "The local sign-in callback port is busy. Try connecting again.": "Lokalny port logowania jest zajęty. Spróbuj połączyć ponownie.",
    "The provider returned an invalid sign-in response.": "Dostawca zwrócił niepoprawną odpowiedź logowania.",
    "Could not complete cloud sign-in. Check the application credentials and redirect settings.": "Nie udało się dokończyć logowania. Sprawdź dane aplikacji i ustawienia przekierowania.",
    "Enter the selected provider's application ID/key in Settings → Cloud.": "Wpisz identyfikator lub klucz aplikacji dostawcy w Ustawienia → Chmura.",
    "The project file exceeds the supported size limit.": "Plik projektu przekracza obsługiwany limit rozmiaru.",
    "The cloud provider requested an unsafe download redirect.": "Dostawca chmury zażądał niebezpiecznego przekierowania pobierania.",
    "The cloud provider returned an invalid upload session.": "Dostawca chmury zwrócił niepoprawną sesję wysyłania.",
}


def localized_cloud_error(error, language="en"):
    message = str(error)
    if language != "pl":
        return message
    match = re.fullmatch(r"Cloud request failed \(HTTP (\d+)\)\.", message)
    if match:
        return f"Żądanie do dostawcy chmury nie powiodło się (HTTP {match.group(1)})."
    return _ERROR_TRANSLATIONS.get(message, message)


@dataclass(frozen=True)
class CloudProjectFile:
    file_id: str
    name: str
    modified: str = ""


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Avoid forwarding credentials to a host selected by a redirect."""

    @staticmethod
    def _origin(url):
        parsed = urlparse(url)
        return parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        old_url = request.full_url
        if urlparse(old_url).scheme.lower() == "https" and urlparse(new_url).scheme.lower() != "https":
            return None
        redirected = super().redirect_request(request, file_pointer, code, message, headers, new_url)
        if redirected and self._origin(old_url) != self._origin(new_url):
            sensitive = {"authorization", "proxy-authorization"}
            for header_map in (redirected.headers, redirected.unredirected_hdrs):
                for key in tuple(header_map):
                    if key.lower() in sensitive:
                        del header_map[key]
        return redirected


def _read_url(url: str, method="GET", headers=None, body=None) -> tuple[bytes, dict]:
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        opener = build_opener(_SafeRedirectHandler())
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read(MAX_PROJECT_BYTES + 1), dict(response.headers.items())
    except HTTPError as error:
        # Provider error bodies may contain account data; do not expose/log them.
        status = error.code
        if status in (401, 403):
            raise CloudStorageError("Cloud authorization failed. Reconnect the selected provider.") from None
        if status == 404:
            raise CloudStorageError("The cloud folder or project file was not found.") from None
        if status == 409:
            raise CloudStorageError("The cloud provider reported a file conflict.") from None
        if status in (301, 302, 303, 307, 308):
            raise CloudStorageError("The cloud provider requested an unsafe download redirect.") from None
        raise CloudStorageError(f"Cloud request failed (HTTP {status}).") from None
    except (URLError, TimeoutError, OSError):
        raise CloudStorageError("Could not connect to the cloud provider. Check the Internet connection.") from None


def _read_json(url: str, method="GET", headers=None, payload=None) -> dict:
    request_headers = {"Accept": "application/json", **(headers or {})}
    body = None if payload is None else _json_bytes(payload)
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    raw, _ = _read_url(url, method, request_headers, body)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise CloudStorageError("The cloud provider returned an invalid response.") from None
    if not isinstance(value, dict):
        raise CloudStorageError("The cloud provider returned an invalid response.")
    return value


def _validate_els_name(name: str) -> str:
    name = str(name or "").strip()
    if not name:
        raise CloudStorageError("Enter a project file name.")
    name = PurePosixPath(name.replace("\\", "/")).name
    if not name.lower().endswith(".els"):
        name += ".els"
    if len(name) > 180 or any(ord(char) < 32 for char in name):
        raise CloudStorageError("The project file name is invalid.")
    return name


def _google_folder_id(value: str) -> str:
    value = value.strip()
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{8,200}", value):
        return value
    raise CloudStorageError("Enter a Google Drive folder link or folder ID.")


def _onedrive_share_id(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CloudStorageError("Enter a OneDrive HTTPS sharing link.")
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
    return "u!" + encoded


class CloudStorageClient:
    def __init__(self, settings):
        self.settings = settings
        self.provider = settings.cloud_provider
        if self.provider not in PROVIDERS:
            raise CloudStorageError("Choose a supported cloud provider in Settings → Cloud.")
        self._access_token = ""

    def _token(self) -> str:
        token = dict(self.settings.cloud_tokens.get(self.provider, {}))
        access = str(token.get("access_token", ""))
        try:
            expires_at = float(token.get("expires_at", 0))
        except (ValueError, TypeError):
            expires_at = 0
        if access and expires_at > time.time() + 60:
            self._access_token = access
            return access
        refresh = str(token.get("refresh_token", ""))
        if not refresh:
            raise CloudStorageError("Connect your cloud account in Settings → Cloud first.")
        self._refresh_token(token, refresh)
        self._access_token = str(token.get("access_token", ""))
        self.settings.cloud_tokens[self.provider] = token
        return self._access_token

    def _refresh_token(self, token, refresh):
        if self.provider == "google_drive":
            endpoint = "https://oauth2.googleapis.com/token"
            fields = {"client_id": self.settings.google_drive_client_id,
                      "client_secret": self.settings.google_drive_client_secret}
        elif self.provider == "onedrive":
            endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            fields = {"client_id": self.settings.onedrive_client_id}
        else:  # OneDrive
            endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            fields = {"client_id": self.settings.onedrive_client_id}
        fields.update({"grant_type": "refresh_token", "refresh_token": refresh})
        raw, _ = _read_url(endpoint, "POST", {"Content-Type": "application/x-www-form-urlencoded"}, urlencode(fields).encode("ascii"))
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise CloudStorageError("Could not refresh the cloud authorization. Reconnect the provider.") from None
        if not isinstance(result, dict) or not result.get("access_token"):
            raise CloudStorageError("Could not refresh the cloud authorization. Reconnect the provider.")
        token.update(result)
        token["expires_at"] = time.time() + float(result.get("expires_in", 3600))

    def _auth_headers(self):
        return {"Authorization": "Bearer " + self._token()}

    def _google_list(self):
        folder_id = _google_folder_id(self.settings.cloud_folder)
        query = urlencode({"q": f"'{folder_id}' in parents and trashed = false",
                           "fields": "files(id,name,mimeType,modifiedTime,size)", "pageSize": "100"})
        result = _read_json("https://www.googleapis.com/drive/v3/files?" + query, headers=self._auth_headers())
        return [CloudProjectFile(str(item.get("id", "")), str(item.get("name", "")), str(item.get("modifiedTime", "")))
                for item in result.get("files", []) if isinstance(item, dict) and str(item.get("name", "")).lower().endswith(".els")]

    def _onedrive_folder(self):
        share_id = _onedrive_share_id(self.settings.cloud_folder)
        item = _read_json("https://graph.microsoft.com/v1.0/shares/" + quote(share_id, safe="") + "/driveItem",
                          headers=self._auth_headers())
        if not item.get("folder") or not item.get("id") or not item.get("parentReference", {}).get("driveId"):
            raise CloudStorageError("The OneDrive link must point to a folder you can edit.")
        return str(item["parentReference"]["driveId"]), str(item["id"])

    def _onedrive_list(self):
        drive_id, folder_id = self._onedrive_folder()
        url = f"https://graph.microsoft.com/v1.0/drives/{quote(drive_id, safe='')}/items/{quote(folder_id, safe='')}/children?$select=id,name,lastModifiedDateTime,file"
        result = _read_json(url, headers=self._auth_headers())
        return [CloudProjectFile(str(item.get("id", "")), str(item.get("name", "")), str(item.get("lastModifiedDateTime", "")))
                for item in result.get("value", []) if isinstance(item, dict) and str(item.get("name", "")).lower().endswith(".els")]

    def list_projects(self) -> list[CloudProjectFile]:
        if self.provider == "google_drive":
            return self._google_list()
        return self._onedrive_list()

    def download(self, file: CloudProjectFile) -> bytes:
        if self.provider == "google_drive":
            url = "https://www.googleapis.com/drive/v3/files/" + quote(file.file_id, safe="") + "?alt=media"
            headers = self._auth_headers()
        else:  # OneDrive
            drive_id, _ = self._onedrive_folder()
            url = f"https://graph.microsoft.com/v1.0/drives/{quote(drive_id, safe='')}/items/{quote(file.file_id, safe='')}/content"
            headers = self._auth_headers()
        raw, _ = _read_url(url, headers=headers)
        if len(raw) > MAX_PROJECT_BYTES:
            raise CloudStorageError("The project file exceeds the supported size limit.")
        return raw

    def upload(self, name: str, data: bytes, file_id="") -> CloudProjectFile:
        name = _validate_els_name(name)
        if len(data) > MAX_PROJECT_BYTES:
            raise CloudStorageError("The project file exceeds the supported size limit.")
        if self.provider == "google_drive":
            headers = self._auth_headers()
            metadata_value = {"name": name}
            method = "POST"
            endpoint = "https://www.googleapis.com/upload/drive/v3/files"
            if file_id:
                endpoint += "/" + quote(file_id, safe="")
                method = "PATCH"
            else:
                metadata_value["parents"] = [_google_folder_id(self.settings.cloud_folder)]
            if len(data) <= 5_000_000:
                boundary = "electroschem_" + secrets.token_hex(16)
                metadata = _json_bytes(metadata_value)
                body = (b"--" + boundary.encode() + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" + metadata +
                        b"\r\n--" + boundary.encode() + b"\r\nContent-Type: application/octet-stream\r\n\r\n" + data +
                        b"\r\n--" + boundary.encode() + b"--")
                raw, _ = _read_url(endpoint + "?uploadType=multipart&fields=id,name,modifiedTime",
                                   method, {**headers, "Content-Type": "multipart/related; boundary=" + boundary}, body)
            else:
                start_headers = {**headers, "Content-Type": "application/json; charset=UTF-8",
                                 "X-Upload-Content-Type": "application/octet-stream",
                                 "X-Upload-Content-Length": str(len(data))}
                _, response_headers = _read_url(endpoint + "?uploadType=resumable&fields=id,name,modifiedTime",
                                                method, start_headers, _json_bytes(metadata_value))
                session_url = next((value for key, value in response_headers.items() if key.lower() == "location"), "")
                session_host = (urlparse(session_url).hostname or "").lower()
                if (urlparse(session_url).scheme != "https" or
                        not (session_host == "googleapis.com" or session_host.endswith(".googleapis.com"))):
                    raise CloudStorageError("The cloud provider returned an invalid upload session.")
                raw, _ = _read_url(session_url, "PUT", {"Content-Type": "application/octet-stream",
                                                          "Content-Length": str(len(data)),
                                                          "Content-Range": f"bytes 0-{len(data) - 1}/{len(data)}"}, data)
            try:
                meta = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError):
                raise CloudStorageError("The cloud provider returned an invalid response.") from None
            return CloudProjectFile(str(meta.get("id", "")), str(meta.get("name", name)), str(meta.get("modifiedTime", "")))
        if self.provider == "onedrive":
            drive_id, folder_id = self._onedrive_folder()
            item_path = quote(name, safe="")
            if file_id:
                url = f"https://graph.microsoft.com/v1.0/drives/{quote(drive_id, safe='')}/items/{quote(file_id, safe='')}/content"
            else:
                url = f"https://graph.microsoft.com/v1.0/drives/{quote(drive_id, safe='')}/items/{quote(folder_id, safe='')}:/{item_path}:/content"
            raw, _ = _read_url(url, "PUT", {**self._auth_headers(), "Content-Type": "application/octet-stream"}, data)
            meta = json.loads(raw.decode("utf-8"))
            return CloudProjectFile(str(meta.get("id", file_id)), str(meta.get("name", name)), str(meta.get("lastModifiedDateTime", "")))
        raise CloudStorageError("Choose a supported cloud provider in Settings → Cloud.")

    def test_connection(self) -> None:
        # Listing is also the least-destructive provider-specific permission check.
        self.list_projects()


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(48)).decode("ascii").rstrip("=")
    challenge = base64.urlsafe_b64encode(sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


def authorize_provider(settings, progress=None) -> dict[str, str]:
    """Interactive OAuth for Google Drive or OneDrive."""
    provider = settings.cloud_provider
    if provider not in {"google_drive", "onedrive"}:
        raise CloudStorageError("Choose a supported cloud provider.")
    if provider == "google_drive":
        client_id, client_secret = settings.google_drive_client_id.strip(), settings.google_drive_client_secret
        auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        token_endpoint = "https://oauth2.googleapis.com/token"
        scopes = "https://www.googleapis.com/auth/drive"
        extras = {"access_type": "offline", "prompt": "consent"}
    elif provider == "onedrive":
        client_id, client_secret = settings.onedrive_client_id.strip(), ""
        auth_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        token_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        scopes = "Files.ReadWrite offline_access"
        extras = {}
    if not client_id:
        raise CloudStorageError("Enter the selected provider's application ID/key in Settings → Cloud.")

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    host, port, callback_path = "127.0.0.1", 0, "/callback"
    received = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed_callback = urlparse(self.path)
            params = parse_qs(parsed_callback.query)
            if parsed_callback.path != callback_path or params.get("state", [""])[0] != state:
                self.send_response(400); self.end_headers(); self.wfile.write(b"Invalid authorization callback."); return
            received["code"] = params.get("code", [""])[0]
            received["error"] = params.get("error", [""])[0]
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("<html><body><h3>ElectroSchem</h3><p>You can return to ElectroSchem now.</p></body></html>".encode("utf-8"))

        def log_message(self, format, *args):
            return

    try:
        server = HTTPServer((host, port), CallbackHandler)
    except OSError:
        raise CloudStorageError("The local sign-in callback port is busy. Try connecting again.") from None
    server.timeout = 1
    actual_port = server.server_address[1]
    if provider == "onedrive":
        actual_redirect = f"http://localhost:{actual_port}/callback"
    else:
        actual_redirect = f"http://{host}:{actual_port}{callback_path}"
    query = {"client_id": client_id, "response_type": "code", "redirect_uri": actual_redirect,
             "scope": scopes, "state": state, "code_challenge": challenge, "code_challenge_method": "S256", **extras}
    auth_url = auth_endpoint + "?" + urlencode(query)
    if progress:
        progress("Open the provider sign-in page in your browser and approve ElectroSchem.")
    webbrowser.open(auth_url)
    deadline = time.monotonic() + 240
    try:
        while not received and time.monotonic() < deadline:
            server.handle_request()
        if not received:
            raise CloudStorageError("Cloud sign-in timed out. Try connecting again.")
        if received.get("error") or not received.get("code"):
            raise CloudStorageError("Cloud sign-in was cancelled or rejected.")
    finally:
        server.server_close()
    fields = {"client_id": client_id, "grant_type": "authorization_code", "code": received["code"],
              "redirect_uri": actual_redirect, "code_verifier": verifier}
    if client_secret:
        fields["client_secret"] = client_secret
    raw, _ = _read_url(token_endpoint, "POST", {"Content-Type": "application/x-www-form-urlencoded"}, urlencode(fields).encode("ascii"))
    try:
        token = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise CloudStorageError("The provider returned an invalid sign-in response.") from None
    if not isinstance(token, dict) or not token.get("access_token"):
        raise CloudStorageError("Could not complete cloud sign-in. Check the application credentials and redirect settings.")
    token["expires_at"] = time.time() + float(token.get("expires_in", 3600))
    clean_token = {str(k): str(v) for k, v in token.items() if isinstance(v, (str, int, float))}
    settings.cloud_tokens[provider] = clean_token
    CloudStorageClient(settings).test_connection()
    return clean_token
