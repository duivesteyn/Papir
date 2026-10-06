# Papir Mac app

`macos/` contains the native SwiftUI application. Bundle ID: `com.bmd.papir`.

## Current implementation

- Regular app window, opened from Finder/Dock when needed.
- Forest green `#123325`, ivory `#F3EADB`, retained Papir icon, native controls.
- File drop and open panel, batch staging, author override, single-file title.
- Actual destination name, refresh, saved device/library/all defaults.
- Explicit PDF conversion, sending indicator, in-session results and retry.
- Bundled Python engine; no separate Python installation for download users.
- Browser sign-in plus pasted final URL/code, shared CLI credentials and defaults.
- About window names Benjamin M. Duivesteyn and explains why Papir was created.

The engine retains ordinary CLI commands and has a stdin/stdout JSON bridge for
account actions. Authentication parameters go through stdin, not process arguments.

## Still planned

Structured percentage progress, persistent history, automatic browser redirect
capture, Keychain storage, Finder Services/Share extension, a DMG and updater.
These are not present in the current release.

The initial menu bar and rumps proposals are superseded by the on-demand window.
See `macos/README.md` for build and verification instructions.
