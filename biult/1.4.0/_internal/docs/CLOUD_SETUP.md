# Konfiguracja chmur w ElectroSchem 1.4.0

W zakładce **Ustawienia → Chmura** wybierz dostawcę. Aplikacja pokazuje pod
polami instrukcję właściwą dla wybranej usługi. Poniżej znajduje się pełna
wersja kroków oraz odnośniki do oficjalnej dokumentacji.

## Google Drive

Ta integracja korzysta ze zwykłego Dysku Google (My Drive), a nie z Google
Cloud Storage. Projekty zajmują miejsce w Twoim koncie Drive. Link folderu jest
akceptowany jako wskazanie miejsca zapisu, ale sam link — także publiczny — nie
zastępuje logowania OAuth. Aplikacja używa konta z uprawnieniem edycji, aby
listować istniejące projekty oraz zapisywać nowe.

Google podaje, że standardowe użycie Google Drive API nie ma dodatkowej opłaty;
osobne progi i możliwe opłaty dotyczą użycia ponad standardowe limity. Zobacz
[aktualne limity i zasady opłat](https://developers.google.com/workspace/drive/api/guides/limits).
ElectroSchem nie używa Google Cloud Storage ani płatnego serwera. Miejsce na
pliki jest ograniczone pojemnością Twojego konta Google.

1. W [Google Cloud Console](https://console.cloud.google.com/) utwórz projekt
   lub wybierz istniejący. To rejestracja dostępu aplikacji do API, a nie
   tworzenie zasobów Google Cloud Storage.
2. Włącz w projekcie [Google Drive API](https://developers.google.com/workspace/drive/api/quickstart/python).
3. Skonfiguruj ekran zgody OAuth. Jeśli aplikacja jest w trybie testowym, dodaj
   konto, którego użyjesz do logowania, jako użytkownika testowego.
4. W Google Auth Platform → Clients utwórz klienta typu **Desktop app**.
   Wklej jego Client ID i Client secret w odpowiednie pola ElectroSchem.
5. Utwórz docelowy folder na Dysku Google. Wklej jego URL albo ID do pola
   folderu; konto musi mieć możliwość edycji.
6. Kliknij **Połącz / sprawdź połączenie** i zaakceptuj dostęp w przeglądarce.

Folder URL określa miejsce docelowe, ale nie nadaje aplikacji dostępu. Przed
zgodą sprawdź zakres pokazany przez Google.

Ta wersja ElectroSchem prosi o szeroki zakres `drive`, klasyfikowany przez
Google jako ograniczony (restricted). Zależnie od trybu publikacji Google może
wymagać weryfikacji aplikacji; ten sam komputer, przeglądarka i Wi-Fi nie
zmieniają konfiguracji OAuth. W trybie **Testing** dodaj używane konto jako
testera. Zakres `drive.file` jest węższy, ale wymagałby Google Picker i zmienił
sposób wybierania istniejących plików, dlatego aplikacja nie przełącza go
automatycznie.

## OneDrive

1. W [Microsoft Entra admin center](https://entra.microsoft.com/) przejdź do
   **App registrations → New registration**. Wybierz typ kont obejmujący konto
   Microsoft używane z OneDrive (zwykle organizacyjne i osobiste).
2. Otwórz **Authentication → Add a platform → Mobile and desktop
   applications**. Zarejestruj przekierowanie `http://localhost/callback` i
   w Advanced settings włącz **Allow public client flows**.
3. W **API permissions** dodaj delegowane uprawnienie Microsoft Graph
   `Files.ReadWrite`. Skopiuj **Application (client) ID** do ElectroSchem.
4. Utwórz folder OneDrive, udostępnij go swojemu kontu i wklej jego link
   udostępniania. Konto musi mieć uprawnienie edycji.
5. Kliknij **Połącz / sprawdź połączenie** i zaloguj się na właściwe konto.

Delegowane `Files.ReadWrite` pozwala aplikacji czytać i zapisywać pliki konta.
Przed zatwierdzeniem sprawdź ekran zgody Microsoft.

Szczegóły dla aplikacji desktopowych opisuje
[Microsoft identity platform](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-overview).

## GitHub

GitHub jest osobnym dostawcą, ale projekty są przechowywane w lokalnym klonie
repozytorium. Wybierz **GitHub** z listy dostawców, ustaw adres repozytorium i
gałąź oraz wskaż klon jako domyślny folder projektów. Przy starcie aplikacja
pobiera całą wskazaną gałąź; może ją zastosować tylko jako fast-forward.
Każdy poprawny zapis pliku `.els` tworzy osobny lokalny commit. Jego opis
zawiera nazwę pliku, datę i godzinę. Ręczny push wysyła całą gałąź, czyli
wszystkie lokalne commity; ręczny pull jest dostępny w menu **Plik → GitHub**. GitHub
autoryzuje Git Credential Manager/GitHub Desktop, ElectroSchem nie
przechowuje tokenu. Szczegóły konfiguracji: [GitHub setup](GITHUB_SYNC.md).

## Brak chmury i codzienna praca

Wybierz **Brak chmury**, aby wyłączyć dostawcę i pozostać przy plikach lokalnych.
W tym trybie domyślne miejsce jest ustawione na lokalne, a pola logowania i
przycisk łączenia są ukryte. Dane logowania wycofanych dostawców Dropbox i
Nextcloud są usuwane przy następnym zapisie ustawień. W trybie chmury `Alt+O` i `Alt+S` używają
ustawionego domyślnego miejsca; `Ctrl+O` i `Ctrl+S` zawsze otwierają i zapisują
lokalnie. W folderze chmury wyświetlane są wyłącznie projekty `.els`, a folder
musi istnieć przed pierwszym połączeniem.

Tokeny OAuth i hasła aplikacji są przechowywane lokalnie, chronione przez
Windows DPAPI i nie są dodawane do plików `.els`. Korzystaj wyłącznie z własnego
konta i nie udostępniaj nikomu sekretów OAuth ani hasła aplikacji.
