from __future__ import annotations

import logging
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import paramiko


APPNAME = "OpenRoot Utility"
VERSION = "v1.0.1-paramiko-dev2"
LOG_PATH = Path.home() / "open_root.log"
TIMEOUT = 30
PROMPT_RE = r"(?m)[#$]\s*$"

Platform = Literal["debian", "nxp", "unknown"]
RootStatus = Literal["changed", "verified", "closed"]
ProgressCallback = Callable[[str], None]


class OpenRootError(Exception):
    pass


def permit_root_login_command(value: str) -> str:
    quoted_value = shlex.quote(value)
    return (
        "sh -c "
        + shlex.quote(
            "if grep -q '^#\\?PermitRootLogin' /etc/ssh/sshd_config; then "
            f"sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin {value}/' "
            "/etc/ssh/sshd_config; "
            f"else echo PermitRootLogin {quoted_value} >> /etc/ssh/sshd_config; fi"
        )
    )


@dataclass
class CommandResult:
    command: str
    exit_status: int
    stdout: str
    stderr: str


@dataclass
class OpenRootResult:
    platform: Platform
    root_status: RootStatus
    root_password: str


class ShellSession:
    def __init__(self, client: paramiko.SSHClient) -> None:
        self.channel = client.invoke_shell()
        self.channel.settimeout(0.2)
        self.buffer = ""

    def close(self) -> None:
        self.channel.close()

    def send_line(self, line: str) -> None:
        self.channel.send(line + "\n")

    def clear(self) -> None:
        self.buffer = ""
        self._read_available(0.4)
        self.buffer = ""

    def expect(self, patterns: dict[str, str], timeout: int = TIMEOUT) -> tuple[str, str]:
        compiled = {name: re.compile(pattern) for name, pattern in patterns.items()}
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            self._read_available(0.2)
            for name, pattern in compiled.items():
                if pattern.search(self.buffer):
                    return name, self.buffer
            time.sleep(0.05)

        raise OpenRootError("Таймаут ожидания ответа терминала")

    def _read_available(self, wait_seconds: float) -> None:
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if self.channel.recv_ready():
                chunk = self.channel.recv(4096).decode("utf-8", errors="replace")
                self.buffer += chunk
                deadline = time.monotonic() + wait_seconds
                continue
            time.sleep(0.05)


def setup_logging() -> None:
    log_path = LOG_PATH
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8"):
            pass
    except OSError:
        log_path = Path.cwd() / "open_root.log"

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def ping_host(host: str) -> bool:
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "2", host],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def connect_ssh(host: str, username: str, password: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=TIMEOUT,
            auth_timeout=TIMEOUT,
            banner_timeout=TIMEOUT,
            look_for_keys=False,
            allow_agent=False,
        )
    except paramiko.AuthenticationException as exc:
        raise OpenRootError("SSH аутентификация не удалась") from exc
    except Exception as exc:
        raise OpenRootError(f"SSH подключение не удалось: {exc}") from exc

    return client


def run_command(client: paramiko.SSHClient, command: str, timeout: int = TIMEOUT) -> CommandResult:
    logging.info("run command: %s", command)
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    result = CommandResult(
        command=command,
        exit_status=exit_status,
        stdout=stdout.read().decode("utf-8", errors="replace"),
        stderr=stderr.read().decode("utf-8", errors="replace"),
    )
    logging.info(
        "command finished: exit=%s stdout=%r stderr=%r",
        result.exit_status,
        result.stdout,
        result.stderr,
    )
    return result


