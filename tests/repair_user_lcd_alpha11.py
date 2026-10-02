"""Explicit one-file project update, verified before saving, with a backup."""
from datetime import datetime
from pathlib import Path
import shutil
import sys
from app.core.project_file import load_project,save_project
from app.core.board_code import project_code_id
from app.simulation.engine import Circuit
from app.libraries.built_in import get_definition

path=Path(sys.argv[1]).resolve()
project=load_project(path)
board=next(c for c in project.sheets[0].components if get_definition(c.library_id).name=="Raspberry Pi 5")
source=Path(__file__).resolve().parents[1]/"examples"/(board.reference+"_"+project_code_id(project)+"_code.py")
if not source.is_file(): raise RuntimeError("Verified project-specific LCD source is missing")
board.properties.update(sim_source=str(source),sim_mode="gpio")
result=Circuit(project.sheets[0]).step(.001)
if result.faults or not any("LCD dziala!" in text for text in result.readings.values()):
    raise RuntimeError("LCD verification failed; original project was not changed")
backup=path.with_name(path.stem+".before-alfa11."+datetime.now().strftime("%Y%m%d-%H%M%S")+".els")
if backup.exists(): raise RuntimeError("Backup already exists; refusing to overwrite")
shutil.copy2(path,backup)
project.metadata["modified_at"]=datetime.now().astimezone().isoformat(timespec="seconds")
save_project(path,project)
check=Circuit(load_project(path).sheets[0]).step(.001)
if check.faults or not any("LCD dziala!" in text for text in check.readings.values()):
    raise RuntimeError("Saved project verification failed; original is preserved in "+str(backup))
print("Updated:",path)
print("Backup:",backup)
print("Code:",source)
print("LCD:",list(check.readings.values()))
