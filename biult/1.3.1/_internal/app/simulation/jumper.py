"""Pure connector definitions, shared by the netlist and movable graphics."""
from app.libraries.built_in import AVAILABLE_ITEMS
GENDERS={d.id:pair for d in AVAILABLE_ITEMS for name,pair in (('Kabel Męsko-Żeński',('male','female')),('Kabel Żeńsko-Żeński',('female','female')),('Kabel Męsko-Męski',('male','male'))) if d.name==name}
JUMPER_IDS=set(GENDERS)
CABLE_IDS=JUMPER_IDS|{d.id for d in AVAILABLE_ITEMS if d.name=='Kabel USB'}
