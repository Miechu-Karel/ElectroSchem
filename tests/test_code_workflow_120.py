"""Code-folder settings and explicit, non-destructive source assignment."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFormLayout,QLineEdit
from app.core.settings import AppSettings,default_code_directory,load_settings,save_settings
from app.core.board_code import ensure_source,assign_source,default_source_filename
from app.core.models import Project,Sheet
from app.core.project_file import save_project,load_project
from app.libraries.built_in import get_definition
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.settings_dialog import SettingsDialog
from app.simulation.engine import Circuit
from test_simulation import component

APP=QApplication.instance() or QApplication([])


class CodeWorkflow120Tests(unittest.TestCase):
    def test_default_and_separate_folder_preferences_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('app.core.settings.documents_directory',return_value=folder):
                self.assertEqual(AppSettings().default_code_directory,str(root/'ElectroSchem/Code'))
            store=QSettings(str(root/'settings.ini'),QSettings.Format.IniFormat)
            settings=AppSettings(default_directory=str(root/'projects'),default_code_directory=str(root/'code'))
            save_settings(settings,store)
            restored=load_settings(store)
            self.assertEqual(restored.default_directory,settings.default_directory)
            self.assertEqual(restored.default_code_directory,settings.default_code_directory)
            self.assertFalse((root/'code').exists())

    def test_settings_accept_new_code_directory_without_creating_it(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'new-code'
            dialog=SettingsDialog(AppSettings(language='pl',default_directory=folder))
            dialog.code_directory.setText(str(target))
            dialog._accept()
            self.assertEqual(dialog.result_settings().default_code_directory,str(target))
            self.assertEqual(dialog.result_settings().default_directory,folder)
            self.assertFalse(target.exists())
            self.assertIn('Domyślny folder kodów',[label.text() for label in dialog._rows])
            dialog.deleteLater()

    def test_explicit_code_folder_and_existing_links_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); target=root/'chosen-code'; second=root/'another-folder'
            board=component('Raspberry Pi 5',500,400)
            path=ensure_source(board,Project(),target)
            self.assertTrue(path.is_relative_to(target))
            self.assertEqual(path.read_bytes(),b'')
            path.write_text('# user code\n',encoding='utf-8')
            self.assertEqual(ensure_source(board,Project(),second),path)
            self.assertEqual(path.read_text(),'# user code\n')
            self.assertFalse(second.exists())

    def test_assignment_does_not_copy_or_execute_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'existing.py'; source.write_text('raise RuntimeError("must not run")\n',encoding='utf-8')
            board=component('Raspberry Pi 5',500,400,sim_code_folder='old',sim_firmware='old.hex')
            contents=source.read_bytes(); modified=source.stat().st_mtime_ns
            assign_source(board,source)
            self.assertEqual(board.properties['sim_source'],str(source.resolve()))
            self.assertEqual(board.properties['sim_mode'],'gpio')
            self.assertNotIn('sim_code_folder',board.properties)
            self.assertNotIn('sim_firmware',board.properties)
            self.assertEqual(source.read_bytes(),contents)
            self.assertEqual(source.stat().st_mtime_ns,modified)
            self.assertEqual(list(Path(folder).iterdir()),[source])

    def test_invalid_assignments_keep_previous_link(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); ino=root/'sketch.ino'; ino.touch(); text=root/'notes.txt'; text.touch()
            board=component('Raspberry Pi 5',500,400,sim_source='old.py',sim_mode='gpio')
            before=deepcopy(board.properties)
            for source in (ino,text,root,root/'missing.py'):
                with self.subTest(source=source),self.assertRaises(ValueError): assign_source(board,source)
                self.assertEqual(board.properties,before)

    def test_arduino_assignment_selects_compiler_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'sketch.ino'; source.write_text('void setup(){}\nvoid loop(){}\n')
            board=component('Arduino Uno R3',500,400)
            assign_source(board,source)
            self.assertEqual(board.properties['sim_mode'],'arduino')
            self.assertEqual(source.name,'sketch.ino')

    def test_property_buttons_order_cancellation_assignment_and_label_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'existing.py'; source.write_text('from gpiozero import LED\nled=LED(12)\nled.on()\n')
            window=MainWindow(AppSettings(language='pl',fault_effect='mini',window_mode='windowed',default_code_directory=folder),start_setup=False)
            dialog=None
            try:
                board=component('Raspberry Pi 5',500,400)
                window.project.sheets=[Sheet(components=[board])]; window._rebuild_tabs()
                dialog=ComponentPropertiesDialog(board,get_definition(board.library_id),'pl',window)
                self.assertEqual(dialog.edit_code_button.text(),'Utwórz i Przypisz Kod')
                form=dialog.findChild(QFormLayout)
                self.assertEqual(form.getWidgetPosition(dialog.assign_code_button)[0],form.getWidgetPosition(dialog.edit_code_button)[0]+1)
                with patch('app.ui.main_window.QFileDialog.getOpenFileName',return_value=('','')):
                    dialog.assign_code_button.click()
                self.assertNotIn('sim_source',board.properties)
                with patch('app.ui.main_window.QFileDialog.getOpenFileName',return_value=(str(source),'')) as picker:
                    dialog.assign_code_button.click()
                self.assertEqual(picker.call_args.args[2],folder)
                self.assertEqual(dialog.edit_code_button.text(),'Edytuj Kod')
                self.assertIn(str(source.resolve()),dialog.code_path_label.toPlainText())
                dialog.accept(); board.properties.update(dialog.values['simulation_properties'])
                saved=root/'linked.els'; save_project(saved,window.project)
                restored=load_project(saved)
                self.assertEqual(restored.sheets[0].components[0].properties['sim_source'],str(source.resolve()))
                circuit=Circuit(restored.sheets[0]); self.assertFalse(circuit.step().faults)
                self.assertEqual(circuit.gpio_states[board.id]['GPIO12'],1)
            finally:
                if dialog: dialog.deleteLater()
                with patch.object(window,'_confirm_discard',return_value=True): window.close()
                window.deleteLater(); APP.processEvents()

    def test_create_button_uses_setting_then_opens_assigned_code(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); editor=root/'editor.exe'; editor.touch()
            chosen=root/'custom-code'
            window=MainWindow(AppSettings(language='pl',editor_path=str(editor),default_code_directory=str(chosen),fault_effect='mini',window_mode='windowed'),start_setup=False)
            dialog=None
            try:
                board=component('Raspberry Pi 5',500,400)
                window.project.sheets=[Sheet(components=[board])]; window._rebuild_tabs()
                dialog=ComponentPropertiesDialog(board,get_definition(board.library_id),'pl',window)
                with patch('app.ui.main_window.subprocess.Popen') as launch,patch('app.ui.main_window.QFileDialog.getSaveFileName',side_effect=lambda *args,**kwargs:(args[2],'')) as picker:
                    dialog.edit_code_button.click()
                self.assertEqual(picker.call_args.args[2],str(chosen/default_source_filename(board,window.project)))
                source=Path(board.properties['sim_source'])
                self.assertTrue(source.is_relative_to(chosen))
                self.assertEqual(source.read_bytes(),b'')
                self.assertEqual(dialog.edit_code_button.text(),'Edytuj Kod')
                launch.assert_called_once_with([str(editor),str(source)],shell=False)
            finally:
                if dialog: dialog.deleteLater()
                with patch.object(window,'_confirm_discard',return_value=True): window.close()
                window.deleteLater(); APP.processEvents()

    def test_detach_removes_references_only_and_prevents_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'existing.py'; source.write_text('# user code\n')
            board=component('Raspberry Pi 5',500,400)
            assign_source(board,source)
            board.properties.update(sim_code_folder=folder,sim_firmware='compiled.hex',sim_bootrom='boot.bin')
            window=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False)
            dialog=None
            try:
                window.project.sheets=[Sheet(components=[board])]; window._rebuild_tabs(); window.record_history()
                dialog=ComponentPropertiesDialog(board,get_definition(board.library_id),'pl',window)
                self.assertEqual(dialog.assign_code_button.text(),'Odłącz Kod')
                self.assertFalse(dialog.assign_code_button.icon().isNull())
                with patch('app.ui.main_window.QFileDialog.getOpenFileName') as picker:
                    window.assign_component_code(board)
                    picker.assert_not_called()
                with self.assertRaises(ValueError): assign_source(board,source)
                dialog.assign_code_button.click()
                for key in ('sim_source','sim_code_folder','sim_firmware'): self.assertNotIn(key,board.properties)
                self.assertEqual(board.properties['sim_bootrom'],'boot.bin')
                self.assertEqual(source.read_text(),'# user code\n')
                self.assertEqual(dialog.assign_code_button.text(),'Przypisz Istniejący Kod')
                self.assertEqual(dialog.edit_code_button.text(),'Utwórz i Przypisz Kod')
                dialog.accept()
                board.properties.update(dialog.values['simulation_properties'])
                self.assertNotIn('sim_source',board.properties)
                saved=Path(folder)/'detached.els'; save_project(saved,window.project)
                self.assertNotIn('sim_source',load_project(saved).sheets[0].components[0].properties)
                window.undo()
                self.assertEqual(window.project.sheets[0].components[0].properties['sim_source'],str(source.resolve()))
                window.redo()
                self.assertNotIn('sim_source',window.project.sheets[0].components[0].properties)
                self.assertTrue(source.is_file())
            finally:
                if dialog: dialog.deleteLater()
                with patch.object(window,'_confirm_discard',return_value=True): window.close()
                window.deleteLater(); APP.processEvents()

    def test_custom_names_extensions_and_collision_preserve_files(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Project(); board=component('Raspberry Pi 5',500,400)
            source=ensure_source(board,project,folder,'Migające LEDy.py')
            self.assertEqual(source.name,'Migające LEDy.py')
            self.assertTrue(source.is_relative_to(Path(folder)/project.id.replace('-','')))
            source.write_text('# keep this code\n')
            board.properties.pop('sim_source')
            with self.assertRaises(ValueError): ensure_source(board,project,folder,'Migające LEDy')
            self.assertEqual(source.read_text(),'# keep this code\n')
            self.assertNotIn('sim_source',board.properties)
            arduino=component('Arduino Uno R3',300,300)
            self.assertEqual(ensure_source(arduino,project,folder,'blink').name,'blink.ino')

    def test_invalid_names_create_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'not-created'; project=Project()
            for name in ('../escape','C:\\escape','bad:name','CON','NUL.py','..','blink.ino'):
                with self.subTest(name=name):
                    board=component('Raspberry Pi 5',500,400)
                    with self.assertRaises(ValueError): ensure_source(board,project,target,name)
                    self.assertFalse(target.exists())
                    self.assertNotIn('sim_source',board.properties)

    def test_save_dialog_name_location_cancel_and_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); editor=root/'editor.exe'; editor.touch()
            target=root/'code'
            window=MainWindow(AppSettings(language='pl',window_mode='windowed',editor_path=str(editor),default_code_directory=str(target)),start_setup=False)
            try:
                board=component('Raspberry Pi 5',500,400)
                with patch('app.ui.main_window.QFileDialog.getSaveFileName',return_value=('','')),patch('app.ui.main_window.subprocess.Popen') as launch:
                    window.edit_component_code(board)
                    window.edit_component_code_folder(board)
                    launch.assert_not_called()
                self.assertNotIn('sim_source',board.properties)
                self.assertFalse(target.exists())
                selected=root/'chosen elsewhere'/'Mój program.py'
                with patch('app.ui.main_window.QFileDialog.getSaveFileName',return_value=(str(selected),'')),patch('app.ui.main_window.subprocess.Popen') as launch:
                    window.edit_component_code(board)
                    launch.assert_called_once()
                source=Path(board.properties['sim_source'])
                self.assertEqual(source.name,'Mój program.py')
                self.assertEqual(source,selected)
                self.assertFalse(target.exists())
                with patch('app.ui.main_window.QFileDialog.getSaveFileName') as prompt,patch('app.ui.main_window.subprocess.Popen'):
                    window.edit_component_code(board)
                    prompt.assert_not_called()
                self.assertEqual(source.read_bytes(),b'')
            finally:
                with patch.object(window,'_confirm_discard',return_value=True): window.close()
                window.deleteLater(); APP.processEvents()

    def test_exact_destination_extension_and_existing_file_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); project=Project()
            board=component('Raspberry Pi 5',500,400)
            selected=root/'selected folder'/'blink'
            source=ensure_source(board,project,root/'default',destination=selected)
            self.assertEqual(source,selected.with_suffix('.py'))
            self.assertFalse((root/'default').exists())
            source.write_text('# preserve\n')
            board.properties.pop('sim_source')
            with self.assertRaises(ValueError): ensure_source(board,project,destination=source)
            self.assertEqual(source.read_text(),'# preserve\n')
            self.assertNotIn('sim_source',board.properties)

    def test_long_code_path_does_not_widen_properties_form(self):
        board=component('Raspberry Pi 5',500,400,sim_source='C:\\'+('a_very_long_folder_name_'*40)+'\\main.py')
        dialog=ComponentPropertiesDialog(board,get_definition(board.library_id),'pl')
        try:
            dialog.resize(600,650); dialog.show(); APP.processEvents()
            self.assertLessEqual(dialog.form_scroll.widget().width(),dialog.form_scroll.viewport().width())
            self.assertLessEqual(dialog.code_path_label.width(),dialog.form_scroll.viewport().width())
            self.assertEqual(dialog.code_path_label.horizontalScrollBar().maximum(),0)
            self.assertEqual(dialog.code_path_label.toPlainText(),'Przypisany kod: '+board.properties['sim_source'])
            self.assertTrue(dialog.code_path_label.isReadOnly())
        finally:
            dialog.close(); dialog.deleteLater(); APP.processEvents()

    def test_x_activates_delete_tool_but_delete_removes_and_ctrl_x_cuts(self):
        window=MainWindow(AppSettings(window_mode='windowed'),start_setup=False)
        try:
            window.show(); window.activateWindow()
            view=window._current_view(); view.setFocus(); APP.processEvents()
            with patch.object(view,'delete_selected') as deleted,patch.object(window,'selection_command') as selection:
                QTest.keyClick(view,Qt.Key.Key_X)
                self.assertEqual(view.tool,'delete')
                self.assertTrue(window.delete_action.isChecked())
                deleted.assert_not_called()
                QTest.keyClick(view,Qt.Key.Key_Delete)
                deleted.assert_called_once()
                QTest.keyClick(view,Qt.Key.Key_X,Qt.KeyboardModifier.ControlModifier)
                selection.assert_called_once_with('cut')
                field=QLineEdit(window); field.show(); field.setFocus(); APP.processEvents()
                QTest.keyClick(field,Qt.Key.Key_X)
                self.assertEqual(field.text(),'x')
                self.assertEqual(deleted.call_count,1)
                field.deleteLater()
        finally:
            with patch.object(window,'_confirm_discard',return_value=True): window.close()
            window.deleteLater(); APP.processEvents()
