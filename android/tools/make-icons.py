#!/usr/bin/env python3
"""Draw every Papir Android mark from scratch — no source artwork, no stock art.

Two families come out of here:

* the Papir mark, an ivory paper plane on warm ink, sized for Android's
  adaptive-icon safe zone so launchers stop cropping it;
* one silhouette per Kindle family (Scribe, Paperwhite, Colorsoft, Oasis,
  Voyage, Basic, Keyboard, Touch, DX, plus a generic slab for anything else).
  The app shows the one matching whichever Kindle the user picked from the
  share sheet, and in the launcher when one is selected.

Everything is shaped at 4x and resampled per size from a coverage mask plus a
separate colour plane, so transparent exports keep clean ivory edges instead of
black halos.

    python3 android/tools/make-icons.py            # resources + pack
    python3 android/tools/make-icons.py --sheet    # also write /tmp previews
"""

from __future__ import annotations

import argparse
import shutil
import textwrap
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "android" / "app" / "src" / "main" / "res"
PACK = ROOT / "kindle_app_icon_pack.zip"
PACK_NAME = "kindle_app_icon_pack"

S = 1024          # design canvas, in design units
SS = 4            # supersampling factor
PIX = S * SS

IVORY = (243, 234, 219)
INK = (31, 27, 22)
WHITE = (255, 255, 255)
CLAY = (186, 133, 98)
MIST = (191, 214, 208)
TAUPE = (201, 191, 169)

# Adaptive icon geometry: a 108dp canvas of which the interior 66dp circle is
# always visible (radius 0.305 of the canvas), and the launcher's own mask, at
# most 72dp, reaches 0.333. Keep every mark inside that radius: the launcher
# icon used to sit at 0.39, which is why phones cut the top and bottom off the mark.
MASK_RADIUS = 0.333

# The app mark is the plane from art/Iconi/Papir-launcher-glyph-432.png, taken as
# it is: that file is the suite art fitted to 0.315 of the canvas, and this script
# only resizes it. Earlier artwork was scaled to 60% of the canvas *width* (70% of
# its height), which ran under every launcher mask and got cropped.
LAUNCHER_GLYPH = ROOT / "art" / "Iconi" / "Papir-launcher-glyph-432.png"
LAUNCHER_CANVAS = 432   # the glyph asset's own canvas
PAPIR_RADIUS = 0.315
SIZES = (16, 32, 64, 128, 256, 512, 1024)
# The launcher glyph is a 432 px asset, so the papir folder stops there rather
# than shipping upscales. The Kindle marks are drawn and go all the way up.
PAPIR_SIZES = (16, 32, 64, 128, 256, 432)

KINDS = (
    "scribe",
    "paperwhite",
    "basic",
    "colorsoft",
    "oasis",
    "voyage",
    "keyboard",
    "touch",
    "dx",
    "generic",
)


def _px(box):
    return tuple(int(round(v * SS)) for v in box)


def _pts(points):
    return [(int(round(x * SS)), int(round(y * SS))) for x, y in points]


