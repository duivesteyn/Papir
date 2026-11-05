<p align="center">
  <img src="_screenshots/Papir-256.png" width="128" alt="Papir icon — folded ivory paper P on forest green">
</p>

<h1 align="center">Papir</h1>

<p align="center">
  <strong>A little less screen time.</strong><br>
  Beam reading material directly to your e-reader via API — from a native Mac app or a one-line command.
</p>

<p align="center">
  <a href="https://github.com/duivesteyn/Papir/releases"><img src="https://img.shields.io/badge/download-macOS-123325?style=flat-square&logo=apple&logoColor=F3EADB" alt="Download Papir for macOS"></a>
  <a href="https://pypi.org/project/papir-kindle/"><img src="https://img.shields.io/pypi/v/papir-kindle?style=flat-square&color=123325&label=PyPI" alt="papir-kindle on PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-123325?style=flat-square" alt="Python 3.9 or later">
  <img src="https://img.shields.io/badge/license-MIT-123325?style=flat-square" alt="MIT licence">
</p>

<p align="center">
  <img src="_screenshots/Papir-hero.png" width="800" alt="Papir for Mac — a forest-green window with a serif papir header, destination pill for Benjamin's Scribe, and a dashed drop zone reading A little less screen time. Drop something good to read. Choose Documents…">
</p>

Papir is Norwegian for *paper* — with **API** hidden in the middle. It sends PDFs, EPUBs, Word documents, text, HTML and images to Kindle using the same private service as Amazon's Send to Kindle app.

> **Python CLI + native Mac companion.**
> `papir` is the Python CLI. The on-demand SwiftUI `Papir.app` in `macos/` bundles
> Python and browser sign-in, so Mac users need no Terminal at all.
> See [Mac setup](macos/README.md).

**Unofficial.** Not affiliated with Amazon or Kindle. Papir speaks the private protocol used by Amazon's Send to Kindle desktop app (following `stkclient` by Max Johnson, MIT, and `cyrgim/stk`). Amazon can break it without notice — use it on an account you own.

## Why Papir

- **Native Mac app, zero setup.** The download includes its own Python runtime. Drag documents onto the window, review the batch, and send.
- **Correct Author and Title.** Documents arrive with the metadata you chose, not a mangled filename.
- **Defaults that stick.** Pick a default Kindle and author once; the CLI and Mac app share the same configuration.
- **Scriptable by design.** `papir send` writes only Amazon's SKU to stdout, so it drops cleanly into scripts and automations.
- **No middleman.** Papir talks directly to Amazon and keeps credentials on your Mac.

## Install

### Mac app

