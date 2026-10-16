"""Loopback-only Chat Completions adapter for an existing local AI server."""
from urllib.parse import urlsplit,urlunsplit

def endpoint(base):
    parsed=urlsplit(base.strip())
    if parsed.scheme not in {'http','https'} or parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Local AI requires a loopback HTTP(S) URL without credentials or query parameters')
    try: parsed.port
    except ValueError as error: raise ValueError('Invalid local AI port') from error
    path=parsed.path.rstrip('/')
    if path not in {'','/v1'}: raise ValueError('Local AI base URL must end in /v1')
    return urlunsplit((parsed.scheme,parsed.netloc,'/v1/chat/completions','',''))

def body(model,instructions,content,purpose='draw',json_mode='schema'):
    if not model.strip() or len(model)>200 or any(ord(c)<32 for c in model): raise ValueError('Choose an installed local AI model in Settings')
    if purpose=='plan':
        schema={'type':'object','properties':{'goal':{'type':'string'},'tasks':{'type':'array','items':{'type':'object','properties':{'id':{'type':'integer'},'task':{'type':'string'},'check':{'type':'string'},'depends_on':{'type':'array','items':{'type':'integer'}}},'required':['id','task','check','depends_on'],'additionalProperties':False}},'questions':{'type':'array','items':{'type':'string'}}},'required':['goal','tasks','questions'],'additionalProperties':False}
        name='electroschem_plan'
    else:
        schema={'type':'object','properties':{'summary':{'type':'string'},'commands':{'type':'string'}},'required':['summary','commands'],'additionalProperties':False}
        name='electroschem_answer'
    response_format={'type':'json_schema','json_schema':{'name':name,'strict':True,'schema':schema}}
    if json_mode=='object': response_format={'type':'json_object'}
    elif json_mode!='schema': raise ValueError('Invalid local AI JSON mode')
    return {'model':model.strip(),'messages':[{'role':'system','content':instructions},{'role':'user','content':content}],
            'stream':False,'max_tokens':3072,'response_format':response_format}

def answer(result):
    if not isinstance(result,dict): raise ValueError('Local AI response must be an object')
    if 'error' in result: raise ValueError('Local AI endpoint rejected request; use OpenAI-compatible /v1/chat/completions, not /api/v1/chat')
    choices=result.get('choices',[])
    if not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict) or choices[0].get('finish_reason') not in {'stop',None}: raise ValueError('Local AI did not complete the response')
    if not isinstance(choices[0].get('message'),dict): raise ValueError('Local AI response has no message')
    message=choices[0].get('message',{})
    text=message.get('content')
    # Some reasoning-oriented Qwen adapters put structured output in this
    # field while leaving the standard OpenAI-compatible content empty.
    if not isinstance(text,str) or not text.strip(): text=message.get('reasoning_content')
    if not isinstance(text,str): raise ValueError('Local AI response has no text')
    return text


def localized_error(message,language):
    if language!='pl': return message
    messages={
        'Local AI requires a loopback HTTP(S) URL without credentials or query parameters':'Lokalne AI wymaga adresu HTTP(S) tego komputera (127.0.0.1, localhost lub ::1), bez loginu i parametrów zapytania.',
        'Invalid local AI port':'Nieprawidłowy port lokalnego serwera AI.',
        'Local AI base URL must end in /v1':'Adres serwera lokalnego musi kończyć się na /v1 (lub nie zawierać ścieżki).',
        'Choose an installed local AI model in Settings':'Wybierz zainstalowany model lokalnego AI w Ustawieniach.',
        'Local AI response must be an object':'Lokalne AI zwróciło nieprawidłowy format odpowiedzi.',
        'Local AI did not complete the response':'Lokalne AI nie dokończyło odpowiedzi. Sprawdź limit generowania i możliwości modelu.',
        'Local AI response has no message':'Odpowiedź lokalnego AI nie zawiera wiadomości.',
        'Local AI response has no text':'Odpowiedź lokalnego AI nie zawiera tekstu.',
        'Local AI response redirected or failed':'Lokalny serwer zwrócił błąd lub niedozwolone przekierowanie.',
        'Invalid local API token':'Nieprawidłowy token lokalnego API: nie może zawierać spacji ani znaków spoza ASCII.',
    }
    if 'Local AI request failed ' in message:
        import re
        match=re.search(r'HTTP (\d{3})',message)
        code=match[1] if match else 'network error'
        prefix=message.split('Local AI request failed ',1)[0]
        hints={'401':'Serwer odrzucił uwierzytelnianie. Wpisz token z LM Studio → Server Settings → Manage Tokens w ustawieniach AI aplikacji.',
               '403':'Token nie ma uprawnień do tego modelu. Sprawdź uprawnienia tokenu w LM Studio.',
               '404':'Sprawdź port serwera i endpoint OpenAI-compatible /v1/chat/completions oraz identyfikator modelu.',
               '400':'Sprawdź nazwę załadowanego modelu, długość kontekstu i obsługę formatu JSON.',
               '503':'Lokalny model jest niedostępny lub serwer przeciążony.'}
        detail=message.split('): ',1)[1].strip() if '): ' in message else ''
        if code=='network error':
            hint='Nie można połączyć się z lokalnym serwerem. Sprawdź adres, port i czy serwer nasłuchuje.'
        else:
            hint=hints.get(code,'Sprawdź adres i port uruchomionego serwera oraz załadowany model.')
        return prefix+f'Lokalne AI: HTTP {code}. '+hint+(f' Odpowiedź serwera: {detail}' if detail else '')
    if message.startswith('Local AI endpoint rejected'): return 'Lokalne API odrzuciło zapytanie. Użyj endpointu OpenAI-compatible /v1/chat/completions (nie /api/v1/chat). Sprawdź port w LM Studio.'
    return messages.get(message,message)
