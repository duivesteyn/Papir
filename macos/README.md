# Papir for Mac

An on-demand SwiftUI app around the Python `papir` core. The development build is
now self-contained: it bundles its own Python runtime and requests dependencies.
It always uses the bundled engine by default, independently of any pip-installed
version. No menu bar item or launch-at-login behavior.

## For download users

See [INSTALL.md](INSTALL.md). Sign in through the app, choose the default device
and author in Settings, then drop documents and send. Existing CLI credentials
are reused automatically. Browser sign-in currently requires pasting the final
redirect URL or authorization code; no Terminal is needed.

## Build locally

Requires Apple Command Line Tools, Python 3.10+ (compatible with the pinned
PyInstaller), and internet access for the first dependency installation:

```sh
xcode-select --install
bash macos/build.sh
open macos/build/Papir.app
bash macos/package.sh
```

The script creates `macos/build-tools/`, installs dependencies there, freezes the
Python engine with PyInstaller, compiles the SwiftUI app, and applies a free
ad-hoc signature. It does not require Xcode login or Apple Developer membership.
`PAPIR_BUILD_PYTHON` can point to an existing environment with the build tools.
Builds target the host architecture; build separately on Intel and Apple Silicon.
Choose a Python runtime and build host appropriate to the oldest OS you support.
The Swift interface targets macOS 14+, while the packaged runtime needs separate
compatibility verification. The bundled engine extracts its runtime into a
private temporary directory per invocation and cleans up when that process exits.

`macos/package.sh` creates app and source ZIPs, install instructions, and SHA-256 checksums in
`macos/releases/`. These can be uploaded to GitHub Releases. It packages only
`Papir.app`; credentials, sample documents, and the build environment are excluded.
It does not publish anything or change system security settings.

## Architecture

- `Sources/PapirApp.swift`: native interface, browser sign-in, preferences, sending.
- `engine.py`: frozen engine entry point; keeps normal CLI behavior.
- `papir/desktop.py`: stdin/stdout JSON bridge for account status, sign-in, devices,
  shared defaults, and sign-out. Auth URLs and verifiers are sent over stdin,
  never command-line arguments. Bridge errors do not expose server auth bodies.
- `../art/Iconi/Papir.icns`: canonical retained artwork copied into the bundle.
- `build/Papir.app/Contents/Helpers/papir-engine`: bundled executable.

The GUI sends argument arrays without a shell. Credentials live in the existing
CLI file, not the distributable app. Settings can select an external compatible
engine for development; the bundle is used again on next launch. Title override
is available for one document; author applies to the selected batch. Failed files
remain for retry; successful sends are shown in the in-session history. Sending
uses an indeterminate indicator; structured percentage progress is still planned.

The planning reference is `../planning/`; the latest
on-demand window direction supersedes its menu bar/rumps milestones.

## Verification

```sh
python3 test.py
python3 -m unittest discover -s macos/tests -v
python3 macos/verify-package.py
```

The package verifier extracts the release to a different location and runs its
engine with a minimal PATH, no external Python configuration, and an isolated
credential path. It checks fresh account status, offline sign-in URL generation,
and bundled dependency/runtime behavior without a login or document upload.
It also checks the archive allowlist, architecture, and nested code signature.

## Release limits

The package is ad-hoc signed, unnotarized, and has no Developer ID signature.
Downloaded copies may require Apple's explicit per-app Open Anyway approval.
Local arm64 UI testing has passed. Tagged releases build and check both architectures
on macOS 15 runners; older macOS and an actual fresh-machine download need release QA. Login UI
and token handoff have offline coverage; completing a real fresh account login
requires the user. Keychain, automatic browser redirect capture, persistent
history, Finder Services, DMG layout, and a self-updater remain future work.

## GitHub releases

Push a matching version tag after committing the release to main. The release
workflow builds arm64 and x86_64 on standard macOS 15 runners, verifies both,
and publishes a pre-release with app/source ZIPs, install notes and checksums.
No personal GitHub token or Apple signing secrets are required.
