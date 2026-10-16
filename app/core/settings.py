"""Ustawienia użytkownika oddzielone od projektu i jego pliku ELS.

Klucz API zapisujemy wyłącznie po zaszyfrowaniu przez Windows DPAPI. Ten sam
plik ustawień skopiowany na inne konto Windows nie pozwoli odszyfrować klucza.
Nie ma awaryjnego zapisu klucza jawnym tekstem.
"""

from __future__ import annotations

import base64
import ctypes
import os
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import re
import json

from PySide6.QtCore import QSettings, QStandardPaths


def documents_directory() -> str:
    """Systemowe Dokumenty, również po przeniesieniu ich do OneDrive/innego dysku."""
    return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home() / "Documents")


def default_code_directory() -> str:
    return str(Path(documents_directory()) / "ElectroSchem" / "Code")


def code_dialog_directory(settings) -> str:
    """Start at the chosen code directory, or its closest existing parent."""
    chosen=Path(settings.default_code_directory or default_code_directory()).expanduser()
    for candidate in (chosen,*chosen.parents):
        if candidate.is_dir(): return str(candidate)
    return documents_directory()


def file_dialog_directory(settings) -> str:
    """Nie tworzymy ani nie zmieniamy katalogów przy samym otwieraniu dialogu."""
    chosen = Path(settings.default_directory).expanduser() if settings.default_directory else None
    return str(chosen) if chosen and chosen.is_dir() else documents_directory()


def appdata_directory() -> Path:
    """Zwraca katalog ustawień ElectroSchem w %APPDATA%.

    Jawna funkcja pozwala ustawieniom i usługom pomocniczym korzystać z jednej
    lokalizacji niezależnie od domyślnego formatu QSettings Windows.
    """
    root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    target = root / "ElectroSchem"
    target.mkdir(parents=True, exist_ok=True)
    return target


def settings_store() -> QSettings:
    """Plik INI w AppData (zamiast niejawnego rejestru Windows)."""
    return QSettings(str(appdata_directory() / "settings.ini"), QSettings.Format.IniFormat)


@dataclass
class AppSettings:
    language: str = "en"
    standard: str = "EN"
    paper_size: str = "A4"
    orientation: str = "landscape"
    grid_visible: bool = True
    default_author: str = ""
    dramatic_faults: bool = False
    fault_effect: str = "mega"
    theme: str = "light"
    window_mode: str = "maximized"
    scope_size: str = 'normal'
    scope_volts_div: float = 5.
    scope_time_div: float = .01
    scope_autoscale: bool = False
    stop_on_fault: bool = True
    editor_path: str = ""
    default_directory: str = field(default_factory=documents_directory)
    default_code_directory: str = field(default_factory=default_code_directory)
    gemini_model: str = "auto"
    ai_provider: str = "gemini"
    openai_model: str = "gpt-6-astra"
    local_ai_url: str = "http://127.0.0.1:11434/v1"
    local_ai_model: str = ""
    local_ai_token: str = field(default='',repr=False)
    rotation_direction: str = 'cw'
    wires_through_cases: bool = False
    openai_api_key: str = field(default="", repr=False)
    # repr=False zapobiega przypadkowemu wypisaniu sekretu podczas diagnostyki.
    api_key: str = field(default="", repr=False)
    setup_complete: bool = False
    ai_chat_consent: bool = False
    ai_request_consents: dict[str,bool] = field(default_factory=dict)
    # Preferencje nazwy wyświetlanej są globalne dla biblioteki, a nie dla
    # konkretnego projektu. Kluczem jest stabilne library_id.
    default_display_names: dict[str, str] = field(default_factory=dict)
    default_component_values: dict[str, dict] = field(default_factory=dict)
    favorite_components: dict[str, dict] = field(default_factory=dict)


