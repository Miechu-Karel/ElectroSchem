"""Regresje rc10. Sieć jest pozorowana; żaden test nie używa klucza użytkownika."""
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from copy import deepcopy

from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox

from app.core.models import Project, Sheet, Wire, Annotation
from app.core.settings import AppSettings
from app.canvas.schematic_view import SchematicView
from app.libraries.built_in import BUILT_IN_ITEMS
from app.services.clipboard import encode_selection, decode_selection, prepare_paste, MIME_TYPE
from app.services.gemini import GeminiClient, request_body, available_chat_models
from app.ui.ai_dialog import AiDialog
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from test_ai_settings import FakeReply, empty_proposal, custom_definition

APP = QApplication.instance() or QApplication([])
RES = next(d for d in BUILT_IN_ITEMS if d.name == "Rezystor")


class ClipboardAndGroupTests(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.sheet = self.project.sheets[0]
        self.a = self.project.new_component(RES.id, 200, 200)
        self.b = self.project.new_component(RES.id, 440, 200)
        self.sheet.components = [self.a, self.b]
        self.wire = Wire(240, 200, 400, 200, start_component_id=self.a.id, start_pin_index=1,
                         start_pin_number=RES.pins[1].number,
                         end_component_id=self.b.id, end_pin_index=0, end_pin_number=RES.pins[0].number)
        self.sheet.wires = [self.wire]
        self.sheet.comments = [Annotation("test", 200, 120)]
        self.view = SchematicView(project=self.project, settings=AppSettings(), sheet=self.sheet)
        self.view.resize(1000, 750)
        self.view.show()
        APP.processEvents()

    def tearDown(self):
        self.view.close()
        self.view.deleteLater()
        APP.processEvents()

    def select(self, *objects):
        self.view.scene.clearSelection()
        ids = {o.id for o in objects}
        for item in self.view.scene.items():
            if item.data(1) in ids:
                item.setSelected(True)

    def test_duplicate_keeps_internal_links_new_ids_and_does_not_touch_clipboard(self):
        QApplication.clipboard().setText("keep me")
        self.select(self.a, self.b, self.wire, self.sheet.comments[0])
        self.assertTrue(self.view.paste_selection(duplicate=True))
        self.assertEqual(QApplication.clipboard().text(), "keep me")
        self.assertEqual(len(self.sheet.components), 4)
        first, second = self.sheet.components[2:]
        wire = self.sheet.wires[1]
        self.assertEqual((first.reference, second.reference), ("Res003", "Res004"))
        self.assertEqual((wire.start_component_id, wire.end_component_id), (first.id, second.id))
        self.assertEqual((first.x, first.y, wire.start_x, wire.start_y), (220, 220, 260, 220))
        self.assertEqual(len(self.view.scene.selectedItems()), 4)
        self.assertEqual(len(self.sheet.comments), 2)

    def test_partial_copy_detaches_external_anchor_and_pastes_to_target(self):
        self.select(self.a, self.wire)
        self.assertTrue(self.view.copy_selected())
        self.assertTrue(QApplication.clipboard().mimeData().hasFormat(MIME_TYPE))
        self.view.paste_selection(target=QPointF(220, 320))
        clone = self.sheet.wires[-1]
        self.assertEqual(clone.start_component_id, self.sheet.components[-1].id)
        self.assertIsNone(clone.end_component_id)
        self.assertEqual((clone.end_x, clone.end_y), (420, 320))

    def test_failed_paste_is_atomic_and_cut_only_deletes_selected(self):
        self.select(self.a, self.wire)
        self.view.copy_selected()
        snapshot = deepcopy(self.project.to_dict())
        with self.assertRaises(ValueError):
            self.view.paste_selection(target=QPointF(-100, -100))
        self.assertEqual(snapshot, self.project.to_dict())
        self.view.cut_selected()
        self.assertEqual(self.sheet.components, [self.b])
        self.assertEqual(self.sheet.wires, [])

    def test_custom_definition_conflict_is_remapped_without_overwrite(self):
        definition = custom_definition()
        source = Project(custom_components=[definition])
        component = source.new_component(definition["id"], 200, 200)
        source.sheets[0].components.append(component)
        data = encode_selection(source, source.sheets[0], {component.id})
        destination = Project(custom_components=[dict(definition, name="Different")])
        staged, additions = prepare_paste(destination, decode_selection(data), 20, 20)
        self.assertEqual(len(staged.custom_components), 2)
        self.assertEqual(staged.custom_components[0]["name"], "Different")
        self.assertNotEqual(additions.components[0].library_id, definition["id"])
        self.assertEqual(len(destination.custom_components), 1)

    def test_free_junctions_move_and_unselected_branches_stretch(self):
        self.wire.end_component_id = self.wire.end_pin_index = self.wire.end_pin_number = None
        self.wire.end_junction_id = "junction"
        branch = Wire(400, 200, 500, 300, start_junction_id="junction")
        self.sheet.wires.append(branch)
        self.view.load_sheet(self.sheet)
        self.select(self.a, self.wire)
        self.view._begin_selection_group(QPointF(200, 200))
        self.assertTrue(self.view._move_selection_group(QPointF(40, 60)))
        self.assertEqual((self.a.x, self.a.y), (240, 260))
        self.assertEqual((self.wire.end_x, self.wire.end_y), (440, 260))
        self.assertEqual((branch.start_x, branch.start_y), (440, 260))
        self.assertEqual((branch.end_x, branch.end_y), (500, 300))
        self.assertTrue(self.view._move_selection_group(QPointF()))
        self.assertEqual((self.wire.end_x, self.wire.end_y), (400, 200))

    def test_group_preserves_unselected_pin_anchor_and_rejects_margin(self):
        self.select(self.a, self.wire)
        self.view._begin_selection_group(QPointF())
        self.assertTrue(self.view._move_selection_group(QPointF(20, 20)))
        self.assertEqual((self.wire.start_x, self.wire.start_y), (260, 220))
        self.assertEqual((self.wire.end_x, self.wire.end_y), (400, 200))
        snapshot = deepcopy(self.project.to_dict())
        self.assertFalse(self.view._move_selection_group(QPointF(-1000, -1000)))
        self.assertEqual(snapshot, self.project.to_dict())

    def test_mouse_drag_moves_free_wire_group_on_grid(self):
        self.wire.start_component_id = self.wire.end_component_id = None
        self.view.load_sheet(self.sheet)
        self.select(self.a, self.wire)
        start = self.view.mapFromScene(QPointF(200, 200))
        end = self.view.mapFromScene(QPointF(240, 240))
        changed = []
        self.view.on_change = lambda: changed.append(True)
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(self.view.viewport(), end)
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual((self.wire.end_x, self.wire.end_y), (440, 240))
        self.assertEqual((self.a.x, self.a.y), (240, 240))
        self.assertEqual(len(changed), 1)

    def test_wire_only_selection_moves_both_free_ends(self):
        self.sheet.components.clear()
        self.wire.start_component_id = self.wire.end_component_id = None
        second = Wire(400, 200, 440, 300)
        self.sheet.wires.append(second)
        self.view.load_sheet(self.sheet)
        self.select(self.wire, second)
        self.view._begin_selection_group(QPointF())
        self.view._move_selection_group(QPointF(20, 40))
        self.assertEqual((self.wire.start_x, self.wire.start_y, self.wire.end_x, self.wire.end_y), (260, 240, 420, 240))
        self.assertEqual((second.start_x, second.start_y), (420, 240))

    def test_bad_clipboard_endpoint_is_rejected(self):
        self.select(self.wire)
        data = encode_selection(self.project, self.sheet, {self.wire.id})
        payload = json.loads(data)
        payload["project"]["sheets"][0]["wires"][0]["end_x"] = -1000
        with self.assertRaises(ValueError):
            decode_selection(json.dumps(payload).encode())


class AiRc10Tests(unittest.TestCase):
    def model(self, name, **extra):
        return dict(name="models/" + name, supportedGenerationMethods=["generateContent"], **extra)

    def test_automatic_model_filters_and_ranks(self):
        models = [self.model("gemini-2.5-flash"), self.model("gemini-3.8-flash"),
                  self.model("gemini-9.0-flash-preview"), self.model("gemini-3.8-flash-image"),
                  self.model("gemini-3.8-pro"), self.model("gemini-3.8-flash-tts")]
        available = available_chat_models(models)
        self.assertEqual(available[0]["name"], "models/gemini-3.8-flash")
        self.assertEqual(len(available), 3)

    def test_discovery_pagination_and_generation_use_header_and_limit(self):
        first = FakeReply(body=json.dumps({"models": [], "nextPageToken": "next"}).encode())
        second = FakeReply(body=json.dumps({"models": [self.model("gemini-3.8-flash", outputTokenLimit=8192)]}).encode())
        result = empty_proposal()
        last = FakeReply(body=json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(result)}]}}]}).encode())
        client = GeminiClient()
        completed = []
        client.completed.connect(completed.append)
        with patch.object(client.manager, "get", side_effect=[first, second]) as get, patch.object(client.manager, "post", return_value=last) as post:
            client.start("dummy-key", "auto", request_body("Hello", {}))
            first.finished.emit()
            self.assertIn("pageToken=next", get.call_args.args[0].url().toString())
            second.finished.emit()
            request, body = post.call_args.args
            self.assertIn("gemini-3.8-flash:generateContent", request.url().toString())
            self.assertNotIn("dummy-key", request.url().toString())
            self.assertEqual(json.loads(bytes(body))["generationConfig"]["maxOutputTokens"], 8192)
            last.finished.emit()
        self.assertEqual(completed, [result])
        self.assertEqual(client._api_key, "")

    def test_discovery_errors_cancel_and_no_model(self):
        for status, body, expected in ((403, b"secret", "http_403"), (200, b'{"models":[]}', "no_model")):
            client, failed = GeminiClient(), []
            client.failed.connect(failed.append)
            reply = FakeReply(status=status, body=body)
            with patch.object(client.manager, "get", return_value=reply), patch.object(client.manager, "post") as post:
                client.start("dummy-key", "auto", request_body("hi", {}))
                reply.finished.emit()
                self.assertEqual(failed, [expected])
                post.assert_not_called()
        reply = FakeReply()
        client, cancelled = GeminiClient(), []
        client.cancelled.connect(lambda: cancelled.append(True))
        with patch.object(client.manager, "get", return_value=reply):
            client.start("dummy-key", "auto", request_body("hi", {}))
            client.cancel()
        self.assertEqual(cancelled, [True])
        self.assertIsNone(client.reply)

    def test_unavailable_model_falls_back_once_but_never_on_quota_errors(self):
        for status, expected_posts in ((503, 3), (404, 2), (429, 1), (403, 1), (400, 1)):
            listing = FakeReply(body=json.dumps({"models": [
                self.model("gemini-3.8-flash", outputTokenLimit=24000),
                self.model("gemini-2.5-flash", outputTokenLimit=8192)]}).encode())
            first, second, third = FakeReply(status=status), FakeReply(status=status), FakeReply(status=503)
            client, failed = GeminiClient(), []
            client.failed.connect(failed.append)
            with patch.object(client.manager, "get", return_value=listing), patch.object(client.manager, "post", side_effect=[first, second, third]) as post:
                client.start("dummy-key", "auto", request_body("test", {}))
                listing.finished.emit()
                first.finished.emit()
                if expected_posts > 1:
                    self.assertTrue(client.busy)
                    client._run_retry()
                    if status == 503:
                        second.finished.emit()
                        client._run_retry()
                    self.assertEqual(json.loads(bytes(post.call_args.args[1]))["generationConfig"]["maxOutputTokens"], 8192)
                    (third if status == 503 else second).finished.emit()
                    self.assertEqual(failed, [f"http_{503 if status == 503 else 404}"])
                else:
                    self.assertEqual(failed, [f"http_{status}"])
                self.assertEqual(post.call_count, expected_posts)
                self.assertIsNone(client.reply)

    def test_chat_history_and_separate_document_tool(self):
        chat = AiDialog(AppSettings(api_key="dummy-key"), {"sheet": {}}, lambda p: None)
        docs = AiDialog(AppSettings(api_key="dummy-key"), {"library": []}, lambda p: None, documentation=True)
        self.assertTrue(chat.pdf_panel.isHidden())
        self.assertFalse(docs.pdf_panel.isHidden())
        docs._generate()
        self.assertIn("PDF", docs.status.text())
        chat._pending_prompt = "Build something"
        chat._completed(empty_proposal())
        self.assertEqual([turn["role"] for turn in chat.history], ["user", "model"])
        body = json.loads(request_body("Now connect it", {}, history=chat.history))
        self.assertEqual(len(body["contents"]), 3)
        self.assertEqual(docs.history, [])
        proposal = empty_proposal()
        proposal["components"] = [{"key": "r", "library_id": RES.id, "x": 200, "y": 200}]
        docs._completed(proposal)
        self.assertFalse(docs.apply_button.isEnabled())
        chat._reset_chat()
        self.assertFalse(chat.history)
        chat.deleteLater()
        docs.deleteLater()

    def test_send_uses_auto_even_with_stale_saved_model(self):
        dialog = AiDialog(AppSettings(api_key="dummy-key", gemini_model="old-model"), {}, lambda p: None)
        dialog.prompt.setPlainText("Add a resistor")
        with patch("app.ui.ai_dialog.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), patch.object(dialog.client, "start") as start:
            dialog._generate()
            self.assertEqual(start.call_args.args[1], "auto")
        dialog._failed("http_429")
        self.assertTrue(dialog.generate_button.isEnabled())
        self.assertIn("limit", dialog.status.text())
        dialog.deleteLater()

    def test_settings_have_no_required_model_input(self):
        dialog = SettingsDialog(AppSettings(gemini_model="broken/old"))
        self.assertNotIsInstance(dialog.model, QLineEdit)
        dialog._accept()
        self.assertEqual(dialog.result_settings().gemini_model, "broken/old")
        dialog.deleteLater()


class Rc10WindowTests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(AppSettings(), start_setup=False)
        self.window.show()
        self.window.activateWindow()
        self.view = self.window._current_view()
        self.view.setFocus()
        APP.processEvents()

    def tearDown(self):
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_shortcut_duplicate_cut_copy_paste_and_undo(self):
        c = self.window.project.new_component(RES.id, 200, 200)
        self.view._sheet.components.append(c)
        self.view.load_sheet(self.view._sheet)
        self.window.record_history()
        self.view._component_items[c.id].setSelected(True)
        QTest.keyClick(self.view, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(self.view._sheet.components), 2)
        QTest.keyClick(self.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(QApplication.clipboard().mimeData().hasFormat(MIME_TYPE))
        QTest.keyClick(self.view, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(self.view._sheet.components), 1)
        QTest.keyClick(self.view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(self.view._sheet.components), 2)
        self.window.undo()
        self.assertEqual(len(self.window.project.sheets[0].components), 1)
        self.window.redo()
        self.assertEqual(len(self.window.project.sheets[0].components), 2)

    def test_text_clipboard_shortcuts_are_not_stolen(self):
        field = QLineEdit("ordinary text", self.window)
        field.show()
        field.setFocus()
        field.selectAll()
        with patch.object(self.window, "selection_command") as command:
            QTest.keyClick(field, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(QApplication.clipboard().text(), "ordinary text")
            QTest.keyClick(field, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(field.text(), "")
            QTest.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(field.text(), "ordinary text")
            command.assert_not_called()

    @unittest.skip("Wejście do AI wycofane w rc14")
    def test_document_entry_has_no_sheet_context(self):
        self.window.settings.api_key = "dummy-key"
        with patch("app.ui.main_window.AiDialog") as dialog:
            self.window.show_datasheet_ai()
            self.assertTrue(dialog.call_args.kwargs["documentation"])
            self.assertNotIn("sheet", dialog.call_args.args[1])

    def test_inline_text_keeps_native_paste(self):
        self.view._begin_inline_comment(QPointF(200, 200))
        QApplication.clipboard().setText("Comment text")
        with patch.object(self.window, "selection_command") as command:
            QTest.keyClick(self.view.viewport(), Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(self.view._annotation_editor.toPlainText(), "Comment text")
            command.assert_not_called()
        self.view.finish_text_editing()

    def test_copy_to_another_sheet_and_group_undo(self):
        a = self.window.project.new_component(RES.id, 200, 200)
        wire = Wire(300, 300, 400, 300)
        self.view._sheet.components.append(a)
        self.view._sheet.wires.append(wire)
        self.view.load_sheet(self.view._sheet)
        self.window.record_history()
        self.view._component_items[a.id].setSelected(True)
        self.view._wire_items[wire.id].setSelected(True)
        self.view.copy_selected()
        self.view._begin_selection_group(QPointF(200, 200))
        self.view._move_selection_group(QPointF(40, 40))
        self.view._group_drag = None
        self.view._changed()
        self.window.undo()
        self.assertEqual(self.window.project.sheets[0].wires[0].end_x, 400)
        self.window.redo()
        self.assertEqual(self.window.project.sheets[0].wires[0].end_x, 440)
        self.window.add_sheet()
        self.window._current_view().paste_selection(target=QPointF(200, 200))
        new_sheet = self.window.project.sheets[1]
        self.assertEqual(len(new_sheet.components), 1)
        self.assertNotEqual(new_sheet.components[0].id, a.id)
        self.assertEqual(new_sheet.components[0].reference, "Res002")

    @unittest.skip("Wejście do AI wycofane w rc14")
    def test_chat_proposal_apply_and_undo_end_to_end(self):
        self.window.settings.api_key = "dummy-key"
        self.window.show_ai()
        panel = self.window.ai_panel
        panel._snapshot = deepcopy(self.window.project.to_dict())
        panel._sheet_id = self.window.project.sheets[0].id
        panel._pending_prompt = "Add one resistor"
        proposal = empty_proposal()
        proposal["components"] = [{"key": "res", "library_id": RES.id, "x": 200, "y": 200, "value": "1", "unit": "kΩ"}]
        panel._completed(proposal)
        self.assertEqual(len(self.window.project.sheets[0].components), 0)
        self.assertTrue(panel.apply_button.isEnabled())
        panel.apply()
        self.assertEqual(len(self.window.project.sheets[0].components), 1)
        self.window.undo()
        self.assertEqual(len(self.window.project.sheets[0].components), 0)


if __name__ == "__main__":
    unittest.main()
