#!/usr/bin/env bash

set -euo pipefail

INSTALL_DIR="${OPENROOT_INSTALL_DIR:-$HOME/.local/share/openroot}"
BIN_DIR="${OPENROOT_BIN_DIR:-$HOME/.local/bin}"

echo "================================="
echo " OpenRoot Utility Uninstaller"
echo "================================="
echo ""

rm -f "$BIN_DIR/openroot" "$BIN_DIR/openroot-gui"
rm -rf "$INSTALL_DIR"

echo "[+] OpenRoot удален"
echo ""
