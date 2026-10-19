# ElectroSchem 1.4.0alfa2

- Added provider-specific cloud setup instructions that update when the
  provider selection changes in Settings → Cloud.
- Added the **No cloud / Brak chmury** option. It hides cloud credentials and
  connection controls, forces the default project location to local, and keeps
  local open/save shortcuts available.
- Added a full setup reference in `docs/CLOUD_SETUP.md` for Google Drive,
  OneDrive, Dropbox and Nextcloud.
- Updated the in-app manual and README to direct users to the matching guide.
- Cloud transfers and OAuth flows are unchanged from alfa1; the offline tests
  do not verify real provider accounts or internet connectivity.
