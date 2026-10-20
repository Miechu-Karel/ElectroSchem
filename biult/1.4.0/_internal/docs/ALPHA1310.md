# ElectroSchem 1.3.0alfa10

## Pomiary i symulacja

- Stykanie: multimetr piszczy przy oporze poniżej 10 Ω. Rozłączenie sond,
  zmiana trybu lub globalne „Wycisz dźwięk” wyłącza sygnał. Symbol testera
  ciągłości również może wydawać sygnał.
- Otwarte przełączniki nie przenoszą zasilania do odłączonej gałęzi podczas
  sprawdzania, czy wolno mierzyć opór. Stara historia napięcia nie blokuje pomiaru.
  Obwód pod napięciem nadal blokuje pomiar Ω; zero sinusoidy nie oznacza odłączenia AC.
- Oscyloskop ma stałą pionową skalę: domyślnie ±10 V, regulację V/działkę oraz
  przesunięcia środka. Sygnał poza zakresem jest obcinany, a nie automatycznie
  przesuwany na środek. Rozmiary ekranu: 480×260, 640×350, 800×440.
- Ustawienie „Zatrzymaj symulację po awarii” domyślnie włączone. Wyłączenie pozwala
  kontynuować zdrowe, niezależne wyspy elektryczne; cała uszkodzona wyspa jest
  odłączana. Jeśli nie pozostał zdrowy obwód, symulacja zatrzymuje się. Nie jest
  to ustawienie zamykające aplikację.
- Źródło AC: napięcie skuteczne RMS lub jawne minimum/maksimum, również z offsetem
  DC. Dotychczasowe projekty pozostają w RMS. Kształt fali pozostaje wybieralny.

## Biblioteka

Nazwy scalaków zaczynają się od oznaczenia i opisują funkcję. Dodano osobne grupy
wzmacniaczy, timerów, liczników, dekoderów, kluczy, driverów, komunikacji, zasilania,
czujników, RTC i pamięci. Istniejące identyfikatory biblioteki pozostają bez zmian.
NE567 zastępuje wcześniejszą niejednoznaczną prośbę „NE56”: jest osobnym scalakiem
dekodera tonu, z ośmioma wyprowadzeniami. Jego model obecnie odwzorowuje tylko
obciążenie zasilania, **nie PLL ani rozpoznawanie tonu**. Pomoc podaje ograniczenia
każdego modelu i rozróżnia scalak w obudowie od gotowego modułu.

## Asystent AI

Osobny planista rozbija prośbę na maksymalnie 12 zadań z zależnościami i warunkami
sprawdzenia. Brak ważnych danych powoduje pytania zamiast rysowania. Agent rysujący
dostaje plan, pierwotną prośbę i kontekst schematu; projekt nadal zmienia dopiero
„Akceptuj”. Dodano reguły zasilania, GPIO, limitowania prądu, pomiarów, AC oraz
uczciwego deklarowania ograniczeń modeli. To kontekst i zapamiętane ćwiczenia,
nie trening wag modelu.

Planowanie i rysowanie to do dwóch logicznych zapytań do dostawcy. Chmurowe
wywołania mogą kosztować; zgoda pokazuje też osobne ćwiczenia startowe i możliwość
wcześniej opisanych prób transportu Gemini. Nie dodano nowych automatycznych
płatnych ponowień. Regeneracja powtarza również etap planowania.

Kliknięcie błędu AI otwiera krótki lokalny opis. HTTP 503 oznacza chwilową
niedostępność/przeciążenie usługi, nie dowodzi błędnego klucza ani schematu.

## Weryfikacja

Testy offline obejmują stykanie, wyciszanie, odłączone gałęzie, RMS i limity AC,
stałą skalę wykresu, ustawienia awarii, schemat planu, pytania planisty i opis 503.
Nie wykonują płatnych zapytań ani nie potwierdzają dźwięku na fizycznym urządzeniu.
