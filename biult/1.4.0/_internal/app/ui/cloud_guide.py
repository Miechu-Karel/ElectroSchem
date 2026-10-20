"""Provider-specific setup instructions shown in Settings > Cloud."""


def cloud_guide_html(provider: str, language: str = "en") -> str:
    """Return concise, provider-matched setup steps as rich-text HTML."""
    pl = language == "pl"
    guides = {
        "google_drive": (
            "Google Drive",
            """<p>To zwykły Dysk Google (My Drive), a nie Google Cloud Storage. Pliki zajmują miejsce na Twoim koncie Drive. Link do folderu można wkleić, ale sam link — także publiczny — nie zastępuje logowania OAuth potrzebnego ElectroSchem do listowania i zapisywania plików przez API.</p>
<p>Według <a href="https://developers.google.com/workspace/drive/api/guides/limits">aktualnych zasad Google</a> standardowe użycie Google Drive API nie ma dodatkowej opłaty. Google opisuje osobne progi i możliwe opłaty dopiero za użycie ponad standardowy limit. ElectroSchem nie potrzebuje Google Cloud Storage ani własnego serwera.</p>
<ol>
<li>W <a href="https://console.cloud.google.com/">Google Cloud Console</a> zarejestruj konfigurację aplikacji OAuth i włącz w projekcie <a href="https://developers.google.com/workspace/drive/api/quickstart/python">Google Drive API</a>. To konfiguracja dostępu aplikacji, nie uruchamianie Google Cloud Storage.</li>
<li>Skonfiguruj ekran zgody OAuth. Gdy aplikacja jest w trybie testowym, dodaj swoje konto Google jako użytkownika testowego.</li>
<li>W Google Auth Platform → Clients utwórz klienta typu <b>Desktop app</b>. Skopiuj Client ID i Client secret do pól powyżej.</li>
<li>Utwórz folder na Dysku Google i wklej jego adres z przeglądarki albo samo ID folderu. Konto musi mieć możliwość edycji.</li>
<li>Kliknij „Połącz / sprawdź połączenie” i zaakceptuj dostęp w przeglądarce.</li>
</ol>
<p>Ta wersja aplikacji prosi o szeroki zakres <code>drive</code>, który Google klasyfikuje jako ograniczony (restricted). W zależności od trybu publikacji aplikacji Google może wymagać weryfikacji; ten sam komputer, przeglądarka i Wi-Fi tego nie zmieniają. W trybie testowym konto musi być dodane jako tester. Węższy zakres <code>drive.file</code> wymagałby selektora Google i zmieniłby sposób wyboru istniejących plików, więc nie jest tu używany.</p>
<p>Adres folderu wskazuje miejsce docelowe, ale nie nadaje aplikacji dostępu. Przed zgodą sprawdź zakres dostępu do Dysku pokazany przez Google.</p>""",
            """<p>This connects to regular Google Drive (My Drive), not Google Cloud Storage. Files use your Drive account storage. You can paste a folder link, but the link alone — even a public one — does not replace the OAuth sign-in ElectroSchem needs to list and save files through the API.</p>
<p>Google currently says standard Google Drive API use has no additional charge; separate thresholds and possible charges apply only above standard quotas. ElectroSchem does not need Google Cloud Storage or its own server.</p>
<ol>
<li>In the <a href="https://console.cloud.google.com/">Google Cloud Console</a>, register the app's OAuth configuration and enable the <a href="https://developers.google.com/workspace/drive/api/quickstart/python">Google Drive API</a> for that project. This configures app access; it does not use Google Cloud Storage.</li>
<li>Configure the OAuth consent screen. If the app is in testing mode, add your Google account as a test user.</li>
<li>Under Google Auth Platform → Clients, create a <b>Desktop app</b> client. Copy its Client ID and Client secret into the fields above.</li>
<li>Create a folder in Drive and paste its browser URL or folder ID. The connected account needs edit access.</li>
<li>Click “Connect / test connection” and approve access in your browser.</li>
</ol>
<p>This app version requests the broad <code>drive</code> scope, which Google classifies as restricted. Depending on the app's publishing status, Google may require verification; using the same computer, browser, and Wi-Fi does not change that. In Testing mode, the account must be added as a test user. The narrower <code>drive.file</code> scope would require Google's picker and change how existing files are selected, so it is not used here.</p>
<p>The folder URL identifies the destination; it does not grant the app access. Review Google's consent screen before approving the requested Drive access.</p>""",
            "https://developers.google.com/workspace/drive/api/quickstart/python"),
        "onedrive": (
            "OneDrive",
            """<ol>
<li>W <a href="https://entra.microsoft.com/">Microsoft Entra admin center</a> → App registrations wybierz <b>New registration</b>. Wybierz typ kont obejmujący Twoje konto Microsoft/OneDrive (zwykle organizacyjne i osobiste).</li>
<li>Na stronie aplikacji otwórz Authentication → Add a platform → <b>Mobile and desktop applications</b>. Dodaj przekierowanie <code>http://localhost/callback</code> i w Advanced settings włącz <b>Allow public client flows</b>.</li>
<li>W API permissions dodaj delegowane uprawnienie Microsoft Graph <code>Files.ReadWrite</code>. Skopiuj <b>Application (client) ID</b> do pola powyżej.</li>
<li>Utwórz folder OneDrive, udostępnij go swojemu kontu i skopiuj link udostępniania do pola folderu. Link musi dawać Ci możliwość edycji.</li>
<li>Kliknij „Połącz / sprawdź połączenie” i zaloguj się do właściwego konta Microsoft.</li>
</ol>
<p>Delegowane <code>Files.ReadWrite</code> pozwala aplikacji czytać i zapisywać pliki konta. Przed zatwierdzeniem sprawdź ekran zgody Microsoft.</p>""",
            """<ol>
<li>In the <a href="https://entra.microsoft.com/">Microsoft Entra admin center</a> → App registrations, select <b>New registration</b>. Choose an account type that includes your Microsoft/OneDrive account (usually organizational and personal accounts).</li>
<li>On the app page, open Authentication → Add a platform → <b>Mobile and desktop applications</b>. Add <code>http://localhost/callback</code> and enable <b>Allow public client flows</b> under Advanced settings.</li>
<li>Under API permissions, add the delegated Microsoft Graph permission <code>Files.ReadWrite</code>. Copy the <b>Application (client) ID</b> into the field above.</li>
<li>Create a OneDrive folder, share it with your account, and paste its sharing link in the folder field. You need edit access.</li>
<li>Click “Connect / test connection” and sign in to the correct Microsoft account.</li>
</ol>
<p>The Microsoft Graph <code>Files.ReadWrite</code> permission allows the app to read and write files covered by that consent. Review Microsoft's consent screen before approving.</p>""",
            "https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-overview"),
        "github": (
            "GitHub",
            """<p>GitHub działa jako osobny dostawca, ale używa lokalnego klonu repozytorium w folderze projektów ElectroSchem. Ustaw adres repozytorium i nazwę gałęzi; przy starcie aplikacja pobiera aktualizacje całej tej gałęzi i stosuje je tylko jako fast-forward.</p>
<ol>
<li>Zainstaluj Git for Windows i zaloguj się przez Git Credential Manager lub GitHub Desktop.</li>
<li>Sklonuj repozytorium do folderu projektów wskazanego w zakładce Ogólne albo ustaw folder projektów na już istniejący klon.</li>
<li>Wpisz adres repozytorium HTTPS/SSH i gałąź, która jest aktualnie sprawdzona w lokalnym klonie.</li>
<li>W Git ustaw <code>user.name</code> i <code>user.email</code>. Każdy zapis pliku <code>.els</code> tworzy osobny commit, nawet gdy treść się nie zmieniła; opis zawiera nazwę pliku i datę z godziną.</li>
</ol>
<p>Ręczny push wysyła wszystkie lokalne commity gałęzi; ręczny pull jest w menu Plik → GitHub. ElectroSchem nie przechowuje tokenu. Rozbieżnej historii nie resetuje ani nie nadpisuje; konflikt trzeba rozwiązać w GitHub Desktop lub innym kliencie Git.</p>""",
            """<p>GitHub is a separate provider backed by a local repository clone in ElectroSchem's project folder. Set the repository URL and branch; on startup the app pulls the complete branch and applies it only as a fast-forward.</p>
<ol>
<li>Install Git for Windows and sign in through Git Credential Manager or GitHub Desktop.</li>
<li>Clone the repository into the project folder configured under General settings, or set that folder to an existing clone.</li>
<li>Enter the HTTPS/SSH repository URL and the branch currently checked out in the local clone.</li>
<li>Set <code>user.name</code> and <code>user.email</code> in Git. Every <code>.els</code> save creates its own commit, even when its contents are unchanged; the subject includes the filename and local date/time.</li>
</ol>
<p>Manual push sends all local commits on the branch; manual pull is in File → GitHub. ElectroSchem does not store a token. Divergent history is never reset or overwritten; resolve conflicts in GitHub Desktop or another Git client.</p>""",
            "https://docs.github.com/en/get-started/git-basics/about-remote-repositories"),
        "none": (
            "Brak chmury" if pl else "No cloud",
            "<p>Chmura jest wyłączona. Projekty będą otwierane i zapisywane lokalnie. Skróty Alt+O i Alt+S użyją ustawień lokalnych; Ctrl+O i Ctrl+S nadal pozostają operacjami lokalnymi.</p>",
            "<p>Cloud storage is disabled. Projects will be opened and saved locally. Alt+O and Alt+S use local settings; Ctrl+O and Ctrl+S remain local operations.</p>",
            ""),
    }
    selected = guides.get(provider, guides["none"])
    title, polish_instructions, english_instructions, source = selected
    instructions = polish_instructions if pl else english_instructions
    common = (
        "<p><b>Po połączeniu:</b> ustaw folder i wybierz domyślnie Lokalnie albo W chmurze. Alt+O/Alt+S używają tego wyboru, a Ctrl+O/Ctrl+S zawsze pracują lokalnie. W chmurze widoczne są tylko pliki <code>.els</code>; folder musi już istnieć.</p>"
        if pl else
        "<p><b>After connecting:</b> set the folder and choose Local or Cloud as the default. Alt+O/Alt+S use that choice; Ctrl+O/Ctrl+S always use local files. Only <code>.els</code> files are listed, and the folder must already exist.</p>"
    ) if provider not in {"none", "github"} else ""
    source_html = (f'<p><a href="{source}">Oficjalna dokumentacja dostawcy</a></p>' if pl else
                   f'<p><a href="{source}">Provider documentation</a></p>') if source else ""
    safety = (
        "<p>Dane OAuth i hasła aplikacji pozostają lokalnie zaszyfrowane przez Windows DPAPI i nie są dodawane do pliku projektu. Zakres dostępu zobaczysz na ekranie zgody dostawcy.</p>"
        if pl else
        "<p>OAuth credentials and app passwords stay locally protected with Windows DPAPI and are not included in project files. Review the provider's consent screen to see the requested access.</p>"
    ) if provider not in {"none", "github"} else ""
    return f"<h3>{title}</h3>{instructions}{common}{source_html}{safety}"
