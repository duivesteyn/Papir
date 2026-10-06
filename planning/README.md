# Papir planning

Retained design and protocol notes for the Python CLI and native Mac companion.
All project work now lives in this repository; original artwork lives in `../art/`.

Papir was created by Benjamin M. Duivesteyn as a lightweight, open-source,
unintrusive way to send documents to his Kindle from the command line.
The Mac app provides the same engine in a native, on-demand window.

## Current state

- Python CLI and shared sending core: `../papir/`.
- Native SwiftUI app and bundled Python engine: `../macos/`.
- Original master, fixed icon exports, asset catalog and style spec: `../art/`.
- Local generated packages: `../macos/releases/` (ignored by Git).
- Public downloads: GitHub Releases, built from version tags.

The app is not a persistent menu bar utility. It opens when needed and quits
when its windows close. The free distribution route uses ad-hoc signatures,
with explicit user approval for an unnotarized download where macOS requires it.

## Notes

1. [Vision](docs/01-vision.md)
2. [Protocol research](docs/02-protocol.md) — recorded reverse-engineering observations
3. [Python package design](docs/03-package.md) — early design, implementation is authoritative
4. [Mac app](docs/04-mac-app.md)
5. [Distribution](docs/05-distribution.md)
6. [Roadmap](docs/06-roadmap.md)
7. [Risks and limitations](docs/07-risks.md)
8. [Art](docs/08-art.md)

Earlier implementation proposals in the package/protocol notes are retained
for context; current behavior is described in the root and Mac READMEs.
