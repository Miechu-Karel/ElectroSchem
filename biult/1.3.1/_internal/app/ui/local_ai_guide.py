"""Offline, bilingual setup guide; opening it never starts or downloads a model."""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout


def guide_html(language='en'):
    pl = language == 'pl'
    def t(en, polish): return polish if pl else en
    html = '<h1>' + t('Local AI: setup tutorial', 'Lokalne AI: tutorial konfiguracji') + '</h1>'
    html += '<p>' + t(
        'Use an existing local model, not training from scratch. B means billion parameters; quantization (e.g. Q4) reduces memory use. Parameter count alone does not guarantee correct circuits. The suggestions below are starting estimates, not hardware requirements measured with ElectroSchem.',
        'Uruchamiasz gotowy model lokalny, nie trenujesz go od zera. B oznacza miliardy parametrów; kwantyzacja (np. Q4) zmniejsza zapotrzebowanie na pamięć. Sama liczba parametrów nie gwarantuje poprawnych układów. Poniższe propozycje to orientacyjny punkt startowy, nie wymagania zmierzone w ElektroSchem.') + '</p>'
    html += '<h2>' + t('How large a model?', 'Ile parametrów potrzeba?') + '</h2><ul>'
    for en, polish in [
        ('7-8B: experiment with simple circuits; start with 16 GB system RAM. Small models may fail command/JSON validation.', '7-8B: próby prostych układów; zacznij od 16 GB RAM. Małe modele mogą nie radzić sobie z poleceniami i formatem JSON.'),
        ('14B: a reasonable next step for harder instructions; plan around 32 GB RAM. More memory is needed for long project context.', '14B: rozsądny kolejny krok do trudniejszych poleceń; zaplanuj około 32 GB RAM. Długi kontekst projektu wymaga dodatkowej pamięci.'),
        ('32B: a larger hardware budget, around 64 GB RAM as a starting estimate. It still needs electrical validation.', '32B: większy budżet sprzętowy, orientacyjnie około 64 GB RAM na początek. Nadal konieczna jest weryfikacja elektryczna.'),
        ('For example, Qwen3 Q4 tags 8b / 14b / 32b download about 5.2 / 9.3 / 20 GB of weights. These are disk sizes, NOT total RAM/VRAM requirements. Allow room for the OS, context cache and runtime. A supported GPU accelerates inference; CPU/RAM execution can be much slower.', 'Przykładowe modele Qwen3 Q4 8b / 14b / 32b mają około 5,2 / 9,3 / 20 GB wag do pobrania. To rozmiary na dysku, NIE pełne wymagania RAM/VRAM. Zostaw zapas na system, kontekst i silnik. Obsługiwana karta graficzna przyspiesza pracę; wykonywanie na CPU/RAM może być znacznie wolniejsze.'),
    ]: html += '<li>' + t(en, polish) + '</li>'
    html += '</ul><h2>1. Ollama (Windows)</h2><ol>'
    steps = [
        ('Download the Windows installer from ollama.com/download/windows and install it. Open a NEW PowerShell window, not the ElectroSchem editor terminal.', 'Pobierz instalator Windows z ollama.com/download/windows i zainstaluj. Otwórz NOWE okno PowerShell, nie terminal poleceń ElektroSchem.'),
        ('Download one local model, for example with the command below. This requires Internet and several GB of disk space; ElectroSchem does not run the command for you.', 'Pobierz jeden model lokalny, np. poniższą komendą. Wymaga to internetu i kilku GB miejsca; ElektroSchem nie wykonuje jej za Ciebie.'),
        ('Keep Ollama running. The Windows app serves the API in the background. If using only the CLI, start ollama serve; do not start a second server if the port is already occupied.', 'Pozostaw Ollama uruchomioną. Aplikacja Windows udostępnia API w tle. Przy samej wersji CLI uruchom ollama serve; nie uruchamiaj drugiego serwera, jeśli port jest już zajęty.'),
        ('In ElectroSchem Settings → AI, choose Local AI, URL http://127.0.0.1:11434/v1 and the exact installed model name, e.g. qwen3:8b. Save. No cloud API key is needed.', 'W ElektroSchem: Ustawienia → AI → Lokalne AI. Adres http://127.0.0.1:11434/v1, dokładna nazwa zainstalowanego modelu, np. qwen3:8b. Zapisz. Klucz chmurowego API nie jest potrzebny.'),
    ]
    for en, polish in steps: html += '<li>' + t(en, polish) + '</li>'
    html += '</ol><pre>ollama pull qwen3:8b\nollama list\nollama ps</pre>'
    html += '<p>' + t('The example model has not been certified against the ElectroSchem exercise suite. Start with a resistor/LED project and inspect the proposal before accepting.', 'Przykładowy model nie został certyfikowany w zestawie ćwiczeń ElektroSchem. Zacznij od projektu rezystor/LED i obejrzyj propozycję przed akceptacją.') + '</p>'
    html += '<h2>2. LM Studio</h2><p>' + t(
        'Alternatively download a local instruction model in LM Studio, load it, and start its local server in the Developer tab. Use http://127.0.0.1:1234/v1 (or its displayed port) and the exact model identifier exposed by the server. The server must support Chat Completions and JSON object responses.',
        'Alternatywnie w LM Studio pobierz lokalny model instrukcyjny, załaduj go i uruchom lokalny serwer w zakładce Developer. Użyj http://127.0.0.1:1234/v1 (lub portu wyświetlanego przez serwer) i dokładnego identyfikatora udostępnionego modelu. Serwer musi obsługiwać Chat Completions i odpowiedzi JSON object.') + '</p>'
    html += '<h2>' + t('Context, privacy and troubleshooting', 'Kontekst, prywatność i rozwiązywanie problemów') + '</h2><ul>'
    html += '<li>'+t('HTTP 401: the server is running but rejected authentication. If LM Studio requires authentication, create a token in Server Settings → Manage Tokens and enter it in ElectroSchem Settings → AI → Local API token. It is protected by Windows DPAPI and is not stored in the project. Use the exact displayed server port; 1234 is only the default. The endpoint is OpenAI-compatible /v1/chat/completions, not native /api/v1/chat.',
        'HTTP 401: serwer działa, ale odrzucił uwierzytelnianie. Jeśli LM Studio wymaga autoryzacji, utwórz token w Server Settings → Manage Tokens i wpisz go w ElectroSchem: Ustawienia → AI → Token lokalnego API. Token chroni Windows DPAPI; nie jest zapisywany w projekcie. Użyj portu wyświetlanego przez serwer; 1234 jest tylko domyślnym. Endpoint to OpenAI-compatible /v1/chat/completions, a nie natywne /api/v1/chat.')+'</li>'
    for en, polish in [
        ('Context is separate from parameters: it holds rules, the library, the project and conversation. Increase context in server settings within the model limit if input is truncated. Larger context consumes more memory; ollama ps shows the allocated context and CPU/GPU split. There is no fixed context size sufficient for every project.', 'Kontekst to nie parametry: mieści zasady, bibliotekę, projekt i rozmowę. Jeśli wejście jest obcinane, zwiększ kontekst w ustawieniach serwera w granicach modelu. Większy kontekst zużywa więcej pamięci; ollama ps pokazuje jego przydział i podział CPU/GPU. Nie ma jednej wielkości wystarczającej dla wszystkich projektów.'),
        ('Connection refused: start the server and check its port. Unknown model: compare the name with ollama list or the LM Studio server. Incomplete/invalid JSON: try an instruction model with a larger context, a simpler task or a stronger model. A larger model can also exceed the request timeout on a slow computer.', 'Brak połączenia: uruchom serwer i sprawdź port. Nieznany model: porównaj nazwę z ollama list lub serwerem LM Studio. Niepełny/błędny JSON: spróbuj modelu instrukcyjnego z większym kontekstem, prostszego zadania lub mocniejszego modelu. Większy model może też przekroczyć limit czasu na wolnym komputerze.'),
        ('Only loopback URLs (127.0.0.1, localhost, ::1) are accepted. Local requests send project/chat/library to your server, with no automatic cloud fallback. Choose a LOCAL model, not a cloud-backed tag. Initial downloads need Internet; local inference needs no provider API billing, but uses your hardware and electricity. Check the server’s own privacy/update settings.', 'Obsługiwane są tylko adresy tego komputera (127.0.0.1, localhost, ::1). Zapytania lokalne przekazują projekt/czat/bibliotekę Twojemu serwerowi; nie ma automatycznego przełączenia na chmurę. Wybierz model LOKALNY, nie wariant chmurowy. Pobranie wymaga internetu; lokalna praca nie nalicza opłat API dostawcy, ale zużywa Twój sprzęt i prąd. Sprawdź też prywatność i aktualizacje samego serwera.'),
        ('The introductory exercises store verified examples locally, not new model weights. They are not permanent fine-tuning. Review outputs and run simulation; neither parameters nor passing exercises guarantee electrical safety.', 'Ćwiczenia wprowadzające zapisują zweryfikowane przykłady lokalnie, nie nowe wagi modelu. Nie jest to trwały fine-tuning. Sprawdzaj wyniki i uruchamiaj symulację; ani liczba parametrów, ani zaliczenie ćwiczeń nie gwarantują bezpieczeństwa układu.'),
    ]: html += '<li>' + t(en, polish) + '</li>'
    html += '</ul><h2>' + t('Official sources (checked 2026-10-10)', 'Oficjalne źródła (sprawdzone 10.10.2026)') + '</h2><ul>'
    for url, title in [
        ('https://docs.ollama.com/windows', 'Ollama: Windows'),
        ('https://docs.ollama.com/context-length', 'Ollama: context length'),
        ('https://ollama.com/library/qwen3', 'Qwen3: models and sizes'),
        ('https://lmstudio.ai/docs/developer/core/server', 'LM Studio: local server'),
        ('https://lmstudio.ai/docs/developer/core/authentication', 'LM Studio: API tokens (checked 2026-10-13)'),
    ]: html += f'<li><a href="{url}">{title}</a></li>'
    return html + '</ul>'


class LocalAIGuide(QDialog):
    def __init__(self, language='en', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Lokalne AI — tutorial' if language == 'pl' else 'Local AI — tutorial')
        self.resize(820, 700)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser(); self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(guide_html(language)); layout.addWidget(self.browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('Zamknij' if language == 'pl' else 'Close')
        buttons.rejected.connect(self.reject); layout.addWidget(buttons)
