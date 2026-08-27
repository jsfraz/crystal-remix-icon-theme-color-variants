#!/bin/sh

set -e -x

INSTALL_PATH="$HOME/.local/share/icons/crystal-remix/"

if [ "$USER" = "root" ]; then
    INSTALL_PATH="/usr/share/icons/crystal-remix/"
fi

mkdir -p ${INSTALL_PATH}
rsync -a --exclude=".*" --exclude="tools" --exclude="docs" \
    --exclude="build.sh" --exclude="*.md" --exclude="*.jpg" . ${INSTALL_PATH}

which gtk-update-icon-cache && gtk-update-icon-cache -q ${INSTALL_PATH}
