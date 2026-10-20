# ElectroSchem 1.4.0

ElectroSchem 1.4.0 is the stable release promoted from 1.4.0rc2.

## Highlights

- Every wire endpoint without a component pin or another connected wire shows
  a node marker. Shared endpoints and real branches retain the correct
  junction behavior after edits.
- Wire coloring is a visual-only tool. It colors an unbranched connected wire
  run and stops at a component pin or an ambiguous multi-wire junction.
- Cloud settings offer **No cloud**, **GitHub**, **Google Drive** and
  **OneDrive**. Provider-specific setup instructions are included in Settings
  and in the [cloud setup guide](CLOUD_SETUP.md).
- GitHub uses a local clone. The configured branch is pulled on startup when
  it can fast-forward; each successful project save creates a commit, while
  push and manual pull remain user-controlled.
- The portable Windows x64 build is available on the versioned
  [`build-v1.4.0` branch](https://github.com/Miechu-Karel/ElectroSchem/tree/build-v1.4.0).

## Compatibility and setup

Project files use the ELS format v4 introduced in ElectroSchem 1.3.0. Earlier
versions that only support formats v1-v3 reject these files rather than opening
them. Cloud credentials and Git configuration remain local to the computer;
they are not stored inside project files.

See the in-app **Usage Instructions** for shortcuts and editor guidance, the
[GitHub synchronization guide](GITHUB_SYNC.md), and the
[simulation guide](SIMULATION.md).
