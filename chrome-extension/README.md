# Send to Papir — browser button

A one-click Chromium extension (Chrome, Arc, Edge, Brave). It hands the current
page or PDF to Papir, which opens the usual review window so you can check the
title and destination before anything reaches your Kindle.

The extension contains no configuration and no personal data. Your token lives
in Chrome's own extension storage on this Mac; your Kindle, author and device
list stay in Papir's config.

## Why an extension

Chrome's PDF viewer is a `chrome-extension://` page, so `javascript:` bookmarks
don't run on the documents you most want to send. A toolbar button can still see
the tab's URL, and a local endpoint can still receive it.

## Install

1. In Chrome: `chrome://extensions` → turn on **Developer mode** → **Load unpacked**
   → pick this `chrome-extension/` folder.
2. Open Papir → Settings → **Browser** → switch on **Accept papir:// links**.
3. Press **Connect Browser**. A tab opens, pairs itself, and says *Connected to
   Papir* — there is no token to copy.
4. Pin the button and click it on any PDF or page.

Manual pairing still works if you prefer: the token is shown in the same
settings section and can be pasted into the extension's options.

No terminal and no extra process: the receiver lives inside `Papir.app`, starts
when you enable the setting, and stops when you quit the app.

## What happens to the link

```
extension → POST http://127.0.0.1:47821/send   (Bearer token, loopback only)
          → Papir.app validates, downloads, pre-fills the review window
```

The review window pre-fills the author with the site's domain (for example
`example.com.au`), because a shared report is published by someone else. Edit it
before sending if you'd rather use your own name.

The receiver binds loopback only, rejects anything that isn't `http(s)`, and
never sends anything by itself — you still press Send. The token is generated on
first enable and kept in
`~/Library/Application Support/Papir/intake.json` (mode 600). Turn the setting
off and the port closes; enabling again reuses the same token.

## What the button tells you

Every click ends in a macOS notification, not just a badge:

| Message | Meaning |
|---|---|
| "Sent to Papir" | Review window is open; press Send there |
| "Papir isn't answering on …" | App closed, or an older build without the receiver |
| "Papir rejected the token" | Copy Token again from Settings ▸ Browser |
| "Sharing is switched off" | Settings ▸ Browser ▸ Accept papir:// links |
| "This tab has no web address" | Chrome settings pages can't be sent |

After changing `manifest.json` (permissions), reload the extension from
`chrome://extensions` before testing.

## Watching it work

The app's status line reports each accepted link, and the terminal equivalent
(`papir serve`, for CLI-only setups) prints:

```
papir serve: → Papir: reporting.example.com.au/L1-Long-Short-Fund-Limited-Monthly-Report-October-2026.pdf
papir serve: "POST /send HTTP/1.1" 202 -
```

Start it with `--quiet` to silence it. The terminal only covers intake; delivery is confirmed in Papir's own window.

## Turn it off

- Settings ▸ Browser ▸ **Accept papir:// links** off, and the receiver stops and
  the port closes; the button then reports that nothing is listening.
- Remove the extension from `chrome://extensions`.

## Notes

- Chrome may ask for local-network permission the first time; allow it for
  `127.0.0.1` only.
- Sign-in-gated documents fail loudly ("returned a web page, not a document")
  rather than sending a login screen to your Kindle.
- Downloads are kept in `~/Library/Application Support/Papir/Inbox/`; delete that
  folder whenever you like.
