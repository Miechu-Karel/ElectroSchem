"""Asynchroniczny proces emulatora, limit czasu i brak uruchamiania powłoki."""
import json
import shutil
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, QTimer, Signal

ENGINE_DIR = Path(__file__).parent / "emulators"


class EmulatorProcess(QObject):
    result = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(ENGINE_DIR))
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.errorOccurred.connect(lambda _: self._fail(self.process.errorString()))
        self.process.finished.connect(self._finished)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(lambda: self._fail("Emulator timeout / Przekroczony czas emulatora"))
        self.buffer, self.busy, self.stopping = b"", False, False
        self.init_connected = False

    def start(self, engine, firmware, bootrom=""):
        self.stop()
        self.stopping = False
        node = shutil.which("node")
        if not node or not (ENGINE_DIR/"node_modules"/engine/"package.json").is_file():
            self.failed.emit("Install Node.js and run npm ci --ignore-scripts in app/simulation/emulators")
            return
        self.initial = {"op":"init", "engine":engine, "firmware":str(Path(firmware).resolve())}
        if bootrom: self.initial["bootrom"] = str(Path(bootrom).resolve())
        self.process.started.connect(self._initialize)
        self.init_connected = True
        self.process.start(node, [str(ENGINE_DIR/"bridge.cjs")])
        self.timeout.start(10000)

    def _initialize(self):
        self.process.started.disconnect(self._initialize)
        self.init_connected = False
        self.send(self.initial)

    def send(self, data):
        if self.busy or self.process.state() != QProcess.ProcessState.Running:
            return False
        self.busy = True
        self.process.write((json.dumps(data)+"\n").encode())
        self.timeout.start(10000)
        return True

    def _read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        if len(self.buffer)>65536:
            self._fail("Emulator response too large")
            return
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n",1)
            self.timeout.stop()
            self.busy = False
            try:
                data = json.loads(line)
                if not isinstance(data,dict) or not data.get("ok"):
                    raise ValueError(data.get("error","Invalid emulator response"))
            except (ValueError, TypeError) as exc:
                self._fail(str(exc))
                return
            self.result.emit(data)

    def _fail(self, message):
        if self.stopping: return
        self.stop()
        self.failed.emit(message)

    def _finished(self, *_):
        if not self.stopping: self._fail("Emulator process exited unexpectedly")

    def stop(self):
        self.stopping = True
        self.timeout.stop()
        if self.process.state()!=QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        if self.init_connected:
            self.process.started.disconnect(self._initialize)
            self.init_connected = False
        self.buffer, self.busy = b"", False
