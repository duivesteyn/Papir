# Security

Papir stores shared CLI/Mac credentials in `~/.config/papir/client.json` with mode
600. That file contains an account token and signing key; treat it as sensitive.
Keychain storage is planned. The release bundle and source ZIP exclude credentials.

The Mac app sends sign-in material to its Python bridge over stdin, not process
arguments. Sign-in bridge errors deliberately omit raw authentication responses.
Sign out through Papir or `papir logout` to deregister the Papir client.

The Android app stores the same registration (signing key and ADP token) in its
private app storage, readable only by Papir; signing out removes it. Sign-in
happens on Amazon's own pages in the browser or an in-app WebView, so Papir never
receives the Amazon password — only the authorization code that follows a
successful login. The sideload APK is signed with a local development key and is
not a store release.

Do not post tokens, keys, complete redirect URLs, real device serials or private
documents in public issues. For a potential vulnerability, contact the author at
`duivesteyn@gmail.com` with a description and sanitized reproduction steps.

Releases are ad-hoc signed and unnotarized. Follow Apple's per-app approval
instructions in `macos/INSTALL.md`; disabling system-wide protections is not needed.
This is an unofficial client of a private protocol; upstream behavior may change.
