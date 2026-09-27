"""Regresje formatu ELS, czytelnych ID i jednostek — bez uruchamiania GUI."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from app.core.models import Annotation, Project, Sheet, Wire
from app.core.project_file import load_project, save_project
from app.core.units import parse_value
from app.libraries.built_in import BUILT_IN_ITEMS


def library_id(name):
    return next(item.id for item in BUILT_IN_ITEMS if item.name == name)


class ModelTests(unittest.TestCase):
    def test_counter_is_project_wide_and_does_not_wrap_or_reuse(self):
        project = Project(sheets=[Sheet(), Sheet()])
        resistor = library_id("Rezystor")
        first = project.new_component(resistor, 100, 100)
        project.sheets[0].components.append(first)
        second = project.new_component(resistor, 100, 100)
        project.sheets[1].components.append(second)
        self.assertEqual((first.reference, second.reference), ("Res001", "Res002"))
        project.sheets[1].components.clear()
        self.assertEqual(project.new_component(resistor, 0, 0).reference, "Res003")
        led = library_id("Dioda LED 3mm")
        project.reference_counters["LED"] = 999
        self.assertEqual(project.new_component(led, 0, 0).reference, "LED1000")

    def test_units_are_idempotent_and_si_case_sensitive(self):
        for text, unit, expected in [
            ("300", "Ω", ("300", "Ω")), ("1k", "Ω", ("1", "kΩ")),
            ("1", "kΩ", ("1", "kΩ")), ("2m", "kΩ", ("2", "mΩ")),
            ("4k7", "Ω", ("4.7", "kΩ")), ("4R7", "kΩ", ("4.7", "Ω")),
            ("100nF", "F", ("100", "nF")), ("1,5uF", "F", ("1.5", "µF")),
            ("2MΩ", "Ω", ("2", "MΩ")), ("2mΩ", "Ω", ("2", "mΩ")),
        ]:
            with self.subTest(text=text, unit=unit):
                self.assertEqual(parse_value(text, unit), expected)
        with self.assertRaises(ValueError):
            parse_value("not a number", "Ω")

    def test_els_roundtrip_retains_models_counters_and_uuid_links(self):
        project = Project(name="Roundtrip")
        c = project.new_component(library_id("Rezystor"), 100, 100)
        c.display_name, c.value, c.unit = "R test", "1", "kΩ"
        c.show_name = False
        sheet = project.sheets[0]
        sheet.components.append(c)
        sheet.comments.append(Annotation("Arial text", 100, 200, font_size=12))
        sheet.wires.append(Wire(60, 100, 20, 100, start_component_id=c.id,
                                start_pin_index=0, start_pin_number="1"))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/"test.els"
            save_project(destination, project)
            restored = load_project(destination)
        self.assertEqual(restored.to_dict(), project.to_dict())

    def test_legacy_unknown_pin_mapping_is_not_silently_vcc(self):
        project = Project()
        component = project.new_component(library_id("Czujnik Odległości HC-SR04"), 100, 100)
        project.sheets[0].components.append(component)
        wire = Wire(61, 100, 0, 100, start_component_id=component.id, start_pin_index=0)
        project.sheets[0].wires.append(wire)
        raw = project.to_dict()
        raw["format_version"] = 2
        restored = Project.from_dict(raw)
        migrated = restored.sheets[0].wires[0]
        self.assertIsNone(migrated.start_component_id)
        self.assertEqual((migrated.start_x, migrated.start_y), (61, 100))
        self.assertIn("migration_notice", restored.metadata)
        self.assertEqual(json.loads(restored.metadata["migration_detached_pins"])[0]["component"], component.id)

    def test_pin_number_takes_priority_over_stale_index(self):
        project = Project()
        c = project.new_component(library_id("Rezystor"), 100, 100)
        project.sheets[0].components.append(c)
        project.sheets[0].wires.append(Wire(60, 100, 0, 100, start_component_id=c.id,
                                             start_pin_index=1, start_pin_number="1"))
        restored = Project.from_dict(project.to_dict())
        self.assertEqual(restored.sheets[0].wires[0].start_pin_index, 0)

    def test_malformed_document_and_future_package_are_rejected(self):
        raw = Project().to_dict()
        raw["sheets"].append(dict(raw["sheets"][0]))
        with self.assertRaises(ValueError):
            Project.from_dict(raw)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"bad.els"
            with ZipFile(path, "w") as archive:
                archive.writestr("manifest.json", json.dumps({"application":"ElektroSchem", "format_version":999}))
                archive.writestr("project.json", json.dumps(Project().to_dict()))
            with self.assertRaises(ValueError):
                load_project(path)


if __name__ == "__main__":
    unittest.main()