def run_sudo(
    client: paramiko.SSHClient,
    support_password: str,
    command: str,
    timeout: int = TIMEOUT,
) -> CommandResult:
    sudo_command = f"sudo -S -p '' {command}"
    logging.info("run sudo command: %s", command)

    stdin, stdout, stderr = client.exec_command(sudo_command, timeout=timeout, get_pty=True)
    stdin.write(support_password + "\n")
    stdin.flush()

    exit_status = stdout.channel.recv_exit_status()
    result = CommandResult(
        command=command,
        exit_status=exit_status,
        stdout=stdout.read().decode("utf-8", errors="replace"),
        stderr=stderr.read().decode("utf-8", errors="replace"),
    )
    logging.info(
        "sudo command finished: exit=%s stdout=%r stderr=%r",
        result.exit_status,
        result.stdout,
        result.stderr,
    )
    return result


def require_success(result: CommandResult, error_message: str) -> CommandResult:
    if result.exit_status != 0:
        details = (result.stderr or result.stdout).strip()
        if details:
            raise OpenRootError(f"{error_message}: {details}")
        raise OpenRootError(error_message)
    return result


def detect_platform(client: paramiko.SSHClient) -> Platform:
    result = require_success(
        run_command(client, "cat /etc/os-release"),
        "Не удалось определить платформу",
    )

    os_release = result.stdout
    if "ID=debian" in os_release:
        return "debian"
    if "ID=fsl-imx-xwayland" in os_release:
        return "nxp"
    return "unknown"


def open_terminal_root(
    host: str,
    suffix: str,
    support_password: str,
    root_password: str = "123",
    progress: ProgressCallback | None = None,
) -> OpenRootResult:
    emit = progress or (lambda _message: None)
    user = f"support-{suffix}"
    root_password = root_password or "123"

    emit("Проверка доступности терминала...")
    if not ping_host(host):
        raise OpenRootError(f"терминал {host} недоступен")
    emit("OK")

    client: paramiko.SSHClient | None = None
    try:
        emit("[1/4] Подключение к терминалу...")
        client = connect_ssh(host, user, support_password)
        emit("[1/4] Подключение к терминалу... OK")

        emit("Определение платформы...")
        platform = detect_platform(client)
        if platform == "debian":
            emit("Платформа: Debian")
            root_status = open_root_debian(host, client, support_password, root_password, emit)
        elif platform == "nxp":
            emit("Платформа: NXP")
            root_status = open_root_nxp(client, host, root_password, emit)
        else:
            raise OpenRootError("Не удалось определить платформу.")
    finally:
        if client is not None:
            client.close()

    return OpenRootResult(
        platform=platform,
        root_status=root_status,
        root_password=root_password,
    )


def close_terminal_root(
    host: str,
    suffix: str,
    support_password: str,
    root_password: str = "123",
    progress: ProgressCallback | None = None,
) -> OpenRootResult:
    emit = progress or (lambda _message: None)
    user = f"support-{suffix}"
    root_password = root_password or "123"

    emit("Проверка доступности терминала...")
    if not ping_host(host):
        raise OpenRootError(f"терминал {host} недоступен")
    emit("OK")

    client: paramiko.SSHClient | None = None
    try:
        emit("[1/4] Подключение к терминалу...")
        client = connect_ssh(host, user, support_password)
        emit("[1/4] Подключение к терминалу... OK")

        emit("Определение платформы...")
        platform = detect_platform(client)
        if platform == "debian":
            emit("Платформа: Debian")
            root_status = close_root_debian(host, client, support_password, root_password, emit)
        elif platform == "nxp":
            emit("Платформа: NXP")
            root_status = close_root_nxp(client, host, root_password, emit)
        else:
            raise OpenRootError("Не удалось определить платформу.")
    finally:
        if client is not None:
            client.close()

    return OpenRootResult(
        platform=platform,
        root_status=root_status,
        root_password=root_password,
    )


