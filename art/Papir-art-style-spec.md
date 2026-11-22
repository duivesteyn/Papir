# Papir — Art Style Spec

Version 1.3 · 2026-11-22 · source of truth for all Papir artwork.
Artwork lives in `art/Iconi/` (derived, used by the builds) and the delivered
icon suite is archived at `art/Papir-macOS-IconSuite-v2.zip`.
Spec lives here, next to the art. Code repos reference it; nothing is
duplicated except `_screenshots/Papir-256.png` in the CLI repo (README header).

> Current scope: Python CLI plus an on-demand native Mac app. The Mac window
> uses warm ink on parchment. Menu bar glyph guidance is retained for reference;
> a resident menu bar app is not part of the product.

## 1. Identity

Ivory paper **plane** with ruled lines on a warm ink field, transparent
outer corners (macOS applies the rounded-rect mask — never bake rounding into
exports). One mark, two colours, no words in the mark. Calm, reliable, productive.

Norwegian *papir* = paper. The plane reads as paper first, travel second: a
document on its way to the reader.

## 2. Palette (current master plus the v2 suite's `colors.json`)

| Role | Hex | Use |
|---|---|---|
| Ink field | `#1F1B16` | App-icon field (1024 master) |
| Forest green | `#122E21` | Archived v2 suite field; Android launcher art |
| Pine leaf | `#2A4D3A` | Subtle top highlight, elevated cards |
| Midnight green | `#0D1F17` | Dark-mode surface |
| Parchment cream | `#F6EFE3` | Paper plane, light surfaces, CTA buttons |
| Warm terracotta | `#D96B43` | Reserved accent; never on the mark |

The Mac and Android interfaces use warm ink `#1F1B16` on parchment `#F3EADB`
with rules at `#D8CDB9`; no green appears in Mac app chrome or the Mac app
icon. The archived v2 suite keeps its forest edition, and the Android launcher
art still uses that field until it is retoned.

Rules: never place cream text on cream; the icon field is not retoned per
season or variant (the ink master is a one-off rebrand of the suite's forest
edition). System colours (SF Blue links, traffic lights) may
appear in chrome but never *on* brand surfaces. Nothing Amazon-adjacent:
no Amazon orange, no smile arrows, no "Kindle" wordmark anywhere near the art.

## 3. Construction

- Master: `Papir-master-1024.png` (1024 × 1024, the suite's primary export).
  All edits happen here, then re-export the fixed sizes. Never edit an export.
- The plane sits optically centred, nose up and to the right; its ruled lines
  run with the fold, not across it.
- Exports: 1024 / 512 / 256 / 128 / 64 / 32 / 16. Small sizes (≤32) must be
  checked at 100% — if the fold and lines read muddy, redraw the 32/16 by hand
  rather than downscaling.
- Android: the adaptive icon is this mark's plane on transparency,
  `Papir-launcher-glyph-432.png`, fitted to 0.315 of the 108dp canvas (inside the
  66dp safe circle, so no launcher mask crops it). `android/tools/make-icons.py`
  only resizes it and writes the transparent foreground and adaptive-icon XML
  into `android/app/src/main/res/`. The Kindle silhouettes in
  `kindle_app_icon_pack.zip` come from the same script and are device marks,
  not part of the Papir mark.
- Header: `Papir-Header-Mark.png` is the plane as an ink silhouette on
  transparency, for the parchment app window header and success badge.
- `Papir.icns` and `AppIcon.appiconset/` are generated from these exports
  (`iconutil -c icns Papir.iconset`). Catalog validated: 10 slots, no gaps.

## 4. Clearspace & minimum size

- Clearspace = one third of the plane's height on all sides. Nothing enters it.
- Minimum digital size: 16 px (favicon/menu contexts use the glyph-only
  redraw, §6, never the full-colour icon).
- Never stretch, rotate, drop-shadow, outline, or gradient-shift the mark.
  macOS Dock magnification and dark-mode dimming are the only allowed effects,
  applied by the OS, not baked in.

## 5. Backgrounds

- Light UI: full-colour icon as-is.
- Dark UI: full-colour icon as-is (the green field holds its own; do not add
  a light halo).
- Photography/busy backgrounds: place on an ivory `#F3EADB` chip with
  clearspace §4, or don't place it.

## 6. Menu-bar glyph — FUTURE, but specified now so it isn't improvised later

- Separate monochrome **template** glyph (not the colour icon): simplified plane,
  single weight, no ruled lines, no green field. The v2 suite ships this as
  `05_MenuBar/Papir-MenuBar-Template.svg` plus @1x/@2x/@3x PNGs in
  `art/Papir-macOS-IconSuite-v2.zip`.
- Sizes: 16 / 18 / 22 px template PDFs; renders black-in-light-mode,
  white-in-dark-mode automatically via `isTemplate = true`.
- Test against translucent menu bars over light *and* dark wallpapers before ship.

## 7. CLI — CURRENT, the only artwork in the shipped app

- Terminal output is text. The entire brand expression is two emoji:
  📤 sending/progress, ✅ done. No other emoji in `papir` output.
- Progress bar: `█` full / `░` empty, 24 cells, `%` + `sent/total` + rate.
  All status lines go to **stderr**; **stdout is the sku only** (scriptable).
- README header uses `_screenshots/Papir-256.png` at 128 px (`<img width="128">`).
  No other images ship in the pip package. The Mac bundle includes the ICNS.

## 8. README / web / PyPI

- Header: icon (128 px) → `# Papir` → one-line pitch → CLI and native Mac companion callout.
- App window header: the ivory plane (`Papir-Header-Mark.png`) at 21 pt beside the
  serif `papir` wordmark, settings icon trailing. Keep the mark at the wordmark's
  optical weight; do not enlarge it to a full app-icon tile.
- Hero: `_screenshots/Papir-hero.png` (1200 × 920, a 2× window capture on warm
  sand) shows the current Mac window. Refresh it whenever the app's empty state
  or chrome changes; keep the capture free of credentials and personal documents.
- Screenshots of terminal output: dark terminal, SF Mono or equivalent,
  16 px minimum capture height for the bar frames; always show the 100% frame
  (the bar guarantees it renders — see progress spec).
- PyPI renders no local images: keep the header graceful without it
  (alt text carries the description).

## 9. Disk image & installer — FUTURE

- `Papir.dmg` background: warm ink at ≤12% alpha over system canvas,
  ivory directional cue toward `/Applications`, app icon per §4 clearspace.
- No license-agreement-on-mount; drag-install only.

## 10. File pipeline (how to change the art)

1. Take the layered source or `Papir-master-1024.png` from the icon suite.
2. Re-export all sizes + rebuild `.iconset` / `.icns` / `.appiconset`, and the
   trimmed `Papir-Header-Mark.png`.
3. Re-zip the suite (and the derived `art/Iconi/` set if it changed).
4. Bump this spec's version + note it in the repo changelog.
5. The Mac build copies `art/Iconi/Papir.icns` and
   `art/Iconi/Papir-Header-Mark.png` into the generated bundle;
   `_screenshots/Papir-256.png` is the README display export.

## 11. Don'ts (quick reference)

No Amazon orange · no gradients added to the mark · no baked rounded corners ·
no text inside the icon · no colour icon in the menu bar · no emoji beyond
📤/✅ in CLI output · no Amazon trade dress anywhere.
