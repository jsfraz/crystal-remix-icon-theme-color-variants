"""Soft-masked hue rotation for Crystal Remix icons.

Only the Hue channel is modified. Saturation and Value are left untouched so the
3D gloss, specular highlights and drop shadows survive intact, and the alpha
channel is split off before any color conversion and reattached unchanged.
"""

from __future__ import annotations

import cv2
import numpy as np

# Crystal blue measured across */places/: the saturated body pixels of
# folder.png, folder-videos, folder-network, folder-print and folder-templates
# sit almost entirely in 200-220 degrees.
BLUE_LO = 195.0
BLUE_HI = 225.0
BLUE_CENTER = 207.0

# Feather on each side of the band. Wide enough to catch anti-aliased boundary
# pixels, narrow enough to stay clear of green documents (80-120) and the
# purple zip icon (270).
HUE_FEATHER = 15.0

# The white body and specular gloss of a Crystal folder are genuinely
# achromatic (S <= 0.02), while the pale blue glass tint runs down to S ~ 0.03.
# A higher floor leaves that tint behind and the icon comes out two-tone.
SAT_LO = 0.025
SAT_HI = 0.09

# Hue is numerically meaningless in near-black pixels.
VAL_LO = 0.10
VAL_HI = 0.16


def _ramp(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Linear 0->1 ramp between lo and hi, clamped outside."""
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def _hue_distance(hue: np.ndarray, center: float) -> np.ndarray:
    """Shortest angular distance in degrees, honouring the 360 wraparound."""
    d = np.abs(hue - center) % 360.0
    return np.minimum(d, 360.0 - d)


def blue_weight(hsv: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Continuous [0,1] mask of how much each pixel counts as Crystal blue.

    A hard cv2.inRange mask leaves jagged color seams on the 22x22 icons, so
    every term here is a ramp rather than a threshold and the final weight is
    their product.
    """
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    half_width = (BLUE_HI - BLUE_LO) / 2.0
    dist = _hue_distance(hue, BLUE_CENTER)
    hue_w = 1.0 - _ramp(dist, half_width, half_width + HUE_FEATHER)

    sat_w = _ramp(sat, SAT_LO, SAT_HI)
    val_w = _ramp(val, VAL_LO, VAL_HI)
    alpha_w = (alpha > 0).astype(np.float32)

    return hue_w * sat_w * val_w * alpha_w


def recolor_array(
    bgra: np.ndarray,
    hue_shift: float,
    sat_scale: float = 1.0,
    val_scale: float = 1.0,
) -> tuple[np.ndarray, int]:
    """Rotate the blue band of a BGRA image. Returns (image, changed pixels)."""
    if bgra.ndim != 3:
        raise ValueError("expected a color image")

    if bgra.shape[2] == 3:
        alpha = np.full(bgra.shape[:2], 255, dtype=bgra.dtype)
        bgr = bgra
    else:
        alpha = bgra[..., 3]
        bgr = bgra[..., :3]

    # float32 HSV keeps Hue at full 0-360 precision. The 8-bit path quantises
    # Hue to 2 degree steps, which bands these gradients visibly.
    hsv = cv2.cvtColor(bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2HSV)
    weight = blue_weight(hsv, alpha)

    changed = int(np.count_nonzero(weight > 0.0))
    if changed == 0:
        return bgra, 0

    hsv[..., 0] = (hsv[..., 0] + hue_shift * weight) % 360.0
    if sat_scale != 1.0:
        blend = 1.0 + (sat_scale - 1.0) * weight
        hsv[..., 1] = np.clip(hsv[..., 1] * blend, 0.0, 1.0)
    if val_scale != 1.0:
        blend = 1.0 + (val_scale - 1.0) * weight
        hsv[..., 2] = np.clip(hsv[..., 2] * blend, 0.0, 1.0)

    out_bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    out_bgr = np.clip(out_bgr * 255.0, 0.0, 255.0).round().astype(np.uint8)

    # The float round-trip can shift untouched pixels by +/-1, so restore the
    # original bytes wherever the mask is zero.
    out_bgr = np.where((weight > 0.0)[..., None], out_bgr, bgr)

    return np.dstack([out_bgr, alpha]), changed


def read_icon(path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise OSError(f"cannot read {path}")
    return img


def write_icon(path, bgra: np.ndarray) -> None:
    if not cv2.imwrite(str(path), bgra, [cv2.IMWRITE_PNG_COMPRESSION, 9]):
        raise OSError(f"cannot write {path}")


def recolor_file(path, hue_shift, sat_scale=1.0, val_scale=1.0) -> int:
    """Recolor a PNG in place. Returns the number of pixels touched."""
    img = read_icon(path)
    out, changed = recolor_array(img, hue_shift, sat_scale, val_scale)
    if changed:
        write_icon(path, out)
    return changed


def shift_for_target(target_hue: float) -> float:
    """Delta that moves the center of the blue band onto target_hue."""
    return (target_hue - BLUE_CENTER + 180.0) % 360.0 - 180.0
