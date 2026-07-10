#!/usr/bin/env python3

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter as ctk
except ImportError:
    print("Ошибка: не установлен модуль customtkinter.")
    print("Установите зависимости: python3 -m pip install -r requirements.txt")
    raise

from openroot_core import (
    APPNAME,
    VERSION,
    OpenRootError,
    OpenRootResult,
    close_terminal_root,
    open_terminal_root,
    setup_logging,
)


class OpenRootApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APPNAME)
        self.geometry("760x620")
        self.minsize(680, 560)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.action = tk.StringVar(value="open")
        self.host = tk.StringVar()
        self.suffix = tk.StringVar()
        self.support_password = tk.StringVar()
        self.root_password = tk.StringVar(value="123")
        self.status = tk.StringVar(value="Готово")

        self._build_layout()
        self.after(100, self._drain_events)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text=APPNAME, font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, padx=24, pady=(18, 2), sticky="w")

        subtitle = ctk.CTkLabel(header, text=f"{VERSION}  ·  Debian / NXP", text_color=("gray35", "gray70"))
        subtitle.grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, padx=18, pady=18, sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        action_label = ctk.CTkLabel(form, text="Действие")
        action_label.grid(row=0, column=0, padx=(18, 12), pady=(18, 10), sticky="w")

        action_control = ctk.CTkSegmentedButton(
            form,
            values=["Открыть root", "Закрыть root"],
            command=self._set_action,
        )
        action_control.set("Открыть root")
        action_control.grid(row=0, column=1, padx=(0, 18), pady=(18, 10), sticky="ew")

        self._add_entry(form, 1, "IP терминала", self.host)
        self._add_entry(form, 2, "Support suffix", self.suffix)
        self._add_entry(form, 3, "Пароль поддержки", self.support_password, show="*")
        self._add_entry(form, 4, "Root пароль", self.root_password, show="*")

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(row=5, column=0, columnspan=2, padx=18, pady=(8, 18), sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)

        self.run_button = ctk.CTkButton(buttons, text="Выполнить", command=self._start)
        self.run_button.grid(row=0, column=1, padx=(8, 0), sticky="e")

        self.clear_button = ctk.CTkButton(buttons, text="Очистить лог", fg_color="gray45", command=self._clear_log)
        self.clear_button.grid(row=0, column=0, sticky="w")

        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_title = ctk.CTkLabel(log_frame, text="Лог", font=ctk.CTkFont(size=16, weight="bold"))
        log_title.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        self.log = ctk.CTkTextbox(log_frame, wrap="word")
        self.log.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.log.configure(state="disabled")

        footer = ctk.CTkFrame(self, corner_radius=0)
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        status = ctk.CTkLabel(footer, textvariable=self.status, anchor="w")
        status.grid(row=0, column=0, padx=18, pady=10, sticky="ew")

    def _add_entry(
        self,
        parent: ctk.CTkFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        show: str | None = None,
    ) -> None:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=(18, 12), pady=8, sticky="w")
        entry = ctk.CTkEntry(parent, textvariable=variable, show=show)
        entry.grid(row=row, column=1, padx=(0, 18), pady=8, sticky="ew")

    def _set_action(self, value: str) -> None:
        self.action.set("close" if value.startswith("Закрыть") else "open")

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        host = self.host.get().strip()
        suffix = self.suffix.get().strip()
        support_password = self.support_password.get()
        root_password = self.root_password.get() or "123"

        if not host:
            messagebox.showerror(APPNAME, "IP терминала не указан")
            return
        if not suffix:
            messagebox.showerror(APPNAME, "Support suffix не указан")
            return
        if not support_password:
            messagebox.showerror(APPNAME, "Пароль поддержки не указан")
            return

        self._clear_log()
        self._set_running(True)

        self.worker = threading.Thread(
            target=self._run_operation,
            args=(self.action.get(), host, suffix, support_password, root_password),
            daemon=True,
        )
        self.worker.start()

    def _run_operation(
        self,
        action: str,
        host: str,
        suffix: str,
        support_password: str,
        root_password: str,
    ) -> None:
        try:
            if action == "open":
                result = open_terminal_root(
                    host=host,
                    suffix=suffix,
                    support_password=support_password,
                    root_password=root_password,
                    progress=self._progress,
                )
            else:
                result = close_terminal_root(
                    host=host,
                    suffix=suffix,
                    support_password=support_password,
                    root_password=root_password,
                    progress=self._progress,
                )
        except OpenRootError as exc:
            logging.exception("openroot gui failed")
            self.events.put(("error", str(exc)))
        except Exception as exc:
            logging.exception("unexpected gui failure")
            self.events.put(("error", f"Непредвиденная ошибка: {exc}"))
        else:
            self.events.put(("done", result))

    def _progress(self, message: str) -> None:
        self.events.put(("log", message))

    def _drain_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(str(payload))
                self.status.set(str(payload))
            elif kind == "error":
                self._append_log(f"FAILED: {payload}")
                self.status.set("Ошибка")
                self._set_running(False)
                messagebox.showerror(APPNAME, str(payload))
            elif kind == "done":
                result = payload
                if isinstance(result, OpenRootResult):
                    self._append_result(result)
                self.status.set("Успешно")
                self._set_running(False)

        self.after(100, self._drain_events)

    def _append_log(self, message: str) -> None:
        if message.endswith("... OK"):
            message = "[OK] " + message[:-6]
        elif message == "OK":
            message = "[OK]"

        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _append_result(self, result: OpenRootResult) -> None:
        self._append_log("")
        self._append_log("УСПЕШНО")
        if result.root_status == "closed":
            self._append_log("Root SSH закрыт")
            self._append_log("PermitRootLogin = prohibit-password")
        else:
            self._append_log("Root логин: root")
            self._append_log(f"Root пароль: {result.root_password}")
            self._append_log("Root SSH проверен")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.status.set("Готово")

    def _set_running(self, running: bool) -> None:
        self.run_button.configure(state="disabled" if running else "normal")
        self.clear_button.configure(state="disabled" if running else "normal")
        if running:
            self.status.set("Выполняется")


def main() -> int:
    setup_logging()
    app = OpenRootApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