class Mark:
    """A drawing made of a coverage mask and a colour plane.

    Resampling the mask and the (opaque) colour plane separately, then merging,
    is what keeps ivory edges from picking up dark fringes after downscaling.
    """

    def __init__(self, base=IVORY, punch=None):
        self.mask = Image.new("L", (PIX, PIX), 0)
        self.md = ImageDraw.Draw(self.mask)
        self.colour = Image.new("RGB", (PIX, PIX), base)
        self.cd = ImageDraw.Draw(self.colour)
        # What a "screen" is made of: transparent for an adaptive foreground,
        # warm ink when the mark sits on a baked ink tile.
        self.punch = punch

    # -- primitives ---------------------------------------------------------

    def rounded(self, box, radius, colour=IVORY):
        limit = min(abs(box[2] - box[0]), abs(box[3] - box[1])) / 2
        r = max(0, int(round(min(radius, limit) * SS)))
        self.md.rounded_rectangle(_px(box), radius=r, fill=255)
        self.cd.rounded_rectangle(_px(box), radius=r, fill=colour)

    def cut(self, box, radius):
        """A hole — or, on a tile, a repaint in the field colour."""
        if self.punch is None:
            limit = min(abs(box[2] - box[0]), abs(box[3] - box[1])) / 2
            r = max(0, int(round(min(radius, limit) * SS)))
            self.md.rounded_rectangle(_px(box), radius=r, fill=0)
        else:
            self.rounded(box, radius, self.punch)

    def wedge(self, box, start, end, colour=IVORY):
        """Half-disc (or slice) fill, for rounded device marks."""
        self.md.pieslice(_px(box), start, end, fill=255)
        self.cd.pieslice(_px(box), start, end, fill=colour)

    def wedge_cut(self, box, start, end):
        if self.punch is None:
            self.md.pieslice(_px(box), start, end, fill=0)
        else:
            self.wedge(box, start, end, self.punch)

    def dot(self, cx, cy, r, colour=IVORY):
        self.rounded((cx - r, cy - r, cx + r, cy + r), r, colour)

    def ring(self, cx, cy, r, width, colour=IVORY):
        xy = _px((cx - r, cy - r, cx + r, cy + r))
        w = max(1, int(round(width * SS)))
        self.md.ellipse(xy, outline=255, width=w)
        self.cd.ellipse(xy, outline=colour, width=w)

    def stroke(self, points, width, colour=IVORY):
        if len(points) >= 2:
            w = max(1, int(round(width * SS)))
            self.md.line(_pts(points), fill=255, width=w, joint="curve")
            self.cd.line(_pts(points), fill=colour, width=w, joint="curve")
        for x, y in points:
            self.dot(x, y, width / 2, colour)

    def polygon(self, points, colour=IVORY):
        self.md.polygon(_pts(points), fill=255)
        self.cd.polygon(_pts(points), fill=colour)

    # -- output -------------------------------------------------------------

    def bust(self, size=96, pad=0.06):
        """The mark cropped to its ink, for the small previews in settings."""
        box = self.mask.getbbox()
        if box is None:
            return Image.new("RGBA", (size, size), (0, 0, 0, 0))
        mask = self.mask.crop(box)
        colour = self.colour.crop(box)
        side = int(max(mask.width, mask.height) / (1 - 2 * pad))
        offset = ((side - mask.width) // 2, (side - mask.height) // 2)
        mask_canvas = Image.new("L", (side, side), 0)
        mask_canvas.paste(mask, offset)
        colour_canvas = Image.new("RGB", (side, side), IVORY)
        colour_canvas.paste(colour, offset)
        small_mask = mask_canvas.resize((size, size), Image.LANCZOS)
        small_colour = colour_canvas.resize((size, size), Image.LANCZOS)
        return Image.merge("RGBA", (*small_colour.split(), small_mask))

    def render(self, size, colour=None):
        mask = self.mask.resize((size, size), Image.LANCZOS)
        plane = self.colour if colour is None else Image.new("RGB", (PIX, PIX), colour)
        rgb = plane.resize((size, size), Image.LANCZOS)
        return Image.merge("RGBA", (*rgb.split(), mask))


# --------------------------------------------------------------------- shapes


def device(m, cx, cy, w, h, radius, bezel, screen_radius=14):
    """A slab with its screen punched out; returns the screen rectangle."""
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    m.rounded((x0, y0, x1, y1), radius)
    screen = (x0 + bezel[0], y0 + bezel[1], x1 - bezel[2], y1 - bezel[3])
    m.cut(screen, screen_radius)
    return screen


def text_lines(m, screen, count=4, top=0.14, gap=0.12, thickness=15, width=0.84):
    x0, y0, x1, y1 = screen
    bw, bh = x1 - x0, y1 - y0
    for i in range(count):
        line_w = bw * width * (0.58 if i == count - 1 else 1.0)
        left = x0 + (bw - line_w) / 2
        y = y0 + bh * (top + i * gap)
        m.rounded((left, y, left + line_w, y + thickness), thickness / 2)


def key_rows(m, box, rows, cols, gap_x=10, gap_y=12):
    x0, y0, x1, y1 = box
    key_w = ((x1 - x0) - (cols - 1) * gap_x) / cols
    key_h = ((y1 - y0) - (rows - 1) * gap_y) / rows
    for r in range(rows):
        for c in range(cols):
            left = x0 + c * (key_w + gap_x)
            top = y0 + r * (key_h + gap_y)
            m.cut((left, top, left + key_w, top + key_h), min(key_h, key_w) * 0.35)


# ----------------------------------------------------------------------- marks


_ARTWORK = None


def artwork():
    """The launcher glyph as (mask, colour), cropped to its ink."""
    global _ARTWORK
    if _ARTWORK is None:
        glyph = Image.open(LAUNCHER_GLYPH).convert("RGBA")
        box = glyph.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
        cropped = glyph.crop(box)
        _ARTWORK = (cropped.getchannel("A"), cropped.convert("RGB"))
    return _ARTWORK


def resample(image, size):
    """Resize straight-alpha art without letting its edges go dark."""
    mask = image.getchannel("A").resize((size, size), Image.LANCZOS)
    rgb = image.convert("RGB").resize((size, size), Image.LANCZOS)
    return Image.merge("RGBA", (*rgb.split(), mask))


def papir_layer(size=LAUNCHER_CANVAS, tint=None):
    """The plane on transparency, fitted to the safe circle.

    Nothing is redrawn: same art, same crop. It is fitted to 0.315 of the
    canvas instead of 60% of its width, which is the only change.
    """
    mask, colour = artwork()
    base = min(size, LAUNCHER_CANVAS)
    scale = (PAPIR_RADIUS * base) / ink_radius_px(mask)
    width, height = max(1, round(mask.width * scale)), max(1, round(mask.height * scale))
    plane = colour if tint is None else Image.new("RGB", colour.size, tint)
    layer = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    layer.paste(
        Image.merge("RGBA", (*plane.resize((width, height), Image.LANCZOS).split(),
                             mask.resize((width, height), Image.LANCZOS))),
        ((base - width) // 2, (base - height) // 2),
    )
    return layer if base == size else resample(layer, size)


def papir_icon(size=LAUNCHER_CANVAS):
    """The warm ink tile with the P — the app's own icon."""
    base = min(size, LAUNCHER_CANVAS)
    big = base * 4
    corners = Image.new("L", (big, big), 0)
    ImageDraw.Draw(corners).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=round(big * 0.2237), fill=255
    )
    tile = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    tile.paste(Image.new("RGBA", (base, base), INK + (255,)), (0, 0),
               corners.resize((base, base), Image.LANCZOS))
    tile.alpha_composite(papir_layer(base))
    return tile if base == size else resample(tile, size)


def papir_bust(size=96, pad=0.06):
    """The glyph cropped to its ink, for the small previews in settings."""
    layer = papir_layer()
    box = layer.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
    cropped = layer.crop(box)
    side = max(1, round(max(cropped.width, cropped.height) / (1 - 2 * pad)))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2), cropped)
    return resample(canvas, size)


