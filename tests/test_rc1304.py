"""RC4: readability, editable isolated preview and interaction regressions."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtCore import QPointF,QTimer,Qt
from PySide6.QtWidgets import QApplication,QPushButton,QMenu
from app.core.models import Project,Sheet,Wire
from app.core.settings import AppSettings
from app.services.layout_review import review
from app.ui.main_window import MainWindow
from app.ui.ai_preview import AiPreview,connectivity
from app.simulation.reconfigure import reconfigure
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])

class RC4Tests(unittest.TestCase):
    def test_automatic_question_detection_does_not_swallow_draw_requests(self):
        from app.services.assistant_intent import explanation_only
        self.assertTrue(explanation_only('Dlaczego dioda potrzebuje rezystora?'))
        self.assertFalse(explanation_only('Czy możesz narysuj układ z LED?'))

    def test_special_keyboard_symbols_have_font_independent_icons(self):
        from app.ui.usb_keyboard import special_icon
        for key in ('Win','RWin','Shift','Caps','Enter','Backspace','Tab','Menu','Left','Right','Up','Down'):
            self.assertFalse(special_icon(key).isNull())
    def test_visual_audit_is_independent_of_electrical_validation(self):
        b=Bench(); a=b.add('Rezystor'); z=b.add('Rezystor')
        a.x,a.y=z.x,z.y=300,300
        sheet=Sheet(components=b.components,wires=[Wire(100,300,500,300)])
        before=deepcopy(sheet)
        report=review(Project(sheets=[sheet]))
        codes={i['code'] for i in report['issues']}
        self.assertIn('overlapping_symbols',codes); self.assertIn('wire_through_symbol_or_label',codes)
        self.assertEqual(sheet,before)
        z.x=650; sheet.wires=[]
        self.assertFalse(review(Project(sheets=[sheet]))['issues'])

    def test_topology_rebuild_preserves_clock_and_capacitor_memory(self):
        b=Bench(); s,g=b.power(); r=b.add('Rezystor','1000','Ω'); cap=b.add('Kondensator Ceramiczny','10','µF',voltage='25 V')
        b.connect(s,0,r,0); b.connect(r,1,cap,0); b.connect(cap,1,g,0)
        old=b.circuit()
        for _ in range(100): old.step(.0001)
        before=next(d for d in old.devices if d.component.id==cap.id)
        b.wires=b.wires[1:]
        new=reconfigure(old,Sheet(components=b.components,wires=b.wires))
        after=next(d for d in new.devices if d.component.id==cap.id)
        self.assertAlmostEqual(new.time,old.time); self.assertEqual(after.previous,before.previous)
        self.assertEqual(after.state,before.state); self.assertIsNot(after.state,before.state)

    def test_preview_move_rotate_commits_only_to_proposal(self):
        b=Bench(); a=b.add('Rezystor','330','Ω'); a.x,a.y=400,300
        project=Project(sheets=[Sheet(components=b.components)])
        preview=AiPreview(); preview.set_project(project,0,AppSettings(language='pl'))
        received=[]; preview.projectEdited.connect(received.append)
        def edit():
            view=preview.inspection_view
            item=view._component_items[a.id]; item.setSelected(True); item.setPos(600,400)
            view.rotate_selected_components()
            next(button for button in preview.inspection_dialog.findChildren(QPushButton) if button.text()=='Zapisz do propozycji').click()
        QTimer.singleShot(0,edit); preview.inspect('pl')
        self.assertEqual(len(received),1)
        edited=received[0].sheets[0].components[0]
        self.assertEqual((edited.x,edited.y,edited.rotation),(600,400,90))
        self.assertEqual((a.x,a.y,a.rotation),(400,300,0))
        self.assertEqual(connectivity(project,0),connectivity(received[0],0))
        preview.deleteLater(); APP.processEvents()


class RC4UITests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language='pl',theme='dark',window_mode='windowed'),start_setup=False)
    def tearDown(self):
        if getattr(self.window,'simulation_window',None): self.window.simulation_window.close()
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict()
        self.window.close(); self.window.deleteLater(); APP.processEvents()
    def test_sound_button_cycles_and_meter_starts_disconnected(self):
        b=Bench(); b.add('Rezystor','1000','Ω')
        self.window.project=Project(sheets=[Sheet(components=b.components)]); self.window._rebuild_tabs()
        self.window.show_simulation(); sim=self.window.simulation_window
        for volume,muted in ((.5,False),(.25,False),(.25,True),(1.,False)):
            sim.buzzer_sound_button.click()
            self.assertEqual(sim.sound_volume,volume); self.assertEqual(sim.buzzer_sound_button.isChecked(),muted)
        sim.open_measurements(); panel=sim.measurement_panel
        self.assertTrue(all(probe.node is None for probe in panel.probes))
        self.assertEqual((panel.positive.currentIndex(),panel.negative.currentIndex()),(-1,-1))
        instrument=panel.instrument; sim.single_step(); t=sim.circuit.time
        sim.reconfigure_cables()
        self.assertEqual(sim.circuit.time,t); self.assertIs(sim.measurement_panel.instrument,instrument)
        self.assertTrue(all(probe.node is None for probe in panel.probes))
    def test_rotation_direction_and_readability_context(self):
        view=self.window._current_view(); b=Bench(); c=b.add('Rezystor','330','Ω'); c.x,c.y=400,300
        self.window.project.sheets[0]=Sheet(components=b.components); view.load_sheet(self.window.project.sheets[0])
        view._component_items[c.id].setSelected(True)
        self.window.settings.rotation_direction='ccw'
        view.rotate_selected_components(); self.assertEqual(c.rotation,270)
        view.rotate_selected_components(opposite=True); self.assertEqual(c.rotation,0)
        self.window.show_command_panel(); panel=self.window.command_panel; panel.prepare(); panel.show_proposal()
        self.assertIn('layout_report',panel.working_context())
        before=panel.session.working.to_dict()
        with patch.object(panel.client,'start') as start:
            panel.request_readability(); start.assert_not_called()
        self.assertIn('Zachowaj wszystkie połączenia',panel.prompt.toPlainText())
        self.assertEqual(before,panel.session.working.to_dict())
        candidate=deepcopy(panel.session.working)
        candidate.sheets[0].components[0].x=600
        candidate.sheets[0].components[0].rotation=270
        panel.preview_edited(candidate)
        self.assertEqual(self.window.project.sheets[0].components[0].x,400)
        panel.accept()
        actual=self.window.project.sheets[0].components[0]
        self.assertEqual((actual.x,actual.rotation),(600,270))
    def test_favorites_rmb_removes_without_removing_component(self):
        from PySide6.QtWidgets import QMessageBox
        b=Bench(); c=b.add('Rezystor','330','Ω')
        self.window.settings.favorite_components[c.library_id]={'value':'330','properties':{}}
        def interact():
            menu=APP.activePopupWidget(); action=menu.actions()[0]
            def remove():
                popup=APP.activePopupWidget(); popup.actions()[0].trigger(); popup.close()
            QTimer.singleShot(0,remove)
            menu.customContextMenuRequested.emit(menu.actionGeometry(action).center()); menu.close()
        with patch('app.ui.main_window.save_settings'):
            QTimer.singleShot(0,interact); self.window.open_library(5)
        self.assertNotIn(c.library_id,self.window.settings.favorite_components)

    def test_explanation_skips_practice_and_blocks_edit_commands(self):
        self.window.settings.ai_provider='gemini'; self.window.settings.api_key='fake-not-sent'
        self.window.settings.ai_chat_consent=True; self.window.settings.ai_request_consents={'gemini':True}
        self.window.show_command_panel(); panel=self.window.command_panel
        original=self.window.project.to_dict()
        panel.request_mode.setCurrentIndex(1); panel.prompt.setPlainText('Wyjaśnij zasadę działania rezystora')
        with (patch('app.services.assistant_curriculum.read_profile',side_effect=AssertionError('Questions must not start exercises')),
             patch.object(panel.client,'start') as client,patch.object(panel.planner,'start') as planner):
            panel.send_request(); client.assert_called_once(); planner.assert_not_called()
        self.assertIsNone(panel.curriculum)
        before=panel.session.working.to_dict()
        panel.completed({'summary':'Rezystor ogranicza prąd.','commands':''})
        self.assertFalse(panel.busy); self.assertEqual(panel.session.working.to_dict(),before)
        panel.completed({'summary':'Invalid edit','commands':'DELETE_COMPONENT id=R1'})
        self.assertIn('zablokowana',panel.last_error)
        self.assertEqual(panel.session.working.to_dict(),before); self.assertEqual(self.window.project.to_dict(),original)

if __name__=='__main__': unittest.main()
