# ElectroSchem 1.4.1alfa4

This alpha aligns the RFID chip's top and bottom with the two label rows without
moving the labels. GitHub is now a separate provider in Settings → Cloud and
uses the configured local project folder as its repository clone:

- pull on application startup (fast-forward only);
- commit the saved `.els` file locally after each successful local save;
- manual push and pull from File → GitHub;
- Git credentials stay in Git Credential Manager or GitHub Desktop, not in
  ElectroSchem settings.

Google Drive notes now explain that this build requests Google's restricted
`drive` scope and why using the narrower `drive.file` scope would require a
different file-picker workflow.