def kindle_scribe(m):
    """Note tablet with the pen parked alongside — the Scribe silhouette."""
    cx = 484
    screen = device(m, cx, 512, 348, 508, 40, (24, 24, 24, 46), 12)
    x0, y0, x1, y1 = screen
    bw, bh = x1 - x0, y1 - y0
    for i, ratio in enumerate((0.18, 0.28)):
        line_w = bw * (0.62 - i * 0.16)
        m.rounded((x0 + bw * 0.13, y0 + bh * ratio,
                   x0 + bw * 0.13 + line_w, y0 + bh * ratio + 13), 7)
    squiggle = [
        (x0 + bw * 0.10, y0 + bh * 0.74),
        (x0 + bw * 0.23, y0 + bh * 0.55),
        (x0 + bw * 0.35, y0 + bh * 0.76),
        (x0 + bw * 0.49, y0 + bh * 0.57),
        (x0 + bw * 0.63, y0 + bh * 0.78),
        (x0 + bw * 0.76, y0 + bh * 0.61),
        (x0 + bw * 0.90, y0 + bh * 0.70),
    ]
    m.stroke(squiggle, 14)
    pen_x = cx + 174 + 40
    m.rounded((pen_x - 18, 288, pen_x + 18, 604), 18)          # barrel
    m.rounded((pen_x - 12, 596, pen_x + 12, 652), 9)           # grip
    m.polygon([(pen_x - 12, 648), (pen_x + 12, 648), (pen_x, 702)])
    m.dot(pen_x, 700, 5)


