#!/usr/bin/env python3
"""Regenerate the Android launcher marks from the Papir master artwork.

The master is an ivory folded P on a forest-green card. Android's adaptive
icon wants a foreground glyph with transparency, so the P is keyed out of the
card by its warm-vs-cool channel difference (the field is green, the paper is
warm), then recoloured flat ivory for crispness at 48dp.

Run from the repository root:  python3 android/tools/make-icons.py
"""

from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "art" / "Iconi" / "Papir-1024.png"
OUT = ROOT / "android" / "app" / "src" / "main" / "res" / "drawable-nodpi"

IVORY = (243, 234, 219)
WHITE = (255, 255, 255)
CANVAS = 432          # 4x of the 108dp adaptive canvas
GLYPH_RATIO = 0.60    # inside the 66/108 safe zone


def glyph() -> Image.Image:
    """Return the P as a white alpha mask, tightly cropped."""
    im = Image.open(SRC).convert("RGBA")
    w, h = im.size
    px = im.load()
    mask = Image.new("L", (w, h))
    mask.putdata([
        0 if px[x, y][3] < 40 else
        max(0, min(255, int(255 * ((px[x, y][0] - px[x, y][1]) + 8) / 24)))
        for y in range(h) for x in range(w)
    ])
    mask = mask.filter(ImageFilter.MedianFilter(3))
    return mask.crop(mask.point(lambda v: 255 if v > 60 else 0).getbbox())


def render(mask: Image.Image, colour: tuple[int, int, int]) -> Image.Image:
    w = int(CANVAS * GLYPH_RATIO)
    h = int(w * mask.height / mask.width)
    scaled = mask.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    tint = Image.new("RGBA", (w, h), (*colour, 255))
    out.paste(tint, ((CANVAS - w) // 2, (CANVAS - h) // 2), scaled)
    return out


def main() -> None:
    mask = glyph()
    OUT.mkdir(parents=True, exist_ok=True)
    render(mask, IVORY).save(OUT / "ic_launcher_foreground.png")
    render(mask, WHITE).save(OUT / "ic_launcher_monochrome.png")
    print(f"wrote {OUT}/ic_launcher_foreground.png and ic_launcher_monochrome.png ({CANVAS}px)")


if __name__ == "__main__":
    main()