def open_root_debian(
    host: str,
    client: paramiko.SSHClient,
    support_password: str,
    root_password: str,
    emit: ProgressCallback,
) -> RootStatus:
    root_pair = shlex.quote(f"root:{root_password}")

    emit("[2/4] Установка пароля root...")
    require_success(
        run_sudo(client, support_password, f"sh -c {shlex.quote(f'echo {root_pair} | chpasswd')}"),
        "Не удалось изменить пароль root",
    )

    passwd_status = require_success(
        run_sudo(client, support_password, "passwd -S root"),
        "Не удалось проверить пароль root",
    )
    if "root P" not in passwd_status.stdout:
        raise OpenRootError("Пароль root не установлен")
    emit("[2/4] Установка пароля root... OK")

    emit("[3/4] Настройка SSH...")
    require_success(
        run_sudo(
            client,
            support_password,
            permit_root_login_command("yes"),
        ),
        "Не удалось изменить sshd_config",
    )

    permit_root = require_success(
        run_sudo(client, support_password, "grep '^PermitRootLogin' /etc/ssh/sshd_config"),
        "Не удалось проверить PermitRootLogin",
    )
    if "PermitRootLogin yes" not in permit_root.stdout:
        raise OpenRootError("PermitRootLogin не изменился")
    emit("[3/4] Настройка SSH... OK")

    emit("[4/4] Перезапуск SSH...")
    require_success(
        run_sudo(
            client,
            support_password,
            "sh -c 'systemctl restart sshd || systemctl restart ssh'",
        ),
        "Не удалось перезапустить SSH",
    )

    ssh_status = require_success(
        run_sudo(
            client,
            support_password,
            "sh -c 'if systemctl is-active sshd >/dev/null 2>&1 || "
            "systemctl is-active ssh >/dev/null 2>&1; then echo __SSH_OK__; "
            "else echo __SSH_FAIL__; fi'",
        ),
        "Не удалось проверить состояние SSH",
    )
    if "__SSH_OK__" not in ssh_status.stdout:
        raise OpenRootError("SSH не запущен")
    emit("[4/4] Перезапуск SSH... OK")

    emit("Проверка root SSH...")
    verify_root_login(host, root_password)
    emit("Проверка root SSH... OK")
    return "changed"


def close_root_debian(
    host: str,
    client: paramiko.SSHClient,
    support_password: str,
    root_password: str,
    emit: ProgressCallback,
) -> RootStatus:
    emit("[2/4] Закрытие root SSH...")
    require_success(
        run_sudo(
            client,
            support_password,
            permit_root_login_command("prohibit-password"),
        ),
        "Не удалось изменить sshd_config",
    )

    permit_root = require_success(
        run_sudo(client, support_password, "grep '^PermitRootLogin' /etc/ssh/sshd_config"),
        "Не удалось проверить PermitRootLogin",
    )
    if "PermitRootLogin prohibit-password" not in permit_root.stdout:
        raise OpenRootError("PermitRootLogin не изменился")
    emit("[2/4] Закрытие root SSH... OK")

    emit("[3/4] Перезапуск SSH...")
    require_success(
        run_sudo(
            client,
            support_password,
            "sh -c 'systemctl restart sshd || systemctl restart ssh'",
        ),
        "Не удалось перезапустить SSH",
    )

    ssh_status = require_success(
        run_sudo(
            client,
            support_password,
            "sh -c 'if systemctl is-active sshd >/dev/null 2>&1 || "
            "systemctl is-active ssh >/dev/null 2>&1; then echo __SSH_OK__; "
            "else echo __SSH_FAIL__; fi'",
        ),
        "Не удалось проверить состояние SSH",
    )
    if "__SSH_OK__" not in ssh_status.stdout:
        raise OpenRootError("SSH не запущен")
    emit("[3/4] Перезапуск SSH... OK")

    emit("[4/4] Проверка закрытия root SSH...")
    verify_root_login_denied(host, root_password)
    emit("[4/4] Проверка закрытия root SSH... OK")
    return "closed"


def restart_ssh_nxp(shell: ShellSession) -> None:
    shell.clear()
    shell.send_line(
        "if systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || "
        "/etc/init.d/sshd restart 2>/dev/null || /etc/init.d/ssh restart 2>/dev/null; "
        "then echo __RESTART_OK__; else echo __RESTART_FAIL__; fi"
    )
    _, output = shell.expect({"ok": "__RESTART_OK__", "fail": "__RESTART_FAIL__"})
    if "__RESTART_OK__" not in output:
        raise OpenRootError("Не удалось перезапустить SSH")
    shell.expect({"prompt": PROMPT_RE})


