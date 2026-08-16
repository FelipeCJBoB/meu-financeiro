"""Build-time script: renders icon.ico from scratch with Pillow (supersampled AA).

Not part of the app - the app never runs this. Run once, or after design tweaks:
    python app/assets/_make_icon.py
Requires Pillow (not a runtime dependency of the app itself).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).parent
SCALE = 8  # supersample factor for clean edges at small sizes
BASE = 256

BG_TOP = (0xB3, 0x71, 0x3F)      # warm terracotta (accent)
BG_BOTTOM = (0x3E, 0x5B, 0x36)   # deep forest green (accent2)
BAR = (0xF6, 0xF2, 0xE9)         # cream (matches Linen s2)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render(size: int) -> Image.Image:
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Diagonal gradient background, drawn as horizontal stripes interpolated by
    # (x+y)/2 so the two accent colours blend corner to corner, then clipped to
    # a rounded square via a mask - matches the app's own Linen/Dusk accents.
    grad = Image.new("RGB", (s, s))
    px = grad.load()
    for y in range(s):
        for x in range(0, s, 4):
            t = (x + y) / (2 * s)
            color = _lerp(BG_TOP, BG_BOTTOM, min(1.0, t))
            for dx in range(4):
                if x + dx < s:
                    px[x + dx, y] = color

    mask = Image.new("L", (s, s), 0)
    mdraw = ImageDraw.Draw(mask)
    radius = round(s * 56 / BASE)
    mdraw.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)

    img.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    bars = [
        # x, top_y, width, height, opacity
        (60, 120, 34, 70, 0.78),
        (112, 80, 34, 110, 0.90),
        (164, 40, 34, 150, 1.0),
    ]
    for x, top, w, h, opacity in bars:
        x0, y0 = x * s // BASE, top * s // BASE
        x1, y1 = (x + w) * s // BASE, (top + h) * s // BASE
        bar_r = round(8 * s / BASE)
        fill = (*BAR, round(255 * opacity))
        draw.rounded_rectangle([x0, y0, x1, y1], radius=bar_r, fill=fill)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [render(s) for s in sizes]
    ico_path = OUT_DIR / "icon.ico"
    # Pillow's ICO writer skips any requested size larger than the base image
    # it was called on, so the base must be the largest rendering - passing the
    # 16px image as base silently dropped every size above 16.
    images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    images[-1].save(OUT_DIR / "icon_preview_256.png")
    print(f"wrote {ico_path} ({ico_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
