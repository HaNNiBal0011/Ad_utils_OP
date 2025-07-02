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
        search_container.grid(row=row, column=column, padx=5, pady=5, sticky="ew")
        
        # Поле поиска
        self.search_entry = ctk.CTkEntry(
            search_container,
            width=200,
            placeholder_text="Поиск принтеров..."
        )
        self.search_entry.pack(side="left", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        
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
        
        # Кнопка обновления
        self.refresh_button = ctk.CTkButton(
            button_frame,
            text="🔄 Обновить",
            command=self.refresh_printers,
            width=100
        )
        self.refresh_button.pack(side="left")
        
        # Статус
        self.status_label = ctk.CTkLabel(
            search_container,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70")
        )
        self.status_label.pack(side="left", padx=(10, 0))
        
        # Фрейм для Treeview
        self.printer_frame = ctk.CTkFrame(self.parent)
        self.printer_frame.grid(row=tree_row, column=column, padx=5, pady=5, sticky="nsew")
        self.printer_frame.grid_rowconfigure(0, weight=1)
        self.printer_frame.grid_columnconfigure(0, weight=1)
        
        # Настройка Treeview
        self._setup_treeview(tree_height, tree_columns)
        
        # Начальное отображение
        self.refresh_printers()
    
    def _setup_treeview(self, height: int, column_widths: Optional[Dict]):
        """Настройка таблицы принтеров."""
        columns = ("Printer", "IP", "Server", "Status")  # Убрали Model
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
                printer = Printer(
                    name=item.get("Printer", ""),
                    ip=item.get("IP", ""),
                    server=item.get("Server", ""),
                    model=None,  # Больше не используем
                    location=item.get("Location"),
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
            {"Printer": "HP_LaserJet_1", "IP": "192.168.1.100", "Server": "TS-IT0", "Location": "IT Office, 2nd Floor"},
            {"Printer": "Canon_Color_1", "IP": "192.168.1.101", "Server": "TS-IT0", "Location": "Reception, 1st Floor"},
            {"Printer": "Xerox_MFP_1", "IP": "192.168.1.102", "Server": "TS-HR0", "Location": "HR Department, 3rd Floor"},
        ]
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_printers, f, ensure_ascii=False, indent=4)
            logger.info("Создан файл принтеров по умолчанию")
            
            # Перезагружаем принтеры
            self._load_printers()
        except Exception as e:
            logger.error(f"Ошибка создания файла принтеров: {e}")
    
    def refresh_printers(self):
        """Обновление списка принтеров с фильтрацией по серверу."""
        server_filter = self.parent.server_entry.get().strip().lower()
        search_text = self.search_entry.get().strip().lower()
        
        # Фильтрация принтеров
        self.filtered_printers = []
        seen_printers = set()  # Для отслеживания уже добавленных принтеров
        
        for printer in self.printers:
            # Фильтр по серверу
            if server_filter and printer.server.lower() != server_filter:
                continue
            
            # Фильтр по поиску
            if search_text:
                if not any(search_text in str(getattr(printer, attr, "")).lower() 
                        for attr in ['name', 'ip', 'server', 'location']):
                    continue
            
            # Проверяем на дублирование принтеров
            # Всегда исключаем дубли по IP адресу, но при общем поиске 
            # показываем принтер с наиболее релевантным сервером
            printer_key = printer.ip
            
            if printer_key not in seen_printers:
                seen_printers.add(printer_key)
                self.filtered_printers.append(printer)
        
        # Обновление таблицы
        self._update_treeview()
        
        # Обновление статуса
        status_text = f"Найдено: {len(self.filtered_printers)} из {len(self.printers)}"
        if server_filter:
            status_text += f" (сервер: {server_filter})"
        self.status_label.configure(text=status_text)
        
        # Запуск проверки статусов в фоне
        if self.filtered_printers:
            self._start_status_check()
    
    def _update_treeview(self):
        """Обновление содержимого таблицы."""
        # Сохраняем выделение
        selected = self.tree.selection()
        selected_values = []
        for item in selected:
            selected_values.append(self.tree.item(item, "values"))
        
        # Очищаем таблицу
        self.tree.delete(*self.tree.get_children())
        
        # Добавляем отфильтрованные принтеры
        for printer in self.filtered_printers:
            # Определяем тег для статуса
            tag = self._get_status_tag(printer.status)
            
            values = (
                printer.name,
                printer.ip,
                printer.server,
                printer.status
            )
            
            item = self.tree.insert("", "end", values=values, tags=(tag,))
            
            # Восстанавливаем выделение
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
    
    def search_printers(self):
        """Поиск принтеров по запросу."""
        self.refresh_printers()
    
    def _on_search_change(self, event):
        """Обработка изменения поискового запроса."""
        # Автоматический поиск при вводе
        self.refresh_printers()
    
    def _on_double_click(self, event):
        """Обработка двойного клика по принтеру."""
        selected = self.tree.selection()
        if not selected:
            return
        
        values = self.tree.item(selected[0], "values")
        if len(values) > 1:
            ip = values[1]
            if ip:
                # Открытие веб-интерфейса принтера
                import webbrowser
                webbrowser.open(f"http://{ip}")
                logger.info(f"Открыт веб-интерфейс принтера: {ip}")
    
    def _sort_by_column(self, column: str):
        """Сортировка таблицы по колонке."""
        # Получаем данные
        data = [(self.tree.item(child, "values"), child) for child in self.tree.get_children()]
        
        # Определяем индекс колонки
        columns = self.tree["columns"]
        col_index = columns.index(column)
        
        # Сортируем
        data.sort(key=lambda x: x[0][col_index])
        
        # Перестраиваем таблицу
        for index, (values, item) in enumerate(data):
            self.tree.move(item, "", index)
    
    def _start_status_check(self):
        """Запуск проверки статусов принтеров."""
        # Останавливаем предыдущую проверку если есть
        self._stop_status_check.set()
        if self._status_check_thread and self._status_check_thread.is_alive():
            self._status_check_thread.join(timeout=1)
        
        # Запускаем новую проверку
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
            
            # Проверяем кэш
            if printer.ip in self._status_cache:
                cached_status, cached_time = self._status_cache[printer.ip]
                if datetime.now() - cached_time < timedelta(seconds=self._cache_timeout):
                    printer.status = cached_status
                    self.parent.after(0, self._update_printer_status_in_tree, printer)
                    continue
            
            # Проверяем статус
            status = self._check_single_printer_status(printer.ip)
            printer.status = status
            printer.last_checked = datetime.now()
            
            # Обновляем кэш
            self._status_cache[printer.ip] = (status, datetime.now())
            
            # Обновляем UI
            self.parent.after(0, self._update_printer_status_in_tree, printer)
    
    def _check_single_printer_status(self, ip: str) -> str:
        """Проверка статуса одного принтера."""
        try:
            # Простая проверка доступности через HTTP
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
            if values[1] == printer.ip:  # Сравниваем по IP
                values[3] = printer.status
                tag = self._get_status_tag(printer.status)
                self.tree.item(item, values=values, tags=(tag,))
                break
    
    def export_printer_list(self, filename: str):
        """Экспорт списка принтеров в файл."""
        try:
            data = []
            for printer in self.printers:
                data.append({
                    "Printer": printer.name,
                    "IP": printer.ip,
                    "Server": printer.server,
                    "Location": printer.location
                })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Список принтеров экспортирован в {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка экспорта принтеров: {e}")
            return False
    
    def import_printer_list(self, filename: str):
        """Импорт списка принтеров из файла."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.printers = []
            for item in data:
                printer = Printer(
                    name=item.get("Printer", ""),
                    ip=item.get("IP", ""),
                    server=item.get("Server", ""),
                    model=None,  # Больше не используем
                    location=item.get("Location"),
                    status="Неизвестно"
                )
                self.printers.append(printer)
            
            # Сохраняем в файл по умолчанию
            default_path = self._get_resource_path("test_images/printers.json")
            with open(default_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            # Обновляем отображение
            self.refresh_printers()
            
            logger.info(f"Импортировано {len(self.printers)} принтеров")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка импорта принтеров: {e}")
            return False
    
    def add_printer(self, printer: Printer) -> bool:
        """Добавление нового принтера."""
        try:
            # Проверка на дубликаты
            for existing in self.printers:
                if existing.ip == printer.ip:
                    logger.warning(f"Принтер с IP {printer.ip} уже существует")
                    return False
            
            self.printers.append(printer)
            self._save_printers()
            self.refresh_printers()
            
            logger.info(f"Добавлен принтер: {printer.name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка добавления принтера: {e}")
            return False
    
    def remove_printer(self, ip: str) -> bool:
        """Удаление принтера по IP адресу."""
        try:
            self.printers = [p for p in self.printers if p.ip != ip]
            self._save_printers()
            self.refresh_printers()
            
            logger.info(f"Удален принтер с IP: {ip}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления принтера: {e}")
            return False
    
    def _save_printers(self):
        """Сохранение списка принтеров."""
        try:
            data = []
            for printer in self.printers:
                data.append({
                    "Printer": printer.name,
                    "IP": printer.ip,
                    "Server": printer.server,
                    "Location": printer.location
                })
            
            file_path = self._get_resource_path("test_images/printers.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения принтеров: {e}")
    
    def get_printer_by_ip(self, ip: str) -> Optional[Printer]:
        """Получение принтера по IP адресу."""
        for printer in self.printers:
            if printer.ip == ip:
                return printer
        return None
    
    def get_printers_by_server(self, server: str) -> List[Printer]:
        """Получение списка принтеров для сервера."""
        return [p for p in self.printers if p.server.lower() == server.lower()]
    
    def cleanup(self):
        """Очистка ресурсов."""
        # Останавливаем проверку статусов
        self._stop_status_check.set()
        if self._status_check_thread and self._status_check_thread.is_alive():
            self._status_check_thread.join(timeout=1)
        
        # Очищаем кэш
        self._status_cache.clear()
    
    def _adjust_columns_width(self):
        """Автоматическая подстройка ширины колонок под размер фрейма."""
        try:
            # Ждем полной отрисовки
            self.parent.update_idletasks()
            
            # Получаем доступную ширину (минус скроллбар)
            available_width = self.printer_frame.winfo_width() - 20
            
            if available_width > 100:  # Минимальная разумная ширина
                # Проверяем, есть ли сохраненные размеры из родителя
                if hasattr(self.parent, 'config_data'):
                    saved_columns = self.parent.config_data.get("printer_tree_columns", {})
                    
                    if saved_columns and all(col in saved_columns for col in self.tree["columns"]):
                        # Используем сохраненные размеры
                        for col in self.tree["columns"]:
                            self.tree.column(col, width=saved_columns[col])
                        return
                
                # Используем процентное распределение
                for col, (_, percentage) in self.column_config.items():
                    width = int(available_width * percentage)
                    self.tree.column(col, width=width)
        except Exception as e:
            logger.debug(f"Ошибка подстройки колонок принтеров: {e}")
    
    def _on_frame_resize(self, event):
        """Обработка изменения размера фрейма."""
        # Откладываем обработку для предотвращения множественных вызовов
        if hasattr(self, '_resize_job'):
            self.parent.after_cancel(self._resize_job)
        self._resize_job = self.parent.after(150, self._adjust_columns_width)