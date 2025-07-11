import customtkinter as ctk
from tkinter import ttk, messagebox, Menu
import subprocess
import webbrowser
import re
import threading
import queue
from typing import Dict, List, Optional, Tuple
from utils.printer_utils import PrinterManager
from utils.ad_utils import search_groups, check_password_ldap_with_auth
import logging

logger = logging.getLogger(__name__)

class TabHomeFrame(ctk.CTkFrame):
    """Фрейм для отдельной вкладки с RDP сессиями."""
    
    def __init__(self, parent, tab_name: str, app, load_from_config: bool = False, 
                 config_data: Optional[Dict] = None):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        
        self.parent = parent
        self.tab_name = tab_name
        self.app = app
        self.load_from_config = load_from_config
        self.config_data = config_data or {}
        
        # Очередь для асинхронных операций
        self.async_queue = queue.Queue()
        
        # Флаг для отслеживания инициализации
        self._initialization_complete = False
        
        # ИСПРАВЛЕНИЕ: Простая настройка сетки с правильными пропорциями
        self._setup_grid()
        
        # Создание UI элементов
        self._create_widgets()
        
        # Настройка стилей
        self._setup_styles()
        
        # Привязка событий
        self._bind_events()
        
        # Загрузка начальных данных
        if not self.load_from_config:
            self.after(100, self.refresh_sessions)
        
        # Запуск обработчика очереди
        self._process_queue()
        
        # Отложенная инициализация
        self.after(200, self._delayed_init)
    
    def _setup_grid(self):
        """Простая настройка сетки с правильными пропорциями."""
        # Настройка строк
        self.grid_rowconfigure((0, 1, 2, 3), weight=0)
        self.grid_rowconfigure(4, weight=1)
        
        # ИСПРАВЛЕНИЕ: Простая настройка колонок с правильными пропорциями
        self.grid_columnconfigure(0, weight=25)  # Сессии - 25%
        self.grid_columnconfigure(1, weight=40)  # Группы - 40%
        self.grid_columnconfigure(2, weight=35)  # Принтеры - 35%
    
    def _delayed_init(self):
        """Отложенная инициализация."""
        def stage1():
            self.update_idletasks()
            self.after(100, stage2)
        
        def stage2():
            self.update_idletasks()
            self._adjust_all_columns()
            self.after(100, stage3)
        
        def stage3():
            self.update_idletasks()
            self._adjust_all_columns()
            self._initialization_complete = True
            logger.debug("Инициализация TabHomeFrame завершена")
        
        stage1()
    
    def _adjust_all_columns(self):
        """Подстройка всех колонок."""
        try:
            # Подстройка колонок сессий
            if hasattr(self, 'session_frame') and self.session_frame.winfo_width() > 1:
                self._adjust_session_columns()
            
            # Подстройка колонок групп
            if hasattr(self, 'group_frame') and self.group_frame.winfo_width() > 1:
                self._adjust_group_columns()
            
            # Подстройка колонок принтеров
            if hasattr(self, 'printer_manager') and hasattr(self.printer_manager, 'printer_frame'):
                if self.printer_manager.printer_frame.winfo_width() > 1:
                    self._adjust_printer_columns()
        except Exception as e:
            logger.debug(f"Ошибка подстройки колонок: {e}")
    
    def _create_widgets(self):
        """Создание всех виджетов."""
        self._create_session_controls()
        self._create_session_treeview()
        self._create_group_controls()
        self._create_group_treeview()
        self._create_printer_section()
        self._create_tab_controls()
        self._create_context_menu()
    
    def _create_session_controls(self):
        """Создание элементов управления сессиями."""
        # Фрейм для сервера и кнопки обновления
        server_frame = ctk.CTkFrame(self, fg_color="transparent")
        server_frame.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        
        # Поле ввода сервера
        self.server_entry = ctk.CTkEntry(
            server_frame, 
            width=150,
            placeholder_text="Имя сервера"
        )
        self.server_entry.pack(side="left", padx=(0, 5))
        self.server_entry.insert(0, self.config_data.get("server", "TS-IT0"))
        
        # Кнопка обновления
        self.refresh_button = ctk.CTkButton(
            server_frame, 
            text="Обновить", 
            command=self.refresh_sessions,
            width=100
        )
        self.refresh_button.pack(side="left")
        
        # Индикатор загрузки
        self.loading_label = ctk.CTkLabel(
            server_frame,
            text="",
            text_color=("gray50", "gray70"),
            font=ctk.CTkFont(size=11)
        )
        self.loading_label.pack(side="left", padx=(10, 0))
        
        # Выбор домена
        self.combobox_domain = ctk.CTkComboBox(
            self, 
            values=["corp.local", "nd.lan"],
            width=150
        )
        self.combobox_domain.set(self.config_data.get("domain", "nd.lan"))
        self.combobox_domain.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        
        # Статус пароля
        self.password_status_entry = ctk.CTkEntry(
            self, 
            placeholder_text="Статус пароля",
            state="readonly"
        )
        self.password_status_entry.grid(row=2, column=0, padx=2, pady=2, sticky="ew")
        
        # Установка значения после создания виджета
        status = self.config_data.get("password_status", "")
        if status:
            self.password_status_entry.configure(state="normal")
            self.password_status_entry.insert(0, status)
            self.password_status_entry.configure(state="readonly")
    
    def _create_session_treeview(self):
        """Создание таблицы сессий."""
        # Фрейм для Treeview
        self.session_frame = ctk.CTkFrame(self)
        self.session_frame.grid(row=4, column=0, padx=2, pady=2, sticky="nsew")
        self.session_frame.grid_rowconfigure(0, weight=1)
        self.session_frame.grid_columnconfigure(0, weight=1)
        
        # Создание Treeview
        columns = ("SessionName", "Username", "SessionID", "Status")
        self.tree = ttk.Treeview(
            self.session_frame, 
            columns=columns,
            show="headings", 
            height=15
        )
        
        # Настройка заголовков
        self.tree.heading("SessionName", text="Имя сессии")
        self.tree.heading("Username", text="Пользователь")
        self.tree.heading("SessionID", text="ID сессии")
        self.tree.heading("Status", text="Статус")
        
        # Настройка колонок
        for col in columns:
            self.tree.column(col, width=100, stretch=True)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        # Привязка событий
        self.session_frame.bind("<Configure>", self._on_session_frame_resize)
    
    def _create_group_controls(self):
        """Создание элементов управления группами."""
        # Фрейм для поиска групп
        group_frame = ctk.CTkFrame(self, fg_color="transparent")
        group_frame.grid(row=2, column=1, padx=2, pady=2, sticky="ew")
        
        # Поле поиска
        self.group_search_entry = ctk.CTkEntry(
            group_frame, 
            width=200, 
            placeholder_text="Введите логин"
        )
        self.group_search_entry.pack(side="left", padx=(0, 5))
        self.group_search_entry.insert(0, self.config_data.get("group_search", ""))
        
        # Кнопка поиска
        self.search_groups_button = ctk.CTkButton(
            group_frame, 
            text="🔍", 
            width=30, 
            command=self.handle_group_search
        )
        self.search_groups_button.pack(side="left")
    
    def _create_group_treeview(self):
        """Создание таблицы групп."""
        # Фрейм для Treeview
        self.group_frame = ctk.CTkFrame(self)
        self.group_frame.grid(row=4, column=1, padx=2, pady=2, sticky="nsew")
        self.group_frame.grid_rowconfigure(0, weight=1)
        self.group_frame.grid_columnconfigure(0, weight=1)
        
        # Создание Treeview
        self.group_tree = ttk.Treeview(
            self.group_frame, 
            columns=("GroupName",), 
            show="headings", 
            height=15
        )
        
        # Настройка колонок
        self.group_tree.heading("GroupName", text="Группа")
        self.group_tree.column("GroupName", width=400, stretch=True)
        
        self.group_tree.grid(row=0, column=0, sticky="nsew")
        
        # Загрузка сохраненных групп
        if self.load_from_config and "groups" in self.config_data:
            for group in self.config_data.get("groups", []):
                if group:
                    self.group_tree.insert("", "end", values=group)
        
        # Привязка событий
        self.group_frame.bind("<Configure>", self._on_group_frame_resize)
    
    def _create_printer_section(self):
        """Создание секции принтеров."""
        self.printer_manager = PrinterManager(self)
        self.printer_manager.setup_ui(
            row=2, 
            column=2, 
            tree_row=4,
            tree_height=15,
            tree_columns=self.config_data.get("printer_tree_columns", {})
        )
    
    def _create_tab_controls(self):
        """Создание элементов управления вкладками."""
        # Фрейм для кнопок вкладок
        self.tab_buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_buttons_frame.grid(row=0, column=2, padx=2, pady=2, sticky="ne")
        
        # Кнопка добавления вкладки
        self.add_tab_button = ctk.CTkButton(
            self.tab_buttons_frame, 
            text="➕ Новая вкладка", 
            command=self.add_new_tab,
            width=165
        )
        self.add_tab_button.pack(side="left", padx=(0, 5))
        
        # Кнопка удаления вкладки
        self.delete_tab_button = ctk.CTkButton(
            self.tab_buttons_frame, 
            text="✖", 
            width=30, 
            command=self.delete_current_tab,
            fg_color="transparent",
            hover_color=("gray70", "gray30")
        )
        self.delete_tab_button.pack(side="left")
        
        # Кнопка переименования вкладки
        self.rename_tab_button = ctk.CTkButton(
            self, 
            text="✏️ Переименовать", 
            command=self.rename_tab, 
            width=200, 
            height=30
        )
        self.rename_tab_button.grid(row=1, column=2, padx=2, pady=2, sticky="ne")
    
    def _create_context_menu(self):
        """Создание контекстного меню."""
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Копировать", command=self.copy_selected_item)
        self.context_menu.add_command(label="Копировать всю строку", command=self.copy_entire_row)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Открыть веб-интерфейс", 
            command=self.open_printer_web_interface
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Подключиться к сессии", 
            command=lambda: self.connect_to_session(None)
        )
    
    def _setup_styles(self):
        """Настройка стилей."""
        self.update_treeview_style(ctk.get_appearance_mode())
    
    def _bind_events(self):
        """Привязка событий."""
        # События для полей ввода
        self.server_entry.bind("<Return>", lambda e: self.refresh_sessions())
        self.group_search_entry.bind("<Return>", lambda e: self.handle_group_search())
        
        # События для таблиц
        self.tree.bind("<Double-1>", self.connect_to_session)
        self.group_tree.bind("<Double-1>", self.on_group_double_click)
        
        # Контекстное меню
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.group_tree.bind("<Button-3>", self.show_context_menu)
        
        # ИСПРАВЛЕНИЕ: Простая обработка изменения размеров
        self.bind("<Configure>", self._on_resize)
        
        # Привязка событий для принтеров
        self.after(200, self._bind_printer_events)
    
    def _bind_printer_events(self):
        """Привязка событий для принтеров."""
        try:
            if hasattr(self.printer_manager, 'tree'):
                self.printer_manager.tree.bind("<Button-3>", self.show_context_menu)
        except Exception as e:
            logger.debug(f"Ошибка привязки событий принтеров: {e}")
    
    def _on_resize(self, event):
        """Простая обработка изменения размеров."""
        if event.widget != self or not self._initialization_complete:
            return
        
        # Откладываем обновление
        if hasattr(self, '_resize_job'):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(200, self._adjust_all_columns)
    
    def _process_queue(self):
        """Обработка асинхронной очереди."""
        try:
            while True:
                callback = self.async_queue.get_nowait()
                callback()
        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_queue)
    
    def show_loading(self, text: str = "Загрузка..."):
        """Показать индикатор загрузки."""
        self.loading_label.configure(text=text)
        self.refresh_button.configure(state="disabled")
    
    def hide_loading(self):
        """Скрыть индикатор загрузки."""
        self.loading_label.configure(text="")
        self.refresh_button.configure(state="normal")
    
    def refresh_sessions(self):
        """Обновление списка RDP сессий."""
        server = self.server_entry.get().strip()
        if not server:
            self.app.show_warning("Предупреждение", "Введите имя сервера")
            return
        
        self.show_loading("Получение сессий...")
        
        def worker():
            try:
                result = subprocess.run(
                    f"qwinsta /server:{server}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or "Неизвестная ошибка"
                    self.async_queue.put(
                        lambda: self._handle_session_error(server, error_msg)
                    )
                    return
                
                sessions = self._parse_qwinsta_output(result.stdout)
                self.async_queue.put(
                    lambda: self._update_session_tree(sessions)
                )
                
            except subprocess.TimeoutExpired:
                self.async_queue.put(
                    lambda: self._handle_session_error(server, "Превышено время ожидания")
                )
            except Exception as e:
                self.async_queue.put(
                    lambda: self._handle_session_error(server, str(e))
                )
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def _parse_qwinsta_output(self, output: str) -> List[Tuple[str, str, str, str]]:
        """Парсинг вывода команды qwinsta."""
        sessions = []
        lines = output.splitlines()
        
        if len(lines) < 2:
            return sessions
        
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                session_name = parts[0]
                username = parts[1] if not parts[1].isdigit() else ""
                session_id = next((p for p in parts[1:] if p.isdigit()), "")
                status = parts[-1] if len(parts) > 3 else "Unknown"
                
                sessions.append((session_name, username, session_id, status))
        
        return sessions
    
    def _update_session_tree(self, sessions: List[Tuple[str, str, str, str]]):
        """Обновление таблицы сессий."""
        self.hide_loading()
        
        self.tree.delete(*self.tree.get_children())
        
        if not sessions:
            self.app.show_info(
                "Информация", 
                f"На сервере {self.server_entry.get()} нет активных сессий"
            )
            return
        
        for session in sessions:
            self.tree.insert("", "end", values=session)
        
        if self._initialization_complete:
            self.after(50, self._adjust_session_columns)
        
        logger.info(f"Загружено {len(sessions)} сессий")
    
    def _handle_session_error(self, server: str, error: str):
        """Обработка ошибок при получении сессий."""
        self.hide_loading()
        logger.error(f"Ошибка получения сессий для {server}: {error}")
        self.app.show_error(
            "Ошибка", 
            f"Не удалось получить список сессий для {server}:\n{error}"
        )
    
    def handle_group_search(self):
        """Обработка поиска групп."""
        if not self.group_search_entry.get().strip():
            self.app.show_warning("Предупреждение", "Введите логин пользователя")
            return
        
        search_groups(self, self.app)
        check_password_ldap_with_auth(self, self.app)
        self.set_user_server_from_groups()
    
    def set_user_server_from_groups(self):
        """Автоматическое определение сервера по группам."""
        for item in self.group_tree.get_children():
            group_name = self.group_tree.item(item, "values")[0]
            match = re.search(r'(TS-.+)', group_name)
            if match:
                server_short = match.group(1)
                self.server_entry.delete(0, "end")
                self.server_entry.insert(0, server_short)
                self.refresh_sessions()
                break
    
    def on_group_double_click(self, event):
        """Обработка двойного клика по группе."""
        selected_item = self.group_tree.selection()
        if not selected_item:
            return
        
        group_name = self.group_tree.item(selected_item[0], "values")[0]
        match = re.search(r'(TS-.+)', group_name)
        if match:
            server_short = match.group(1)
            self.server_entry.delete(0, "end")
            self.server_entry.insert(0, server_short)
            self.refresh_sessions()
    
    def connect_to_session(self, event):
        """Подключение к выбранной RDP сессии."""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        try:
            session_id = self.tree.item(selected_item[0], "values")[2]
            server = self.server_entry.get()
            
            cmd = f"mstsc /v:{server} /shadow:{session_id} /control"
            subprocess.Popen(cmd, shell=True)
            
            logger.info(f"Подключение к сессии {session_id} на сервере {server}")
            
        except Exception as e:
            logger.error(f"Ошибка подключения к сессии: {e}")
            self.app.show_error("Ошибка", f"Не удалось подключиться к сессии: {e}")
    
    def show_context_menu(self, event):
        """Отображение контекстного меню."""
        tree = event.widget
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
        
        try:
            if tree == self.printer_manager.tree:
                self.context_menu.entryconfig("Открыть веб-интерфейс", state="normal")
                self.context_menu.entryconfig("Подключиться к сессии", state="disabled")
            elif tree == self.tree:
                self.context_menu.entryconfig("Открыть веб-интерфейс", state="disabled")
                self.context_menu.entryconfig("Подключиться к сессии", state="normal")
            else:
                self.context_menu.entryconfig("Открыть веб-интерфейс", state="disabled")
                self.context_menu.entryconfig("Подключиться к сессии", state="disabled")
        except:
            pass
        
        self.context_menu.post(event.x_root, event.y_root)
    
    def copy_selected_item(self):
        """Копирование выбранного элемента."""
        tree = self.get_focused_treeview()
        if not tree:
            return
        
        selected_item = tree.selection()
        if not selected_item:
            return
        
        try:
            x = tree.winfo_pointerx() - tree.winfo_rootx()
            column_id = tree.identify_column(x)
            column_index = int(column_id.replace('#', '')) - 1
            
            item_values = tree.item(selected_item[0], "values")
            if item_values and 0 <= column_index < len(item_values):
                value = str(item_values[column_index])
                self.clipboard_clear()
                self.clipboard_append(value)
                self.update()
                
                logger.info(f"Скопировано в буфер: {value}")
        except Exception as e:
            logger.error(f"Ошибка копирования: {e}")
    
    def copy_entire_row(self):
        """Копирование всей строки."""
        tree = self.get_focused_treeview()
        if not tree:
            return
        
        selected_item = tree.selection()
        if not selected_item:
            return
        
        try:
            item_values = tree.item(selected_item[0], "values")
            if item_values:
                row_text = "\t".join(str(v) for v in item_values)
                self.clipboard_clear()
                self.clipboard_append(row_text)
                self.update()
                
                logger.info(f"Скопирована строка: {row_text}")
        except Exception as e:
            logger.error(f"Ошибка копирования строки: {e}")
    
    def open_printer_web_interface(self):
        """Открытие веб-интерфейса принтера."""
        try:
            if self.get_focused_treeview() != self.printer_manager.tree:
                return
            
            selected_item = self.printer_manager.tree.selection()
            if not selected_item:
                return
            
            item_values = self.printer_manager.tree.item(selected_item[0], "values")
            if item_values and len(item_values) > 1:
                ip_address = item_values[1]
                if ip_address:
                    webbrowser.open(f"http://{ip_address}")
                    logger.info(f"Открыт веб-интерфейс принтера: {ip_address}")
        except Exception as e:
            logger.error(f"Ошибка открытия веб-интерфейса: {e}")
    
    def get_focused_treeview(self):
        """Получение активного Treeview."""
        focused = self.focus_get()
        try:
            if focused in [self.tree, self.group_tree, self.printer_manager.tree]:
                return focused
        except:
            pass
        return None
    
    def add_new_tab(self):
        """Добавление новой вкладки."""
        self.app.home_frame.add_new_tab()
    
    def delete_current_tab(self):
        """Удаление текущей вкладки."""
        current_tab = self.app.home_frame.tabview.get()
        tab_names = list(self.app.home_frame.tabview._tab_dict.keys())
        
        if len(tab_names) <= 1:
            self.app.show_warning("Предупреждение", "Нельзя удалить последнюю вкладку!")
            return
        
        confirm = messagebox.askyesno(
            "Подтверждение", 
            f"Вы уверены, что хотите удалить вкладку '{current_tab}'?"
        )
        
        if confirm:
            self.app.home_frame.tabview.delete(current_tab)
            remaining_tabs = list(self.app.home_frame.tabview._tab_dict.keys())
            if remaining_tabs:
                self.app.home_frame.tabview.set(remaining_tabs[0])
            
            logger.info(f"Вкладка '{current_tab}' удалена")
    
    def rename_tab(self):
        """Переименование текущей вкладки."""
        current_tab = self.app.home_frame.tabview.get()
        
        dialog = ctk.CTkInputDialog(
            text=f"Введите новое имя для вкладки '{current_tab}':", 
            title="Переименовать вкладку"
        )
        new_name = dialog.get_input()
        
        if not new_name:
            return
        
        if new_name in self.app.home_frame.tabview._tab_dict:
            self.app.show_error("Ошибка", "Вкладка с таким именем уже существует!")
            return
        
        self.app.home_frame.rename_tab(current_tab, new_name)
        logger.info(f"Вкладка переименована: '{current_tab}' -> '{new_name}'")
    
    def update_treeview_style(self, appearance_mode: str):
        """Обновление стиля таблиц."""
        style = ttk.Style()
        style.theme_use("clam")
        
        if appearance_mode == "Dark":
            bg_color = "#2b2b2b"
            fg_color = "#ffffff"
            select_bg = "#404040"
            heading_bg = "#333333"
        else:
            bg_color = "#ffffff"
            fg_color = "#000000"
            select_bg = "#e0e0e0"
            heading_bg = "#f0f0f0"
        
        style.configure(
            "Treeview",
            background=bg_color,
            foreground=fg_color,
            fieldbackground=bg_color,
            borderwidth=0
        )
        
        style.configure(
            "Treeview.Heading",
            background=heading_bg,
            foreground=fg_color,
            relief="flat"
        )
        
        style.map(
            "Treeview",
            background=[('selected', select_bg)],
            foreground=[('selected', fg_color)]
        )
        
        try:
            for tree in [self.tree, self.group_tree, self.printer_manager.tree]:
                tree.configure(style="Treeview")
        except:
            pass
    
    def get_treeview_column_widths(self, tree) -> Dict[str, int]:
        """Получение ширины колонок таблицы."""
        try:
            return {col: tree.column(col, "width") for col in tree["columns"]}
        except:
            return {}
    
    def cleanup(self):
        """Очистка ресурсов."""
        try:
            if hasattr(self, 'printer_manager'):
                self.printer_manager.cleanup()
        except:
            pass
    
    def _adjust_session_columns(self):
        """Подстройка ширины колонок таблицы сессий."""
        try:
            available_width = self.session_frame.winfo_width() - 20
            
            if available_width > 200:
                saved_columns = self.config_data.get("session_tree_columns", {})
                
                if saved_columns and all(col in saved_columns for col in self.tree["columns"]):
                    for col in self.tree["columns"]:
                        self.tree.column(col, width=saved_columns[col])
                else:
                    widths = {
                        "SessionName": int(available_width * 0.25),
                        "Username": int(available_width * 0.35),
                        "SessionID": int(available_width * 0.15),
                        "Status": int(available_width * 0.25)
                    }
                    
                    for col, width in widths.items():
                        self.tree.column(col, width=width)
        except Exception as e:
            logger.debug(f"Ошибка подстройки колонок сессий: {e}")
    
    def _adjust_group_columns(self):
        """Подстройка ширины колонок таблицы групп."""
        try:
            available_width = self.group_frame.winfo_width() - 20
            
            if available_width > 200:
                saved_columns = self.config_data.get("group_tree_columns", {})
                
                if saved_columns and "GroupName" in saved_columns:
                    self.group_tree.column("GroupName", width=saved_columns["GroupName"])
                else:
                    self.group_tree.column("GroupName", width=available_width)
        except Exception as e:
            logger.debug(f"Ошибка подстройки колонок групп: {e}")
    
    def _adjust_printer_columns(self):
        """Подстройка ширины колонок таблицы принтеров."""
        try:
            available_width = self.printer_manager.printer_frame.winfo_width() - 20
            
            if available_width > 200:
                saved_columns = self.config_data.get("printer_tree_columns", {})
                
                if saved_columns and all(col in saved_columns for col in self.printer_manager.tree["columns"]):
                    for col in self.printer_manager.tree["columns"]:
                        self.printer_manager.tree.column(col, width=saved_columns[col])
                else:
                    widths = {
                        "Printer": int(available_width * 0.40),
                        "IP": int(available_width * 0.25),
                        "Server": int(available_width * 0.20),
                        "Status": int(available_width * 0.15)
                    }
                    
                    for col, width in widths.items():
                        if col in self.printer_manager.tree["columns"]:
                            self.printer_manager.tree.column(col, width=width)
        except Exception as e:
            logger.debug(f"Ошибка подстройки колонок принтеров: {e}")
    
    def _on_session_frame_resize(self, event):
        """Обработка изменения размера фрейма сессий."""
        if not self._initialization_complete:
            return
        
        if hasattr(self, '_resize_job'):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self._adjust_session_columns)
    
    def _on_group_frame_resize(self, event):
        """Обработка изменения размера фрейма групп."""
        if not self._initialization_complete:
            return
        
        if hasattr(self, '_group_resize_job'):
            self.after_cancel(self._group_resize_job)
        self._group_resize_job = self.after(100, self._adjust_group_columns)


