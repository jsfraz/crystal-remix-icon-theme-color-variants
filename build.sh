#!/bin/sh
#
# Build recolored variants of the Crystal Remix icon theme and install them.
#
#   ./build.sh red purple        build and install two variants
#   ./build.sh all               build and install every available color
#
# Each variant is generated in a temporary directory, installed, and then
# removed again, so nothing is left lying around next to the repository.
# The Python virtualenv is created on first run, so there is nothing to set up
# by hand.

set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
VENV="$REPO/.venv"
PY="$VENV/bin/python"

JOBS=""
WORK_PARENT=""
WORKDIR=""
COLORS=""

# install.sh picks its target the same way; keep the two in sync so the summary
# below never claims a path the install did not use.
if [ "$USER" = "root" ]; then
    INSTALL_ROOT="/usr/share/icons"
else
    INSTALL_ROOT="$HOME/.local/share/icons"
fi

usage() {
    cat <<'EOF'
Usage: ./build.sh [options] <color>... | all

Builds each color variant and installs it straight into the icon directory.

Options:
  --work-dir DIR  where the temporary build happens (default: $TMPDIR)
  --jobs N        worker processes to use (default: all CPU cores)
  --list          list the available colors and exit
  -h, --help      show this help

Examples:
  ./build.sh red
  ./build.sh red green purple
  ./build.sh all
EOF
}

cleanup() {
    if [ -n "$WORKDIR" ] && [ -d "$WORKDIR" ]; then
        rm -rf "$WORKDIR"
    fi
}
trap 'cleanup' EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

ensure_venv() {
    if [ ! -x "$PY" ]; then
        echo "Setting up the Python environment in .venv (first run only)..."
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --quiet --disable-pip-version-check \
            -r "$REPO/tools/requirements.txt"
    fi
}

# Read the color list from generate_theme.py so it cannot drift out of sync.
list_colors() {
    "$PY" - "$1" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
from generate_theme import PRESETS
print(" ".join(sorted(PRESETS)))
EOF
}

variant_dir() {
    "$PY" - "$REPO/tools" "$1" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
from generate_theme import titleize
print("Crystal-Remix-" + titleize(sys.argv[2]))
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --work-dir) WORK_PARENT="$2"; shift ;;
        --jobs) JOBS="$2"; shift ;;
        --list)
            ensure_venv
            echo "Available colors: $(list_colors "$REPO/tools")"
            exit 0
            ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
        *) COLORS="$COLORS $1" ;;
    esac
    shift
done

if [ -z "$COLORS" ]; then
    usage >&2
    exit 1
fi

ensure_venv

if [ "$(echo "$COLORS" | tr -d ' ')" = "all" ]; then
    COLORS="$(list_colors "$REPO/tools")"
fi

if [ -n "$WORK_PARENT" ]; then
    mkdir -p "$WORK_PARENT"
else
    WORK_PARENT="${TMPDIR:-/tmp}"
fi
WORKDIR="$(mktemp -d "$WORK_PARENT/crystal-remix-build.XXXXXX")"

EXTRA=""
[ -n "$JOBS" ] && EXTRA="$EXTRA --jobs $JOBS"

INSTALLED=""

for color in $COLORS; do
    echo
    echo "=== Building $color ==="
    variant="$(variant_dir "$color")"

    # shellcheck disable=SC2086
    "$PY" "$REPO/tools/generate_theme.py" --color-name "$color" --force \
        --no-hint --dest-parent "$WORKDIR" $EXTRA

    echo "=== Installing $color ==="
    (cd "$WORKDIR/$variant" && ./install.sh)

    # Drop it immediately so a full run needs room for one variant, not all of them.
    rm -rf "$WORKDIR/$variant"
    INSTALLED="$INSTALLED $(echo "$variant" | tr 'A-Z' 'a-z')"
done

echo
echo "Installed under $INSTALL_ROOT:"
for slug in $INSTALLED; do
    echo "  $slug"
done
echo "Pick the theme in the icon section of your desktop settings."
