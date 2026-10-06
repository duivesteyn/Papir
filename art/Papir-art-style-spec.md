# Papir — Art Style Spec

Version 1.0 · 2026-10-06 · source of truth for all Papir artwork.
Artwork lives in `art/Iconi/` (+ `Papir-icon-pack.zip`).
Spec lives here, next to the art. Code repos reference it; nothing is
duplicated except `_screenshots/Papir-256.png` in the CLI repo (README header).

> Current scope: Python CLI plus an on-demand native Mac app. The Mac window
> uses forest green and ivory. Menu bar glyph guidance is retained for reference;
> a resident menu bar app is not part of the product.

## 1. Identity

Folded ivory paper **P** monogram on a forest-green field, transparent outer
corners (macOS applies the rounded-rect mask — never bake rounding into exports).
One glyph, two colours, no words in the mark. Calm, reliable, productive.

Norwegian *papir* = paper. The mark reads as paper first, letter second.

## 2. Palette (sampled from `Papir-1024.png`, authoritative hexes)

| Role | Hex | Sampled range | Use |
|---|---|---|---|
| Forest green | `#123325` | `#103022`–`#133426` (subtle vertical gradient) | Icon field, headers, dmg tint |
| Ivory | `#F3EADB` | `#F3EADA`–`#F5ECDD` | Monogram, light surfaces, accents |

Rules: never place ivory text on ivory; green field is never recoloured
(no seasonal variants). System colours (SF Blue links, traffic lights) may
appear in chrome but never *on* brand surfaces. Nothing Amazon-adjacent:
no orange, no smile arrows, no "Kindle" wordmark anywhere near the art.

## 3. Construction

- Master: `Papir-master-1254.png` (1254 × 1254). All edits happen here, then
  re-export the fixed sizes. Never edit an export.
- Monogram sits optically centred (it reads slightly high at exact centre —
  that is intentional, do not "fix" it).
- Exports: 1024 / 512 / 256 / 128 / 64 / 32 / 16. Small sizes (≤32) must be
  checked at 100% — if the fold reads muddy, redraw the 32/16 by hand rather
  than downscaling.
- `Papir.icns` and `AppIcon.appiconset/` are generated from these exports
  (`iconutil -c icns Papir.iconset`). Catalog validated: 10 slots, no gaps.

## 4. Clearspace & minimum size

- Clearspace = height of the P's bowl on all sides. Nothing enters it.
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

- Separate monochrome **template** glyph (not the colour icon): simplified P
  fold, single weight, no green field.
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
- Screenshots of terminal output: dark terminal, SF Mono or equivalent,
  16 px minimum capture height for the bar frames; always show the 100% frame
  (the bar guarantees it renders — see progress spec).
- PyPI renders no local images: keep the header graceful without it
  (alt text carries the description).

## 9. Disk image & installer — FUTURE

- `Papir.dmg` background: forest green at ≤12% alpha over system canvas,
  ivory directional cue toward `/Applications`, app icon per §4 clearspace.
- No license-agreement-on-mount; drag-install only.

## 10. File pipeline (how to change the art)

1. Edit `Papir-master-1254.png` (or its layered source if one is added later).
2. Re-export all sizes + rebuild `.iconset` / `.icns` / `.appiconset`.
3. Re-zip `Papir-icon-pack.zip`.
4. Bump this spec's version + note it in the repo changelog.
5. The Mac build copies `art/Iconi/Papir.icns` into the generated bundle;
   `_screenshots/Papir-256.png` is the README display export.

## 11. Don'ts (quick reference)

No orange · no gradients added to the mark · no baked rounded corners ·
no text inside the icon · no colour icon in the menu bar · no emoji beyond
📤/✅ in CLI output · no Amazon trade dress anywhere.
