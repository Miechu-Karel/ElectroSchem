"""Regresje granic między dialogami, biblioteką, modelem i odpowiedziami AI."""
from copy import deepcopy
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QDialog
from app.core.models import Project
from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS, get_definition
from app.services.proposals import apply_proposal
from app.ui.component_dialogs import CustomComponentDialog
from app.ui.properties_dialog import ComponentPropertiesDialog

APP = QApplication.instance() or QApplication([])
RES = next(i for i in BUILT_IN_ITEMS if i.name == "Rezystor")


class IntegrationTests(unittest.TestCase):
    def test_property_value_normalization_does_not_lose_kilo_on_accept(self):
        component = Project().new_component(RES.id, 100, 100)
        dialog = ComponentPropertiesDialog(component, RES)
        dialog.value.setText("1k")
        self.assertTrue(dialog.normalize_value())
        self.assertEqual(dialog.unit.text(), "kΩ")
        dialog.accept()
        self.assertEqual(dialog.values["value"], "1")
        self.assertEqual(dialog.values["unit"], "kΩ")
        # Formularz nie zapisuje zmian w modelu przed zatwierdzeniem przez okno.
        self.assertEqual(component.value, "")
        dialog.deleteLater()

    def test_property_cancel_keeps_data_and_visibility(self):
        component = Project().new_component(RES.id, 100, 100)
        before = deepcopy(component)
        dialog = ComponentPropertiesDialog(component, RES, "pl")
        dialog.name.setPlainText("Custom resistor\nSecond line")
        dialog.show_name.setChecked(False)
        dialog.reject()
        self.assertEqual(component, before)
        dialog.deleteLater()

    def test_manual_custom_can_be_created_placed_and_roundtripped(self):
        dialog = CustomComponentDialog("en")
        dialog.name.setText("My sensor")
        dialog.english_name.setText("Test Sensor")
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        project = Project(custom_components=[dialog.definition])
        definition = get_definition(dialog.definition["id"], project.custom_components)
        self.assertEqual(definition.reference_prefix, dialog.definition["reference_prefix"])
        self.assertEqual(len(definition.pins), 3)
        component = project.new_component(definition.id, 300, 300)
        project.sheets[0].components.append(component)
        restored = Project.from_dict(project.to_dict())
        self.assertEqual(restored.to_dict(), project.to_dict())
        dialog.deleteLater()

    def test_ai_proposal_is_atomic_and_connects_existing_rotated_pin(self):
        project = Project()
        old = project.new_component(RES.id, 300, 300)
        old.rotation = 90
        project.sheets[0].components.append(old)
        before = deepcopy(project.to_dict())
        payload = {"components": [{"key": "new", "library_id": RES.id, "x": 500, "y": 300}],
                   "custom_components": [], "wires": [{"from": old.id, "to": "new", "from_pin": 0, "to_pin": 1}]}
        after = apply_proposal(project, 0, payload)
        self.assertEqual(project.to_dict(), before)
        self.assertEqual(len(after.sheets[0].components), 2)
        wire = after.sheets[0].wires[0]
        self.assertEqual((wire.start_x, wire.start_y), (300, 260))
        self.assertEqual(wire.start_pin_number, "1")
        self.assertEqual(wire.end_pin_number, "2")
        payload["wires"][0]["to_pin"] = 70
        with self.assertRaises(ValueError):
            apply_proposal(project, 0, payload)
        self.assertEqual(project.to_dict(), before)

    def test_ai_custom_keeps_prefix_and_behavior_as_inert_text(self):
        project = Project()
        custom = {"id": "custom-example", "name": "Przykład", "name_en": "Example",
                  "reference_prefix": "CusExa", "width": 120, "height": 80,
                  "pins": [{"number": "1", "name": "VCC", "x": -60, "y": 0},
                           {"number": "2", "name": "GND", "x": 60, "y": 0}],
                  "behavior": "Plain documentation; do not execute."}
        payload = {"custom_components": [custom], "wires": [],
                   "components": [{"key": "u1", "library_id": "custom-example", "x": 200, "y": 200}]}
        result = apply_proposal(project, 0, payload)
        self.assertEqual(result.sheets[0].components[0].reference, "CusExa001")
        self.assertEqual(result.custom_components[0]["behavior"], custom["behavior"])
        self.assertFalse(project.custom_components)

    def test_invalid_ai_library_or_off_sheet_position_never_partially_applies(self):
        for library_id, x in [("missing", 200), (RES.id, -400)]:
            project = Project()
            payload = {"custom_components": [], "wires": [], "components": [
                {"key": "a", "library_id": RES.id, "x": 200, "y": 200},
                {"key": "bad", "library_id": library_id, "x": x, "y": 500}]}
            with self.assertRaises(ValueError):
                apply_proposal(project, 0, payload)
            self.assertFalse(project.sheets[0].components)
            self.assertFalse(project.reference_counters)
