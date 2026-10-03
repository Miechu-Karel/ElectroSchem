"""Model ELS niezależny od Qt. UUID wiąże przewody, reference opisuje element.

Zmiana nazwy lub języka nie zmienia kluczy połączeń. Czytelne oznaczenia mają
liczniki projektowe, a nie arkuszowe, i nie zależą od liczby żywych obiektów.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field, fields
import math
import re
import json
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from datetime import datetime

FORMAT_VERSION = 3
PAPER_SIZES_MM = {"A0": (841, 1189), "A1": (594, 841), "A2": (420, 594),
                  "A3": (297, 420), "A4": (210, 297), "A5": (148, 210)}

def new_id() -> str:
    return str(uuid4())

@dataclass
class ComponentInstance:
    library_id: str
    x: float
    y: float
    id: str = field(default_factory=new_id)
    rotation: int = 0
    properties: dict[str, str] = field(default_factory=dict)
    reference: str = ""
    display_name: str = ""
    show_name: bool = True
    value: str = ""
    unit: str = ""
    show_value: bool = True

@dataclass
class Wire:
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    id: str = field(default_factory=new_id)
    points: list[list[float]] = field(default_factory=list)
    start_component_id: str | None = None
    start_pin_index: int | None = None
    end_component_id: str | None = None
    end_pin_index: int | None = None
    # Jawny węzeł pozwala połączyć kilka kabli także bez komponentu.
    start_junction_id: str | None = None
    end_junction_id: str | None = None
    # Numer fizycznego wyprowadzenia zabezpiecza zapis przed zmianą kolejności
    # pinów w nowszym katalogu. Indeks pozostaje wygodnym cache dla widoku.
    start_pin_number: str | None = None
    end_pin_number: str | None = None

@dataclass
class Annotation:
    text: str
    x: float
    y: float
    id: str = field(default_factory=new_id)
    font_size: int = 12

@dataclass
class Sheet:
    name: str = "Sheet 1"
    id: str = field(default_factory=new_id)
    components: list[ComponentInstance] = field(default_factory=list)
    wires: list[Wire] = field(default_factory=list)
    paper_size: str = "A4"
    orientation: str = "landscape"
    # Norma rysunkowa przypisana do konkretnego arkusza.  Dzięki temu można
    # zmienić ją w locie bez zmiany ustawień domyślnych nowych projektów.
    standard: str = "EN"
    comments: list[Annotation] = field(default_factory=list)

    def dimensions_mm(self) -> tuple[float, float]:
        short, long = PAPER_SIZES_MM.get(self.paper_size, PAPER_SIZES_MM["A4"])
        return (long, short) if self.orientation == "landscape" else (short, long)

def _read_dataclass(cls, value: dict):
    """Dane dokumentu nigdy nie są interpretowane jako instrukcje/kod."""
    if not isinstance(value, dict):
        raise ValueError("Invalid ELS object / Niepoprawny obiekt ELS")
    allowed = {f.name for f in fields(cls)}
    try:
        return cls(**{k: v for k, v in value.items() if k in allowed})
    except TypeError as error:
        raise ValueError("Incomplete ELS object / Niekompletny obiekt ELS") from error

@dataclass
class Project:
    name: str = "New project"
    format_version: int = FORMAT_VERSION
    sheets: list[Sheet] = field(default_factory=lambda: [Sheet()])
    custom_components: list[dict] = field(default_factory=list)
    reference_counters: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=lambda: {
        "modified_at": datetime.now().astimezone().isoformat(timespec="seconds")})
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return asdict(self)

    def _prefix(self, library_id: str) -> str:
        from app.libraries.built_in import get_definition
        definition = get_definition(library_id, self.custom_components)
        return re.sub(r"\s+", ".", definition.reference_prefix) if definition else "CusEle"

    def allocate_reference(self, library_id: str) -> str:
        """Minimum trzy cyfry, po 999 naturalnie następuje 1000."""
        prefix = self._prefix(library_id)
        existing = {c.reference for s in self.sheets for c in s.components}
        number = self.reference_counters.get(prefix, 0) + 1
        while f"{prefix}{number:03d}" in existing:
            number += 1
        self.reference_counters[prefix] = number
        return f"{prefix}{number:03d}"

    def new_component(self, library_id: str, x: float, y: float) -> ComponentInstance:
        from app.libraries.built_in import get_definition
        definition = get_definition(library_id, self.custom_components)
        if definition is None:
            raise ValueError(f"Unknown component / Nieznany element: {library_id}")
        from app.core.component_defaults import nominal_value
        value,unit=nominal_value(definition)
        return ComponentInstance(library_id, x, y, reference=self.allocate_reference(library_id), value=value,unit=unit)

    def ensure_references(self) -> None:
        """Nadaje oznaczenia starszym plikom, nie zmieniając prawidłowych ID."""
        seen, missing = set(), []
        # Migrate visible references only; UUIDs used by wire anchors stay
        # stable. Merge counter keys to avoid reusing deleted references.
        counters = {}
        for key, value in self.reference_counters.items():
            key = re.sub(r"\s+", ".", key)
            counters[key] = max(counters.get(key, 0), value)
        self.reference_counters = counters
        for sheet in self.sheets:
            for component in sheet.components:
                component.reference = re.sub(r"\s+", ".", component.reference)
                prefix = self._prefix(component.library_id)
                reference = component.reference
                if not reference or reference in seen:
                    missing.append(component)
                    continue
                seen.add(reference)
                match = re.fullmatch(re.escape(prefix) + r"(\d+)", reference)
                if match:
                    self.reference_counters[prefix] = max(self.reference_counters.get(prefix, 0), int(match[1]))
        for component in missing:
            component.reference = self.allocate_reference(component.library_id)

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        if not isinstance(data, dict):
            raise ValueError("Invalid ELS document")
        version = data.get("format_version", 1)
        if type(version) is not int or not 1 <= version <= FORMAT_VERSION:
            raise ValueError("Unsupported ELS version / Nieobsługiwana wersja ELS")
        raw_sheets = data.get("sheets", [])
        if not isinstance(raw_sheets, list) or len(raw_sheets) > 200:
            raise ValueError("Invalid sheet list")
        sheets, ids = [], set()
        for raw in raw_sheets:
            if not isinstance(raw, dict):
                raise ValueError("Invalid sheet")
            sheet = _read_dataclass(Sheet, {k: v for k, v in raw.items() if k not in {"components", "wires", "comments"}})
            if not isinstance(sheet.id, str) or not sheet.id or sheet.id in ids or not isinstance(sheet.name, str):
                raise ValueError("Invalid sheet ID/name")
            ids.add(sheet.id)
            if sheet.paper_size not in PAPER_SIZES_MM or sheet.orientation not in ("portrait", "landscape"):
                raise ValueError("Invalid sheet size / Niepoprawny format arkusza")
            if sheet.standard not in {"EN", "PN", "ISO", "IEEE/ANSI"}:
                sheet.standard = "EN"
            for key, kind in (("components", ComponentInstance), ("wires", Wire), ("comments", Annotation)):
                objects = raw.get(key, [])
                if not isinstance(objects, list) or len(objects) > 20000:
                    raise ValueError("Too many document objects")
                result = []
                for obj in objects:
                    item = _read_dataclass(kind, obj)
                    if not isinstance(item.id, str) or not item.id or item.id in ids:
                        raise ValueError("Duplicate/invalid object ID")
                    ids.add(item.id)
                    coordinates = ("x", "y") if kind != Wire else ("start_x", "start_y", "end_x", "end_y")
                    for key_coord in coordinates:
                        value = getattr(item, key_coord)
                        if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1000000:
                            raise ValueError("Invalid coordinate")
                    if kind == ComponentInstance:
                        if not isinstance(item.library_id, str) or not isinstance(item.properties, dict):
                            raise ValueError("Invalid component")
                        if any(not isinstance(getattr(item, attr), str) for attr in ("reference", "display_name", "value", "unit")):
                            raise ValueError("Invalid component labels")
                        if type(item.show_name) is not bool or type(item.show_value) is not bool:
                            raise ValueError("Invalid label visibility")
                        item.rotation = int(item.rotation) % 360
                        if item.rotation % 90:
                            raise ValueError("Unsupported rotation")
                        if not item.value:
                            item.value = str(item.properties.get("value", ""))
                    if kind == Wire:
                        if not isinstance(item.points, list) or len(item.points) > 10000:
                            raise ValueError("Invalid wire points")
                        for point in item.points:
                            if not isinstance(point, list) or len(point) != 2 or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in point):
                                raise ValueError("Invalid wire point")
                        for pin in (item.start_pin_index, item.end_pin_index):
                            if pin is not None and (type(pin) is not int or pin < 0):
                                raise ValueError("Invalid pin index")
                        for attr in ("start_component_id", "end_component_id", "start_junction_id", "end_junction_id", "start_pin_number", "end_pin_number"):
                            value = getattr(item, attr)
                            if value is not None and not isinstance(value, str):
                                raise ValueError("Invalid connection identifier")
                    if kind == Annotation:
                        item.font_size = max(6, min(72, int(item.font_size)))
                        item.text = str(item.text)[:20000]
                    result.append(item)
                setattr(sheet, key, result)
            sheets.append(sheet)
        custom, counters = data.get("custom_components", []), data.get("reference_counters", {})
        if not isinstance(custom, list) or not isinstance(counters, dict):
            raise ValueError("Invalid project library/counters")
        if any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in counters.items()):
            raise ValueError("Invalid reference counter")
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()):
            raise ValueError("Invalid metadata")
        if len(custom) > 2000 or any(not isinstance(entry, dict) for entry in custom):
            raise ValueError("Invalid custom library")
        from app.libraries.built_in import ITEM_BY_ID, validate_custom_definition
        custom_ids = set()
        validated_custom = []
        for entry in custom:
            entry = validate_custom_definition(entry)
            if entry["id"] in custom_ids or entry["id"] in ITEM_BY_ID:
                raise ValueError("Duplicate custom component ID")
            custom_ids.add(entry["id"])
            validated_custom.append(entry)
        project_id = data.get("id")
        if project_id is None:
            # Legacy documents have stable sheet UUIDs, even when titles match.
            # Derivation keeps their identity stable before the first migrated save.
            project_id = str(uuid5(NAMESPACE_URL, "electroschem:legacy-project:" +
                                  ":".join(sorted(sheet.id for sheet in sheets)))) if sheets else new_id()
        try:
            if not isinstance(project_id, str): raise ValueError("Invalid project ID")
            project_id = str(UUID(project_id))
        except ValueError as error:
            raise ValueError("Invalid project ID") from error
        result = cls(name=str(data.get("name", "New project")), sheets=sheets or [Sheet()],
                     custom_components=validated_custom, reference_counters=counters,
                     metadata=dict(metadata), id=project_id)
        result.ensure_references()
        result._resolve_pin_links(version)
        return result

    def _resolve_pin_links(self, old_version: int) -> None:
        """Nie zgadujemy VCC/GND na podstawie dawnych dwóch atrap pinów.

        Przy migracji wielopinowy symbol zachowuje przewody i ich końce, lecz
        wymaga jawnego podpięcia do nowego, opisanego pinu. Oryginalne powiązanie
        zapisujemy w metadanych; użytkownik nie traci ani geometrii, ani śladu
        połączenia. Proste dwukońcówkowe symbole zachowują połączenia.
        """
        from app.libraries.built_in import get_definition
        detached = []
        for sheet in self.sheets:
            components = {c.id: c for c in sheet.components}
            for wire in sheet.wires:
                for side in ("start", "end"):
                    component_id = getattr(wire, side+"_component_id")
                    index = getattr(wire, side+"_pin_index")
                    if component_id is None:
                        setattr(wire, side+"_pin_index", None)
                        setattr(wire, side+"_pin_number", None)
                        continue
                    component = components.get(component_id)
                    definition = get_definition(component.library_id, self.custom_components) if component else None
                    pins = definition.pins if definition else ()
                    number = getattr(wire, side+"_pin_number")
                    if old_version >= 3 and number is not None:
                        index = next((i for i, p in enumerate(pins) if p.number == number), None)
                    safe_legacy = (len(pins) == 2 and pins[0].x == -40 and pins[0].y == 0 and
                                   pins[1].x == 40 and pins[1].y == 0)
                    if index is None or index >= len(pins) or (old_version < 3 and not safe_legacy):
                        detached.append({"wire": wire.id, "end": side, "component": component_id, "old_pin_index": index})
                        setattr(wire, side+"_component_id", None)
                        setattr(wire, side+"_pin_index", None)
                        setattr(wire, side+"_pin_number", None)
                    else:
                        setattr(wire, side+"_pin_index", index)
                        setattr(wire, side+"_pin_number", pins[index].number)
        if detached:
            self.metadata["migration_detached_pins"] = json.dumps(detached, ensure_ascii=False)
            self.metadata["migration_notice"] = (f"{len(detached)} legacy or unavailable pin links require reconnection; wire geometry was retained. / "
                                                f"{len(detached)} dawnych lub niedostępnych przypisań pinów wymaga ponownego podpięcia; zachowano geometrię przewodów.")
