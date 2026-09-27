"""Podgląd, zatwierdzanie i ponowienie bez sieci i bez prawdziwego klucza."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import test_rc11 as fixtures
from app.services.proposals import apply_proposal


@unittest.skip("Historyczny panel AI wycofany w rc14; blokady sprawdza test_rc14")
class Rc13Tests(unittest.TestCase):
    setUp = fixtures.PanelTests.setUp
    tearDown = fixtures.PanelTests.tearDown
    send_fake = fixtures.PanelTests.send_fake
    proposal = fixtures.PanelTests.proposal

    def test_preview_then_real_button_click_then_undo(self):
        self.send_fake()
        original = deepcopy(self.window.project.to_dict())
        self.panel._completed(self.proposal())
        fixtures.APP.processEvents()
        self.assertFalse(self.panel.preview.image.isNull())
        self.assertEqual(self.window.project.to_dict(), original)
        self.assertTrue(self.panel.apply_button.isEnabled())
        preview = self.panel._candidate.to_dict()
        QTest.mouseClick(self.panel.apply_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.project.to_dict()["sheets"], preview["sheets"])
        self.assertEqual(len(self.window.project.sheets[0].components), 1)
        self.assertFalse(self.panel.regenerate_button.isEnabled())
        self.window.undo()
        self.assertEqual(len(self.window.project.sheets[0].components), 0)

    def test_invalid_semantic_proposal_has_explanation_before_apply(self):
        self.send_fake()
        proposal = self.proposal()
        proposal["components"][0]["library_id"] = "unknown-part"
        self.panel._completed(proposal)
        self.assertIsNone(self.panel._candidate)
        self.assertFalse(self.panel.apply_button.isEnabled())
        self.assertTrue(self.panel.regenerate_button.isEnabled())
        self.assertIn("Nie można", self.panel.status.text())
        self.assertEqual(len(self.window.project.sheets[0].components), 0)

    def test_regenerate_replaces_history_and_preserves_draft(self):
        self.send_fake("Dodaj rezystor")
        self.panel._completed(self.proposal())
        self.panel.prompt.setPlainText("Szkic następnego pytania")
        with patch.object(self.panel.client, "start") as start:
            QTest.mouseClick(self.panel.regenerate_button, Qt.MouseButton.LeftButton)
            body = json.loads(start.call_args.args[2])
        self.assertEqual(len(body["contents"]), 1)
        self.assertIn("Dodaj rezystor", body["contents"][0]["parts"][0]["text"])
        self.assertEqual(self.panel.prompt.toPlainText(), "Szkic następnego pytania")
        self.assertEqual(self.panel.history, [])
        self.assertIsNone(self.panel._candidate)
        self.assertFalse(self.panel.regenerate_button.isEnabled())
        self.panel._completed(self.proposal())
        self.assertEqual(len(self.panel.history), 2)

    def test_regenerate_works_after_error_and_ask(self):
        self.send_fake("Wyjaśnij rezystor", "ask")
        self.panel._failed("http_503")
        self.assertTrue(self.panel.regenerate_button.isEnabled())
        with patch.object(self.panel.client, "start") as start:
            self.panel.regenerate()
        self.assertEqual(json.loads(start.call_args.args[2])["generationConfig"]["responseMimeType"], "text/plain")
        self.panel._completed(fixtures.empty_proposal())
        self.assertTrue(self.panel.regenerate_button.isEnabled())
        self.assertTrue(self.panel.proposal_card.isHidden())

    def test_disable_ai_hides_dock_and_blocks_action(self):
        self.window.settings.api_key = ""
        self.window._translate_ui()
        self.assertFalse(self.window.ai_action.isEnabled())
        self.assertFalse(self.window.datasheet_action.isEnabled())
        self.assertTrue(self.window.ai_dock.isHidden())
        self.window.show_ai()
        self.assertTrue(self.window.ai_dock.isHidden())
        self.window.settings.api_key = "dummy-key"
        self.window._translate_ui()
        self.assertTrue(self.window.ai_action.isEnabled())
        self.window.show_ai()
        self.assertFalse(self.window.ai_dock.isHidden())

    def test_legal_lower_left_area_is_accepted(self):
        proposal = self.proposal()
        proposal["components"][0].update(x=200, y=740)
        candidate = apply_proposal(self.window.project, 0, proposal)
        self.assertEqual(candidate.sheets[0].components[0].y, 740)
        proposal["components"][0].update(x=900, y=740)
        with self.assertRaises(ValueError):
            apply_proposal(self.window.project, 0, proposal)
