#!/usr/bin/env python3
"""Render before/after contact sheets so the HSV math can be eyeballed.

Run this before committing to a full 280 file batch:

    .venv/bin/python tools/test_recolor.py --hue 0 --hue 120 --hue 280
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from recolor import recolor_array, shift_for_target

REPO = Path(__file__).resolve().parent.parent

# Deliberately weighted towards the cases most likely to break: mixed icons
# with non-blue inserts, icons that must not change at all, and the smallest
# and largest renderings of the plain folder.
SAMPLES = [
    "48x48/places/folder.png",
    "48x48/places/folder-download.png",
    "48x48/places/folder-locked.png",
    "48x48/places/folder-favorites.png",
    "48x48/places/folder-documents.png",
    "48x48/places/folder-red.png",
    "48x48/places/user-home.png",
    "48x48/places/user-desktop.png",
    "48x48/places/network-workgroup.png",
    "22x22/places/folder.png",
    "128x128/places/folder.png",
]

TILE = 144
PAD = 10
LABEL_H = 18
CHECKER = 8


def checkerboard(h: int, w: int) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w]
    light = ((ys // CHECKER + xs // CHECKER) % 2).astype(np.uint8)
    board = np.where(light == 0, 210, 165).astype(np.uint8)
    return np.dstack([board] * 3)


def over_checker(bgra: np.ndarray, size: int) -> np.ndarray:
    """Composite a BGRA icon onto a checkerboard, centred in a size x size tile."""
    if bgra.shape[2] == 3:
        bgra = np.dstack([bgra, np.full(bgra.shape[:2], 255, np.uint8)])

    h, w = bgra.shape[:2]
    scale = min(size / w, size / h, 1.0) if max(h, w) > size else 1.0
    if scale != 1.0:
        interp = cv2.INTER_AREA
        bgra = cv2.resize(bgra, (int(w * scale), int(h * scale)), interpolation=interp)
        h, w = bgra.shape[:2]

    tile = checkerboard(size, size)
    y0, x0 = (size - h) // 2, (size - w) // 2
    a = (bgra[..., 3:4].astype(np.float32) / 255.0)
    patch = tile[y0:y0 + h, x0:x0 + w].astype(np.float32)
    blended = bgra[..., :3].astype(np.float32) * a + patch * (1.0 - a)
    tile[y0:y0 + h, x0:x0 + w] = blended.round().astype(np.uint8)
    return tile


def label(width: int, text: str) -> np.ndarray:
    strip = np.full((LABEL_H, width, 3), 245, np.uint8)
    cv2.putText(strip, text, (2, LABEL_H - 5), cv2.FONT_HERSHEY_SIMPLEX,
                0.34, (40, 40, 40), 1, cv2.LINE_AA)
    return strip


def build_sheet(hue: float, sat_scale: float, val_scale: float) -> np.ndarray:
    shift = shift_for_target(hue)
    cols = []
    for rel in SAMPLES:
        src = REPO / rel
        original = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
        if original is None:
            print(f"  skip (unreadable): {rel}")
            continue
        shifted, changed = recolor_array(original, shift, sat_scale, val_scale)
        visible = int(np.count_nonzero(original[..., 3] > 0)) if original.shape[2] == 4 else original[..., 0].size
        pct = 100.0 * changed / max(visible, 1)

        name = Path(rel).name.replace(".png", "")
        col = np.vstack([
            label(TILE, f"{name}"),
            over_checker(original, TILE),
            label(TILE, f"{pct:.0f}% masked"),
            over_checker(shifted, TILE),
        ])
        cols.append(col)
        print(f"  {rel:34} {changed:6d} px  ({pct:.0f}% of visible)")

    gap = np.full((cols[0].shape[0], PAD, 3), 245, np.uint8)
    body = cols[0]
    for col in cols[1:]:
        body = np.hstack([body, gap, col])

    header = np.full((26, body.shape[1], 3), 245, np.uint8)
    cv2.putText(header, f"target hue {hue:.0f}  (shift {shift:+.0f})  top: original  bottom: recolored",
                (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 30, 30), 1, cv2.LINE_AA)

    border = np.full((PAD, body.shape[1], 3), 245, np.uint8)
    return np.vstack([header, body, border])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hue", type=float, action="append",
                    help="target hue in degrees, repeatable (default: 0, 120, 280)")
    ap.add_argument("--sat-scale", type=float, default=1.0)
    ap.add_argument("--val-scale", type=float, default=1.0)
    ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent / "preview"))
    args = ap.parse_args()

    hues = args.hue or [0.0, 120.0, 280.0]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for hue in hues:
        print(f"hue {hue:.0f}:")
        sheet = build_sheet(hue, args.sat_scale, args.val_scale)
        dst = out_dir / f"preview-hue{int(hue):03d}.png"
        cv2.imwrite(str(dst), sheet, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        print(f"  -> {dst}")


if __name__ == "__main__":
    main()
