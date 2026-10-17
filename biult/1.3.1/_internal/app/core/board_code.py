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


def default_source_filename(component,project):
    definition=get_definition(component.library_id)
    extension='.ino' if definition and definition.name in {'Arduino Uno R3','Arduino Nano'} else '.py'
    reference=re.sub(r'[\s<>:"/\\|?*\x00-\x1f]+', '.', component.reference).strip('. ')
    return (reference or 'MC')+'_'+project_code_id(project)+'_code'+extension


def ensure_source(component, project=None, code_directory=None, source_name="", destination=None):
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
    target=Path(destination).expanduser() if destination is not None else None
    if target is not None and not target.is_absolute():
        raise ValueError("Code folder must be an absolute path")
    custom=target.name if target is not None else source_name.strip()
    if custom:
        if (re.search(r'[<>:"/\\|?*\x00-\x1f]',custom) or custom.endswith('.')
                or custom.split('.')[0].upper() in {'CON','PRN','AUX','NUL',
                    *(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}):
            raise ValueError("Enter a valid code filename, without a folder path.")
        if Path(custom).suffix.lower() in {'.py','.ino'}:
            if Path(custom).suffix.lower()!=extension:
                raise ValueError("The code filename extension does not match this board.")
            custom=custom[:-len(extension)]
        if not custom or custom in {'.','..'}:
            raise ValueError("Enter a valid code filename, without a folder path.")
        filename=custom+extension
    definition=get_definition(component.library_id)
    pins=[a for p in definition.pins if (a:=gpio_alias(p.name))]
    if not pins: raise ValueError("No programmable GPIO pins in this definition")
    pin=next((p for p in ("GPIO12","D13","GP0") if p in pins),pins[0])
    # Explicit location is supplied by the UI's separate code-folder setting.
    # The old default remains for legacy callers without settings.
    root=target.parent if target is not None else Path(code_directory).expanduser() if code_directory is not None else appdata_directory()/"code"
    if not root.is_absolute(): raise ValueError("Code folder must be an absolute path")
    identity=sha256(component.id.encode()).hexdigest()[:24]
    folder=root if target is not None else root/project_id/identity if project_id else root/identity
    path=folder/filename
    if (source_name.strip() or target is not None) and path.exists():
        raise ValueError("Code destination already exists; existing files were kept: "+str(path))
    folder.mkdir(parents=True, exist_ok=True)
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


def ensure_code_folder(component, project, code_directory=None, source_name="", destination=None):
    """Create an editable multi-file workspace; never replace existing files."""
    source=ensure_source(component, project, code_directory, source_name, destination)
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


def assign_source(component, source):
    """Link an existing supported entry point without copying or executing it."""
    if component.properties.get("sim_source", "").strip():
        raise ValueError("Detach the assigned code before assigning another source file.")
    from app.libraries.emulator_catalog import profile_for
    definition=get_definition(component.library_id)
    if definition is None or profile_for(definition) is None:
        raise ValueError("Component is not programmable")
    path=Path(source).expanduser().resolve()
    if not path.is_file(): raise ValueError("Assigned source file is missing: "+str(path))
    extension=path.suffix.lower()
    if extension not in {".py",".ino"}: raise ValueError("Choose a Python .py or Arduino .ino source file")
    if extension==".ino" and definition.name not in {"Arduino Uno R3","Arduino Nano"}:
        raise ValueError("Arduino .ino compilation/emulation supports Uno R3 and classic Nano only.")
    if str(path)!=component.properties.get("sim_source"):
        component.properties.pop("sim_code_folder",None)
    component.properties.update(sim_source=str(path),sim_mode="gpio" if extension==".py" else "arduino")
    component.properties.pop("sim_firmware",None)
    return path
