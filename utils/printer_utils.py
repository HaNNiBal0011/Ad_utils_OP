# utils/printer_utils.py
import customtkinter as ctk
from tkinter import ttk
import json
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import threading
import requests
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class Printer:
    """Модель данных принтера."""
    name: str
    ip: str
    server: str
    model: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    last_checked: Optional[datetime] = None

class PrinterManager:
    """Менеджер для работы с принтерами."""
    
    def __init__(self, parent):
        self.parent = parent
        self.printers: List[Printer] = []
        self.filtered_printers: List[Printer] = []
        self.tree = None
        self.search_entry = None
        self.status_label = None
        
        # Флаг для режима поиска
        self.search_mode = False
        
        # Кэш статусов принтеров
        self._status_cache: Dict[str, Tuple[str, datetime]] = {}
        self._cache_timeout = 300  # 5 минут
        
        # Поток для проверки статусов
        self._status_check_thread = None
        self._stop_status_check = threading.Event()
        
        # Загрузка принтеров
        self._load_printers()
    
    def setup_ui(self, row: int, column: int, tree_row: int, 
                 tree_height: int = 10, tree_columns: Optional[Dict] = None):
        """Настройка пользовательского интерфейса."""
        # Контейнер для поиска
        search_container = ctk.CTkFrame(self.parent, fg_color="transparent")
        search_container.grid(row=row, column=column, padx=2, pady=2, sticky="ew")
        
        # Поле поиска
        self.search_entry = ctk.CTkEntry(
            search_container,
            width=200,
            placeholder_text="Поиск принтеров..."
        )
        self.search_entry.pack(side="left", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        self.search_entry.bind("<Return>", lambda e: self.search_printers())
        
        # Кнопки
        button_frame = ctk.CTkFrame(search_container, fg_color="transparent")
        button_frame.pack(side="right")
        
        # Кнопка поиска
        self.search_button = ctk.CTkButton(
            button_frame,
            text="🔍",
            width=30,
            command=self.search_printers
        )
        self.search_button.pack(side="left", padx=(0, 5))
        
        # Кнопка очистки поиска
        self.clear_search_button = ctk.CTkButton(
            button_frame,
            text="✖",
            width=30,
            command=self.clear_search,
            fg_color="transparent",
            hover_color=("gray70", "gray30")
        )
        self.clear_search_button.pack(side="left", padx=(0, 5))
        
        # Кнопка обновления
        self.refresh_button = ctk.CTkButton(
            button_frame,
            text="🔄 Обновить",
            command=self.refresh_printers,
            width=100
        )
        self.refresh_button.pack(side="left", padx=(0, 5))
        
        # Кнопка проверки статусов принтеров
        self.check_status_button = ctk.CTkButton(
            button_frame,
            text="📊 Статусы",
            command=self._start_status_check,
            width=100,
            fg_color="transparent",
            border_width=1
        )
        self.check_status_button.pack(side="left")
        
        # Статус
        self.status_label = ctk.CTkLabel(
            search_container,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray70")
        )
        self.status_label.pack(side="left", padx=(10, 0))
        
        # Фрейм для Treeview
        self.printer_frame = ctk.CTkFrame(self.parent)
        self.printer_frame.grid(row=tree_row, column=column, padx=2, pady=2, sticky="nsew")
        self.printer_frame.grid_rowconfigure(0, weight=1)
        self.printer_frame.grid_columnconfigure(0, weight=1)
        
        # Настройка Treeview
        self._setup_treeview(tree_height, tree_columns)
    
    def _setup_treeview(self, height: int, column_widths: Optional[Dict]):
        """Настройка таблицы принтеров."""
        columns = ("Printer", "IP", "Server", "Status")
        self.tree = ttk.Treeview(
            self.printer_frame,
            columns=columns,
            show="headings",
            height=height
        )
        
        # Настройка колонок
        column_config = {
            "Printer": ("Принтер", 180),
            "IP": ("IP адрес", 120),
            "Server": ("Сервер", 100),
            "Status": ("Статус", 100)
        }
        
        default_widths = {col: width for col, (_, width) in column_config.items()}
        widths = column_widths or default_widths
        
        for col, (heading, default_width) in column_config.items():
            self.tree.heading(col, text=heading, command=lambda c=col: self._sort_by_column(c))
            width = widths.get(col, default_width)
            self.tree.column(col, width=width, stretch=True)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        # Привязка событий
        self.tree.bind("<Double-1>", self._on_double_click)
        
        # Настройка тегов для статусов
        self.tree.tag_configure("online", foreground="green")
        self.tree.tag_configure("offline", foreground="red")
        self.tree.tag_configure("warning", foreground="orange")
        self.tree.tag_configure("unknown", foreground="gray")
    
    def _load_printers(self):
        """Загрузка списка принтеров из файла."""
        file_path = self._get_resource_path("test_images/printers.json")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.printers = []
            
            for item in data:
                printer_name = item.get("Printer", "").strip()
                printer_ip = item.get("IP", "").strip()
                printer_server = item.get("Server", "").strip()
                
                if not printer_name and not printer_ip:
                    continue
                
                printer = Printer(
                    name=printer_name,
                    ip=printer_ip,
                    server=printer_server,
                    model=None,
                    location=item.get("Location", "").strip(),
                    status="Неизвестно"
                )
                self.printers.append(printer)
            
            logger.info(f"Загружено {len(self.printers)} принтеров")
            
        except FileNotFoundError:
            logger.warning(f"Файл принтеров не найден: {file_path}")
            self._create_default_printer_file(file_path)
        except Exception as e:
            logger.error(f"Ошибка загрузки принтеров: {e}")
    
    def _get_resource_path(self, relative_path: str) -> Path:
        """Получение пути к ресурсу."""
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent
        return base_path / relative_path
    
    def _create_default_printer_file(self, file_path: Path):
        """Создание файла принтеров по умолчанию."""
        default_printers = [
            {"Printer": "HP_LaserJet_1", "IP": "192.168.1.100", "Server": "TS-IT0", "Location": "IT Office"},
            {"Printer": "Canon_Color_1", "IP": "192.168.1.101", "Server": "TS-IT0", "Location": "Reception"},
            {"Printer": "Xerox_MFP_1", "IP": "192.168.1.102", "Server": "TS-HR0", "Location": "HR Department"},
        ]
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_printers, f, ensure_ascii=False, indent=4)
            logger.info("Создан файл принтеров по умолчанию")
            
            self._load_printers()
        except Exception as e:
            logger.error(f"Ошибка создания файла принтеров: {e}")
    
    def search_printers(self):
        """Поиск принтеров по названию, IP и серверу."""
        search_text = self.search_entry.get().strip()
        
        if not search_text:
            self.clear_search()
            return
        
        self.search_mode = True
        
        search_text_lower = search_text.lower()
        self.filtered_printers = []
        seen_printers = set()
        
        for printer in self.printers:
            matches = False
            
            if search_text_lower in printer.name.lower():
                matches = True
            elif search_text_lower in printer.ip.lower():
                matches = True
            elif search_text_lower in printer.server.lower():
                matches = True
            elif printer.location and search_text_lower in printer.location.lower():
                matches = True
            
            if matches:
                unique_key = f"{printer.ip.lower()}:{printer.name.lower()}"
                if unique_key not in seen_printers:
                    seen_printers.add(unique_key)
                    self.filtered_printers.append(printer)
        
        self.filtered_printers.sort(key=lambda p: (p.name.lower(), p.ip))
        
        self._update_treeview()
        
        if self.filtered_printers:
            status_text = f"Найдено: {len(self.filtered_printers)} принтеров по запросу '{search_text}'"
        else:
            status_text = f"Принтеры не найдены по запросу '{search_text}'"
        
        self.status_label.configure(text=status_text)
        
        logger.info(f"Поиск '{search_text}': найдено {len(self.filtered_printers)} принтеров")
    
    def clear_search(self):
        """Очистка поиска и возврат к обычному режиму."""
        self.search_entry.delete(0, "end")
        self.search_mode = False
        self.refresh_printers()
    
    def refresh_printers(self):
        """Обновление списка принтеров с фильтрацией по серверу."""
        if self.search_mode:
            return
        
        server_filter = self.parent.server_entry.get().strip().lower()
        
        self.filtered_printers = []
        seen_printers = set()
        
        for printer in self.printers:
            if server_filter and printer.server.lower() != server_filter:
                continue
            
            unique_key = f"{printer.ip.lower()}:{printer.name.lower()}"
            
            if unique_key not in seen_printers:
                seen_printers.add(unique_key)
                self.filtered_printers.append(printer)
        
        self.filtered_printers.sort(key=lambda p: (p.name.lower(), p.ip))
        
        self._update_treeview()
        
        if server_filter:
            status_text = f"Сервер {server_filter.upper()}: {len(self.filtered_printers)} принтеров"
        else:
            status_text = f"Всего принтеров: {len(self.filtered_printers)}"
        
        self.status_label.configure(text=status_text)
    
    def _update_treeview(self):
        """Обновление содержимого таблицы."""
        selected = self.tree.selection()
        selected_values = []
        for item in selected:
            selected_values.append(self.tree.item(item, "values"))
        
        self.tree.delete(*self.tree.get_children())
        
        for printer in self.filtered_printers:
            tag = self._get_status_tag(printer.status)
            
            values = (
                printer.name,
                printer.ip,
                printer.server,
                printer.status
            )
            
            item = self.tree.insert("", "end", values=values, tags=(tag,))
            
            if values in selected_values:
                self.tree.selection_add(item)
    
    def _get_status_tag(self, status: str) -> str:
        """Получение тега для статуса принтера."""
        status_lower = status.lower()
        if "онлайн" in status_lower or "online" in status_lower:
            return "online"
        elif "офлайн" in status_lower or "offline" in status_lower:
            return "offline"
        elif "предупреждение" in status_lower or "warning" in status_lower:
            return "warning"
        else:
            return "unknown"
    
    def _on_search_change(self, event):
        """Обработка изменения поискового запроса при вводе."""
        search_text = self.search_entry.get().strip()
        if not search_text:
            if self.search_mode:
                self.clear_search()
    
    def _on_double_click(self, event):
        """Обработка двойного клика по принтеру."""
        selected = self.tree.selection()
        if not selected:
            return
        
        values = self.tree.item(selected[0], "values")
        if len(values) > 1:
            ip = values[1]
            if ip:
                import webbrowser
                webbrowser.open(f"http://{ip}")
                logger.info(f"Открыт веб-интерфейс принтера: {ip}")
    
    def _sort_by_column(self, column: str):
        """Сортировка таблицы по колонке."""
        data = [(self.tree.item(child, "values"), child) for child in self.tree.get_children()]
        
        columns = self.tree["columns"]
        col_index = columns.index(column)
        
        data.sort(key=lambda x: x[0][col_index])
        
        for index, (values, item) in enumerate(data):
            self.tree.move(item, "", index)
    
    def _start_status_check(self):
        """Запуск проверки статусов принтеров."""
        self._stop_status_check.set()
        if self._status_check_thread and self._status_check_thread.is_alive():
            self._status_check_thread.join(timeout=1)
        
        self._stop_status_check.clear()
        self._status_check_thread = threading.Thread(
            target=self._check_printer_statuses,
            daemon=True
        )
        self._status_check_thread.start()
    
    def _check_printer_statuses(self):
        """Проверка статусов принтеров в фоновом режиме."""
        for printer in self.filtered_printers:
            if self._stop_status_check.is_set():
                break
            
            if printer.ip in self._status_cache:
                cached_status, cached_time = self._status_cache[printer.ip]
                if datetime.now() - cached_time < timedelta(seconds=self._cache_timeout):
                    printer.status = cached_status
                    self.parent.after(0, self._update_printer_status_in_tree, printer)
                    continue
            
            status = self._check_single_printer_status(printer.ip)
            printer.status = status
            printer.last_checked = datetime.now()
            
            self._status_cache[printer.ip] = (status, datetime.now())
            
            self.parent.after(0, self._update_printer_status_in_tree, printer)
    
    def _check_single_printer_status(self, ip: str) -> str:
        """Проверка статуса одного принтера."""
        try:
            response = requests.get(f"http://{ip}", timeout=2)
            if response.status_code == 200:
                return "Онлайн"
            else:
                return f"Ошибка HTTP {response.status_code}"
        except requests.ConnectionError:
            return "Офлайн"
        except requests.Timeout:
            return "Тайм-аут"
        except Exception as e:
            logger.debug(f"Ошибка проверки принтера {ip}: {e}")
            return "Неизвестно"
    
    def _update_printer_status_in_tree(self, printer: Printer):
        """Обновление статуса принтера в таблице."""
        for item in self.tree.get_children():
            values = list(self.tree.item(item, "values"))
            if values[1] == printer.ip:
                values[3] = printer.status
                tag = self._get_status_tag(printer.status)
                self.tree.item(item, values=values, tags=(tag,))
                break
    
    def cleanup(self):
        """Очистка ресурсов."""
        self._stop_status_check.set()
        if self._status_check_thread and self._status_check_thread.is_alive():
            self._status_check_thread.join(timeout=1)
        
        self._status_cache.clear()
