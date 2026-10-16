# ElectroSchem 1.3.0alfa11

## Oscyloskop

W oknie pomiarowym w symulatorze regulujesz V/działkę, środek pionowy i czas/działkę
bez zatrzymywania symulacji. Oś pozioma obejmuje osiem działek, pionowa cztery.
Inspekcja oscyloskopu klawiszem E otwiera od razu tryb przebiegu i jego sondy.
Zmiany skali są wspólne dla podglądów oscyloskopów w tym sandboxie.

Przebieg okresowy jest wyzwalany na zboczu rosnącym: pokazujemy ostatnią pełną
ramkę, z osią 0…wybrany czas. Fala nie przesuwa się stale wraz z zegarem. Zmiana
samego sygnału nadal zmienia jego kształt. DC pozostaje poziomą linią; przy braku
pełnej ramki lub wyraźnego wyzwolenia używany jest dostępny fragment historii.

Ustawienia → Symulacja zawierają domyślne V/działkę, czas/działkę oraz automatyczne
dopasowanie obu osi. W trybie automatycznym napięcie dostaje margines, a czas
obejmuje około czterech wykrytych okresów. Bez wykrytego okresu pozostaje ustawiony
czas. Wyłącz automatykę, aby ręcznie regulować obie osie na żywo.

Historia jest ograniczona do 50 000 próbek. Długi wybrany zakres może zawierać
tylko dostępny fragment; wymagane jest odpowiednie próbkowanie sygnału. To nie
oscyloskop o nieograniczonej pamięci ani gwarantowana akwizycja impulsów jednorazowych.

## Zasilacz laboratoryjny

Nowy element ma wyjścia +/−, nastawę napięcia, ograniczenie prądowe, częstotliwość
i falę: stała, sinusoidalna, prostokątna, trójkątna, piłokształtna. Kontrolki są
nad modułem w symulatorze. Wyświetlany jest aktualny prąd, napięcie i tryb CV/CC.
Napięcie AC jest zadawane jako RMS. Natężenie jest **limitem**, a nie wymuszanym
prądem niezależnie od obciążenia: po osiągnięciu limitu napięcie spada.
Zmiany dotyczą tylko kopii sandboxu, nie schematu. Idealny model edukacyjny nie
odwzorowuje ograniczeń pasma, mocy, zabezpieczeń ani wejścia sieciowego zasilacza.

## Kable i goldpiny

- Kabel Męsko-Żeński, Żeńsko-Żeński, Męsko-Męski oraz Goldpin żeński.
- Dotychczasowy Goldpin jest męski. Dłuższy koniec TOP służy do podpięcia
  ruchomej końcówki kabla przeciwnej płci; BOTTOM jest końcem PCB dla przewodu
  schematowego. TOP i BOTTOM pozostają jednym przewodnikiem.
- USB i jumpery można przeciągać/podpinać już w edytorze, nie tylko w symulatorze.
  Zajęte złącze odrzuca kolejną końcówkę. Odciągnięcie od złącza odłącza kabel.
  USB wymaga zgodnego rodzaju końcówki; jumper przeciwnej płci goldpina.
- Podpięcia i położenia z edytora zapisują się w ELS i podlegają Cofnij.
  Podpięcia w symulatorze są lokalne dla sandboxu; zmiana połączenia restartuje go.
- Kable są pasywne. Nie dodają zasilania i nie emulują protokołów USB/HID/PD.

## AI i menu

Panel ma karty rozmowy, pole wiadomości, edycję ostatniego polecenia, zatrzymanie
odpowiedzi i bezpośredni dostęp do edytowalnych komend propozycji. Projekt zmienia
się nadal dopiero po Akceptuj. Zatrzymanie nie gwarantuje anulowania naliczonego
już kosztu u dostawcy.

Zgoda na wysyłanie zapytań jest zapamiętywana osobno dla dostawców. Kolejne
zapytania i regenerowanie nie wyświetlają ponownie okna kosztów. Cofnięcie zgody
w zakładce AI przywraca potwierdzenie. Pierwsza zgoda nadal przedstawia koszty
i liczbę wywołań. Informacja o internecie i kosztach pozostaje w panelu; dla
lokalnego AI zamiast internetu potrzebny jest działający model/serwer lokalny.

Planista ma maksymalnie jedną turę pytań. Odpowiedź trafia bez kolejnego wywiadu
prosto do agenta rysującego razem z oryginalną prośbą i zapamiętanym planem.
Brak preferencji estetycznych lub parametrów mających sensowne ustawienia
katalogowe nie powinien blokować rysowania. Model nadal może zwrócić błędną
propozycję — walidacja i akceptacja użytkownika pozostają wymagane.
Instrukcje są jawnie oddzielone od kontekstu projektu i ograniczają pytania;
pomocnicza dokumentacja: [OpenAI Docs — prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering).

Buzzery mają dodatkowe wyszarzone miejsce w Dźwięk, bez duplikowania definicji.
Kategorię „Scalaki zegarów RTC” przemianowano na „Zegary RTC”.

## Testy

Offline: wyzwalanie i zakresy obu osi, auto-skala, nastawy CV/CC, zmiany na kopii
sandboxu, podpinanie zgodnych i niezgodnych końcówek, rzeczywiste przeciągnięcie
jumpera myszą w Qt, zapis zgody, edycja i zatrzymanie, jedna tura doprecyzowania.
Kontrola wyglądu obejmuje ustawienia, oscyloskop, zasilacz, kable i panel rozmowy.
Nie wykonano płatnych zapytań ani testu na rzeczywistym serwerze modelu AI.
