"""Create an editable, per-component GPIO source without overwriting code."""
from pathlib import Path
from hashlib import sha256
from uuid import UUID
import re
from app.core.settings import appdata_directory
from app.libraries.built_in import get_definition
from app.simulation.gpio_script import gpio_alias


def project_code_id(project):
    """Persistent project identity, independent of its editable title."""
    return UUID(project.id).hex


def ensure_source(component, project=None):
    existing=component.properties.get("sim_source", "")
    definition=get_definition(component.library_id)
    reference=re.sub(r'[\s<>:"/\\|?*\x00-\x1f]+', '.', component.reference).strip('. ')
    arduino=project is not None and definition.name in {"Arduino Uno R3","Arduino Nano"}
    extension=Path(existing).suffix if existing else ".ino" if arduino else ".py"
    project_id=project_code_id(project) if project is not None else ""
    filename=(reference or "MC")+("_"+project_id if project_id else "")+"_code"+(extension or ".py")
    if existing:
        path=Path(existing)
        if not path.is_file(): raise ValueError("Assigned source file is missing: "+str(path))
        # Existing links (including legacy names and multi-file folders) stay
        # untouched. Never move an entry point away from its helper modules.
        return path
    definition=get_definition(component.library_id)
    pins=[a for p in definition.pins if (a:=gpio_alias(p.name))]
    if not pins: raise ValueError("No programmable GPIO pins in this definition")
    pin=next((p for p in ("GPIO12","D13","GP0") if p in pins),pins[0])
    root=appdata_directory()/"code"
    identity=sha256(component.id.encode()).hexdigest()[:24]
    folder=root/project_id/identity if project_id else root/identity
    folder.mkdir(parents=True, exist_ok=True)
    path=folder/filename
    legacy=root/(identity+extension) if project is None else None
    # Exclusive creation preserves code from an earlier session, even when
    # an older copy of the ELS file does not yet contain the source link.
    if not path.exists():
        source=("# ElectroSchem GPIO simulation; not full CPU/OS emulation.\n"
                "# Use a series resistor with an LED. Pin names follow the schematic.\n"
                "from electroschem import Pin, sleep\n\n"
                f"led = Pin({pin!r}, Pin.OUT)\n\n"
                "while True:\n    led.on()\n    sleep(0.5)\n    led.off()\n    sleep(0.5)\n")
        if extension==".ino":
            source=("// Arduino Uno/Nano: real sketch, compiled by Arduino CLI.\n"
                    "void setup() { pinMode(LED_BUILTIN, OUTPUT); }\n"
                    "void loop() {\n  digitalWrite(LED_BUILTIN, HIGH); delay(500);\n"
                    "  digitalWrite(LED_BUILTIN, LOW); delay(500);\n}\n")
        elif project is not None:
            source=""
        if legacy is not None and legacy.is_file():
            # Copy old code before updating the link. Old ELS files may still
            # point at the previous path, so do not delete or overwrite it.
            with path.open("xb") as stream: stream.write(legacy.read_bytes())
        else:
            with path.open("x",encoding="utf-8") as stream: stream.write(source)
    component.properties["sim_source"]=str(path)
    if path.suffix.lower() == ".py": component.properties["sim_mode"]="gpio"
    elif path.suffix.lower()==".ino" and project is not None: component.properties["sim_mode"]="arduino"
    return path


def ensure_code_folder(component, project):
    """Create an editable multi-file workspace; never replace existing files."""
    source=ensure_source(component, project)
    folder=source.parent if component.properties.get("sim_code_folder")==str(source.parent) else source.parent/source.stem
    folder.mkdir(parents=True,exist_ok=True)
    entry=folder/source.name
    if entry != source and entry.exists():
        raise ValueError("Code destination already exists; existing files were kept: "+str(entry))
    if not entry.exists():
        with entry.open("xb") as stream: stream.write(source.read_bytes())
    documents={"README.md":f"# {source.stem}\n\nEntry point: `{entry.name}`.\n\nPython entry points support the simulated GPIO/I2C/LCD APIs and local Python helper modules. Arduino Uno/Nano .ino entry points are compiled by Arduino CLI and executed by AVR emulation. This is not Raspberry Pi OS or an unrestricted Python runtime; unsupported APIs raise errors. See docs/SIMULATION.md for limitations.\n",
               "requirements.txt":"# Dependencies for deployment on the real board, not for the GPIO sandbox.\n"}
    for name,content in documents.items():
        target=folder/name
        if not target.exists():
            with target.open("x",encoding="utf-8") as stream: stream.write(content)
    component.properties["sim_source"]=str(entry)
    component.properties["sim_code_folder"]=str(folder)
    return folder
