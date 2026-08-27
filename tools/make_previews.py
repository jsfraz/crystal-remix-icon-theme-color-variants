#!/usr/bin/env python3
"""Render the README showcase grid for every color preset.

    .venv/bin/python tools/make_previews.py

Writes docs/previews/<color>.png, one 3x3 grid per preset, on a transparent
background so the images read correctly in both light and dark README themes.

The grid is composed from the real theme PNGs rather than by recoloring
crystal-remix-icon-theme.jpg: that JPEG has compression ringing around the
icons, and 1464 of its near-white background pixels fall inside the blue mask,
which would leave a colored halo around every icon.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from generate_theme import PRESETS, slugify
from recolor import recolor_array, shift_for_target

REPO = Path(__file__).resolve().parent.parent

# Mirrors the layout of the original showcase image: a folder, browser and mail
# globes, the multicolor cubes, a media button, people, an optical disc and a
# spreadsheet. Deliberately mixes heavily blue icons with ones that barely move,
# so a preview shows both the accent and what the mask leaves alone.
GRID = [
    ["places/folder.png", "apps/internet-web-browser.png", "apps/firefox.png"],
    ["apps/internet-mail.png", "places/start-here.png", "actions/media-playback-start.png"],
    ["apps/system-users.png", "devices/media-optical.png", "apps/libreoffice-calc.png"],
]

SIZE = "128x128"
CELL = 148


def place(canvas: np.ndarray, icon: np.ndarray, row: int, col: int) -> None:
    """Alpha-composite one icon into its cell of the transparent canvas."""
    h, w = icon.shape[:2]
    y = row * CELL + (CELL - h) // 2
    x = col * CELL + (CELL - w) // 2
    dst = canvas[y:y + h, x:x + w]

    src_a = icon[..., 3:4].astype(np.float32) / 255.0
    dst_a = dst[..., 3:4].astype(np.float32) / 255.0
    out_a = src_a + dst_a * (1.0 - src_a)
    rgb = icon[..., :3].astype(np.float32) * src_a + \
        dst[..., :3].astype(np.float32) * dst_a * (1.0 - src_a)
    with np.errstate(invalid="ignore", divide="ignore"):
        rgb = np.where(out_a > 0, rgb / np.maximum(out_a, 1e-6), 0)

    dst[..., :3] = rgb.round().astype(np.uint8)
    dst[..., 3:4] = (out_a * 255.0).round().astype(np.uint8)


def build_grid(hue: float) -> np.ndarray:
    shift = shift_for_target(hue)
    rows, cols = len(GRID), max(len(r) for r in GRID)
    canvas = np.zeros((rows * CELL, cols * CELL, 4), np.uint8)

    for r, line in enumerate(GRID):
        for c, rel in enumerate(line):
            src = REPO / SIZE / rel
            icon = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
            if icon is None:
                raise SystemExit(f"missing showcase icon: {src}")
            if icon.shape[2] == 3:
                icon = np.dstack([icon, np.full(icon.shape[:2], 255, np.uint8)])
            recolored, _ = recolor_array(icon, shift)
            place(canvas, recolored, r, c)

    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(REPO / "docs" / "previews"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, hue in sorted(PRESETS.items(), key=lambda kv: kv[1]):
        grid = build_grid(hue)
        dst = out_dir / f"{slugify(name)}.png"
        cv2.imwrite(str(dst), grid, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        print(f"  hue {hue:5.0f}  {dst.relative_to(REPO)}  "
              f"({dst.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
