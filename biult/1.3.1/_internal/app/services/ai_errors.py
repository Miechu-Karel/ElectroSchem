"""Offline error explanations; no credentials, provider calls or retries."""
import re
def explanation(message,provider,language):
    pl=language=='pl'
    match=re.search(r'(?:http[_ :]+)(\d{3})',message,re.I); code=int(match[1]) if match else None
    reasons={
      400:('Invalid request parameters or unsupported model settings.','Nieprawidłowe parametry zapytania lub ustawienia nieobsługiwane przez model.'),
      401:('Authentication failed; check the provider API key.','Nie udało się uwierzytelnić; sprawdź klucz API dostawcy.'),
      403:('The key/project lacks permission for this model.','Klucz lub projekt nie ma uprawnień do tego modelu.'),
      404:('The model/API endpoint is unavailable for this account.','Model lub adres API jest niedostępny dla tego konta.'),
      429:('Quota or rate limit reached. Check limits/billing and wait before retrying.','Osiągnięto limit użycia lub liczby zapytań. Sprawdź limity i rozliczenia, odczekaj przed ponowieniem.'),
      500:('Internal provider error; try again later.','Wewnętrzny błąd dostawcy; spróbuj ponownie później.'),
      502:('The provider gateway received an invalid response; try later.','Serwer pośredniczący dostawcy otrzymał błędną odpowiedź; spróbuj później.'),
      503:('The AI service is temporarily unavailable or overloaded. Try again later.','Usługa AI jest chwilowo niedostępna lub przeciążona. Spróbuj ponownie za chwilę.'),
      504:('The provider gateway timed out; shorten the request or try later.','Serwer dostawcy przekroczył czas oczekiwania; skróć prośbę lub spróbuj później.'),
    }
    lower=message.lower()
    if provider=='local' and code==401: text=('The local server requires a valid token. Enter a token from LM Studio → Server Settings → Manage Tokens in ElectroSchem AI Settings. Running the server alone does not authenticate requests.','Lokalny serwer wymaga poprawnego tokenu. Wpisz token z LM Studio → Server Settings → Manage Tokens w ustawieniach AI ElectroSchem. Samo uruchomienie serwera nie uwierzytelnia zapytań.')[pl]
    elif provider=='local' and code==404: text=('Check the displayed server port and OpenAI-compatible /v1/chat/completions endpoint and loaded model ID.','Sprawdź wyświetlany port serwera, endpoint OpenAI-compatible /v1/chat/completions i identyfikator załadowanego modelu.')[pl]
    elif code in reasons: text=reasons[code][pl]
    elif 'command repair' in lower or 'invalid assistant response' in lower or 'proposal rejected' in lower:
        text=('The model returned a response that failed validation. Check the diagnostic and try rephrasing the request if the problem persists.','Model zwrócił odpowiedź, która nie przeszła walidacji. Sprawdź szczegóły błędu i spróbuj inaczej sformułować pytanie, jeśli problem się powtarza.')[pl]
    elif 'json compatibility retry' in lower:
        text=('The local server rejected the fallback JSON-object request too. Check its OpenAI-compatible chat endpoint and model support for JSON output.','Lokalny serwer odrzucił również zapasowe żądanie JSON-object. Sprawdź endpoint OpenAI-compatible i obsługę JSON przez model.')[pl]
    elif 'plan' in lower: text=('The AI returned an invalid internal response. Try again or rephrase the request.','AI zwróciło nieprawidłową odpowiedź. Spróbuj ponownie lub inaczej sformułuj pytanie.')[pl]
    elif 'timed out' in lower or 'timeout' in lower: text=('Waiting time expired. Check server performance and connectivity.','Przekroczono czas oczekiwania. Sprawdź działanie serwera i połączenie.')[pl]
    elif 'key' in lower or 'klucz' in lower: text=('Configure the selected provider API key in Settings.','Ustaw klucz API wybranego dostawcy w Ustawieniach.')[pl]
    elif 'local ai' in lower or 'lokaln' in lower: text=('Check that the local server is running and the model is installed.','Sprawdź, czy lokalny serwer jest uruchomiony, a model zainstalowany.')[pl]
    elif 'logic' in lower or 'logicz' in lower: text=('The AI response did not pass validation. Try again or rephrase the question.','Odpowiedź AI nie przeszła walidacji. Spróbuj ponownie lub inaczej sformułuj pytanie.')[pl]
    elif 'response' in lower or 'proposal' in lower or 'line ' in lower: text=('The model returned an invalid response format. Check the diagnostic and try again.','Model zwrócił odpowiedź w nieprawidłowym formacie. Sprawdź szczegóły błędu i spróbuj ponownie.')[pl]
    else: text=('Request or local validation failed; check parameters and connectivity.','Zapytanie lub lokalna walidacja nie powiodły się; sprawdź parametry i połączenie.')[pl]
    text+='\n\n'+('Your project was not changed.','Projekt nie został zmieniony.')[pl]
    if provider!='local': text+='\n'+('Another request may incur API costs.','Kolejne zapytanie może wiązać się z kosztami API.')[pl]
    return text
