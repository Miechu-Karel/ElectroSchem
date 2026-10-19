# ElectroSchem 1.4.1alfa3

- Moved the RFID card chip to the clear area left of its labels, away from the
  decorative inset outlines.
- Clarified that Google Drive uses regular My Drive storage, not Google Cloud
  Storage. A folder link identifies the destination but does not replace OAuth
  authorization for listing and writing files through the Drive API.
- Updated the in-app and full cloud setup guides.

The public folder-link-only approach is not supported for full project
management: a link is not an OAuth token, and the app needs authorized access
to list projects and upload saved files.
