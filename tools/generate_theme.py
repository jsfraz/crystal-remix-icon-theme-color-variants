#!/usr/bin/env python3
"""Generate a recolored variant of the Crystal Remix icon theme.

The source theme is copied to a sibling directory and every PNG in it, across
all contexts, is passed through a soft-masked hue rotation for a unified system
accent color. Icons with no Crystal blue in them (flag, dialog-ok, folder-red,
...) come out byte-identical because the mask is hue-driven rather than
filename-driven, so no allowlist is needed.

    .venv/bin/python tools/generate_theme.py --color-name Red
    .venv/bin/python tools/generate_theme.py --color-name Ocean --hue 190
    .venv/bin/python tools/generate_theme.py --color-name Red --jobs 1
"""

from __future__ import annotations

import argparse
import functools
import os
import re
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from recolor import BLUE_CENTER, init_worker, recolor_file, shift_for_target

SIZE_DIR = re.compile(r"^\d+x\d+$")

PRESETS = {
    "red": 0.0,
    "orange": 25.0,
    "yellow": 50.0,
    "green": 120.0,
    "teal": 175.0,
    "blue": BLUE_CENTER,
    "purple": 280.0,
    "pink": 320.0,
}

_IGNORE_PATTERNS = shutil.ignore_patterns(
    "__pycache__", "tools", "docs", "build.sh", "*.md", "*.jpg", "*.pyc"
)


def IGNORE(directory, names):
    """Skip the tooling and every dotfile, matching what install.sh rsyncs."""
    return set(_IGNORE_PATTERNS(directory, names)) | {n for n in names if n.startswith(".")}


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


def theme_icons(root: Path) -> list[Path]:
    """Every icon in the theme, across all contexts.

    Restricted to `<size>x<size>/<context>/` so tooling output can never be
    picked up if the caller points --source at a working directory.
    """
    return sorted(
        p for p in root.glob("*/*/*.png")
        if p.is_file() and SIZE_DIR.match(p.relative_to(root).parts[0])
    )


def _process(path: Path, hue_shift: float, sat_scale: float, val_scale: float) -> int:
    """Worker entry point. Returns pixels touched, or -1 if the file failed."""
    try:
        return recolor_file(path, hue_shift, sat_scale, val_scale)
    except OSError:
        return -1


def iter_results(targets, fn, jobs: int):
    """Map fn over targets, in a process pool unless jobs is 1.

    ProcessPoolExecutor.map preserves input order, so the caller can zip the
    results straight back against targets. Workers edit the already-copied
    destination files in place and return only an int, which keeps image data
    out of the IPC path entirely.
    """
    if jobs == 1:
        yield from map(fn, targets)
        return
    with ProcessPoolExecutor(max_workers=jobs, initializer=init_worker) as ex:
        yield from ex.map(fn, targets, chunksize=16)


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
    ap.add_argument("--jobs", type=int, default=None,
                    help="worker processes (default: all CPU cores, currently "
                         f"{os.cpu_count()}). Use 1 to run in-process")
    ap.add_argument("--force", action="store_true",
                    help="replace the destination directory if it exists")
    ap.add_argument("--no-hint", action="store_true",
                    help="skip the closing 'install with' line, for callers such "
                         "as build.sh that install the variant themselves")
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
        targets = theme_icons(src)
        print(f"dry run: would copy the theme and process {len(targets)} icons")
        return

    started = time.monotonic()
    copy_theme(src, dst, args.force)
    print(f"copied theme in {time.monotonic() - started:.1f}s")

    targets = theme_icons(dst)
    total = len(targets)
    jobs = args.jobs if args.jobs else (os.cpu_count() or 1)
    jobs = max(1, min(jobs, total))
    print(f"processing {total} icons on {jobs} worker{'s' if jobs > 1 else ''}")

    fn = functools.partial(_process, hue_shift=shift,
                           sat_scale=args.sat_scale, val_scale=args.val_scale)
    recolored = skipped = failed = 0
    pixels = 0
    by_context: Counter[str] = Counter()
    context_totals: Counter[str] = Counter()
    step = max(1, total // 20)

    for i, (icon, changed) in enumerate(zip(targets, iter_results(targets, fn, jobs)), 1):
        context = icon.relative_to(dst).parts[1]
        context_totals[context] += 1
        if changed < 0:
            failed += 1
            print(f"  warning: failed to process {icon}", file=sys.stderr)
        elif changed:
            recolored += 1
            pixels += changed
            by_context[context] += 1
        else:
            skipped += 1
        if i % step == 0 or i == total:
            print(f"  {100 * i // total:3d}%  {i}/{total}")

    update_index_theme(dst / "index.theme", display_name)
    update_install_script(dst / "install.sh", slug)

    elapsed = time.monotonic() - started
    print(f"done in {elapsed:.1f}s: {recolored} icons recolored ({pixels} pixels), "
          f"{skipped} had no Crystal blue and were left untouched")
    if failed:
        print(f"  {failed} icons failed", file=sys.stderr)
    print("  by context:")
    for context in sorted(context_totals):
        hit, tot = by_context[context], context_totals[context]
        print(f"    {context:12} {hit:5d} / {tot:5d}  ({100 * hit // tot:3d}%)")
    if not args.no_hint:
        print(f"install with: cd {dst} && ./install.sh")


if __name__ == "__main__":
    main()
