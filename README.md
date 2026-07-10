# OpenRoot Utility

Утилита для управления root-доступом на тестовых терминалах.

## Возможности

* Подключение под support-пользователем
* Автоопределение Debian / NXP
* Открытие root SSH
* Закрытие root SSH
* Настройка `PermitRootLogin`
* Перезапуск SSH-службы
* Проверка root SSH после операции
* CLI с оформлением на Rich
* GUI-прототип на CustomTkinter

## Установка

```bash
git clone https://github.com/robloxtourist/OpenRootUtility.git
cd OpenRootUtility
chmod +x install.sh
./install.sh
```

Если нужен GUI, на Debian/Ubuntu может понадобиться:

```bash
sudo apt install python3-tk
```

После установки:

```bash
git clone git@github.com:robloxtourist/OpenRootUtility.git
cd OpenRootUtility

GUI:

```bash
openroot-gui
```

Если `~/.local/bin` не добавлен в `PATH`, installer покажет команду, которую нужно добавить в `~/.bashrc` или `~/.profile`.

## Локальный запуск без установки

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python openroot_paramiko.py
```

GUI:

```bash
.venv/bin/python openroot_gui.py
```

## Удаление

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## Структура

* `openroot_core.py` — основная логика SSH, Debian/NXP, open/close
* `openroot_paramiko.py` — CLI
* `openroot_gui.py` — GUI
* `install.sh` — установка в `~/.local/share/openroot`
* `uninstall.sh` — удаление
