"""User-visible theme/export preservation and fault-level behaviour."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
from pathlib import Path
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QRectF,QSettings
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from app.core.settings import AppSettings,load_settings,save_settings
from app.core.models import Annotation
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import canvas_colors,apply_theme
from app.ui.effects import fault_effect,FLASH_SECONDS,RING_TAIL_SECONDS
from app.simulation.examples import example

APP=QApplication.instance() or QApplication([])


class Alpha9Tests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language="pl",window_mode="windowed",theme="dark"),start_setup=False)
        self.window.project.sheets=[example("dc")]
        self.window.project.sheets[0].comments=[Annotation("A dark comment",160,320)]
        self.window._rebuild_tabs(); self.window.show(); APP.processEvents()

    def tearDown(self):
        self.window._saved_state=deepcopy(self.window.project.to_dict())
        self.window.close(); self.window.deleteLater(); APP.processEvents()

    def test_dark_canvas_and_light_export_restore_selection_and_model(self):
        view=self.window._current_view(); colours=canvas_colors(self.window.settings)
        original=deepcopy(self.window.project.to_dict())
        item=next(iter(view._component_items.values())); item.setSelected(True)
        self.assertEqual(item.ink_color,colours["ink"])
        self.assertLess(next(iter(view._comment_items.values())).defaultTextColor().lightness(),100)
        image=QImage(1188,840,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.transparent)
        painter=QPainter(image)
        view.render_page(painter,QRectF(0,0,1188,840)); painter.end()
        self.assertGreater(image.pixelColor(903,103).lightness(),240)
        self.assertEqual(item.ink_color,colours["ink"]); self.assertTrue(item.isSelected())
        self.assertEqual(self.window.project.to_dict(),original)
        painter=QPainter(image)
        with patch.object(view.scene,"render",side_effect=RuntimeError("export error")):
            with self.assertRaises(RuntimeError): view.render_page(painter)
        painter.end()
        self.assertEqual(item.ink_color,colours["ink"]); self.assertTrue(item.isSelected()); self.assertFalse(view._exporting)

    def test_settings_apply_theme_without_changing_project(self):
        original=deepcopy(self.window.project.to_dict())
        for theme in ("light","dark"):
            candidate=replace(self.window.settings,theme=theme,fault_effect="medium")
            with patch("app.ui.main_window.SettingsDialog") as dialog,patch("app.ui.main_window.save_settings"):
                dialog.return_value.exec.return_value=QDialog.DialogCode.Accepted
                dialog.return_value.result_settings.return_value=candidate
                self.window.show_settings()
            item=next(iter(self.window._current_view()._component_items.values()))
            self.assertEqual(item.ink_color,canvas_colors(candidate)["ink"])
            self.assertEqual(self.window.project.to_dict(),original)
        settings=SettingsDialog(self.window.settings,self.window)
        self.assertEqual(settings.theme.currentData(),"dark"); self.assertEqual(settings.fault_effect.currentData(),"medium")
        settings.reject(); settings.deleteLater()

    def test_preference_migration_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            store=QSettings(str(Path(directory)/"settings.ini"),QSettings.Format.IniFormat)
            for legacy,expected in ((False,"mini"),(True,"mega")):
                store.clear(); store.setValue("dramatic_faults",legacy)
                self.assertEqual(fault_effect(load_settings(store)),expected)
            for level in ("mini","medium","mega"):
                chosen=AppSettings(theme="dark",fault_effect=level)
                save_settings(chosen,store); loaded=load_settings(store)
                self.assertEqual(loaded.theme,"dark"); self.assertEqual(fault_effect(loaded),level)
            store.setValue("theme","broken"); store.setValue("fault_effect","broken")
            self.assertEqual(load_settings(store).theme,"light")

    def test_three_levels_and_escape_reset_stop_audio(self):
        self.window.project.sheets=[example("capacitor")]; self.window._rebuild_tabs()
        self.window.show_simulation(); sim=self.window.simulation_window
        with patch("app.ui.fault_sound.FaultSound") as audio:
            for level in ("mini","medium","mega"):
                self.window.settings.fault_effect=level; sim.reset()
                for _ in range(100):
                    sim.advance()
                    if sim.circuit.result.faults: break
                self.assertTrue(sim.circuit.result.faults)
                sim.fault_animation.stop(); sim.animate_faults(.3)
                self.assertEqual(bool(sim.flash_overlay.opacity),level=="mega")
                self.assertEqual(bool(sim.explosion_visuals),level!="mini")
                for visual in sim.explosion_visuals:
                    self.assertEqual(visual.level,level); self.assertAlmostEqual(visual.progress,.3)
                QTest.keyClick(sim,Qt.Key.Key_Escape)
                self.assertEqual(sim.flash_overlay.opacity,0)
                self.assertTrue(all(not visual.isVisible() for visual in sim.explosion_visuals))
                sim.reset(); self.assertFalse(sim.explosion_visuals)
            self.assertEqual(audio.return_value.play.call_count,2)
            audio.return_value.stop.assert_called()

    def test_medium_and_mega_sound_duration_and_volume_without_playback(self):
        with patch("app.ui.fault_sound.QAudioSink") as audio:
            from app.ui.fault_sound import FaultSound
            medium=FaultSound(self.window,"medium"); mega=FaultSound(self.window,"mega")
            self.assertEqual(medium.buffer.size(),int(22050*.85)*2)
            self.assertEqual(mega.buffer.size(),int(22050*(FLASH_SECONDS+RING_TAIL_SECONDS))*2)
            audio.return_value.start.assert_not_called()
            self.assertEqual([call.args[0] for call in audio.return_value.setVolume.call_args_list],[.45,.9])


if __name__=="__main__": unittest.main()
