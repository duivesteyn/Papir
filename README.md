<img src="_screenshots/Papir-256.png" width="128" alt="Papir icon — folded ivory paper P on forest green">

# Papir

A lightweight utility to beam reading material directly to your e-reader via API.

> **Python CLI + native Mac companion.** `papir` remains the Python CLI.
> A self-contained, on-demand SwiftUI `Papir.app` lives in `macos/`, with bundled
> Python and browser sign-in; see [Mac setup](macos/README.md).

`papir` is Norwegian for paper. p-[api]-r hides API in the middle.

Unofficial. Not affiliated with Amazon / Kindle. Speaks the private protocol used by
Amazon's Send to Kindle desktop app (following `stkclient` by Max Johnson, MIT, and
`cyrgim/stk`). Amazon can break it without notice — use on an account you own.

# Downloads and project layout

[Mac releases](https://github.com/duivesteyn/Papir/releases) ·
[Mac installation](macos/INSTALL.md) · [Local builds](macos/README.md)

The Mac download includes Python and browser sign-in. Releases are unnotarized;
see the install instructions for macOS approval. Early releases are marked as
pre-releases while fresh-account/device-delivery and older-OS testing continues.

Everything for this mini project lives in this repository:

- `papir/`: Python CLI, protocol and shared sending engine.
- `macos/`: native Mac UI, bundling, verification and packaging.
- `planning/`: current plan and retained protocol/package research.
- `art/`: original icon master, fixed exports, asset catalog and style spec.
- `.github/workflows/`: offline CI and tagged Mac release builds.

Build environments and generated releases stay local and are ignored by Git.
Downloadable binaries belong in GitHub Releases, not in source commits.

# Example Usage

An example usage file is included called main.py. It contains the basics. In essence:

```python
from papir import papirSend

sku = papirSend("report.pdf", author="deCapital", title="Imperial Investment Case", target="all")
print(sku)

# author/title optional — author falls back to your stored default, title to the filename:
sku = papirSend("report.pdf")
```

CLI:

```
pip install .
papir login                          # sign in, set default author + Kindle
papir devices                        # SERIAL: Name (* marks the default)
papir set-default                    # arrow-key/number picker (or `papir --set-default`)
papir set-default SERIAL             # non-interactive (or `all` to clear)
papir set-default --author "deCapital"
papir send report.pdf
papir send report.pdf --author "deCapital" --title "Imperial Investment Case" --to DEVICE_SERIAL
papir document.pdf --title "Design Systems"   # shorthand, uses defaults
papir doctor [--live]
papir logout
```

`papir send` without `--to` uses your default Kindle (else all devices).
`--to` accepts a serial, `all`, or `library` (cloud-library-only, no device needed).

# Example Output Data

`papirSend` returns the sku Amazon assigns:

```
8A47909664E246F0BAAB1738D7E9A154
```

# Brand

Folded ivory paper P on forest green (`#123325` / ivory `#F3EADB`).
Full spec: [art/Papir-art-style-spec.md](art/Papir-art-style-spec.md). The Mac app uses an on-demand forest-green window and the retained app icon.
The CLI's only artwork is 📤/✅ in terminal output.

# Changelog

- v0.2.1 2026-10-06 Forest-green native title bars across app windows.

- v0.2.0 2026-10-06 Self-contained native Mac app, browser sign-in/preferences, JSON desktop bridge, shared library-only default fix, consolidated planning/art and release builds.

- v0.1.1 2026-10-06 Native-PDF fix: dropped stkclient's invented `outputFormat=MOBI`/`deliveryMechanism` (backend converted PDFs), send `forceConvert:false` like the official app. Added `--convert` opt-in.
- v0.1.0 2026-10-06 Initial revision. login/devices/send/logout/doctor, correct Author+Title via DocumentMetadata.

# Notes for uploading to pypi

- `python -m build && twine upload dist/*`

# Inspirations

- https://github.com/maxdjohnson/stkclient
- https://github.com/cyrgim/stk

# Credits

designed in 2026 by bmd. Protocol work: `maxdjohnson/stkclient` (MIT) + `cyrgim/stk`
(bare-digest signing quirk, per-install serials).