1. Download the ZIP for your Mac (Apple Silicon or Intel) from [Releases](https://github.com/duivesteyn/Papir/releases).
2. Extract it and drag `Papir.app` to Applications.
3. Open Papir, sign in with Amazon in your browser, then paste the final address back into the app.
4. Choose your default Kindle and author in Settings, drop a document, and send.

The release is ad-hoc signed and **not notarized**, so macOS may ask you to approve it under **System Settings → Privacy & Security → Open Anyway**. [Install notes](macos/INSTALL.md) have the details. The app targets macOS 14+. Early releases are marked as pre-releases while fresh-account/device-delivery and older-OS testing continues.

### Command line

```bash
pip install papir-kindle
papir login          # browser sign-in; set your default author and Kindle
papir send report.pdf
```

Requires Python 3.9+ and `pip`. The CLI and Mac app use the same credentials at `~/.config/papir/client.json` (mode 600), so signing in with either one signs in both.

## Everyday commands

```bash
papir login                                  # sign in, set default author + Kindle
papir login --url URL --verifier VERIFIER    # non-interactive (or --code CODE for a bare pasted code)
papir devices                                # SERIAL: Name (* marks the default)
papir devices --json                         # machine-readable devices + default
papir set-default                            # arrow-key/number picker (or `papir --set-default`)
papir set-default SERIAL                     # non-interactive (or `all` to clear)
papir set-default --author "deCapital"       # change the stored author
papir send report.pdf
papir send report.pdf --author "deCapital" --title "Imperial Investment Case" --to DEVICE_SERIAL
papir send report.pdf --convert              # convert PDF to Kindle format (default keeps native PDF)
papir document.pdf --title "Design Systems"  # shorthand, uses defaults
papir doctor [--live]                        # self-test; --live also checks Amazon
papir logout
```

`papir send` without `--to` uses your default Kindle, falling back to all devices. `--to` accepts a serial, `all`, or `library` (cloud library only, no device needed). `--format` overrides the detected file type (default `auto`); `--no-archive` skips saving to your Kindle library. `--client PATH` overrides the credential file.

### Supported formats

`PDF` · `EPUB` · `DOC` · `DOCX` · `RTF` · `TXT` · `HTM` / `HTML` · `MOBI` · `AZW` · `JPEG` · `PNG` · `GIF` · `BMP`

PDFs stay native by default; pass `--convert` (or toggle **Convert PDF to Kindle format** in the app) to let Amazon convert them.

## Python API

A runnable example is included in [`main.py`](main.py). In short:

```python
from papir import papirSend

sku = papirSend("report.pdf", author="deCapital", title="Imperial Investment Case", target="all")
print(sku)

# author/title optional — author falls back to your stored default, title to the filename:
sku = papirSend("report.pdf")
```

`papirSend` returns the SKU Amazon assigns:

```
8A47909664E246F0BAAB1738D7E9A154
```

## How it works

Papir registers itself as a Send-to-Kindle device, signs requests with a per-install serial, and uploads through Amazon's private API. There is no Papir server, no telemetry, and no Amazon password prompt — sign-in happens in your browser using PKCE. Accepted by the service means Amazon accepted the request; it does not confirm that a physical Kindle has downloaded the document.

The Mac app is a thin SwiftUI layer over the same Python engine. It adds drag-and-drop, batch sending, progress, browser sign-in and shared defaults. Everything else lives in `papir/`.

## Project layout

Everything for this mini project lives in this repository:

- `papir/`: Python CLI, protocol and shared sending engine.
- `macos/`: native Mac UI, bundling, verification and packaging.
- `planning/`: current plan and retained protocol/package research.
- `art/`: original icon master, fixed exports, asset catalog and style spec.
- `.github/workflows/`: offline CI and tagged Mac release builds.

Build environments and generated releases stay local and are ignored by Git. Downloadable binaries belong in GitHub Releases, not in source commits.

## Brand

Folded ivory paper P on forest green (`#123325` / ivory `#F3EADB`). Full spec: [art/Papir-art-style-spec.md](art/Papir-art-style-spec.md). The Mac app uses an on-demand forest-green window and the retained app icon. The CLI's only artwork is 📤/✅ in terminal output.

## Changelog

- v1.0 2026-10-17 Stable 1.0. Python package `papir-kindle` (`pip install papir-kindle`, CLI stays `papir`), Mac app + CLI.
- v0.2.2 2026-10-06 Forest-green native title bars across app windows.
- v0.2.0 2026-10-06 Self-contained native Mac app, browser sign-in/preferences, JSON desktop bridge, shared library-only default fix, consolidated planning/art and release builds.
- v0.1.1 2026-10-06 Native-PDF fix: dropped stkclient's invented `outputFormat=MOBI`/`deliveryMechanism` (backend converted PDFs), send `forceConvert:false` like the official app. Added `--convert` opt-in.
- v0.1.0 2026-10-06 Initial revision. login/devices/send/logout/doctor, correct Author+Title via DocumentMetadata.

## Python package

```bash
pip install papir-kindle
papir --help
```

Releases: pushing tag `v*` runs `.github/workflows/pypi.yml` — offline tests, `python -m build`, Trusted Publishing to PyPI as `papir-kindle`, then attaches `dist/*` to the GitHub Release. First publish needs a PyPI Trusted Publisher for this repo + workflow.

## Inspirations

- https://github.com/maxdjohnson/stkclient
- https://github.com/cyrgim/stk

## Credits

Designed in 2026 by bmd. Protocol work: `maxdjohnson/stkclient` (MIT) + `cyrgim/stk` (bare-digest signing quirk, per-install serials).

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). For security reports, follow [SECURITY.md](SECURITY.md). Papir is released under the [MIT licence](LICENSE).
