"""Bundled few-shot editor examples, not training of provider model weights."""
import json
from app.libraries.built_in import AVAILABLE_ITEMS


def examples():
    ids = {item.name: item.id for item in AVAILABLE_ITEMS}
    commands = '\n'.join((
        f'ADD_COMPONENT type={ids["Bateria"]} id=B1 x=200 y=300 value=9 unit=V',
        f'ADD_COMPONENT type={ids["Rezystor"]} id=R1 x=400 y=200 value=1 unit=kΩ',
        f'ADD_COMPONENT type={ids["Masa GND"]} id=G1 x=400 y=400',
        'ROTATE_COMPONENT id=B1 angle=90',
        'CONNECT from=B1 to=R1 from_pin=0 to_pin=0',
        'CONNECT from=R1 to=G1 from_pin=1 to_pin=0',
        'CONNECT from=B1 to=G1 from_pin=1 to_pin=0'))
    from app.services.power_recipe import commands as recipe_commands,summary
    return [
        {"request": "Create a 9 V battery with a 1 kΩ load on an empty sheet.",
         "response": {"summary": "Battery and resistor load. Inspect the simulator report before accepting.", "commands": commands}},
        {"request": "Change the existing R1 resistance to 2.2 kΩ.",
         "response": {"summary": "R1 changed; the rest of the proposal is preserved.", "commands": 'SET_PROPERTY id=R1 property=value value="2.2 kΩ"'}},
        {"request": "The simulator reports a missing LED colour or capacitor voltage rating.",
         "response": {"summary": "Set the missing rating using the actual existing component reference; do not recreate the circuit.", "commands": ""}},
        {'request':'On an empty A3 landscape sheet: USB-C PD 20 V / 5 A, common GND, separate 3.3/5/9/12 V at 1.5 A and 25 V at 1 A, goldpin outputs. Educational capacities, not active CC.',
         'response':{'summary':summary(),'commands':recipe_commands()}},
    ]


def instruction_examples():
    return "\nBuilt-in editor examples (adapt IDs, references and coordinates to the actual sheet):\n" + json.dumps(examples(), ensure_ascii=False)
