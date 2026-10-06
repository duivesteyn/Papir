# Papir for Mac — install

Papir is a small, open-source app by Benjamin M. Duivesteyn. The download includes
the native interface, Python runtime, and sending engine. No Python, pip, Xcode,
Terminal setup, or Apple Developer account is needed to run the downloaded app.

1. Download the ZIP for your Mac architecture from the project's release page.
2. Extract it and drag `Papir.app` to Applications.
3. Open Papir. This free release is ad-hoc signed and **not notarized**.
   If macOS blocks it as an unidentified developer, follow Apple's per-app
   approval process in **System Settings → Privacy & Security → Open Anyway**:
   https://support.apple.com/en-us/102445
4. Click **Sign in with Amazon**. Complete sign-in in your browser, copy its final
   address, paste it into Papir, and click **Connect Kindle**. Papir does not ask
   for your Amazon password directly.
5. In Settings, choose your default Kindle and author, then click **Save Defaults**.
6. Drop a document into the window, review it, and send.

`arm64` is for Apple Silicon. `x86_64` is for Intel. Only the architecture listed
on a given release is included. The interface targets macOS 14+, but each build's
bundled Python runtime also needs to be compatible with the destination OS.
Local arm64 UI testing used macOS 26. Tagged releases are built and checked on
macOS 15 runners for each published architecture. macOS 14 compatibility, fresh
account sign-in, physical Kindle delivery and download approval still need testing.

Papir shares `~/.config/papir/client.json` with the standalone Python CLI.
Signing out in one signs out the other. Credentials stay outside the app bundle
in that owner-readable file (mode 600). Keychain storage is not yet implemented.

Accepted by service means Amazon accepted the request; it does not confirm that
a physical Kindle has downloaded the document. This project is unofficial and
not affiliated with Amazon. It uses a private protocol that can change.