def kindle_paperwhite(m):
    """Thin side bezels, a wide chin and its round home button."""
    screen = device(m, 512, 512, 372, 530, 40, (24, 24, 24, 106), 14)
    text_lines(m, screen, count=4, top=0.13, gap=0.115)
    m.dot(512, 512 + 265 - 54, 15)


def kindle_basic(m):
    """Even bezel all round, no button, softer corners."""
    screen = device(m, 512, 512, 348, 516, 52, (32, 32, 32, 36), 10)
    text_lines(m, screen, count=4, top=0.16, gap=0.14, width=0.80)


def kindle_colorsoft(m):
    """Paperwhite frame, colour cover on the page."""
    screen = device(m, 512, 512, 372, 526, 40, (24, 24, 24, 74), 14)
    x0, y0, x1, y1 = screen
    bw, bh = x1 - x0, y1 - y0
    inset = 26
    band_top, band_h = y0 + inset, bh * 0.48
    band_w = (bw - inset * 2) / 3
    for index, colour in enumerate((CLAY, MIST, TAUPE)):
        left = x0 + inset + index * band_w
        m.rounded((left, band_top, left + band_w, band_top + band_h), 8, colour)
    for i, ratio in enumerate((0.72, 0.82)):
        line_w = bw * (0.60 - i * 0.18)
        m.rounded((x0 + inset, y0 + bh * ratio,
                   x0 + inset + line_w, y0 + bh * ratio + 13), 6)


def kindle_oasis(m):
    """Side spine with the two page-turn buttons."""
    w, h = 404, 470
    screen = device(m, 512, 512, w, h, 34, (24, 24, 24, 108), 14)
    text_lines(m, screen, count=4, top=0.16, gap=0.14, width=0.82)
    spine_x = 512 + w / 2 - 54
    m.cut((spine_x - 25, 512 - 72, spine_x + 25, 512 - 42), 15)
    m.cut((spine_x - 25, 512 + 42, spine_x + 25, 512 + 72), 15)


def kindle_voyage(m):
    """Flush glass front — almost no bezel at all."""
    screen = device(m, 512, 512, 372, 534, 36, (12, 12, 12, 12), 8)
    text_lines(m, screen, count=5, top=0.12, gap=0.145, thickness=13, width=0.86)


def kindle_keyboard(m):
    """Keyboard under the page."""
    screen = device(m, 512, 512, 384, 546, 44, (30, 30, 30, 190), 10)
    text_lines(m, screen, count=4, top=0.12, gap=0.11, thickness=14, width=0.86)
    key_rows(m, (512 - 160, 512 + 273 - 152, 512 + 160, 512 + 273 - 36), rows=3, cols=6)


def kindle_touch(m):
    """Touch ripple on the page and a home bar on the chin."""
    screen = device(m, 512, 512, 368, 526, 46, (34, 34, 34, 78), 14)
    x0, y0, x1, y1 = screen
    bw, bh = x1 - x0, y1 - y0
    for i in range(2):
        line_w = bw * (0.70 - i * 0.20)
        m.rounded((x0 + bw * 0.14, y0 + bh * (0.15 + i * 0.11),
                   x0 + bw * 0.14 + line_w, y0 + bh * (0.15 + i * 0.11) + 13), 6)
    m.ring(x0 + bw * 0.56, y0 + bh * 0.66, 44, 13)
    m.dot(x0 + bw * 0.56, y0 + bh * 0.66, 15)
    m.cut((512 - 46, 512 + 263 - 40, 512 + 46, 512 + 263 - 26), 7)