def check_ssh_nxp(shell: ShellSession) -> None:
    shell.clear()
    shell.send_line(
        "if systemctl is-active sshd >/dev/null 2>&1 || "
        "systemctl is-active ssh >/dev/null 2>&1 || "
        "pidof sshd >/dev/null 2>&1 || pidof dropbear >/dev/null 2>&1; "
        "then echo __SSH_OK__; else echo __SSH_FAIL__; fi"
    )
    _, output = shell.expect({"ok": "__SSH_OK__", "fail": "__SSH_FAIL__"})
    if "__SSH_OK__" not in output:
        raise OpenRootError("SSH не запущен")


def configure_permit_root_login_nxp(shell: ShellSession, value: str = "yes") -> None:
    shell.clear()
    quoted_value = shlex.quote(value)
    shell.send_line(
        "if grep -q '^#\\?PermitRootLogin' /etc/ssh/sshd_config; then "
        f"sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin {value}/' /etc/ssh/sshd_config; "
        f"else echo PermitRootLogin {quoted_value} >> /etc/ssh/sshd_config; fi; "
        "grep '^PermitRootLogin' /etc/ssh/sshd_config"
    )
    _, output = shell.expect({"value": f"PermitRootLogin {re.escape(value)}", "prompt": PROMPT_RE})
    if f"PermitRootLogin {value}" not in output:
        raise OpenRootError("PermitRootLogin не изменился")
    shell.expect({"prompt": PROMPT_RE})


def verify_root_login(host: str, root_password: str) -> None:
    last_error: OpenRootError | None = None

    for _ in range(5):
        root_client: paramiko.SSHClient | None = None
        try:
            root_client = connect_ssh(host, "root", root_password)
            result = require_success(
                run_command(root_client, "id -u"),
                "Не удалось проверить root SSH",
            )
            if result.stdout.strip() != "0":
                raise OpenRootError("Root SSH подключился, но пользователь не root")
            return
        except OpenRootError as exc:
            last_error = exc
            time.sleep(2)
        finally:
            if root_client is not None:
                root_client.close()

    if last_error is not None:
        if "аутентификация" in str(last_error):
            raise OpenRootError(
                "Root SSH не подтвердился: пароль root не подошел или вход root запрещен"
            ) from last_error
        raise last_error
    raise OpenRootError("Не удалось проверить root SSH")


def verify_root_login_denied(host: str, root_password: str) -> None:
    last_error: OpenRootError | None = None

    for _ in range(5):
        root_client: paramiko.SSHClient | None = None
        try:
            root_client = connect_ssh(host, "root", root_password)
            raise OpenRootError("Root SSH все еще доступен по паролю")
        except OpenRootError as exc:
            if "аутентификация" in str(exc):
                return
            last_error = exc
            time.sleep(2)
        finally:
            if root_client is not None:
                root_client.close()

    if last_error is not None:
        raise last_error
    raise OpenRootError("Не удалось проверить закрытие root SSH")


