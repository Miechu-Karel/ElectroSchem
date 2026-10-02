"""The ringing fades earlier without extending or amplifying the effect."""
import unittest
from app.ui.effects import FLASH_SECONDS, RING_TAIL_SECONDS
from app.ui.fault_sound import ringing_envelope


class Rc9Tests(unittest.TestCase):
    def test_rc10_tail_is_steady_then_fades_for_one_and_a_half_seconds(self):
        duration=FLASH_SECONDS+RING_TAIL_SECONDS
        self.assertAlmostEqual(duration,5.2)
        for offset in (0,.5,1,1.5):
            self.assertAlmostEqual(ringing_envelope(FLASH_SECONDS+offset,duration),1)
        self.assertAlmostEqual(ringing_envelope(FLASH_SECONDS+1.875,duration),.75)
        self.assertAlmostEqual(ringing_envelope(FLASH_SECONDS+2.25,duration),.5)
        self.assertAlmostEqual(ringing_envelope(FLASH_SECONDS+2.625,duration),.25)
        self.assertEqual(ringing_envelope(duration,duration),0)

    def test_attack_and_level_are_unchanged_and_bounded(self):
        self.assertEqual(ringing_envelope(0,5.2),0)
        self.assertEqual(ringing_envelope(.02,5.2),.5)
        self.assertEqual(ringing_envelope(.04,5.2),1)
        self.assertEqual(ringing_envelope(3,5.2),1)
        for time in (-1,0,.02,.04,4.5,5.2,6):
            self.assertGreaterEqual(ringing_envelope(time,5.2),0)
            self.assertLessEqual(ringing_envelope(time,5.2),1)
