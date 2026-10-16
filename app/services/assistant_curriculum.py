"""Twenty actual provider exercises, locally verified and persisted.

This is onboarding/evaluation and reusable few-shot context, NOT a change to
Gemini/OpenAI model weights. No user sheet, key or code file enters the cache.
Network requests are initiated only after explicit UI consent to their cost.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer, QSaveFile, QIODevice
from app.core.models import Project, Sheet
from app.libraries.built_in import AVAILABLE_ITEMS
from app.core.editor_commands import execute_batch

REVISION="alpha4-course-1"

def tasks():
    ids={d.name:d.id for d in AVAILABLE_ITEMS}; result=[]
    def add_task(name, commands, check):
        translations={"9 V resistor load, R1=":"Obciążenie 9 V, R1=", "Series load: R1=1 kΩ and R2=":"Szeregowo: R1=1 kΩ i R2=", "Parallel loads: R1=1 kΩ and R2=":"Równolegle: R1=1 kΩ i R2=",
            "5 V red LED, 1 kΩ current limiter":"Czerwona LED 5 V, ogranicznik 1 kΩ", "5 V green LED, 1 kΩ current limiter":"Zielona LED 5 V, ogranicznik 1 kΩ", "5 V blue LED, 1 kΩ current limiter":"Niebieska LED 5 V, ogranicznik 1 kΩ", "5 V white LED, 1 kΩ current limiter":"Biała LED 5 V, ogranicznik 1 kΩ",
            "NOT gate, input false":"Bramka NOT, wejście 0", "NOT gate, input true":"Bramka NOT, wejście 1", "AND gate, first input true, second false":"Bramka AND, wejścia 1 i 0", "AND gate, first input true, second true":"Bramka AND, wejścia 1 i 1"}
        pl=name
        for en,translation in translations.items(): pl=pl.replace(en,translation)
        result.append({"id":len(result)+1,"name":name,"name_pl":pl,"commands":commands,"check":check})
    def add(name,ref,x,y,value="",unit=""):
        return f'ADD_COMPONENT type={ids[name]} id={ref} x={x} y={y}'+(f' value="{value}" unit="{unit}"' if value else "")
    def connect(a,ap,b,bp): return f"CONNECT from={a} to={b} from_pin={ap} to_pin={bp}"
    base=[add("Bateria","B1",200,300,"9","V"),"ROTATE_COMPONENT id=B1 angle=90",add("Masa GND","G1",600,500)]
    for r in (470,1000,2200,4700):
        commands=base+[add("Rezystor","R1",400,200,str(r),"Ω"),connect("B1",0,"R1",0),connect("R1",1,"G1",0),connect("B1",1,"G1",0)]
        add_task(f"9 V resistor load, R1={r} Ω",commands,{"current":{"reference":"R1","value":9/r}})
    for r in (470,1000,2200,4700):
        commands=base+[add("Rezystor","R1",400,200,"1000","Ω"),add("Rezystor","R2",600,200,str(r),"Ω"),
            connect("B1",0,"R1",0),connect("R1",1,"R2",0),connect("R2",1,"G1",0),connect("B1",1,"G1",0)]
        add_task(f"Series load: R1=1 kΩ and R2={r} Ω",commands,{"current":{"reference":"R1","value":9/(1000+r)}})
    for r in (1000,2200,4700,10000):
        commands=base+[add("Rezystor","R1",400,200,"1000","Ω"),add("Rezystor","R2",400,380,str(r),"Ω"),
            connect("B1",0,"R1",0),connect("B1",0,"R2",0),connect("R1",1,"G1",0),connect("R2",1,"G1",0),connect("B1",1,"G1",0)]
        add_task(f"Parallel loads: R1=1 kΩ and R2={r} Ω",commands,{"current":{"reference":"R2","value":9/r}})
    for color in ("red","green","blue","white"):
        commands=[add("Szyna Zasilania +5V","S1",200,200),add("Rezystor","R1",400,200,"1000","Ω"),
            add("Dioda LED 5mm","L1",600,200),f"SET_PROPERTY id=L1 property=color value={color}",add("Masa GND","G1",600,500),
            connect("S1",0,"R1",0),connect("R1",1,"L1",0),connect("L1",1,"G1",0)]
        add_task(f"5 V {color} LED, 1 kΩ current limiter",commands,{"lit":"L1"})
    for state in ("false","true"):
        commands=[add("Input","I1",200,200),add("Bramka NOT","N1",400,200),add("Output","O1",600,200),
            f"SET_PROPERTY id=I1 property=sim_closed value={state}",connect("I1",0,"N1",0),connect("N1",1,"O1",0)]
        add_task(f"NOT gate, input {state}",commands,{"logic":{"reference":"O1","high":state=="false"}})
    for state in ("false","true"):
        commands=[add("Input","I1",200,200),add("Input","I2",200,380),add("Bramka AND","A1",400,280),add("Output","O1",600,280),
            "SET_PROPERTY id=I1 property=sim_closed value=true",f"SET_PROPERTY id=I2 property=sim_closed value={state}",
            connect("I1",0,"A1",0),connect("I2",0,"A1",1),connect("A1",2,"O1",0)]
        add_task(f"AND gate, first input true, second {state}",commands,{"logic":{"reference":"O1","high":state=="true"}})
    for task in result: task["commands"]="\n".join(task["commands"])
    for task in result:
        if task["id"] in {17,18}: task["stimulus"]={"I1":task["id"]==18}
        elif task["id"] in {19,20}: task["stimulus"]={"I1":True,"I2":task["id"]==20}
    return result

def validate_response(task, answer):
    from app.services.proposal_simulation import simulate_proposal
    from app.simulation.engine import Circuit
    project=execute_batch(Project(sheets=[Sheet()]),0,answer["commands"])
    commands=answer["commands"]
    # Initial input levels are test fixtures, not a hidden requirement on the
    # provider's startup state. Persist the applied stimulus with the solution.
    from app.libraries.built_in import get_definition
    for reference,high in task.get("stimulus",{}).items():
        component=next((c for c in project.sheets[0].components if c.reference==reference),None)
        if component is None or get_definition(component.library_id).symbol!="logic_input":
            raise ValueError("Exercise requires logic input "+reference)
        stimulus=f"SET_PROPERTY id={reference} property=sim_closed value={'true' if high else 'false'}"
        project=execute_batch(project,0,stimulus); commands+="\n"+stimulus
    report=simulate_proposal(project,0)
    if report["status"]!="sampled" or report["faults"]: raise ValueError("Exercise circuit failed the electrical probe")
    refs={c.reference:c.id for c in project.sheets[0].components}; check=task["check"]
    if "current" in check:
        spec=check["current"]; measured=report["peak_current_A"].get(refs.get(spec["reference"]),0)
        if abs(measured-spec["value"])>max(1e-7,spec["value"]*.02): raise ValueError("Unexpected load current")
    if "lit" in check and report["peak_brightness"].get(refs.get(check["lit"]),0)<=.01: raise ValueError("LED is not lit")
    if "logic" in check:
        spec=check["logic"]; circuit=Circuit(project.sheets[0])
        for _ in range(10): reading=circuit.step().readings.get(refs.get(spec["reference"]),"")
        if not reading.startswith(("HIGH","LOW")) or reading.startswith("HIGH")!=spec["high"]:
            raise ValueError(f"Wrong logic output: {spec['reference']} should be {'HIGH' if spec['high'] else 'LOW'}, got {reading or 'no output'}. Check gate type and pin connections.")
        # One matching output is insufficient: an AND with a floating input
        # could accidentally pass the NOT/HIGH exercise. Check its full table.
        cases=[({'I1':False},True),({'I1':True},False)] if task['id'] in {17,18} else [({'I1':a,'I2':b},a and b) for a in (False,True) for b in (False,True)]
        for levels,expected in cases:
            stimulus='\n'.join(f"SET_PROPERTY id={ref} property=sim_closed value={'true' if high else 'false'}" for ref,high in levels.items())
            probe=execute_batch(project,0,stimulus); circuit=Circuit(probe.sheets[0])
            for _ in range(10): output=circuit.step().readings.get(refs.get(spec['reference']),'')
            if not output.startswith(('HIGH','LOW')) or output.startswith('HIGH')!=expected:
                raise ValueError(f"Wrong logic output: truth table {levels}, expected {'HIGH' if expected else 'LOW'}, got {output or 'no output'}.")
    return {"task_id":task["id"],"request":task["name"],"commands":commands,
            "summary":answer["summary"][:2000],"observations":check,"verified":True}

def profile_key(settings):
    model=(settings.local_ai_url+':'+settings.local_ai_model) if settings.ai_provider=='local' else settings.openai_model if settings.ai_provider=="openai" else settings.gemini_model
    return sha256((REVISION+":"+settings.ai_provider+":"+model).encode()).hexdigest()[:20]

def cache_path(settings):
    from app.core.settings import appdata_directory
    return appdata_directory()/("assistant_course_"+profile_key(settings)+".json")

def read_profile(settings,path=None):
    path=path or cache_path(settings)
    if not path.is_file(): return {"version":REVISION,"key":profile_key(settings),"exercises":[]}
    if path.stat().st_size>3000000: raise ValueError("Assistant course cache too large")
    profile=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile,dict): raise ValueError("Invalid course cache")
    if profile.get("version")!=REVISION or profile.get("key")!=profile_key(settings): return {"version":REVISION,"key":profile_key(settings),"exercises":[]}
    if not isinstance(profile.get("exercises"),list) or len(profile["exercises"])>20: raise ValueError("Invalid course cache")
    seen=set()
    for record in profile["exercises"]:
        if (not isinstance(record,dict) or type(record.get("task_id")) is not int
                or not 1<=record["task_id"]<=20 or record["task_id"] in seen
                or record.get("verified") is not True
                or not all(isinstance(record.get(key),str) for key in ("request","commands","summary"))
                or record.get("observations")!=tasks()[record["task_id"]-1]["check"]):
            raise ValueError("Invalid course cache")
        seen.add(record["task_id"])
    return profile

def write_profile(settings,profile,path=None):
    raw=json.dumps(profile,ensure_ascii=False).encode("utf-8"); file=QSaveFile(str(path or cache_path(settings)))
    if len(raw)>3000000: raise ValueError("Course cache too large")
    if not file.open(QIODevice.OpenModeFlag.WriteOnly): raise OSError(file.errorString())
    if file.write(raw)!=len(raw) or not file.commit(): raise OSError(file.errorString())

def remembered_knowledge(settings):
    profile=read_profile(settings)
    return {"revision":REVISION,"scope":"Locally verified examples replayed as context, not trained model weights.",
            "completed":len(profile["exercises"]),"exercises":profile["exercises"]}

class Curriculum(QObject):
    progress=Signal(int,int,str)
    completed=Signal()
    failed=Signal(str)
    def __init__(self,settings,parent=None,client=None,path=None):
        super().__init__(parent)
        from app.services.assistant_client import AssistantClient
        self.settings=deepcopy(settings); self.path=path; self.profile=read_profile(settings,path)
        self.client=client or AssistantClient(self); self.running=False; self.pending=None
        self.client.completed.connect(self.receive); self.client.failed.connect(self.fail)
    def start(self):
        self.running=True; self.next()
    def next(self):
        if not self.running: return
        completed={x["task_id"] for x in self.profile["exercises"]}
        self.pending=next((task for task in tasks() if task["id"] not in completed),None)
        if self.pending is None:
            self.running=False; self.completed.emit(); return
        task=self.pending; self.progress.emit(len(completed)+1,20,task["name_pl"] if self.settings.language=="pl" else task["name"])
        # Isolated empty sheet: no user's project or files. IDs/names/pins are
        # the real installed catalog; model has to produce its own solution.
        context={"sheet":Project().to_dict()["sheets"][0],"grid_step":20,
            "drawing_regions_scene":[[100,100,900,650]],
            "library":[{"id":d.id,"name":d.name_en,"pins":[p.name for p in d.pins]} for d in AVAILABLE_ITEMS],
            "expected_observations":task["check"],"test_input_levels":task.get("stimulus",{}),"required_references":list(task.get("stimulus",{}))}
        try: self.client.start(self.settings,"Onboarding exercise. On the empty sheet build: "+task["name"]+". Use the references explicitly named in the task, R1/R2 for resistors, L1 for LED and O1 for logic output. Return commands, not a verbal answer.",context,[])
        except (ValueError,OSError) as error: self.fail(str(error))
    def receive(self,answer):
        if not self.running: return
        try:
            record=validate_response(self.pending,answer)
            self.profile["exercises"].append(record); write_profile(self.settings,self.profile,self.path)
        except (ValueError,KeyError,TypeError) as error:
            # Exercise-level checks (simulation and truth tables) happen after
            # command parsing, so send their diagnostic through the same single
            # bounded repair pass as editor proposal validation.
            if self.client.repair_last_response(getattr(self.client,'_raw_answer',None),error):
                self.progress.emit(len(self.profile['exercises'])+1,20,
                    (self.pending['name_pl'] if self.settings.language=='pl' else self.pending['name'])+
                    (' — poprawiam' if self.settings.language=='pl' else ' — repairing'))
                return
            self.fail(str(error)); return
        except OSError as error: self.fail(str(error)); return
        QTimer.singleShot(0,self.next)
    def fail(self,message):
        if not self.running: return
        self.running=False; self.failed.emit(message)
    def cancel(self):
        self.running=False; self.client.cancel()
