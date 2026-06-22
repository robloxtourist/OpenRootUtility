# OpenRoot Utility

Утилита для автоматизации открытия root-доступа на тестовых терминалах.

## Возможности

* Подключение под support-пользователем
* Установка пароля root
* Включение PermitRootLogin
* Перезапуск SSH

## Требования

* expect
* ssh

## Запуск

```bash
chmod +x openroot
./openroot
```

## Установка

```bash
git clone git@github.com:kpacuboe/OpenRootUtility.git
cd OpenRootUtility

chmod +x install.sh
./install.sh
```

После установки:

```bash
openroot
```
