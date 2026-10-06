# Vision

Papir is a lightweight, open-source, unintrusive way to send reading documents
to a Kindle from the command line, created by Benjamin M. Duivesteyn.

`papir` is Norwegian for paper. The name also contains API: p-[api]-r.

## Goals

- A small Python CLI and reusable sending function.
- Explicit title, author, destination, and optional PDF conversion.
- A native SwiftUI Mac companion using the same Python engine.
- An on-demand window: no menu bar resident or launch-at-login requirement.
- A self-contained Mac download with browser sign-in and no Terminal setup.
- MIT-licensed source, no telemetry or hosted proxy; sends go directly to Amazon.
- Original artwork and clear credit for the protocol research lineage.

## Scope

Send existing documents. No local conversion engine, ebook library management,
reading sync, document generation, or Windows/Linux GUI is planned for this release.
The Python CLI remains independent of the Mac app.

## Distribution

Source builds and ad-hoc-signed ZIPs are the free route. Developer ID signing
and notarization are optional future improvements. The current name is a design
choice; trademark and package-name availability have not been established.

## Evidence required

Offline tests and relocated-engine checks support each package release.
Fresh-account sign-in, actual device delivery, older macOS, and physical
Intel/Apple Silicon install testing are separate checks, not implied by a build.