class HomeFrame(ctk.CTkFrame):
    """Главный фрейм с вкладками."""
    
    def __init__(self, parent, app, load_from_config: bool = False):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        
        self.app = app
        self.load_from_config = load_from_config
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        if not self.load_from_config:
            self.initial_tab_names = ["Сервер 1", "Сервер 2", "Сервер 3"]
            for tab_name in self.initial_tab_names:
                self._create_tab(tab_name)
            
            if self.initial_tab_names:
                self.tabview.set(self.initial_tab_names[0])
        
        self.update_treeview_style(ctk.get_appearance_mode())
        self.after(300, self._delayed_home_init)
    
    def _delayed_home_init(self):
        """Отложенная инициализация HomeFrame."""
        try:
            self.update_idletasks()
            
            for tab_name in list(self.tabview._tab_dict.keys()):
                tab_frame = self.tabview.tab(tab_name)
                if tab_frame.winfo_children():
                    frame = tab_frame.winfo_children()[0]
                    if hasattr(frame, 'update_idletasks'):
                        frame.update_idletasks()
                    if hasattr(frame, '_adjust_all_columns'):
                        frame._adjust_all_columns()
            
            logger.debug("Инициализация HomeFrame завершена")
        except Exception as e:
            logger.debug(f"Ошибка инициализации HomeFrame: {e}")
    
    def _create_tab(self, tab_name: str, config_data: Optional[Dict] = None) -> TabHomeFrame:
        """Создание новой вкладки."""
        tab = self.tabview.add(tab_name)
        tab_frame = TabHomeFrame(
            tab, 
            tab_name, 
            self.app, 
            load_from_config=self.load_from_config,
            config_data=config_data
        )
        tab_frame.pack(fill="both", expand=True)
        
        return tab_frame
    
    def add_new_tab(self):
        """Добавление новой вкладки."""
        existing_tabs = list(self.tabview._tab_dict.keys())
        new_tab_number = 1
        
        while f"Сервер {new_tab_number}" in existing_tabs:
            new_tab_number += 1
        
        new_tab_name = f"Сервер {new_tab_number}"
        
        self._create_tab(new_tab_name)
        self.tabview.set(new_tab_name)
        
        logger.info(f"Добавлена новая вкладка: {new_tab_name}")
    
    def rename_tab(self, old_name: str, new_name: str):
        """Переименование вкладки."""
        old_tab = self.tabview.tab(old_name)
        old_frame = old_tab.winfo_children()[0]
        
        config_data = {
            "tab_name": new_name,
            "server": old_frame.server_entry.get(),
            "domain": old_frame.combobox_domain.get(),
            "password_status": old_frame.password_status_entry.get(),
            "group_search": old_frame.group_search_entry.get(),
            "groups": [
                old_frame.group_tree.item(item, "values") 
                for item in old_frame.group_tree.get_children()
            ],
            "session_tree_columns": old_frame.get_treeview_column_widths(old_frame.tree),
            "group_tree_columns": old_frame.get_treeview_column_widths(old_frame.group_tree),
            "printer_tree_columns": old_frame.get_treeview_column_widths(old_frame.printer_manager.tree)
        }
        
        new_frame = self._create_tab(new_name, config_data)
        
        for item in old_frame.tree.get_children():
            values = old_frame.tree.item(item, "values")
            new_frame.tree.insert("", "end", values=values)
        
        try:
            for item in old_frame.printer_manager.tree.get_children():
                values = old_frame.printer_manager.tree.item(item, "values")
                new_frame.printer_manager.tree.insert("", "end", values=values)
        except:
            pass
        
        self.tabview.delete(old_name)
        self.tabview.set(new_name)
        
        if not self.load_from_config:
            new_frame.refresh_sessions()
    
    def update_all_treeview_styles(self, appearance_mode: str):
        """Обновление стилей всех таблиц."""
        tab_names = list(self.tabview._tab_dict.keys())
        
        for tab_name in tab_names:
            try:
                tab_frame = self.tabview.tab(tab_name)
                if tab_frame.winfo_children():
                    frame = tab_frame.winfo_children()[0]
                    if isinstance(frame, TabHomeFrame):
                        frame.update_treeview_style(appearance_mode)
            except Exception as e:
                logger.error(f"Ошибка обновления стиля для вкладки {tab_name}: {e}")
    
    def update_treeview_style(self, appearance_mode: str):
        """Обновление стиля таблиц."""
        self.update_all_treeview_styles(appearance_mode)
    
    def cleanup(self):
        """Очистка ресурсов всех вкладок."""
        tab_names = list(self.tabview._tab_dict.keys())
        
        for tab_name in tab_names:
            try:
                tab_frame = self.tabview.tab(tab_name)
                if tab_frame.winfo_children():
                    frame = tab_frame.winfo_children()[0]
                    if hasattr(frame, 'cleanup'):
                        frame.cleanup()
            except Exception as e:
                logger.error(f"Ошибка очистки ресурсов вкладки {tab_name}: {e}")
