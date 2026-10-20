# GitHub synchronization in ElectroSchem 1.4.0

GitHub synchronization uses Git installed on the computer and the configured
local project folder. ElectroSchem does not store a GitHub password or token.

## One-time setup

1. Install Git for Windows and sign in through Git Credential Manager or GitHub
   Desktop.
2. Clone the repository you want to use into the project folder configured in
   ElectroSchem's General settings, or set that folder to an existing clone.
3. Check out the branch you want ElectroSchem to use. Select **GitHub** as the
   provider in Settings → Cloud, then enter the same repository URL and branch.
4. Configure `user.name` and `user.email` in Git so local commits can be made.
5. ElectroSchem always pulls and fast-forwards the configured branch when it
   starts with GitHub selected as the provider.

## Daily use

- Every successful local `.els` save creates a commit for that project file,
  including saves where its contents did not change. The commit subject is the
  saved filename followed by the local date, time, and time-zone offset.
- Push is always manual: use File → GitHub → Push to GitHub.
- Push sends the configured branch, including all local commits not yet on the
  remote; it does not push only the most recent save.
- Pull can be started manually from File → GitHub → Pull from GitHub.
- Pull only fast-forwards. If local and remote history diverged, ElectroSchem
  does not reset or overwrite the work; resolve the branch in GitHub Desktop or
  another Git client, then retry.
- Projects saved outside the configured repository are not included in Git
  commits.

GitHub is a separate provider from the Google Drive and OneDrive APIs, but
uses a local clone as its project folder. A public web URL to a folder is not a
Git remote.
