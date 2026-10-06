# Distribution

## Current free route

- Source in `https://github.com/duivesteyn/Papir`, MIT licence.
- Native `Papir.app` with Python engine included, free ad-hoc signature.
- Versioned ZIPs on GitHub Releases, with source ZIP, installation notes and hashes.
- Users may need Apple's per-app Open Anyway approval for unnotarized downloads.
- No Apple Developer membership or signing secrets required for these builds.

## Release process

`.github/workflows/release.yml` builds and verifies Apple Silicon and Intel
packages on standard macOS runners when a matching `v*` tag is pushed.
The release is published only after both architecture jobs pass. The workflow
uses GitHub's job token solely for release publication.

Local equivalent:

```sh
bash macos/build.sh
bash macos/package.sh
python3 macos/verify-package.py
```

Python CLI distribution is independent; installing from source works with
`pip install .`. PyPI and Homebrew publication are still planned.

Developer ID signing, notarization, DMG presentation and a self-updater can be
added later. Full fresh-account and device-delivery checks require user testing.
