"""Własny kontener projektu ElectroSchem (.els).

ELS jest pojedynczym pakietem aplikacji, nie plikiem JSON wystawionym na
zewnątrz. W środku używamy JSON wyłącznie jako stabilnego formatu danych.
W przyszłości pakiet może zawierać biblioteki użytkownika, miniatury i kod.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, BadZipFile

from app.core.models import Project, FORMAT_VERSION

PROJECT_MEMBER = "project.json"
MANIFEST_MEMBER = "manifest.json"


def save_project(path: str | Path, project: Project) -> None:
    """Zapisuje projekt do samodzielnego pliku .els."""
    destination = Path(path)
    if destination.suffix.lower() != ".els":
        destination = destination.with_suffix(".els")

    manifest = {"application": "ElectroSchem", "format_version": FORMAT_VERSION}
    # Zapis atomowy: awaria nie niszczy wcześniejszej, poprawnej wersji pliku.
    # Plik tymczasowy powstaje w tym samym katalogu (ten sam wolumin).
    descriptor, temporary = tempfile.mkstemp(prefix=".els-", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as package:
            package.writestr(MANIFEST_MEMBER, json.dumps(manifest, ensure_ascii=False, indent=2))
            package.writestr(PROJECT_MEMBER, json.dumps(project.to_dict(), ensure_ascii=False, indent=2, allow_nan=False))
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_project(path: str | Path) -> Project:
    """Wczytuje i podstawowo sprawdza pakiet ELS."""
    try:
        with ZipFile(path, "r") as package:
            if PROJECT_MEMBER not in package.namelist() or MANIFEST_MEMBER not in package.namelist():
                raise ValueError("Invalid ElectroSchem package / Niepoprawny pakiet ELS")
            if package.getinfo(PROJECT_MEMBER).file_size > 20_000_000 or package.getinfo(MANIFEST_MEMBER).file_size > 10000:
                raise ValueError("ELS document exceeds size limit / Zbyt duży dokument")
            manifest = json.loads(package.read(MANIFEST_MEMBER))
            # Wczytujemy również pakiety z literówką z poprzednich wersji.
            if not isinstance(manifest, dict) or manifest.get("application") not in {"ElectroSchem", "ElektroSchem"}:
                raise ValueError("Not an ElectroSchem project")
            manifest_version = manifest.get("format_version", 1)
            if type(manifest_version) is not int or not 1 <= manifest_version <= FORMAT_VERSION:
                raise ValueError("Unsupported ELS package version / Nieobsługiwana wersja pakietu ELS")
            data = json.loads(package.read(PROJECT_MEMBER).decode("utf-8"))
            if not isinstance(data, dict) or data.get("format_version", 1) != manifest_version:
                raise ValueError("Inconsistent ELS versions / Niezgodne wersje wewnątrz ELS")
        return Project.from_dict(data)
    except (BadZipFile, UnicodeError, KeyError, TypeError) as error:
        raise ValueError("Damaged ELS file / Uszkodzony plik ELS") from error
