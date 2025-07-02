import customtkinter as ctk
import subprocess
import win32gui
import win32con
import time
import threading

class PowerShellFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.parent = parent
        self.app = app
        self.process = None  # Для хранения процесса PowerShell
        self.console_hwnd = None  # Для хранения дескриптора окна консоли
        self.is_running = False  # Флаг для управления процессом

        # Контейнер для встраивания консоли
        self.console_container = ctk.CTkFrame(self, width=500, height=300, fg_color="black")
        self.console_container.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.console_container.grid_propagate(False)

        # Поле для ввода команд
        self.command_entry = ctk.CTkEntry(self, width=400, placeholder_text="Введите команду (например, ping 8.8.8.8 -t)")
        self.command_entry.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self.command_entry.bind("<Return>", self.send_command)

        # Кнопка выполнения
        self.execute_button = ctk.CTkButton(self, text="Выполнить", command=self.send_command)
        self.execute_button.grid(row=1, column=1, padx=5, pady=5)

        # Кнопка остановки
        self.stop_button = ctk.CTkButton(self, text="Остановить", command=self.stop_process, state="disabled")
        self.stop_button.grid(row=1, column=2, padx=5, pady=5)

        # Настройка весов для динамического расширения
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Запускаем терминал после инициализации окна
        self.app.after(100, self.embed_terminal)

    def embed_terminal(self):
        # Запускаем PowerShell в отдельном процессе
        self.process = subprocess.Popen(
            ["powershell", "-NoExit"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

        # Даём время на запуск консоли (увеличено для надёжности)
        time.sleep(2)

        # Ищем окно PowerShell
        def enum_windows_callback(hwnd, _):
            title = win32gui.GetWindowText(hwnd).lower()
            if "powershell" in title:
                self.console_hwnd = hwnd
                return False  # Прерываем перебор
            return True

        win32gui.EnumWindows(enum_windows_callback, None)

        if self.console_hwnd:
            # Получаем дескриптор окна контейнера
            container_hwnd = self.console_container.winfo_id()

            # Встраиваем консоль в окно приложения
            win32gui.SetParent(self.console_hwnd, container_hwnd)

            # Удаляем рамки и заголовок консоли
            style = win32gui.GetWindowLong(self.console_hwnd, win32con.GWL_STYLE)
            style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_SYSMENU)
            win32gui.SetWindowLong(self.console_hwnd, win32con.GWL_STYLE, style)
            win32gui.SetWindowLong(self.console_hwnd, win32con.GWL_EXSTYLE, win32gui.GetWindowLong(self.console_hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_NOACTIVATE)

            # Устанавливаем позицию и размер консоли
            self.resize_terminal()

            # Показываем окно консоли и убираем его из задачи
            win32gui.ShowWindow(self.console_hwnd, win32con.SW_SHOW)
            win32gui.SetWindowPos(self.console_hwnd, win32con.HWND_TOP, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

            # Привязываем изменение размера окна
            self.app.bind("<Configure>", self.on_resize)
            self.is_running = True
        else:
            self.console_container.configure(state="normal")
            self.console_container.insert("end", "Не удалось найти окно PowerShell!")
            self.console_container.configure(state="disabled")

    def resize_terminal(self):
        if self.console_hwnd:
            # Получаем размеры контейнера
            container_width = self.console_container.winfo_width()
            container_height = self.console_container.winfo_height()
            win32gui.SetWindowPos(self.console_hwnd, 0, 0, 0, container_width, container_height, win32con.SWP_NOZORDER)

    def on_resize(self, event):
        if self.console_hwnd:
            self.resize_terminal()

    def send_command(self, event=None):
        if self.is_running and self.process:
            command = self.command_entry.get().strip()
            if command:
                # Отправляем команду в консоль через стандартный ввод
                try:
                    # Используем stdin, если доступен (но PowerShell в данном случае работает напрямую)
                    # Для реальной отправки команд нужен доступ к буферу ввода консоли, что сложнее
                    print(f"Отправка команды: {command}")
                    self.process.stdin.write(f"{command}\n")
                    self.process.stdin.flush()
                    self.command_entry.delete(0, "end")
                except Exception as e:
                    print(f"Ошибка отправки команды: {e}")

    def stop_process(self):
        if self.process and self.is_running and not self.process.poll():
            self.is_running = False
            self.stop_button.configure(state="disabled")

            def terminate_process():
                try:
                    print("Attempting to stop process...")
                    if os.name == 'nt':
                        self.process.send_signal(signal.CTRL_C_EVENT)
                    else:
                        self.process.terminate()
                    self.process.wait(timeout=10)
                    print("Process stopped gracefully.")
                except subprocess.TimeoutExpired:
                    print("Timeout expired, forcing kill...")
                    self.process.kill()
                    try:
                        self.process.wait(timeout=5)
                        print("Process killed successfully.")
                    except subprocess.TimeoutExpired:
                        print("Process still alive after kill.")
                finally:
                    self.process = None
                    self.console_hwnd = None
                    self.app.after(0, lambda: self.execute_button.configure(state="normal"))
                    print("Button states updated.")

            threading.Thread(target=terminate_process, daemon=True).start()

    def on_destroy(self):
        self.is_running = False
        if self.process:
            self.process.kill()
            self.process.wait()

if __name__ == "__main__":
    root = ctk.CTk()
    app = PowerShellFrame(root, root)
    app.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.mainloop()