def kindle_dx(m):
    """Big landscape page over a keyboard."""
    screen = device(m, 512, 512, 552, 430, 26, (24, 24, 24, 152), 8)
    text_lines(m, screen, count=4, top=0.14, gap=0.19, thickness=14, width=0.88)
    key_rows(m, (512 - 248, 512 + 215 - 148, 512 + 248, 512 + 215 - 42), rows=3, cols=8,
             gap_x=12, gap_y=11)


def kindle_generic(m):
    """Plain slab: every Kindle we cannot place by name still gets a device."""
    screen = device(m, 512, 512, 368, 524, 42, (34, 34, 34, 44), 12)
    text_lines(m, screen, count=3, top=0.20, gap=0.17, width=0.78)


PAINTERS = {
    "scribe": kindle_scribe,
    "paperwhite": kindle_paperwhite,
    "basic": kindle_basic,
    "colorsoft": kindle_colorsoft,
    "oasis": kindle_oasis,
    "voyage": kindle_voyage,
    "keyboard": kindle_keyboard,
    "touch": kindle_touch,
    "dx": kindle_dx,
    "generic": kindle_generic,
}


# --------------------------------------------------------------------- output


def glyph(kind):
    """The transparent mark used as an adaptive-icon foreground layer."""
    mark = Mark()
    PAINTERS[kind](mark)
    return mark


def ink_radius_px(mask, target_width=320):
    """How far a mask's ink reaches from its centre, in the mask's own pixels."""
    scale = min(1.0, target_width / mask.width)
    small = mask.resize((max(1, round(mask.width * scale)),
                         max(1, round(mask.height * scale))), Image.BILINEAR)
    centre_x, centre_y = (small.width - 1) / 2, (small.height - 1) / 2
    worst = 0.0
    for index, value in enumerate(small.tobytes()):
        if value <= 8:
            continue
        dx = index % small.width - centre_x
        dy = index // small.width - centre_y
        worst = max(worst, (dx * dx + dy * dy) ** 0.5)
    return worst / scale


def ink_radius(mark, samples=256):
    """How far the mark's ink reaches from the centre, as a fraction of the canvas."""
    small = mark.mask.resize((samples, samples), Image.LANCZOS)
    centre = (samples - 1) / 2
    worst = 0.0
    for index, value in enumerate(small.tobytes()):
        if value <= 8:
            continue
        dx = index % samples - centre
        dy = index // samples - centre
        worst = max(worst, (dx * dx + dy * dy) ** 0.5 / samples)
    return worst


def check_safe_zone(radii):
    """Fail the run if a mark has grown into a size a launcher mask will crop."""
    worst = max(radii, key=radii.get)
    if radii[worst] > MASK_RADIUS:
        raise SystemExit(
            f"{worst} reaches {radii[worst]:.3f} of the canvas; a 72dp launcher mask "
            f"stops at {MASK_RADIUS:.3f}. Shrink the mark in its painter."
        )
    return f"safe zones ok (worst {worst} {radii[worst]:.3f}, limit {MASK_RADIUS:.3f})"


def tile(draw, base=INK, radius=0.2237):
    """A baked rounded-square tile: field plus mark, transparent corners."""
    mark = Mark(base=base, punch=base)
    mark.rounded((0, 0, S, S), S * radius, base)
    draw(mark)
    return mark


