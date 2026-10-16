"""Focused UI regressions for RC21's interactive components and controls."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
import unittest

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsRectItem

from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.usb_keyboard import UsbKeyboard, NAV, NUM


APP = QApplication.instance() or QApplication([])


class _Window:
    def __init__(self):
        self.editor = SimpleNamespace(settings=AppSettings())
        self.circuit = None
        self.inputs = []

    @staticmethod
    def t(en, pl):
        return pl

    def set_simulation_input(self, *args):
        self.inputs.append(args)


class RC21ControlTests(unittest.TestCase):
    def test_navigation_and_numpad_keys_are_square(self):
        window = _Window()
        keyboard = UsbKeyboard(window, SimpleNamespace(state={"powered": False}))
        labels = {label for row in NAV + NUM for label in row if label}
        for label in labels:
            with self.subTest(key=label):
                button = keyboard.buttons[label]
                self.assertEqual(button.width(), button.height())
        keyboard.close()

    def test_photoresistor_exposure_slider_updates_model_input(self):
        from app.ui.simulation_controls import add_control

        window = _Window()
        device = SimpleNamespace(kind="ldr", component=SimpleNamespace(id="ldr-1"),
                                 parameters={"sim_light": 1.0, "value": 10000.0})
        item = QGraphicsRectItem(QRectF(-40, -40, 80, 80))
        item._hit_rect = QRectF(-40, -40, 80, 80)
        panel = add_control(window, device, item)
        self.assertEqual((panel.slider.minimum(), panel.slider.maximum()), (0, 100))
        panel.slider.setValue(20)
        self.assertEqual(window.inputs[-1], ("ldr-1", "sim_light", .2))
        panel.close()

    def test_sensor_stimulus_sliders_update_analog_and_distance_inputs(self):
        from app.ui.simulation_controls import add_control

        window = _Window()
        item = QGraphicsRectItem(QRectF(-40, -40, 80, 80))
        item._hit_rect = QRectF(-40, -40, 80, 80)
        analog = SimpleNamespace(kind="analog_sensor", component=SimpleNamespace(id="sensor-1"),
                                 parameters={"sim_signal": .5})
        panel = add_control(window, analog, item)
        panel.slider.setValue(73)
        self.assertEqual(window.inputs[-1], ("sensor-1", "sim_signal", .73))
        panel.close()

        distance = SimpleNamespace(kind="ultrasonic", component=SimpleNamespace(id="range-1"),
                                   parameters={"sim_distance": 1.0})
        item = QGraphicsRectItem(QRectF(-40, -40, 80, 80)); item._hit_rect = QRectF(-40, -40, 80, 80)
        panel = add_control(window, distance, item)
        panel.slider.setValue(245)
        self.assertEqual(window.inputs[-1], ("range-1", "sim_distance", 2.45))
        panel.set_distance_value(.8)
        self.assertEqual(panel.slider.value(), 80)
        panel.close()

    def test_scene_props_drive_ultrasonic_and_pir_stimuli(self):
        from PySide6.QtCore import QPointF
        from app.ui.simulation_window import SimulationWindow

        def visual(name, cid, x, y, properties=None):
            return SimpleNamespace(definition=SimpleNamespace(name=name),
                component=SimpleNamespace(id=cid, x=x, y=y, properties=properties or {}),
                scenePos=lambda: QPointF(x,y), update=lambda: None)

        range_sensor=visual("Czujnik Odległości HC-SR04","range",0,0)
        pir_sensor=visual("Czujnik Ruchu PIR HC-SR501","pir",0,0)
        target=visual("Cel ultradźwiękowy","target",200,0)
        person=visual("Osoba","person",0,200)
        flame_sensor=visual("Czujnik Płomienia","flame",0,0)
        match=visual("Zapałka","match",40,0,{"sim_lit":"false"})
        ultrasonic=SimpleNamespace(kind="ultrasonic",component=range_sensor.component,parameters={"sim_distance":1.0})
        pir=SimpleNamespace(kind="digital_sensor",component=pir_sensor.component,parameters={"sim_active":"false"})
        flame=SimpleNamespace(kind="analog_sensor",component=flame_sensor.component,parameters={"sim_signal":.65})
        fake=SimpleNamespace(circuit=SimpleNamespace(devices=[ultrasonic,pir]),
            symbols={"range":range_sensor,"pir":pir_sensor,"target":target,"person":person,"flame":flame_sensor,"match":match},
            controls={},_interactive_base_distances={"range":1.0},_interactive_base_flame_signals={"flame":.65})
        fake.circuit.devices.append(flame)
        SimulationWindow.update_interactive_inputs(fake,recalculate=False)
        self.assertEqual(ultrasonic.parameters["sim_distance"],2.0)
        self.assertEqual(pir.parameters["sim_active"],"true")
        self.assertEqual(flame.parameters["sim_signal"],.65)
        match.component.properties["sim_lit"]="true"
        SimulationWindow.update_interactive_inputs(fake,recalculate=False)
        self.assertEqual(flame.parameters["sim_signal"],.05)
        match.component.properties["sim_lit"]="false"
        SimulationWindow.update_interactive_inputs(fake,recalculate=False)
        self.assertEqual(flame.parameters["sim_signal"],.65)

    def test_new_props_are_draggable_and_paint_without_clipping(self):
        from app.core.models import Project
        from app.ui.simulation_window import LiveSymbol

        for name in ("Cel ultradźwiękowy", "Osoba", "Pilot IR"):
            with self.subTest(name=name):
                component = Project().new_component(next(d.id for d in BUILT_IN_ITEMS if d.name==name),100,100)
                item = LiveSymbol(component,language="pl")
                self.assertTrue(item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                image=QImage(260,260,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.white)
                painter=QPainter(image); painter.translate(130,130); item.paint(painter,None,None); painter.end()
                self.assertGreater(sum(1 for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x,y)!=image.pixelColor(0,0)),100)

    def test_ir_remote_sends_a_short_stimulus_to_nearby_receiver(self):
        from PySide6.QtCore import QPointF
        from app.ui.simulation_window import SimulationWindow

        receiver=SimpleNamespace(kind="digital_sensor",parameters={"name":"Czujnik Podczerwieni"},
            component=SimpleNamespace(x=0,y=0,id="rx",reference="IR001"))
        remote=SimpleNamespace(definition=SimpleNamespace(name="Pilot IR"),scenePos=lambda:QPointF(100,0))
        messages=[]; pulses=[]
        fake=SimpleNamespace(circuit=SimpleNamespace(result=SimpleNamespace(faults=[]),devices=[receiver]),
            symbols={"remote":remote},log=SimpleNamespace(appendPlainText=messages.append),
            t=lambda en,pl:pl,pulse_input=lambda *args:pulses.append(args))
        SimulationWindow.toggle(fake,"remote")
        self.assertEqual(pulses,[ ("rx","sim_active","true","false",180) ])
        self.assertIn("Wysłano bodziec IR",messages[0])


if __name__ == "__main__":
    unittest.main()
