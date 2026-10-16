import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import unittest

from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.assets import make_asset
from app.core.models import Project,Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.paint_case_editor import PaintAssetCaseEditor
from test_simulation_alpha2 import Bench


APP=QApplication.instance() or QApplication([])


class CaseEditorShortcutTests(unittest.TestCase):
    def definition(self):
        bench=Bench(); resistor=bench.add("Rezystor","330","Ω")
        resistor.x,resistor.y=300,300
        project=Project(sheets=[Sheet(components=bench.components)])
        definition=make_asset(project,project.sheets[0],"Shortcut case",True,{resistor.id})
        definition["asset"]["case"]={"shapes":[{"kind":"rect","rect":[-80,-40,160,80]}]}
        return definition

    def test_ctrl_z_is_confined_across_ten_editor_openings(self):
        window=MainWindow(AppSettings(),start_setup=False)
        dialog=None
        try:
            window.show()
            original_name=window.project.name
            window.project.name="Document state before editor undo"
            window.record_history()
            window.project.name="Document state before editor"
            window.record_history()
            window.undo()
            document_before=window.project.to_dict()
            self.assertTrue(window.undo_action.isEnabled())
            self.assertTrue(window.redo_action.isEnabled())
            original_shortcuts=window.undo_action.shortcuts()
            original_redo_shortcuts=window.redo_action.shortcuts()
            for iteration in range(10):
                with self.subTest(dialog_opening=iteration+1):
                    dialog=PaintAssetCaseEditor(self.definition(),AppSettings(),window)
                    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                    dialog.show(); APP.processEvents()
                    self.assertIs(APP.activeModalWidget(),dialog)
                    self.assertFalse(window.undo_action.isEnabled())
                    self.assertEqual(window.undo_action.shortcuts(),[])

                    dialog.tool.setCurrentIndex(dialog.tool.findData("pencil"))
                    starts=[]
                    for edit_index in range(3):
                        view=dialog.view
                        start=QPointF(-60,-20+edit_index*10)
                        end=QPointF(60,-10+edit_index*10)
                        baseline=len(dialog.shapes)
                        QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=view.mapFromScene(start))
                        QTest.mouseMove(view.viewport(),view.mapFromScene(end))
                        QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=view.mapFromScene(end))
                        APP.processEvents()
                        self.assertEqual(len(dialog.shapes),baseline+1)
                        starts.append(tuple(dialog.shapes[-1]["points"][0]))
                    self.assertEqual(len(set(starts)),3)

                    for undo_index in range(4):
                        before_undo=len(dialog.shapes)
                        expected=before_undo-1 if undo_index<3 else before_undo
                        dialog.view.setFocus(); APP.processEvents()
                        window._refresh_title()  # MainWindow may refresh/re-enable its action.
                        self.assertTrue(window.undo_action.isEnabled())
                        self.assertEqual(window.undo_action.shortcuts(),[])
                        self.assertEqual(window.redo_action.shortcuts(),[])
                        QTest.keyClick(dialog.view.viewport(),Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
                        APP.processEvents()
                        self.assertEqual(len(dialog.shapes),expected)
                        self.assertEqual(window.project.to_dict(),document_before)

                    dialog.reject(); APP.processEvents()
                    self.assertTrue(window.undo_action.isEnabled())
                    self.assertEqual(window.undo_action.shortcuts(),original_shortcuts)
                    self.assertTrue(window.redo_action.isEnabled())
                    self.assertEqual(window.redo_action.shortcuts(),original_redo_shortcuts)
                    dialog.deleteLater(); dialog=None; APP.processEvents()
            window.activateWindow(); window._current_view().setFocus(); APP.processEvents()
            QTest.keyClick(window._current_view().viewport(),Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
            APP.processEvents()
            self.assertEqual(window.project.name,original_name)
            QTest.keyClick(window._current_view().viewport(),Qt.Key.Key_Y,Qt.KeyboardModifier.ControlModifier)
            APP.processEvents()
            self.assertEqual(window.project.name,"Document state before editor undo")
            QTest.keyClick(window._current_view().viewport(),Qt.Key.Key_Y,Qt.KeyboardModifier.ControlModifier)
            APP.processEvents()
            self.assertEqual(window.project.name,"Document state before editor")
            self.assertEqual(len(window.project.sheets),1)
            QTest.keyClick(window._current_view().viewport(),Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
            APP.processEvents()
            self.assertEqual(window.project.name,"Document state before editor undo")
            self.assertEqual(len(window.project.sheets),1)
        finally:
            if dialog is not None:
                dialog.close(); dialog.deleteLater()
            window._saved_state=window.project.to_dict()
            window.close(); window.deleteLater(); APP.processEvents()


if __name__=="__main__":
    unittest.main()