def write_android_resources():
    drawable = RES / "drawable-nodpi"
    mipmap = RES / "mipmap-anydpi-v26"
    drawable.mkdir(parents=True, exist_ok=True)
    mipmap.mkdir(parents=True, exist_ok=True)

    # Foreground is the P alone: the warm ink field arrives from the adaptive
    # icon's <background>, so nothing is double-drawn or cropped by a mask.
    papir_layer().save(drawable / "ic_launcher_foreground.png", optimize=True)
    papir_layer(tint=WHITE).save(drawable / "ic_launcher_monochrome.png", optimize=True)
    papir_bust().save(drawable / "ic_mark_papir.png", optimize=True)

    marks = {}
    for kind in KINDS:
        mark = glyph(kind)
        marks[kind] = mark
        mark.render(432).save(drawable / f"ic_share_{kind}_foreground.png", optimize=True)
        mark.bust().save(drawable / f"ic_mark_{kind}.png", optimize=True)
        (mipmap / f"ic_share_{kind}.xml").write_text(
            textwrap.dedent(
                f"""\
                <?xml version="1.0" encoding="utf-8"?>
                <!-- Generated by android/tools/make-icons.py. Share-sheet mark for a
                     {kind} Kindle, shown while that Kindle is the chosen destination. -->
                <adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
                    <background android:drawable="@color/ic_launcher_background" />
                    <foreground android:drawable="@drawable/ic_share_{kind}_foreground" />
                </adaptive-icon>
                """
            ),
            encoding="utf-8",
        )
    radii = {kind: ink_radius(mark) for kind, mark in marks.items()}
    radii["papir"] = PAPIR_RADIUS
    print(f"res    {drawable.relative_to(ROOT)}  ({len(KINDS) + 1} marks, "
          f"{len(KINDS) + 1} previews)")
    print(f"       {check_safe_zone(radii)}")


def contact_sheet(path, columns=5, cell=236):
    items = [("papir (default)", papir_icon)] + [
        (f"kindle-{kind}", tile(PAINTERS[kind]).render) for kind in KINDS
    ]
    rows = (len(items) + columns - 1) // columns
    pad, header = 26, 78
    width = columns * cell + pad * 2
    height = header + rows * (cell + 40) + pad
    sheet = Image.new("RGB", (width, height), INK)
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 24), "Papir - Kindle share-sheet marks", fill=IVORY,
              font=ImageFont.load_default(size=27))
    draw.text((pad, 54), "warm ink #1F1B16 · ivory #F3EADB", fill=TAUPE,
              font=ImageFont.load_default(size=14))

    for index, (name, render) in enumerate(items):
        row, col = divmod(index, columns)
        x, y = pad + col * cell, header + row * (cell + 40)
        icon = render(cell - 26)
        sheet.paste(icon, (x + 13, y), icon)
        draw.text((x + 13, y + cell - 6), name, fill=IVORY, font=ImageFont.load_default(size=17))
        chip = render(40)
        sheet.paste(chip, (x + cell - 62, y + cell - 8), chip)
        draw.text((x + 13, y + cell + 16), "40 px", fill=TAUPE, font=ImageFont.load_default(size=13))
    sheet.save(path, optimize=True)
    print(f"sheet  {path}")


