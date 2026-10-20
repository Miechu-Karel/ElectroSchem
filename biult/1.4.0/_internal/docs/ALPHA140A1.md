# ElectroSchem 1.4.0alfa1

- Added a Cloud settings tab with Google Drive, OneDrive, Dropbox and Nextcloud
  configuration, account connection, and local/cloud default project location.
- Added Alt+O and Alt+S for opening and saving through the selected default
  location. Existing Ctrl+O and Ctrl+S remain local file operations.
- Cloud `.els` files are transferred directly between ElectroSchem and the
  selected provider; OAuth refresh tokens and app passwords are encrypted with
  Windows DPAPI and are not stored in project files.
- OAuth application IDs must be configured by the user for Google Drive,
  OneDrive and Dropbox. Nextcloud uses a server URL, username and app password.
- Google: enable Google Drive API, create an OAuth client of type Desktop app,
  and enter its client ID and secret. Google may require adding your account as
  a test user while the consent screen is in testing.
- OneDrive: register a Microsoft Entra app for personal/work accounts, add the
  Mobile and desktop platform redirect `http://localhost/callback`, enable
  public-client flow, and enter its client ID.
- Dropbox: create an app with file metadata and content read/write scopes,
  choose App Folder for the narrowest access or Full Dropbox if you need to
  select an existing folder elsewhere in the account. Register the exact local
  callback URL shown in Settings (default
  `http://127.0.0.1:8765/callback`), then enter its app key and secret.
- Nextcloud: enter the server base URL, username, app password, and a folder
  path such as `/Projects/ElectroSchem`. HTTPS is required except on localhost.
- This is an early alpha: provider OAuth flows still need real-account testing,
  especially OneDrive/Dropbox redirect registration, shared-folder permissions
  and conflict handling. Only `.els` files are listed in the configured folder;
  the folder itself must already exist.

No cloud connection or network request is used by the offline test suite.
