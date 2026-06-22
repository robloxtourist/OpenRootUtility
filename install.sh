#!/bin/bash

set -e

echo "================================="
echo " OpenRoot Utility Installer"
echo "================================="
echo ""

if ! command -v expect >/dev/null 2>&1; then
echo "[+] Установка expect..."
sudo apt update
sudo apt install -y expect
else
echo "[+] expect уже установлен"
fi

mkdir -p "$HOME/bin"

cp openroot "$HOME/bin/openroot"
chmod +x "$HOME/bin/openroot"

echo ""
echo "[+] OpenRoot установлен"
echo ""

if ! echo "$PATH" | grep -q "$HOME/bin"; then
echo "ВНИМАНИЕ:"
echo "~/bin отсутствует в PATH"
echo ""
echo "Добавьте в ~/.bashrc:"
echo 'export PATH="$HOME/bin:$PATH"'
echo ""
fi

echo "Запуск:"
echo "openroot"
echo ""
