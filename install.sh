#!/usr/bin/env bash

set -euo pipefail

APP_NAME="OpenRoot Utility"
INSTALL_DIR="${OPENROOT_INSTALL_DIR:-$HOME/.local/share/openroot}"
BIN_DIR="${OPENROOT_BIN_DIR:-$HOME/.local/bin}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "================================="
echo " ${APP_NAME} Installer"
echo "================================="
echo ""

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Ошибка: python3 не найден"
    echo "Установите: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
    echo "Ошибка: модуль venv недоступен"
    echo "Установите: sudo apt install python3-venv"
    exit 1
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
    echo "Внимание: tkinter не найден. CLI будет работать, GUI может не запуститься."
    echo "Для GUI установите: sudo apt install python3-tk"
    echo ""
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

echo "[+] Копирование файлов в $INSTALL_DIR"
cp openroot_core.py "$INSTALL_DIR/"
cp openroot_paramiko.py "$INSTALL_DIR/"
cp openroot_gui.py "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

echo "[+] Создание virtualenv"
"$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv"

echo "[+] Установка Python-зависимостей"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/.venv/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt"

echo "[+] Создание команд openroot и openroot-gui"
cat > "$BIN_DIR/openroot" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/openroot_paramiko.py" "\$@"
EOF

cat > "$BIN_DIR/openroot-gui" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/openroot_gui.py" "\$@"
EOF

chmod +x "$BIN_DIR/openroot" "$BIN_DIR/openroot-gui"

echo ""
echo "[+] OpenRoot установлен"
echo ""

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "ВНИМАНИЕ: $BIN_DIR отсутствует в PATH"
    echo ""
    echo "Добавьте в ~/.bashrc или ~/.profile:"
    echo "export PATH=\"$BIN_DIR:\$PATH\""
    echo ""
    echo "После этого выполните:"
    echo "source ~/.bashrc"
    echo ""
fi

echo "Запуск CLI:"
echo "  openroot"
echo ""
echo "Запуск GUI:"
echo "  openroot-gui"
echo ""