def build_pack():
    staging = Path("/tmp") / PACK_NAME
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    papir = staging / "papir"
    papir.mkdir()
    for size in PAPIR_SIZES:
        papir_icon(size).save(papir / f"papir-{size}.png", optimize=True)
    papir_layer().save(papir / "papir-foreground-432.png", optimize=True)
    papir_layer(tint=WHITE).save(papir / "papir-monochrome-432.png", optimize=True)

    for kind in KINDS:
        folder = staging / f"kindle-{kind}"
        folder.mkdir()
        mark = tile(PAINTERS[kind])
        for size in SIZES:
            mark.render(size).save(folder / f"kindle-{kind}-{size}.png", optimize=True)
        cut_out = glyph(kind)
        cut_out.render(1024).save(folder / f"kindle-{kind}-glyph-1024.png", optimize=True)
        on_ink = Image.new("RGB", (1024, 1024), INK)
        layer = cut_out.render(1024)
        on_ink.paste(layer, (0, 0), layer)
        on_ink.save(folder / f"kindle-{kind}-on-ink-1024.png", optimize=True)

    android = staging / "android"
    android.mkdir()
    for name in ("ic_launcher_foreground", "ic_launcher_monochrome"):
        (android / f"{name}.png").write_bytes((RES / "drawable-nodpi" / f"{name}.png").read_bytes())
    for kind in KINDS:
        source = RES / "drawable-nodpi" / f"ic_share_{kind}_foreground.png"
        (android / source.name).write_bytes(source.read_bytes())
        source = RES / "mipmap-anydpi-v26" / f"ic_share_{kind}.xml"
        (android / source.name).write_bytes(source.read_bytes())
    (android / "ic_launcher.xml").write_text(
        textwrap.dedent(
            """\
            <?xml version="1.0" encoding="utf-8"?>
            <adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
                <background android:drawable="@color/ic_launcher_background" />
                <foreground android:drawable="@drawable/ic_launcher_foreground" />
                <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
            </adaptive-icon>
            """
        ),
        encoding="utf-8",
    )

    contact_sheet(staging / "sheet.png")
    (staging / "README.txt").write_text(
        textwrap.dedent(
            """\
            Kindle app-icon pack for Papir — generated, no stock art.

            The papir mark is the plane from
            art/Iconi/Papir-launcher-glyph-432.png, unchanged except for its size:
            fitted to 0.315 of the 108dp canvas so launcher masks stop cropping
            it. The Kindle silhouettes are drawn from scratch by
            android/tools/make-icons.py.

            Folders: papir, then one per Kindle family.
              kindle-scribe       note tablet with the pen parked alongside
              kindle-paperwhite   thin side bezels, wide chin, round home button
              kindle-basic        even bezel all round, no button
              kindle-colorsoft    the cover on the page is in colour
              kindle-oasis        side spine with page-turn buttons
              kindle-voyage       flush glass front, no chin
              kindle-keyboard     keyboard under the page
              kindle-touch        touch ripple and a home bar
              kindle-dx           landscape page over a keyboard
              kindle-generic      plain slab for anything unmatched

            Each Kindle folder holds the transparent glyph (…-glyph-1024.png),
            the same glyph on the warm ink field (…-on-ink-1024.png) and baked
            tiles at 16, 32, 64, 128, 256, 512 and 1024 px. The papir folder stops
            at 432 px: that is the resolution of the launcher glyph, and
            nothing here upsamples it. `android/` holds what the app
            consumes: the 432 px adaptive-icon foregrounds (66dp safe-zone
            padding, so launcher masks never crop them) and the matching
            adaptive-icon XML.

            How Papir picks a mark: the Kindle name on the account is matched in
            this order — scribe, colorsoft, oasis, voyage, keyboard, dx,
            paperwhite, touch, basic — first hit wins, and anything else gets the
            generic slab. "All devices", or no choice yet, shows the papir mark.

            Palette: warm ink #1F1B16, ivory #F3EADB, with clay #BA8562, mist
            #BFD6D0 and taupe #C9BFA9 only on the Colorsoft cover. No Amazon
            trade dress, no wordmark.
            """
        ),
        encoding="utf-8",
    )

    with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging.parent))
    print(f"pack   {PACK.relative_to(ROOT)} ({PACK.stat().st_size / 1e6:.1f} MB)")


def previews():
    contact_sheet(Path("/tmp/papir-marks.png"))
    row = Image.new("RGB", (len(KINDS) * 74 + 60, 150), INK)
    draw = ImageDraw.Draw(row)
    for index, kind in enumerate(KINDS):
        icon = tile(PAINTERS[kind]).render(48)
        row.paste(icon, (30 + index * 74, 14), icon)
        icon = tile(PAINTERS[kind]).render(32)
        row.paste(icon, (30 + index * 74 + 8, 76), icon)
        draw.text((30 + index * 74, 122), kind[:8], fill=IVORY, font=ImageFont.load_default(size=11))
    row.save("/tmp/papir-marks-small.png")
    print("sheet  /tmp/papir-marks-small.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", action="store_true", help="also write /tmp previews")
    args = parser.parse_args()

    write_android_resources()
    build_pack()
    if args.sheet:
        previews()


if __name__ == "__main__":
    main()
