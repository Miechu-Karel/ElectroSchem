"""Bounded, read-only electrical probes; no firmware, host I/O, audio or camera."""
from copy import deepcopy
from time import perf_counter
from math import isfinite
from app.core.models import Project
from app.libraries.built_in import get_definition
from app.libraries.simulation_catalog import behavior_for
from app.simulation.engine import Circuit, SimulationError


def simulate_proposal(project, index, language="en"):
    clone = Project.from_dict(deepcopy(project.to_dict()))
    sheet = clone.sheets[index]
    from app.core.assets import expand_assets, with_asset_dependencies
    clone.custom_components=with_asset_dependencies(clone.custom_components)
    sheet=expand_assets(sheet,clone.custom_components)
    report = {"status": "not_tested", "seconds": 0, "steps": 0,
              "limits": "Bounded electrical probe only. No firmware execution, full transient verification or real-world safety guarantee.",
              "faults": {}, "warnings": {}, "peak_current_A": {}, "peak_brightness": {}}
    if len(sheet.components) > 40 or len(sheet.wires) > 120:
        report["reason"] = "Układ przekracza limit rozmiaru automatycznego testu." if language == "pl" else "Circuit exceeds the automatic probe size limit."
        return report
    pin_count = 0
    for component in sheet.components:
        definition = get_definition(component.library_id, clone.custom_components)
        if definition is None:
            report["status"] = "blocked"
            report["reason"] = "Nieznany element biblioteki." if language == "pl" else "Unknown library component."
            return report
        pin_count += len(definition.pins)
        if pin_count > 160:
            report["reason"] = "Układ przekracza limit 160 pinów automatycznego testu." if language == "pl" else "Circuit exceeds the 160-pin automatic probe limit."
            return report
        model = behavior_for(definition)
        if model and model.kind in {"mcu", "mcu_gpio"}:
            report["reason"] = "Płytki z kodem wymagają testu w sandboxie; ten test nie odczytuje ani nie uruchamia plików kodu." if language == "pl" else "Firmware boards require manual testing in the sandbox; this probe never reads or runs code files."
            return report
        for key in ("sim_source", "sim_code_folder", "sim_firmware", "sim_bootrom"):
            component.properties.pop(key, None)
    started = perf_counter()
    try:
        circuit = Circuit(sheet, clone.custom_components, language)
        dt = min(.0001, circuit.maximum_time_step())
        for _ in range(250):
            result = circuit.step(dt)
            report["steps"] += 1; report["seconds"] = result.time
            report["faults"].update(result.faults); report["warnings"].update(result.warnings)
            for source, target in ((result.currents, report["peak_current_A"]), (result.brightness, report["peak_brightness"])):
                for key, value in source.items():
                    if isfinite(value): target[key] = max(target.get(key, 0), abs(value))
            if result.faults or perf_counter()-started > .3: break
        report["status"] = "fault" if report["faults"] else "sampled"
    except (SimulationError, ValueError, ArithmeticError, KeyError, TypeError) as error:
        report["status"] = "blocked"; report["reason"] = str(error)[:2000]
    return report
