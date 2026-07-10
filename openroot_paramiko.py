#!/usr/bin/env python3

from __future__ import annotations

import logging
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Ошибка: не установлен модуль rich.")
    print("Установите зависимости: python3 -m pip install -r requirements.txt")
    sys.exit(1)

try:
    from openroot_core import (
        APPNAME,
        VERSION,
        OpenRootError,
        OpenRootResult,
        close_terminal_root,
        open_terminal_root,
        setup_logging,
    )
except ImportError as exc:
    if exc.name == "paramiko":
        print("Ошибка: не установлен модуль paramiko.")
        print("Установите зависимости: python3 -m pip install -r requirements.txt")
        sys.exit(1)
    raise


console = Console()


def print_header() -> None:
    title = Text(APPNAME, style="bold cyan")
    title.append(f"\n{VERSION}", style="dim")
    title.append("\nDebian / NXP root access utility", style="white")
    console.print()
    console.print(Panel(title, border_style="cyan", padding=(1, 2)))
    console.print()


def print_result(result: OpenRootResult) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Root логин", "root")

    if result.root_status == "closed":
        table.add_row("Статус", "[green]Root SSH закрыт[/green]")
        table.add_row("PermitRootLogin", "prohibit-password")
    elif result.root_status == "changed":
        table.add_row("Статус", "[green]Root открыт и проверен[/green]")
        table.add_row("Root пароль", result.root_password)
    elif result.root_status == "verified":
        table.add_row("Статус", "[green]Root открыт и проверен[/green]")
        table.add_row("Root пароль", result.root_password)
    else:
        table.add_row("Статус", "[yellow]Root SSH не проверялся[/yellow]")

    console.print()
    console.print(Panel(table, title="[bold green]УСПЕШНО[/bold green]", border_style="green"))
    console.print()


def choose_action() -> str:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column()
    table.add_row("1", "Открыть root")
    table.add_row("2", "Закрыть root")
    console.print(Panel(table, title="Действие", border_style="blue"))

    choice = Prompt.ask("Выбор", choices=["1", "2"], default="1")
    if choice == "1":
        return "open"
    return "close"


def progress(message: str) -> None:
    if message == "OK":
        console.print("[green]OK[/green]")
    elif message.endswith("... OK"):
        console.print(f"[green]✓[/green] {message[:-6]}")
    elif message.startswith("Платформа:"):
        console.print(f"[cyan]{message}[/cyan]")
    elif message.endswith("..."):
        console.print(f"[dim]{message}[/dim]")
    else:
        console.print(message)


def ask_inputs(action: str) -> tuple[str, str, str, str]:
    console.print(Panel("Данные подключения", border_style="blue"))
    host = Prompt.ask("IP терминала").strip()
    if not host:
        raise OpenRootError("IP терминала не указан")

    suffix = Prompt.ask("Последние 5 символов support-логина").strip()
    support_password = Prompt.ask("Пароль поддержки", password=True)
    if action == "open":
        root_password = Prompt.ask("Пароль root", default="123", password=True)
    else:
        root_password = Prompt.ask("Пароль root для проверки закрытия", default="123", password=True)

    return host, suffix, support_password, root_password


def main() -> int:
    setup_logging()
    print_header()

    try:
        action = choose_action()
        host, suffix, support_password, root_password = ask_inputs(action)
    except OpenRootError as exc:
        console.print(f"[bold red]Ошибка:[/bold red] {exc}")
        return 1
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Операция прервана пользователем[/yellow]")
        return 130

    try:
        console.print()
        if action == "open":
            result = open_terminal_root(
                host=host,
                suffix=suffix,
                support_password=support_password,
                root_password=root_password,
                progress=progress,
            )
        else:
            result = close_terminal_root(
                host=host,
                suffix=suffix,
                support_password=support_password,
                root_password=root_password,
                progress=progress,
            )
    except OpenRootError as exc:
        console.print()
        console.print(Panel(str(exc), title="[bold red]FAILED[/bold red]", border_style="red"))
        logging.exception("openroot failed")
        return 1
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Операция прервана пользователем[/yellow]")
        return 130

    print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
