#!/usr/bin/env bash

set -euo pipefail

INSTALL_DIR="${OPENROOT_INSTALL_DIR:-$HOME/.local/share/openroot}"
BIN_DIR="${OPENROOT_BIN_DIR:-$HOME/.local/bin}"
SYSTEM_BIN_DIR="${OPENROOT_SYSTEM_BIN_DIR:-/usr/local/bin}"
PROFILE_FILE="${OPENROOT_PROFILE_FILE:-$HOME/.profile}"
PATH_MARKER="# OpenRoot Utility PATH"

echo "================================="
echo " OpenRoot Utility Uninstaller"
echo "================================="
echo ""

rm -f "$BIN_DIR/openroot" "$BIN_DIR/openroot-gui"
rm -rf "$INSTALL_DIR"

if [[ -L "$SYSTEM_BIN_DIR/openroot" || -L "$SYSTEM_BIN_DIR/openroot-gui" ]]; then
    if [[ -w "$SYSTEM_BIN_DIR" ]]; then
        rm -f "$SYSTEM_BIN_DIR/openroot" "$SYSTEM_BIN_DIR/openroot-gui"
    elif command -v sudo >/dev/null 2>&1; then
        sudo rm -f "$SYSTEM_BIN_DIR/openroot" "$SYSTEM_BIN_DIR/openroot-gui"
    fi
fi

if [[ -f "$PROFILE_FILE" ]] && grep -Fq "$PATH_MARKER" "$PROFILE_FILE"; then
    sed -i "\|$PATH_MARKER|,+1d" "$PROFILE_FILE"
    echo "[+] PATH запись удалена из $PROFILE_FILE"
fi

echo "[+] OpenRoot удален"
echo ""
