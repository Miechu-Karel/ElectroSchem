"""Compile real Arduino sketches asynchronously, never upload to hardware."""
import shutil
import tempfile
from pathlib import Path
from hashlib import sha256
from PySide6.QtCore import QObject,QProcess,QTimer,Signal
from app.core.settings import appdata_directory

FQBN={"Arduino Uno R3":"arduino:avr:uno","Arduino Nano":"arduino:avr:nano"}


def compiler_path():
    local=Path(__file__).resolve().parents[2]/".tools"/"arduino-cli"/"arduino-cli.exe"
    return shutil.which("arduino-cli") or (str(local) if local.is_file() else "")


class ArduinoCompiler(QObject):
    finished=Signal(str)
    failed=Signal(str)
    progress=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent); self.process=QProcess(self); self.temporary=None; self.output=None; self.log=""; self.stopped=False
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read)
        self.process.finished.connect(self.complete)
        self.process.errorOccurred.connect(lambda _:self.fail(self.process.errorString()))
        self.timeout=QTimer(self); self.timeout.setSingleShot(True); self.timeout.timeout.connect(lambda:self.fail("Arduino compilation timed out"))

    def start(self,component,definition):
        self.stop(); self.stopped=False; self.log=""
        source=Path(component.properties.get("sim_source","")); cli=compiler_path()
        if definition is None or definition.name not in FQBN: self.fail("Arduino .ino compilation/emulation supports Uno R3 and classic Nano only."); return
        if not cli: self.fail("Arduino CLI is missing. Install arduino-cli and the arduino:avr core."); return
        if source.suffix.lower()!=".ino" or not source.is_file(): self.fail("Assign an existing Arduino .ino sketch first."); return
        try:
            self.temporary=tempfile.TemporaryDirectory(prefix="electroschem-sketch-")
            sketch=Path(self.temporary.name)/"ElectroSchemSketch"; sketch.mkdir()
            total=0; digest=sha256(FQBN[definition.name].encode())
            files=sorted(p for p in source.parent.iterdir() if p.suffix.lower() in {".ino",".cpp",".c",".h",".hpp"} and p.is_file())
            if len(files)>200: raise ValueError("Sketch has too many source files")
            for file in files:
                data=file.read_bytes(); total+=len(data)
                if total>10*1024*1024: raise ValueError("Sketch sources exceed 10 MiB")
                digest.update(file.name.encode()); digest.update(data)
                destination=sketch/("ElectroSchemSketch.ino" if file==source else file.name)
                if destination.exists(): raise ValueError("Conflicting sketch filenames")
                destination.write_bytes(data)
            self.output=appdata_directory()/"compiled"/digest.hexdigest()[:24]; self.output.mkdir(parents=True,exist_ok=True)
            arguments=["compile","--fqbn",FQBN[definition.name],"--output-dir",str(self.output),str(sketch)]
            config=Path(cli).parent.parent/"arduino-cli.yaml"
            if config.is_file(): arguments.extend(["--config-file",str(config)])
            self.process.start(cli,arguments); self.timeout.start(180000)
        except (OSError,ValueError) as error: self.fail(str(error))

    def read(self):
        message=(bytes(self.process.readAllStandardOutput())+bytes(self.process.readAllStandardError())).decode("utf-8",errors="replace")
        self.log=(self.log+message)[-32000:]
        if message: self.progress.emit(message)

    def complete(self,code,*_):
        if self.stopped: return
        self.read(); self.timeout.stop()
        firmware=self.output/"ElectroSchemSketch.ino.hex" if self.output else None
        if code!=0 or firmware is None or not firmware.is_file(): self.fail(self.log or "Arduino compilation failed"); return
        path=str(firmware); self.stop(); self.finished.emit(path)

    def fail(self,message):
        if self.stopped: return
        self.stop(); self.failed.emit(message)

    def stop(self):
        self.stopped=True; self.timeout.stop()
        if self.process.state()!=QProcess.ProcessState.NotRunning: self.process.kill(); self.process.waitForFinished(1000)
        if self.temporary is not None: self.temporary.cleanup(); self.temporary=None
