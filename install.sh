#!/usr/bin/env bash

set -euo pipefail

APP_NAME="OpenRoot Utility"
INSTALL_DIR="${OPENROOT_INSTALL_DIR:-$HOME/.local/share/openroot}"
BIN_DIR="${OPENROOT_BIN_DIR:-$HOME/.local/bin}"
SYSTEM_BIN_DIR="${OPENROOT_SYSTEM_BIN_DIR:-/usr/local/bin}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PROFILE_FILE="${OPENROOT_PROFILE_FILE:-$HOME/.profile}"
PATH_MARKER="# OpenRoot Utility PATH"

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

if [[ ":$PATH:" == *":$SYSTEM_BIN_DIR:"* ]]; then
    echo "[+] Создание системных команд в $SYSTEM_BIN_DIR"
    mkdir -p "$SYSTEM_BIN_DIR" 2>/dev/null || true
    if [[ -w "$SYSTEM_BIN_DIR" ]]; then
        ln -sf "$BIN_DIR/openroot" "$SYSTEM_BIN_DIR/openroot"
        ln -sf "$BIN_DIR/openroot-gui" "$SYSTEM_BIN_DIR/openroot-gui"
    elif command -v sudo >/dev/null 2>&1; then
        if sudo ln -sf "$BIN_DIR/openroot" "$SYSTEM_BIN_DIR/openroot" \
            && sudo ln -sf "$BIN_DIR/openroot-gui" "$SYSTEM_BIN_DIR/openroot-gui"; then
            :
        else
            echo "Внимание: не удалось создать системные команды через sudo."
        fi
    else
        echo "Внимание: sudo не найден, системные команды не созданы."
    fi
fi

echo ""
echo "[+] OpenRoot установлен"
echo ""

if [[ ":$PATH:" != *":$BIN_DIR:"* && ! -x "$SYSTEM_BIN_DIR/openroot" ]]; then
    if ! grep -Fq "$PATH_MARKER" "$PROFILE_FILE" 2>/dev/null; then
        {
            echo ""
            echo "$PATH_MARKER"
            echo "export PATH=\"$BIN_DIR:\$PATH\""
        } >> "$PROFILE_FILE"
        echo "[+] $BIN_DIR добавлен в $PROFILE_FILE"
    else
        echo "[+] PATH уже настроен в $PROFILE_FILE"
    fi
    echo ""
    echo "Откройте новый терминал или выполните:"
    echo "source \"$PROFILE_FILE\""
    echo ""
fi

echo "Запуск CLI:"
if command -v openroot >/dev/null 2>&1; then
    echo "  openroot"
else
    echo "  $BIN_DIR/openroot"
fi
echo ""
echo "Запуск GUI:"
if command -v openroot-gui >/dev/null 2>&1; then
    echo "  openroot-gui"
else
    echo "  $BIN_DIR/openroot-gui"
fi
echo ""
