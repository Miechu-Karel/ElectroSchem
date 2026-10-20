"""Low-volume synthesized buzzer tones. Never modify global device volume."""
import math
import struct
from PySide6.QtCore import QIODevice
from PySide6.QtMultimedia import QAudioFormat,QAudioSink,QMediaDevices


class ToneStream(QIODevice):
    def __init__(self,parent=None):
        super().__init__(parent); self.voices=(); self.phases={}
        self.open(QIODevice.OpenModeFlag.ReadOnly)

    def isSequential(self): return True
    def bytesAvailable(self): return 8192+super().bytesAvailable()

    def readData(self,length):
        voices=self.voices; phases=self.phases
        samples=[]
        for _ in range(min(length//2,8192)):
            value=0
            for key,frequency,level in voices:
                phase=phases.get(key,0)
                value+=math.sin(phase)*level
                phases[key]=(phase+2*math.pi*frequency/44100)%(2*math.pi)
            value=max(-1,min(1,value/max(1,len(voices))))
            samples.append(int(value*32767))
        return struct.pack("<"+"h"*len(samples),*samples)


class BuzzerAudio:
    def __init__(self,parent):
        if QMediaDevices.defaultAudioOutput().isNull():
            raise RuntimeError("No audio output device")
        self.stream=ToneStream(parent)
        fmt=QAudioFormat(); fmt.setSampleRate(44100); fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self.audio=QAudioSink(fmt,parent); self.audio.setVolume(.30)
        self.playing=False

    def update(self,sounds):
        self.stream.voices=tuple((key,float(s["frequency"]),min(1,float(s["level"])))
                                for key,s in sounds.items()
                                if s.get("level",0)>0 and 20<=s.get("frequency",0)<=10000)[:8]
        if self.stream.voices and not self.playing:
            self.audio.start(self.stream); self.playing=True
        elif not self.stream.voices: self.stop()

    def stop(self):
        self.stream.voices=(); self.audio.stop(); self.playing=False
