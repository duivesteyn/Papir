# Roadmap

## Implemented

- [x] Python core, RSA signing, login/devices/send/logout/doctor CLI.
- [x] Title/author metadata and saved defaults; native PDF default, opt-in conversion.
- [x] Native SwiftUI on-demand window, file staging and device-name display.
- [x] Forest-green window, original icon, named About page.
- [x] Bundled Python runtime and JSON desktop bridge.
- [x] Browser sign-in with final-URL/code paste, account preferences and sign-out UI.
- [x] ZIP/source packaging, checksums, signatures and relocated-runtime verification.
- [x] Planning and original artwork retained in the same repository.

## Release verification

- [x] Local offline core and account-bridge tests.
- [x] Local arm64 build/signature/relocated engine/TLS certificate checks.
- [ ] CI-built arm64 and Intel packages verified on clean runners.
- [ ] Fresh-account login completed using only the downloaded app.
- [ ] Actual PDF/EPUB delivery checked on a physical Kindle.
- [ ] Download/first-launch flow and older macOS compatibility checked.

## Later

- [ ] Keychain credential storage and automatic browser redirect capture.
- [ ] Upload percentage progress and persistent history.
- [ ] Finder Service / Share extension.
- [ ] PyPI, Homebrew, DMG, updater.
- [ ] Optional Developer ID signing and notarization.
- [ ] Confirm name availability and protocol metadata limits.
