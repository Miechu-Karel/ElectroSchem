"""Short synthesized rupture sound, used only by opt-in fault effects."""
import math
import random
import struct
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtMultimedia import QAudioFormat, QAudioSink

RING_FADE_SECONDS=1.5


def ringing_envelope(time, duration):
    """After the flash: 1.5 seconds steady, then 1.5 seconds of fading."""
    return max(0.,min(1.,time/.04))*max(0.,min(1.,(duration-time)/RING_FADE_SECONDS))


class FaultSound:
    def __init__(self, parent, level="mega"):
        self.level=level
        rate=22050; rng=random.Random(17)
        from app.ui.effects import FLASH_SECONDS,RING_TAIL_SECONDS
        duration=FLASH_SECONDS+RING_TAIL_SECONDS if level=="mega" else .85
        samples=[]
        for i in range(int(rate*duration)):
            t=i/rate
            # Sharp crack followed by a low, decaying thump. Peak-limited;
            # never played unless the user enabled dramatic fault effects.
            crack=rng.uniform(-1,1)*math.exp(-t*18)
            thump=.8*math.sin(2*math.pi*(95*t-45*t*t))*math.exp(-t*9)
            envelope=ringing_envelope(t,duration)
            ring=.065*math.sin(2*math.pi*2400*t)*envelope if level=="mega" else 0
            debris=rng.uniform(-1,1)*.15*math.exp(-max(0,t-.07)*12)*min(1,t/.07)
            resonance=.16*math.sin(2*math.pi*420*t)*math.exp(-t*11)
            value=max(-.95,min(.95,.9*math.tanh(2.2*(crack+thump+debris+resonance))+ring))
            samples.append(int(max(-1,min(1,value))*32767))
        self.buffer=QBuffer(parent)
        self.buffer.setData(QByteArray(struct.pack("<"+"h"*len(samples),*samples)))
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        fmt=QAudioFormat(); fmt.setSampleRate(rate); fmt.setChannelCount(1); fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self.audio=QAudioSink(fmt,parent)
        # Respect system/device volume; never change global audio settings.
        self.audio.setVolume(.9 if level=="mega" else .45)

    def play(self):
        self.audio.stop(); self.buffer.seek(0); self.audio.start(self.buffer)

    def stop(self):
        self.audio.stop()

    def dispose(self):
        self.stop(); self.buffer.close(); self.audio.deleteLater(); self.buffer.deleteLater()