def open_root_nxp(
    client: paramiko.SSHClient,
    host: str,
    root_password: str,
    emit: ProgressCallback,
) -> RootStatus:
    shell = ShellSession(client)
    try:
        shell.expect({"prompt": PROMPT_RE})

        emit("[2/5] Переход в root через su...")
        shell.clear()
        shell.send_line("su")
        matched, output = shell.expect(
            {
                "password": r"(?i)password:\s*$",
                "root_prompt": r"(?m)#\s*$",
            }
        )
        if matched == "password":
            shell.send_line(root_password)
            matched, output = shell.expect(
                {
                    "root_prompt": r"(?m)#\s*$",
                    "auth_failed": r"(?i)(authentication failure|su:.*failure|incorrect)",
                    "user_prompt": r"(?m)\$\s*$",
                }
            )
            if matched != "root_prompt":
                raise OpenRootError(
                    "su запросил пароль root, но введенный root-пароль не подошел"
                )
            emit("[2/5] Переход в root через su... OK")

            emit("[3/5] Настройка SSH...")
            configure_permit_root_login_nxp(shell)
            emit("[3/5] Настройка SSH... OK")

            emit("[4/5] Перезапуск SSH...")
            restart_ssh_nxp(shell)
            check_ssh_nxp(shell)
            emit("[4/5] Перезапуск SSH... OK")

            emit("[5/5] Проверка root SSH...")
            verify_root_login(host, root_password)
            emit("[5/5] Проверка root SSH... OK")
            return "verified"
        if "#" not in output:
            raise OpenRootError("Не удалось получить root shell после su")
        emit("[2/5] Переход в root через su... OK")

        emit("[3/5] Установка пароля root...")
        shell.clear()
        shell.send_line("passwd")
        shell.expect(
            {
                "new_password": r"(?i)(new|enter).*password.*:\s*$",
                "password": r"(?i)password:\s*$",
            }
        )
        shell.send_line(root_password)
        shell.expect(
            {
                "retype": r"(?i)(retype|repeat|again|confirm).*password.*:\s*$",
                "password": r"(?i)password:\s*$",
            }
        )
        shell.send_line(root_password)
        _, passwd_output = shell.expect({"prompt": PROMPT_RE}, timeout=TIMEOUT)
        lowered = passwd_output.lower()
        if any(word in lowered for word in ("failed", "failure", "error", "bad password")):
            raise OpenRootError("passwd вернул ошибку")
        emit("[3/5] Установка пароля root... OK")

        emit("[4/5] Настройка SSH...")
        configure_permit_root_login_nxp(shell)
        emit("[4/5] Настройка SSH... OK")

        emit("[5/5] Перезапуск SSH и проверка...")
        restart_ssh_nxp(shell)
        check_ssh_nxp(shell)
        verify_root_login(host, root_password)
        emit("[5/5] Перезапуск SSH и проверка... OK")
        return "changed"
    finally:
        shell.close()


def close_root_nxp(
    client: paramiko.SSHClient,
    host: str,
    root_password: str,
    emit: ProgressCallback,
) -> RootStatus:
    shell = ShellSession(client)
    try:
        shell.expect({"prompt": PROMPT_RE})

        emit("[2/5] Переход в root через su...")
        shell.clear()
        shell.send_line("su")
        matched, output = shell.expect(
            {
                "password": r"(?i)password:\s*$",
                "root_prompt": r"(?m)#\s*$",
            }
        )
        if matched == "password":
            shell.send_line(root_password)
            matched, output = shell.expect(
                {
                    "root_prompt": r"(?m)#\s*$",
                    "auth_failed": r"(?i)(authentication failure|su:.*failure|incorrect)",
                    "user_prompt": r"(?m)\$\s*$",
                }
            )
            if matched != "root_prompt":
                raise OpenRootError(
                    "su запросил пароль root, но введенный root-пароль не подошел"
                )
        if "#" not in output:
            raise OpenRootError("Не удалось получить root shell после su")
        emit("[2/5] Переход в root через su... OK")

        emit("[3/5] Закрытие root SSH...")
        configure_permit_root_login_nxp(shell, "prohibit-password")
        emit("[3/5] Закрытие root SSH... OK")

        emit("[4/5] Перезапуск SSH...")
        restart_ssh_nxp(shell)
        check_ssh_nxp(shell)
        emit("[4/5] Перезапуск SSH... OK")

        emit("[5/5] Проверка закрытия root SSH...")
        verify_root_login_denied(host, root_password)
        emit("[5/5] Проверка закрытия root SSH... OK")
        return "closed"
    finally:
        shell.close()
