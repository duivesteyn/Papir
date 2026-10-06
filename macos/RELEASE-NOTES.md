Papir is a lightweight, open-source, unintrusive way to send reading documents to
Kindle, created by Benjamin M. Duivesteyn. This early release includes the Python
CLI and a native, on-demand Mac app using the same engine.

- Deep forest-green window and native title bar, file drop/staging, title and author edits.
- Actual Kindle names, shared default device/author preferences, library-only sends.
- Python runtime included: no Python or Terminal installation for app users.
- Browser sign-in with final-URL/code paste, in-session send results and retry.
- Original icon artwork, style specification and planning notes retained in source.

Downloads: `arm64` is for Apple Silicon; `x86_64` is for Intel. The source ZIP
includes the CLI, Mac source, planning and artwork. Checksums cover each ZIP.

The app is ad-hoc signed and **not notarized**. Download users may need
System Settings → Privacy & Security → Open Anyway. See INSTALL.md for setup.

Each package is built on macOS 15 and passes offline tests, signature checks,
and relocated-engine/runtime/TLS checks. The interface targets macOS 14+, but
macOS 14 compatibility, fresh-account sign-in and physical Kindle delivery still
need user testing. Acceptance by the service does not confirm device delivery.

Papir is unofficial and unaffiliated with Amazon. It uses a private protocol
that Amazon may change. Credentials stay outside the downloaded app and source.