def _dpapi(data: bytes, *, decrypt: bool = False) -> bytes:
    """Chroni mały sekret dla aktualnego użytkownika, bez okienek Windows."""
    if os.name != "nt":
        raise OSError("Secure API key storage requires Windows DPAPI.")
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = DataBlob(len(data), buffer)
    result = DataBlob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        function = crypt.CryptUnprotectData
        function.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                             wintypes.DWORD, ctypes.POINTER(DataBlob)]
        description = None
    else:
        function = crypt.CryptProtectData
        function.argtypes = [ctypes.POINTER(DataBlob), wintypes.LPCWSTR,
                             ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                             wintypes.DWORD, ctypes.POINTER(DataBlob)]
        description = "ElectroSchem Gemini API"
    function.restype = wintypes.BOOL
    # CRYPTPROTECT_UI_FORBIDDEN = 1: brak pytań systemowych przy zapisie/odczycie.
    if not function(ctypes.byref(source), description, None, None, None, 1,
                    ctypes.byref(result)):
        raise OSError("Windows could not protect/unprotect the API key.")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel.LocalFree(result.pbData)


def detected_editors() -> list[tuple[str, str]]:
    """Lista istniejących programów; niczego nie instalujemy ani nie uruchamiamy."""
    local = Path(os.environ.get("LOCALAPPDATA", "C:/Users/Default/AppData/Local"))
    program = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    program_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    candidates = [
        ("Visual Studio Code", local / "Programs/Microsoft VS Code/Code.exe"),
        ("Visual Studio Code", program / "Microsoft VS Code/Code.exe"),
        ("Visual Studio Code", program_x86 / "Microsoft VS Code/Code.exe"),
        ("VSCodium", local / "Programs/VSCodium/VSCodium.exe"),
        ("Notepad++", program / "Notepad++/notepad++.exe"),
        ("Notepad++", program_x86 / "Notepad++/notepad++.exe"),
        ("Sublime Text", program / "Sublime Text/sublime_text.exe"),
    ]
    # `code` może wskazywać skrypt .cmd; do późniejszego uruchamiania bez shell
    # wybieramy rzeczywisty Code.exe leżący nad katalogiem bin.
    code_path = shutil.which("code")
    if code_path:
        candidates.insert(0, ("Visual Studio Code", Path(code_path).parent.parent / "Code.exe"))
    candidates.append(("Notepad", Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/notepad.exe"))
    found, seen = [], set()
    for name, path in candidates:
        normalized = str(path).lower()
        if path.is_file() and normalized not in seen:
            found.append((name, str(path)))
            seen.add(normalized)
    return found


def default_editor(editors: list[tuple[str, str]] | None = None) -> str:
    """Domyślny wybór jest jawny: VS Code, a przy jego braku Notatnik.

    Pozostałe wykryte edytory nadal pokazujemy w konfiguracji, ale nie
    wybieramy ich automatycznie zamiast uzgodnionego z użytkownikiem Notatnika.
    """
    editors = detected_editors() if editors is None else editors
    for preferred in ("Visual Studio Code", "Notepad"):
        for name, path in editors:
            if name == preferred:
                return path
    return ""


def load_settings(store: QSettings | None = None) -> AppSettings:
    """Brak ustawień lub uszkodzony klucz nie blokuje pracy bez funkcji AI."""
    if store is None:
        store = settings_store()
        # Jednorazowa migracja ustawień z wcześniejszej, błędnie zapisanej
        # nazwy aplikacji. Nowe zapisy trafiają już do %APPDATA%/ElectroSchem.
        if not store.allKeys():
            legacy = QSettings("ElektroSchem", "ElektroSchem")
            if legacy.allKeys():
                store = legacy
    result = AppSettings()
    try:
        raw=json.loads(str(store.value('ai_request_consents','{}')))
        if isinstance(raw,dict): result.ai_request_consents={k:True for k,v in raw.items() if k in {'gemini','openai','local'} and v is True}
    except (ValueError,TypeError): pass
    for name in ("language", "standard", "paper_size", "orientation", "editor_path", "gemini_model", "ai_provider", "openai_model", "local_ai_url", "local_ai_model", "default_directory", "default_code_directory", "default_author", "window_mode", "theme", "fault_effect"):
        setattr(result, name, str(store.value(name, getattr(result, name))))
    result.scope_size=str(store.value('scope_size',result.scope_size))
    result.rotation_direction=str(store.value('rotation_direction','cw'))
    result.wires_through_cases=str(store.value('wires_through_cases','false')).lower() in ('true','1')
    if result.rotation_direction not in {'cw','ccw'}: result.rotation_direction='cw'
    if result.scope_size not in {'normal','large','huge'}: result.scope_size='normal'
    from math import isfinite
    for key,minimum,maximum in (('scope_volts_div',.001,1e6),('scope_time_div',.000001,100)):
        try:
            value=float(store.value(key,getattr(result,key)))
            if isfinite(value) and minimum<=value<=maximum: setattr(result,key,value)
        except (ValueError,TypeError): pass
    for name in ("grid_visible", "setup_complete", "ai_chat_consent", "dramatic_faults",'stop_on_fault','scope_autoscale'):
        try:
            setattr(result, name, store.value(name, getattr(result, name), type=bool))
        except (TypeError, ValueError):
            # Uszkodzona preferencja nie może blokować startu całej aplikacji.
            pass
    if result.language not in {"en", "pl"}:
        result.language = "en"
    if result.standard not in {"EN", "PN", "ISO", "IEEE/ANSI"}:
        result.standard = "EN"
    if result.paper_size not in {f"A{i}" for i in range(6)}:
        result.paper_size = "A4"
    if result.orientation not in {"landscape", "portrait"}:
        result.orientation = "landscape"
    if result.window_mode not in {"windowed","maximized","fullscreen"}: result.window_mode="maximized"
    if result.theme not in {"light","dark"}: result.theme="light"
    code_path=Path(result.default_code_directory).expanduser()
    if not code_path.is_absolute() or (code_path.exists() and not code_path.is_dir()):
        result.default_code_directory=default_code_directory()
    if not store.contains("fault_effect") and store.contains("dramatic_faults"):
        result.fault_effect="mega" if result.dramatic_faults else "mini"
    elif result.fault_effect not in {"mini","medium","mega"}:
        result.fault_effect="mega" if result.dramatic_faults else "mini"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", result.gemini_model):
        result.gemini_model = AppSettings().gemini_model
    encrypted = store.value("gemini_key_dpapi", "")
    if result.ai_provider not in {"gemini", "openai", "local", "none"}:
        result.ai_provider = "gemini"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", result.openai_model):
        result.openai_model = AppSettings().openai_model
    openai_encrypted = store.value("openai_key_dpapi", "")
    local_encrypted=store.value('local_key_dpapi','')
    if local_encrypted:
        try: result.local_ai_token=_dpapi(base64.b64decode(str(local_encrypted),validate=True),decrypt=True).decode('utf-8')
        except (OSError,ValueError,UnicodeError): result.local_ai_token=''
    if openai_encrypted:
        try:
            result.openai_api_key = _dpapi(base64.b64decode(str(openai_encrypted), validate=True), decrypt=True).decode("utf-8")
        except (OSError, ValueError, UnicodeError):
            result.openai_api_key = ""
    if encrypted:
        try:
            result.api_key = _dpapi(base64.b64decode(str(encrypted), validate=True), decrypt=True).decode("utf-8")
        except (OSError, ValueError, UnicodeError):
            result.api_key = ""
    if not result.editor_path:
        result.editor_path = default_editor()
    raw_names = store.value("default_display_names", {})
    # QSettings INI na różnych wersjach Qt zwraca mapę albo jej tekstową
    # reprezentację. JSON daje stabilny zapis między instalacjami Windows.
    if isinstance(raw_names, str):
        try:
            raw_names = json.loads(raw_names)
        except (TypeError, ValueError):
            raw_names = {}
    if isinstance(raw_names, dict):
        result.default_display_names = {str(k): str(v) for k, v in raw_names.items()
                                       if isinstance(k, str) and isinstance(v, str) and v.strip()}
    raw_values=store.value("default_component_values", "{}")
    if isinstance(raw_values,str):
        try: raw_values=json.loads(raw_values)
        except (ValueError,TypeError): raw_values={}
    from app.core.component_defaults import validate_defaults
    result.default_component_values=validate_defaults(raw_values)
    raw_favorites=store.value("favorite_components","{}")
    try:
        raw_favorites=json.loads(raw_favorites) if isinstance(raw_favorites,str) else raw_favorites
        if isinstance(raw_favorites,dict):
            for k,v in list(raw_favorites.items())[:500]:
                if not isinstance(k,str) or not isinstance(v,dict) or len(k)>=200 or len(json.dumps(v))>=30000: continue
                clean={field:value for field,value in v.items() if (field in {"value","unit","display_name"} and isinstance(value,str)) or (field in {"show_name","show_value"} and isinstance(value,bool))}
                props=v.get("properties",{})
                if isinstance(props,dict): clean["properties"]={key:value for key,value in props.items() if isinstance(key,str) and isinstance(value,str)}
                result.favorite_components[k]=clean
    except (TypeError,ValueError): pass
    return result


def save_settings(settings: AppSettings, store: QSettings | None = None) -> None:
    """Najpierw szyfrujemy sekret; dopiero po sukcesie modyfikujemy ustawienia."""
    encrypted = base64.b64encode(_dpapi(settings.api_key.encode("utf-8"))).decode("ascii") if settings.api_key else ""
    openai_encrypted = base64.b64encode(_dpapi(settings.openai_api_key.encode("utf-8"))).decode("ascii") if settings.openai_api_key else ""
    local_encrypted=base64.b64encode(_dpapi(settings.local_ai_token.encode('utf-8'))).decode('ascii') if settings.local_ai_token else ''
    store = store if store is not None else settings_store()
    for name in ("language", "standard", "paper_size", "orientation", "grid_visible",
                 "editor_path", "gemini_model", "ai_provider", "openai_model", "local_ai_url", "local_ai_model", "setup_complete", "default_directory", "default_code_directory", "ai_chat_consent", "default_author", "dramatic_faults", "window_mode", "theme", "fault_effect",'scope_size','stop_on_fault','scope_volts_div','scope_time_div','scope_autoscale'):
        store.setValue(name, getattr(settings, name))
    store.setValue('rotation_direction',settings.rotation_direction)
    store.setValue('wires_through_cases',settings.wires_through_cases)
    if local_encrypted: store.setValue('local_key_dpapi',local_encrypted)
    else: store.remove('local_key_dpapi')
    store.remove('local_ai_token')
    store.setValue("default_display_names", json.dumps(settings.default_display_names, ensure_ascii=False))
    store.setValue("default_component_values", json.dumps(settings.default_component_values, ensure_ascii=False))
    store.setValue("favorite_components", json.dumps(settings.favorite_components, ensure_ascii=False))
    store.setValue('ai_request_consents',json.dumps(settings.ai_request_consents))
    if encrypted:
        store.setValue("gemini_key_dpapi", encrypted)
    else:
        store.remove("gemini_key_dpapi")
    if openai_encrypted:
        store.setValue("openai_key_dpapi", openai_encrypted)
    else:
        store.remove("openai_key_dpapi")
    # Obrona na wypadek ustawień pozostawionych przez starszy eksperymentalny kod.
    store.remove("api_key")
    store.remove("gemini_api_key")
    store.remove("openai_api_key")
    store.sync()
    if store.status() != QSettings.Status.NoError:
        raise OSError("Settings could not be saved.")


def remember_chat_consent(settings: AppSettings, store=None):
    """Zapisuje tylko zgodę, bez ponownego zapisywania klucza i reszty preferencji."""
    target = store if store is not None else settings_store()
    target.setValue("ai_chat_consent", True)
    target.sync()
    if target.status() != QSettings.Status.NoError:
        raise OSError("Consent could not be saved")
    settings.ai_chat_consent = True

def remember_request_consent(settings: AppSettings,store=None):
    target=store if store is not None else settings_store()
    consents={**settings.ai_request_consents,settings.ai_provider:True}
    target.setValue('ai_request_consents',json.dumps(consents)); target.sync()
    if target.status()!=QSettings.Status.NoError: raise OSError('Consent could not be saved')
    settings.ai_request_consents=consents
