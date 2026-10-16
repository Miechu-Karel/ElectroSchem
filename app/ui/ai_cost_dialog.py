"""Honest per-operation billing consent; no account-status guesses or requests."""
from html import escape
from PySide6.QtWidgets import QDialog,QVBoxLayout,QTextBrowser,QDialogButtonBox

def confirm_requests(parent,settings,count=1,course=False):
    pl=settings.language=="pl"
    def t(en,polish): return polish if pl else en
    if settings.ai_provider=='local':
        from PySide6.QtWidgets import QMessageBox
        message=t(f'Send up to {count*2+7 if course else 6} requests to your local AI server (each exercise may get one correction; planning/drawing may also use a JSON compatibility fallback and one command repair)? No cloud API is called by ElectroSchem. The server and model must be running.','Wysłać do '+str(count*2+7 if course else 6)+' zapytań do lokalnego serwera AI (każde ćwiczenie może dostać jedną próbę poprawy; planowanie i rysowanie mogą dodatkowo użyć awaryjnego formatu JSON i pojedynczej naprawy komend)? ElectroSchem nie wywołuje API w chmurze. Serwer i model muszą być uruchomione.')
        return QMessageBox.question(parent,t('Local AI requests','Lokalne zapytania AI'),message)==QMessageBox.StandardButton.Yes
    provider="OpenAI" if settings.ai_provider=="openai" else "Google Gemini"
    model=settings.openai_model if settings.ai_provider=="openai" else settings.gemini_model
    dialog=QDialog(parent); dialog.setWindowTitle(t("API requests and costs","Zapytania API i koszty")); dialog.resize(680,430)
    layout=QVBoxLayout(dialog); browser=QTextBrowser(); browser.setOpenExternalLinks(True); layout.addWidget(browser)
    details=t("You are about to send a request using your API key. ElectroSchem does not charge a fee and does not enable billing at the provider.",
        "Zapytania zostaną wysłane przez Twój klucz API. ElektroSchem nie pobiera opłat i nie włącza rozliczeń u dostawcy.")
    details+=' '+t('Approval is remembered for this provider, including future requests and regeneration; API costs may recur. Revoke in AI Settings.','Zgoda zostanie zapamiętana dla tego dostawcy, także dla kolejnych zapytań i regenerowania; koszty API mogą naliczać się ponownie. Cofnij zgodę w ustawieniach AI.')
    billing=t("OpenAI API usage is billed according to the model and input/output tokens, possibly including reasoning tokens. API keys do not use your ChatGPT subscription. Credits or your API billing account cover the cost.",
        "OpenAI rozlicza API według modelu i tokenów wejściowych/wyjściowych, w tym możliwych tokenów rozumowania. Klucz API nie korzysta z abonamentu ChatGPT. Koszt pokrywają kredyty lub konto rozliczeniowe API.") if settings.ai_provider=="openai" else t(
        "Gemini Free Tier can be free for eligible models within its limits. Paid Tier is billed according to model and token usage. Exceeding a free limit does not itself upgrade the project to Paid Tier. Check the project linked to this key in Google AI Studio.",
        "Gemini Free Tier może być bezpłatne dla dostępnych modeli w granicach limitów. Paid Tier rozlicza model i użyte tokeny. Przekroczenie darmowego limitu samo nie przełącza projektu na Paid Tier. Sprawdź projekt tego klucza w Google AI Studio.")
    total=t(f"Up to {count*2+1} exercise requests (one correction per failed exercise, plus at most one local JSON fallback), followed by up to 6 local project requests: planning, optional clarification, drawing, fallbacks for planner and drawing, and one command repair. Cloud providers use up to {count*2+4} requests including exercise corrections.",
        f"Do {count*2+1} zapytań ćwiczeniowych (jedna poprawa błędnego zadania i najwyżej jeden lokalny fallback JSON), a potem do 6 lokalnych zapytań projektowych: planowanie, ewentualne doprecyzowanie, rysowanie, fallbacki dla planisty i rysowania oraz jedna naprawa komend. Dostawcy chmurowi mogą wysłać do {count*2+4} zapytań razem z poprawkami ćwiczeń.") if course else t("Up to 6 local project requests: planning, optional clarification, drawing, JSON compatibility fallbacks for planner and drawing, and one command repair. Cloud providers use at most 4. No drawing until essential requirements are resolved. Regeneration starts another request sequence.","Do 6 lokalnych zapytań projektowych: planowanie, ewentualne doprecyzowanie, rysowanie, fallback JSON planisty i rysowania oraz jedna naprawa komend. Dostawcy chmurowi: maksymalnie 4. Rysowanie nie ruszy bez ustalenia istotnych wymagań. Ponowne generowanie rozpoczyna nową serię zapytań.")
    data=t("Exercises send built-in circuits only. The project request sends your conversation, working sheet and library. Code files and API keys are not part of the project context.",
        "Ćwiczenia wysyłają wyłącznie wbudowane układy. Zapytanie dotyczące projektu wysyła rozmowę, roboczy arkusz i bibliotekę. Pliki kodu i klucze nie są częścią kontekstu projektu.")
    unknown=t("Exact cost and billing status are unknown to ElectroSchem. A larger sheet, longer chat and longer response use more tokens. Cancel stops further requests; already processed usage cannot be undone. Each invalid exercise may get one correction attempt; there are no further automatic retries.",
        "ElektroSchem nie zna statusu rozliczeń ani dokładnej ceny. Większy arkusz, dłuższa rozmowa i odpowiedź zużywają więcej tokenów. Anulowanie zatrzymuje kolejne zapytania, ale nie cofa już rozliczonego użycia. Każde błędne ćwiczenie może dostać jedną próbę poprawy; dalszych automatycznych ponowień nie ma.")
    retries=t("Output limit: up to 24,000 tokens per generation (the provider may impose a lower limit). Gemini can retry once after a server error and try one alternate model after 404/503: up to three generation attempts per logical request. Model discovery adds GET requests. These attempts are not guaranteed free. OpenAI does not retry automatically. Rate limits (429) and missing access are not bypassed.",
        "Limit odpowiedzi: do 24 000 tokenów na generację (dostawca może narzucić niższy limit). Gemini może ponowić żądanie raz po błędzie serwera i spróbować jednego innego modelu po 404/503: do trzech prób generacji na jedno zapytanie. Wykrywanie modeli dodaje żądania GET. Nie gwarantujemy bezpłatności tych prób. OpenAI nie ponawia automatycznie. Nie obchodzimy limitu 429 ani braku dostępu.")
    url="https://developers.openai.com/api/docs/pricing" if settings.ai_provider=="openai" else "https://ai.google.dev/gemini-api/docs/pricing"
    browser.setHtml(f"<h2>{provider}</h2><p>{t('Model','Model')}: {escape(model or t('automatic selection','wybór automatyczny'))}</p>"+"".join("<p>"+escape(x)+"</p>" for x in (total,details,billing,data,unknown,retries))+f'<p><a href="{url}">{t("Official pricing","Oficjalny cennik")}</a></p>')
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t("Send requests","Wyślij zapytania")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("Cancel","Anuluj"))
    buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
    return dialog.exec()==QDialog.DialogCode.Accepted
