"""Explicit, bounded live API smoke test. Does not run the curriculum or save keys."""
import sys,json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.core.settings import load_settings
from app.ui.main_window import MainWindow
from app.services.assistant_client import AssistantClient

PROMPT='Zrób układ zasilany przez USB-C który z urzyciem odpowiedznich przetwornic i stabilizatorów, który wyprowadza napięciea 3.3V,5V,9V,12V,25V każde oprócz 25V ma mieć max 1,5A, a 25V ma mieć 1A max natężenia na wyjściu Wyjścia mają być nie połączone ze sobą ale mają mieć wyjście na goldpiny i ma być też wejście do GND (też przez goldpiny)'
app=QApplication([]); settings=load_settings()
window=MainWindow(settings,start_setup=False); client=AssistantClient()
window.project.sheets[0].paper_size='A2'; window._rebuild_tabs()
out=Path('output/rc1301'); out.mkdir(parents=True,exist_ok=True)
clarified='--clarified' in sys.argv
draw_only='--draw' in sys.argv
request=PROMPT
if clarified or draw_only:
    request+='\nPotwierdzone: wspólna masa i pięć niezależnych dodatnich szyn; zewnętrzny zasilacz USB-C PD 100 W, ustalone 20 V / 5 A. W teście przedstaw edukacyjny model już wynegocjowanego 20 V za pomocą zasilacza laboratoryjnego podłączonego do VBUS/GND złącza USB-C; nie podawaj 20 V przez USB-A ani na płytkę SBC. Cztery przetwornice buck i jedna boost. sim_max_current to tylko granica przeciążenia, NIE CC: nie udawaj działającego ograniczenia prądu. Podaj to ograniczenie w podsumowaniu. Brak na razie decyzji użytkownika o CC — nie zmieniaj tego wymagania i nie twierdź, że zostało spełnione. Goldpiny łącz rysowanymi przewodami wyłącznie przez BOTTOM (index 1). Bez nakładania przewodów. Arkusz A2. Wykonaj schemat edukacyjny z jasno opisanymi ograniczeniami.'
context=window._ai_context()
if '--compact' in sys.argv:
    names={'Zasilacz laboratoryjny','Port USB C','Goldpin','Masa GND','Przetwornica DC-DC Step-Up','Przetwornica DC-DC Step-Down','Kondensator Elektrolityczny','Kondensator','Rezystor'}
    context['library']=[d for d in context['library'] if d['name'] in names]
    request+='\nDla tego testu użyj wyłącznie przekazanych części. Rysuj tylko niezbędne elementy: wejście, pięć przetwornic, sześć goldpinów i ewentualne obciążenia testowe. Krótkie podsumowanie; bez nieobsługiwanych dodatkowych elementów.'
if draw_only:
    context['task_plan']={'goal':'Edukacyjny model pięciu wyjść, 20 V / 5 A PD ustawione zewnętrznie, wspólna masa; bez emulacji PD ani CC.', 'questions':[], 'tasks':[{'id':1,'task':'Zasilacz laboratoryjny 20 V / 5 A, gniazdo USB-C zasilane z VBUS/GND; cztery buck 3.3/5/9/12 V (1.5 A) i boost 25 V (1 A); wyprowadź niezależne szyny i wspólne GND na BOTTOM goldpinów.','check':'Przelicz 68.95 W wyjść / sprawność, nie łącz dodatnich szyn; odstępy i rozłączne trasy; uczciwy opis braku PD i hard CC.','depends_on':[]}]}
def completed(plan):
    name='live-plan-clarified.json' if clarified else 'live-plan.json'
    (out/name).write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(plan,ensure_ascii=True),flush=True)
    if clarified and not plan['questions']:
        from app.services.power_requirements import validate_plan
        try: validate_plan(plan,request)
        except ValueError as error: failed(str(error)); return
        client.completed.disconnect(completed); client.completed.connect(drawn)
        context['task_plan']=plan; print('Starting live drawing',flush=True)
        deadline.start(115000); client.start(settings,request,context,[])
    else: app.exit(0)
def drawn(answer):
    (out/'live-drawing.json').write_text(json.dumps(answer,ensure_ascii=False,indent=2),encoding='utf-8')
    from app.core.editor_commands import execute_batch
    from app.core.project_file import save_project
    from app.services.proposal_simulation import simulate_proposal
    try:
        proposal=execute_batch(window.project,0,answer['commands'])
        save_project(proposal,out/'USB-C-5-output-test.els')
        report=simulate_proposal(proposal,0,'pl')
        (out/'live-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Drawing validated; probe:',report['status'],flush=True); app.exit(0)
    except (ValueError,TypeError,KeyError) as error: failed('Drawing rejected: '+str(error))
def failed(error):
    # Provider errors are normalised by the client; never dump requests or headers.
    (out/'live-error.txt').write_text(error,encoding='utf-8')
    print('Live test failed:',error,flush=True); app.exit(1)
client.completed.connect(completed); client.failed.connect(failed)
client.gemini.progress.connect(lambda status:print('API phase:',status,flush=True))
client.gemini.completed.connect(lambda answer:(out/'live-raw-response.json').write_text(json.dumps(answer,ensure_ascii=False,indent=2),encoding='utf-8'))
def expired():
    (out/'live-error.txt').write_text('Live API deadline exceeded (115 s)',encoding='utf-8'); client.cancel(); app.exit(2)
deadline=QTimer(); deadline.setSingleShot(True); deadline.timeout.connect(expired); deadline.start(115000)
print('Starting live planner:',settings.ai_provider,flush=True)
if draw_only:
    client.completed.disconnect(completed); client.completed.connect(drawn)
client.start(settings,request,context,[],purpose='draw' if draw_only else 'plan')
sys.exit(app.exec())
