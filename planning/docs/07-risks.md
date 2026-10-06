# Risks and limitations

- **Private protocol:** Amazon may change endpoints, sign-in, signing or conversion
  behavior without notice. Keep API changes in the shared Python layer.
- **Credentials:** the CLI and Mac app currently share a mode-600 credential file.
  Keychain is planned. Never publish account tokens, private keys or redirect URLs.
- **Unnotarized app:** ad-hoc signatures do not identify the developer to Gatekeeper.
  Use Apple's per-app approval process; do not instruct users to disable Gatekeeper.
- **Backend outages:** device lookups and sends can fail. Keep library-only targeting
  available and show errors. Accepted by service does not prove device delivery.
- **Verification:** clean-runner engine tests do not prove fresh browser login,
  physical-device receipt or compatibility with every macOS version.
- **Naming:** no trademark clearance or PyPI/Homebrew availability is claimed.
  Papir is unofficial and unaffiliated with Amazon; its artwork is original.
- **Scope:** keep a small CLI and on-demand Mac window; no resident menu bar process.
