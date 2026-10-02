"""Testy integracyjne: proces Node wykonuje prawdziwe instrukcje AVR/ARM."""
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from app.simulation.emulator_process import ENGINE_DIR


def hex_firmware(words):
    payload=struct.pack("<"+"H"*len(words),*words)
    record=bytes([len(payload),0,0,0])+payload
    return ":"+(record+bytes([-sum(record)&255])).hex()+"\n:00000001FF\n"


def uf2_firmware(code=None):
    # Thumb: GP0_CTRL=5 (SIO), GPIO_OE=1, GPIO_OUT=1, pętla B .
    if code is None:
        code=struct.pack("<10H2I",0x4804,0x2105,0x6001,0x4804,0x2101,0x6201,0x6101,0xe7fe,0xbf00,0xbf00,0x40014004,0xd0000000)
    block=bytearray(512)
    struct.pack_into("<8I",block,0,0x0a324655,0x9e5d5157,0x2000,0x10000000,256,0,1,0xe48bff56)
    block[32:32+len(code)]=code
    struct.pack_into("<I",block,508,0x0ab16f30)
    return block


AVAILABLE=bool(shutil.which("node") and (ENGINE_DIR/"node_modules"/"avr8js").is_dir() and (ENGINE_DIR/"node_modules"/"rp2040js").is_dir())


@unittest.skipUnless(AVAILABLE,"Optional emulator dependencies not installed")
class FirmwareTests(unittest.TestCase):
    def run_firmware(self,engine,data,inputs=None):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/("code.hex" if isinstance(data,str) else "code.uf2")
            if isinstance(data,str):path.write_text(data,encoding="ascii")
            else:path.write_bytes(data)
            commands=[{"op":"init","engine":engine,"firmware":str(path)},
                      {"op":"step","seconds":.0001,"inputs":inputs or {}}]
            run=subprocess.run([shutil.which("node"),str(ENGINE_DIR/"bridge.cjs")],input="\n".join(map(json.dumps,commands))+"\n",
                capture_output=True,text=True,timeout=10,cwd=ENGINE_DIR)
            self.assertEqual(run.returncode,0,run.stderr)
            return [json.loads(line) for line in run.stdout.splitlines()]

    def test_avr_executes_output_instructions(self):
        results=self.run_firmware("avr8js",hex_firmware([0x9a25,0x9a2d,0xcfff]))
        self.assertTrue(results[0]["ok"],results)
        self.assertTrue(results[1]["ok"],results)
        self.assertEqual(results[1]["gpio"]["D13"],1)
        self.assertGreater(results[1]["time"],0)

    def test_avr_reads_injected_gpio(self):
        # DDRB0=output, IN r16,PIND, OUT PORTB,r16, RJMP loop
        code=hex_firmware([0x9a20,0xb109,0xb905,0xcffd])
        for high in (False,True):
            results=self.run_firmware("avr8js",code,{"D0":high})
            self.assertEqual(results[-1]["gpio"]["D8"],int(high),results)

    def test_rp2040_executes_arm_gpio_instructions(self):
        results=self.run_firmware("rp2040js",uf2_firmware())
        self.assertTrue(results[0]["ok"],results)
        self.assertTrue(results[1]["ok"],results)
        self.assertEqual(results[1]["gpio"]["GP0"],1)

    def test_invalid_hex_and_wrong_uf2_target_rejected(self):
        self.assertFalse(self.run_firmware("avr8js",":0100000000FF\n")[0]["ok"])
        firmware=uf2_firmware()
        struct.pack_into("<I",firmware,28,0x12345678)
        self.assertFalse(self.run_firmware("rp2040js",firmware)[0]["ok"])

    def test_pico_missing_rom_is_explicit_not_silent_zero(self):
        # MOVS r0,#0; LDR r1,[r0] -> odczyt początku nieprzypisanego ROM.
        firmware=uf2_firmware(struct.pack("<3H",0x2000,0x6801,0xe7fe))
        results=self.run_firmware("rp2040js",firmware)
        self.assertFalse(results[1]["ok"])
        self.assertIn("boot ROM",results[1]["error"])
