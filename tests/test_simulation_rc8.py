"""Polish characters must occupy one cell, including across byte transactions."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from app.simulation.peripherals import lcd_byte
from app.ui.effects import FLASH_SECONDS,RING_TAIL_SECONDS
from app.ui.fault_sound import FaultSound
import test_simulation_alpha11 as alpha11

APP=QApplication.instance() or QApplication([])
ROOT=Path(__file__).resolve().parents[1]
LOWER='ąćęłńóśźż'
UPPER='ĄĆĘŁŃÓŚŹŻ'


def send(state,value,rs=0,encoding='utf-8'):
    for nibble in (value>>4,value&15):
        port=(nibble<<4)|8|rs
        state=lcd_byte(state,port|4,encoding)
        state=lcd_byte(state,port,encoding)
    return state


class Rc8Tests(unittest.TestCase):
    def test_ringing_tail_is_three_seconds_without_shortening_flash(self):
        self.assertEqual(RING_TAIL_SECONDS,3)
        self.assertEqual(FLASH_SECONDS,2.2)
        with patch('app.ui.fault_sound.QAudioSink'):
            sound=FaultSound(None,'mega')
            self.assertEqual(sound.buffer.size(),int(22050*5.2)*2)
            sound.dispose()

    def test_utf8_and_windows1250_lowercase_and_uppercase(self):
        for encoding,codec in (('utf-8','utf-8'),('windows-1250','cp1250')):
            with self.subTest(encoding=encoding):
                state={'four_bit':True,'display':True}
                for byte in LOWER.encode(codec): state=send(state,byte,1,encoding)
                state=send(state,0xc0,encoding=encoding)
                for byte in UPPER.encode(codec): state=send(state,byte,1,encoding)
                self.assertEqual(state['cells'][:16],LOWER.ljust(16))
                self.assertEqual(state['cells'][16:],UPPER.ljust(16))
                self.assertEqual(len(state['cells']),32)

    def test_multibyte_letter_in_last_column_does_not_use_extra_cells(self):
        state={'four_bit':True}
        for byte in ('123456789012345Ż').encode('utf-8'): state=send(state,byte,1)
        self.assertEqual(state['cells'][:16],'123456789012345Ż')
        self.assertEqual(state['address'],16)
        self.assertEqual(state['cells'][16:],' '*16)

    def test_clear_discards_incomplete_utf8_sequence(self):
        state=send({'four_bit':True},0xc4,1)
        self.assertIn('utf8_pending',state)
        state=send(state,1)
        self.assertNotIn('utf8_pending',state)
        state=send(state,ord('A'),1)
        self.assertTrue(state['cells'].startswith('A'))

    def test_python_polish_text_reaches_electrically_wired_lcd(self):
        circuit,lcd=alpha11.PythonApiTests().lcd_circuit(ROOT/'examples/lcd_polish.py')
        result=circuit.step(.001)
        self.assertFalse(result.faults)
        self.assertEqual(result.displays[lcd.id]['cells'],
                         'Zażółć gęślą'.ljust(16)+'jaźń ĄĆĘŁŃÓŚŹŻ'.ljust(16))
