#!/usr/bin/env python3
"""Generate a recolored variant of the Crystal Remix icon theme.

The source theme is copied to a sibling directory and every icon in the
places/ contexts is passed through a soft-masked hue rotation. Icons with no
Crystal blue in them (folder-red, folder-green, user-home, ...) come out
byte-identical because the mask is hue-driven rather than filename-driven.

    .venv/bin/python tools/generate_theme.py --color-name Red
    .venv/bin/python tools/generate_theme.py --color-name Ocean --hue 190
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

from recolor import BLUE_CENTER, recolor_file, shift_for_target

PRESETS = {
    "red": 0.0,
    "orange": 25.0,
    "yellow": 50.0,
    "green": 120.0,
    "teal": 175.0,
    "cyan": 190.0,
    "blue": BLUE_CENTER,
    "purple": 280.0,
    "pink": 320.0,
}

IGNORE = shutil.ignore_patterns(
    ".git", ".github", ".venv", "__pycache__", "tools", "*.md", "*.jpg", "*.pyc"
)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def titleize(name: str) -> str:
    return "-".join(p.capitalize() for p in slugify(name).split("-"))


def resolve_shift(args: argparse.Namespace) -> float:
    if args.hue_shift is not None:
        return float(args.hue_shift)
    if args.hue is not None:
        return shift_for_target(float(args.hue))
    preset = PRESETS.get(slugify(args.color_name))
    if preset is None:
        raise SystemExit(
            f"'{args.color_name}' is not a known preset. Pass --hue or --hue-shift, "
            f"or pick one of: {', '.join(sorted(PRESETS))}"
        )
    return shift_for_target(preset)


def update_index_theme(path: Path, display_name: str) -> None:
    text = path.read_text(encoding="utf-8")
    comment = (
        f"A remixed Crystal icon theme for modern Linux desktop environments "
        f"({display_name} folder variant)"
    )
    text = re.sub(r"^Name=.*$", f"Name={display_name}", text, count=1, flags=re.M)
    text = re.sub(r"^Comment=.*$", f"Comment={comment}", text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


def update_install_script(path: Path, slug: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text = text.replace("icons/crystal-remix/", f"icons/{slug}/")
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def copy_theme(src: Path, dst: Path, force: bool) -> None:
    if dst.exists():
        if not force:
            raise SystemExit(f"{dst} already exists. Pass --force to replace it.")
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORE)


def places_icons(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("*/places/*.png") if p.is_file())


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--color-name", required=True,
                    help="variant name, e.g. Red. Doubles as a hue preset when "
                         "neither --hue nor --hue-shift is given")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--hue", type=float,
                       help="absolute target hue in degrees (0-359) for the blue band")
    group.add_argument("--hue-shift", type=float,
                       help="raw hue delta in degrees, applied to the blue band")
    ap.add_argument("--source", default=str(Path(__file__).resolve().parent.parent),
                    help="theme root to copy from (default: repo root)")
    ap.add_argument("--dest-parent", default=None,
                    help="where the variant directory is created "
                         "(default: the source's parent directory)")
    ap.add_argument("--sat-scale", type=float, default=1.0,
                    help="optional saturation multiplier inside the mask")
    ap.add_argument("--val-scale", type=float, default=1.0,
                    help="optional value multiplier inside the mask")
    ap.add_argument("--force", action="store_true",
                    help="replace the destination directory if it exists")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change without writing anything")
    args = ap.parse_args()

    src = Path(args.source).resolve()
    if not (src / "index.theme").is_file():
        raise SystemExit(f"{src} does not look like an icon theme (no index.theme)")

    shift = resolve_shift(args)
    color = titleize(args.color_name)
    dir_name = f"Crystal-Remix-{color}"
    slug = slugify(dir_name)
    dest_parent = Path(args.dest_parent).resolve() if args.dest_parent else src.parent
    dst = dest_parent / dir_name
    display_name = f"Crystal Remix {color}"

    print(f"source      {src}")
    print(f"destination {dst}")
    print(f"hue shift   {shift:+.1f} deg (blue {BLUE_CENTER:.0f} -> "
          f"{(BLUE_CENTER + shift) % 360:.0f})")
    if args.sat_scale != 1.0 or args.val_scale != 1.0:
        print(f"sat x{args.sat_scale:.2f}  val x{args.val_scale:.2f}")

    if args.dry_run:
        targets = places_icons(src)
        print(f"dry run: would copy the theme and process {len(targets)} places icons")
        return

    started = time.monotonic()
    copy_theme(src, dst, args.force)
    print(f"copied theme in {time.monotonic() - started:.1f}s")

    targets = places_icons(dst)
    total = len(targets)
    recolored = untouched = 0
    pixels = 0

    for i, icon in enumerate(targets, 1):
        try:
            changed = recolor_file(icon, shift, args.sat_scale, args.val_scale)
        except OSError as exc:
            print(f"  warning: {exc}", file=sys.stderr)
            continue
        if changed:
            recolored += 1
            pixels += changed
        else:
            untouched += 1
        if i % 50 == 0 or i == total:
            print(f"  processed {i}/{total} icons...")

    update_index_theme(dst / "index.theme", display_name)
    update_install_script(dst / "install.sh", slug)

    elapsed = time.monotonic() - started
    print(f"done in {elapsed:.1f}s: {recolored} icons recolored "
          f"({pixels} pixels), {untouched} left untouched")
    print(f"install with: cd {dst} && ./install.sh")


if __name__ == "__main__":
    main()
