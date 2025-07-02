import customtkinter as ctk
from tkinter import messagebox
import logging
import winreg
import win32cred
import pywintypes
from cryptography.fernet import Fernet
import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from gui.home_frame import TabHomeFrame
from utils.config import ConfigManager
from utils.password_manager import PasswordManager

logger = logging.getLogger(__name__)

class SettingsFrame(ctk.CTkFrame):
    """Фрейм настроек приложения."""
    
    def __init__(self, parent, home_frame, load_from_config: bool = False):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        
        self.parent = parent
        self.home_frame = home_frame
        self.load_from_config = load_from_config
        
        # Менеджеры
        self.config_manager = ConfigManager()
        self.password_manager = PasswordManager()
        
        # Создание UI
        self._create_widgets()
        
        # Загрузка сохраненных настроек
        if self.load_from_config:
            self.after(100, self.load_all_settings)
    
    def _create_widgets(self):
        """Создание всех виджетов настроек."""
        # Основной контейнер с прокруткой
        self.main_container = ctk.CTkScrollableFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Заголовок
        self.title_label = ctk.CTkLabel(
            self.main_container, 
            text="Настройки", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=(0, 20))
        
        # Секции настроек
        self._create_appearance_section()
        self._create_password_section()
        self._create_user_management_section()
        self._create_advanced_section()
        
        # Кнопки действий
        self._create_action_buttons()
    
    def _create_section_frame(self, title: str) -> ctk.CTkFrame:
        """Создание фрейма для секции настроек."""
        # Заголовок секции
        section_label = ctk.CTkLabel(
            self.main_container,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold")
        )
        section_label.pack(anchor="w", pady=(20, 10))
        
        # Фрейм секции
        section_frame = ctk.CTkFrame(self.main_container)
        section_frame.pack(fill="x", pady=(0, 10))
        
        return section_frame
    
    def _create_appearance_section(self):
        """Создание секции настроек внешнего вида."""
        frame = self._create_section_frame("🎨 Внешний вид")
        
        # Масштабирование UI
        scaling_container = ctk.CTkFrame(frame, fg_color="transparent")
        scaling_container.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            scaling_container, 
            text="Масштаб интерфейса:",
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=(0, 20))
        
        self.scaling_slider = ctk.CTkSlider(
            scaling_container,
            from_=0.8,
            to=1.5,
            number_of_steps=14,
            command=self._on_scaling_change
        )
        self.scaling_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.scaling_label = ctk.CTkLabel(
            scaling_container,
            text="100%",
            font=ctk.CTkFont(size=14)
        )
        self.scaling_label.pack(side="left")
        
        # Тема оформления
        theme_container = ctk.CTkFrame(frame, fg_color="transparent")
        theme_container.pack(fill="x", padx=20, pady=(10, 20))
        
        ctk.CTkLabel(
            theme_container,
            text="Тема оформления:",
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=(0, 20))
        
        self.appearance_mode_menu = ctk.CTkSegmentedButton(
            theme_container,
            values=["Светлая", "Тёмная", "Системная"],
            command=self._on_theme_change
        )
        self.appearance_mode_menu.pack(side="left")
        self.appearance_mode_menu.set("Тёмная")
    
    def _create_password_section(self):
        """Создание секции управления паролями."""
        frame = self._create_section_frame("🔐 Управление паролем")
        
        # Контейнер для пароля
        password_container = ctk.CTkFrame(frame, fg_color="transparent")
        password_container.pack(fill="x", padx=20, pady=20)
        
        # Поле ввода пароля
        password_input_frame = ctk.CTkFrame(password_container, fg_color="transparent")
        password_input_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            password_input_frame,
            text="Пароль для AD:",
            font=ctk.CTkFont(size=14)
        ).pack(anchor="w")
        
        self.password_entry = ctk.CTkEntry(
            password_input_frame,
            placeholder_text="Введите пароль",
            show="*"
        )
        self.password_entry.pack(fill="x", pady=(5, 0))
        
        # Кнопка показать/скрыть пароль
        self.show_password_var = ctk.BooleanVar(value=False)
        self.show_password_checkbox = ctk.CTkCheckBox(
            password_input_frame,
            text="Показать пароль",
            variable=self.show_password_var,
            command=self._toggle_password_visibility
        )
        self.show_password_checkbox.pack(anchor="w", pady=(5, 0))
        
        # Метод хранения
        storage_frame = ctk.CTkFrame(password_container, fg_color="transparent")
        storage_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkLabel(
            storage_frame,
            text="Метод хранения:",
            font=ctk.CTkFont(size=14)
        ).pack(anchor="w")
        
        self.storage_optionemenu = ctk.CTkOptionMenu(
            storage_frame,
            values=["Credential Manager", "Реестр (зашифрованный)"],
            command=self._on_storage_method_change
        )
        self.storage_optionemenu.pack(fill="x", pady=(5, 0))
        self.storage_optionemenu.set("Credential Manager")
        
        # Кнопки управления паролем
        button_frame = ctk.CTkFrame(password_container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkButton(
            button_frame,
            text="Сохранить пароль",
            command=self.save_password,
            width=140
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            button_frame,
            text="Очистить пароль",
            command=self.clear_password,
            width=140,
            fg_color="transparent",
            border_width=2
        ).pack(side="left")
    
    def _create_user_management_section(self):
        """Создание секции управления пользователями."""
        frame = self._create_section_frame("👥 Управление доступом")
        
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="x", padx=20, pady=20)
        
        # Список пользователей
        ctk.CTkLabel(
            container,
            text="Пользователи с доступом:",
            font=ctk.CTkFont(size=14)
        ).pack(anchor="w")
        
        # Фрейм для списка
        list_frame = ctk.CTkFrame(container)
        list_frame.pack(fill="x", pady=(5, 10))
        
        self.users_textbox = ctk.CTkTextbox(list_frame, height=100)
        self.users_textbox.pack(fill="x", padx=10, pady=10)
        
        # Загрузка списка пользователей
        self._load_users_list()
        
        # Управление пользователями
        user_control_frame = ctk.CTkFrame(container, fg_color="transparent")
        user_control_frame.pack(fill="x")
        
        self.new_user_entry = ctk.CTkEntry(
            user_control_frame,
            placeholder_text="Логин нового пользователя"
        )
        self.new_user_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(
            user_control_frame,
            text="Добавить",
            command=self._add_user,
            width=100
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            user_control_frame,
            text="Удалить",
            command=self._remove_user,
            width=100,
            fg_color="transparent",
            border_width=2
        ).pack(side="left")
    
    def _create_advanced_section(self):
        """Создание секции расширенных настроек."""
        frame = self._create_section_frame("⚙️ Расширенные настройки")
        
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="x", padx=20, pady=20)
        
        # Автозагрузка
        self.autoload_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            container,
            text="Загружать последнюю конфигурацию при запуске",
            variable=self.autoload_var
        ).pack(anchor="w", pady=(0, 10))
        
        # Автосохранение
        self.autosave_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            container,
            text="Автоматически сохранять изменения",
            variable=self.autosave_var
        ).pack(anchor="w", pady=(0, 10))
        
        # Логирование
        log_frame = ctk.CTkFrame(container, fg_color="transparent")
        log_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkLabel(
            log_frame,
            text="Уровень логирования:",
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=(0, 10))
        
        self.log_level_menu = ctk.CTkOptionMenu(
            log_frame,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            command=self._on_log_level_change
        )
        self.log_level_menu.pack(side="left")
        self.log_level_menu.set("INFO")
    
    def _create_action_buttons(self):
        """Создание кнопок действий."""
        button_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(20, 0))
        
        # Кнопка сохранения всех настроек
        ctk.CTkButton(
            button_frame,
            text="💾 Сохранить все настройки",
            command=self.save_all_settings,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=(0, 10))
        
        # Кнопка сброса настроек
        ctk.CTkButton(
            button_frame,
            text="🔄 Сбросить настройки",
            command=self._reset_settings,
            height=40,
            fg_color="transparent",
            border_width=2
        ).pack(side="left", padx=(0, 10))
        
        # Кнопка экспорта конфигурации
        ctk.CTkButton(
            button_frame,
            text="📤 Экспорт",
            command=self._export_config,
            height=40,
            width=100
        ).pack(side="left", padx=(0, 10))
        
        # Кнопка импорта конфигурации
        ctk.CTkButton(
            button_frame,
            text="📥 Импорт",
            command=self._import_config,
            height=40,
            width=100
        ).pack(side="left")
    
    def _on_scaling_change(self, value: float):
        """Обработка изменения масштаба."""
        percentage = int(value * 100)
        self.scaling_label.configure(text=f"{percentage}%")
        ctk.set_widget_scaling(value)
    
    def _on_theme_change(self, value: str):
        """Обработка изменения темы."""
        theme_map = {
            "Светлая": "Light",
            "Тёмная": "Dark",
            "Системная": "System"
        }
        mode = theme_map.get(value, "System")
        ctk.set_appearance_mode(mode)
        self._update_all_styles(mode)
    
    def _on_storage_method_change(self, method: str):
        """Обработка изменения метода хранения пароля."""
        logger.debug(f"Выбран метод хранения: {method}")
        self.load_password()
    
    def _on_log_level_change(self, level: str):
        """Обработка изменения уровня логирования."""
        logging.getLogger().setLevel(getattr(logging, level))
        logger.info(f"Уровень логирования изменен на: {level}")
    
    def _toggle_password_visibility(self):
        """Переключение видимости пароля."""
        if self.show_password_var.get():
            self.password_entry.configure(show="")
        else:
            self.password_entry.configure(show="*")
    
    def _update_all_styles(self, mode: str):
        """Обновление стилей всех компонентов."""
        # Обновление контекстных меню
        self._update_context_menu_theme()
        
        # Обновление таблиц
        self.home_frame.update_all_treeview_styles(mode)
    
    def _update_context_menu_theme(self):
        """Обновление темы контекстных меню."""
        appearance_mode = ctk.get_appearance_mode()
        
        # Цвета для разных тем
        if appearance_mode == "Dark":
            bg = "#2e2e2e"
            fg = "white"
            active_bg = "#5f5f5f"
        else:
            bg = "white"
            fg = "black"
            active_bg = "#cfcfcf"
        
        # Обновление всех контекстных меню
        tab_names = list(self.home_frame.tabview._tab_dict.keys())
        for tab_name in tab_names:
            try:
                tab_frame = self.home_frame.tabview.tab(tab_name)
                if tab_frame.winfo_children():
                    frame = tab_frame.winfo_children()[0]
                    if hasattr(frame, 'context_menu'):
                        frame.context_menu.configure(
                            bg=bg,
                            fg=fg,
                            activebackground=active_bg,
                            activeforeground=fg
                        )
            except Exception as e:
                logger.error(f"Ошибка обновления контекстного меню: {e}")
    
    def _load_users_list(self):
        """Загрузка списка пользователей."""
        users = self.config_manager.get_allowed_users()
        self.users_textbox.delete("1.0", "end")
        self.users_textbox.insert("1.0", "\n".join(users))
    
    def _add_user(self):
        """Добавление нового пользователя."""
        username = self.new_user_entry.get().strip()
        if not username:
            self.parent.show_warning("Предупреждение", "Введите логин пользователя")
            return
        
        if self.config_manager.add_allowed_user(username):
            self._load_users_list()
            self.new_user_entry.delete(0, "end")
            self.parent.show_info("Успех", f"Пользователь {username} добавлен")
        else:
            self.parent.show_warning("Предупреждение", "Пользователь уже существует")
    
    def _remove_user(self):
        """Удаление выбранного пользователя."""
        # Получаем выделенный текст
        try:
            selected = self.users_textbox.get("sel.first", "sel.last").strip()
            if not selected:
                self.parent.show_warning("Предупреждение", "Выберите пользователя для удаления")
                return
            
            confirm = messagebox.askyesno(
                "Подтверждение",
                f"Удалить пользователя {selected}?"
            )
            
            if confirm and self.config_manager.remove_allowed_user(selected):
                self._load_users_list()
                self.parent.show_info("Успех", f"Пользователь {selected} удален")
        except Exception:
            self.parent.show_warning("Предупреждение", "Выберите пользователя для удаления")
    
    def _reset_settings(self):
        """Сброс всех настроек."""
        confirm = messagebox.askyesno(
            "Подтверждение",
            "Вы уверены, что хотите сбросить все настройки?"
        )
        
        if not confirm:
            return
        
        # Сброс настроек
        self.scaling_slider.set(1.0)
        self._on_scaling_change(1.0)
        
        self.appearance_mode_menu.set("Системная")
        self._on_theme_change("Системная")
        
        self.storage_optionemenu.set("Credential Manager")
        self.password_entry.delete(0, "end")
        
        self.autoload_var.set(True)
        self.autosave_var.set(True)
        self.log_level_menu.set("INFO")
        
        # Сохранение дефолтной конфигурации
        default_config = self.config_manager._get_default_config()
        self.config_manager.save_config(default_config)
        
        self.parent.show_info("Успех", "Настройки сброшены")
    
    def _export_config(self):
        """Экспорт конфигурации."""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")],
            title="Экспорт конфигурации"
        )
        
        if not filename:
            return
        
        try:
            config = self.config_manager.load_config()
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            self.parent.show_info("Успех", f"Конфигурация экспортирована в {filename}")
        except Exception as e:
            logger.error(f"Ошибка экспорта конфигурации: {e}")
            self.parent.show_error("Ошибка", f"Не удалось экспортировать конфигурацию: {e}")
    
    def _import_config(self):
        """Импорт конфигурации."""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")],
            title="Импорт конфигурации"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Сохраняем импортированную конфигурацию
            self.config_manager.save_config(config)
            
            # Перезагружаем настройки
            self.load_all_settings()
            
            self.parent.show_info("Успех", "Конфигурация импортирована")
        except Exception as e:
            logger.error(f"Ошибка импорта конфигурации: {e}")
            self.parent.show_error("Ошибка", f"Не удалось импортировать конфигурацию: {e}")
    
    def save_password(self):
        """Сохранение пароля."""
        password = self.password_entry.get().strip()
        if not password:
            self.parent.show_warning("Предупреждение", "Введите пароль для сохранения")
            return
        
        method = self.storage_optionemenu.get()
        success = self.password_manager.save_password(password, method)
        
        if success:
            self.parent.show_info("Успех", "Пароль сохранен")
            if self.autosave_var.get():
                self.save_all_settings()
        else:
            self.parent.show_error("Ошибка", "Не удалось сохранить пароль")
    
    def load_password(self):
        """Загрузка пароля."""
        method = self.storage_optionemenu.get()
        password = self.password_manager.load_password(method)
        
        self.password_entry.delete(0, "end")
        if password:
            self.password_entry.insert(0, password)
    
    def clear_password(self):
        """Очистка пароля."""
        method = self.storage_optionemenu.get()
        success = self.password_manager.clear_password(method)
        
        if success:
            self.password_entry.delete(0, "end")
            self.parent.show_info("Успех", "Пароль удален")
        else:
            self.parent.show_warning("Предупреждение", "Пароль не найден")
    
    def save_all_settings(self):
        """Сохранение всех настроек."""
        try:
            # Собираем конфигурацию
            config = {
                "ui_scaling": f"{int(self.scaling_slider.get() * 100)}%",
                "appearance_mode": self._get_theme_english_name(),
                "storage_method": self.storage_optionemenu.get(),
                "autoload": self.autoload_var.get(),
                "autosave": self.autosave_var.get(),
                "log_level": self.log_level_menu.get(),
                "tabs": []
            }
            
            # Собираем данные вкладок
            tab_names = list(self.home_frame.tabview._tab_dict.keys())
            for tab_name in tab_names:
                tab_frame = self.home_frame.tabview.tab(tab_name).winfo_children()[0]
                
                # Собираем только группы (не сессии и не принтеры)
                groups = []
                for item in tab_frame.group_tree.get_children():
                    groups.append(tab_frame.group_tree.item(item, "values"))
                
                tab_data = {
                    "tab_name": tab_name,
                    "server": tab_frame.server_entry.get(),
                    "domain": tab_frame.combobox_domain.get(),
                    "password_status": tab_frame.password_status_entry.get(),
                    "group_search": tab_frame.group_search_entry.get(),
                    "groups": groups,  # Только группы, без сессий и принтеров
                    "session_tree_columns": tab_frame.get_treeview_column_widths(tab_frame.tree),
                    "group_tree_columns": tab_frame.get_treeview_column_widths(tab_frame.group_tree),
                    "printer_tree_columns": tab_frame.get_treeview_column_widths(tab_frame.printer_manager.tree)
                }
                config["tabs"].append(tab_data)
            
            # Сохраняем конфигурацию
            success = self.config_manager.save_config(config)
            
            if success:
                logger.info("Настройки успешно сохранены")
                self.parent.show_info("Успех", "Настройки сохранены")
            else:
                self.parent.show_error("Ошибка", "Не удалось сохранить настройки")
                
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}", exc_info=True)
            self.parent.show_error("Ошибка", f"Не удалось сохранить настройки: {e}")
    
    def load_all_settings(self):
        """Загрузка всех настроек."""
        try:
            # Загружаем пароль
            self.load_password()
            
            # Загружаем конфигурацию
            config = self.config_manager.load_config()
            
            # Применяем настройки UI
            scaling = config.get("ui_scaling", "100%")
            scale_value = int(scaling.strip('%')) / 100
            self.scaling_slider.set(scale_value)
            self._on_scaling_change(scale_value)
            
            # Применяем тему
            theme = config.get("appearance_mode", "System")
            theme_russian = self._get_theme_russian_name(theme)
            self.appearance_mode_menu.set(theme_russian)
            self._on_theme_change(theme_russian)
            
            # Метод хранения пароля
            storage = config.get("storage_method", "Credential Manager")
            self.storage_optionemenu.set(storage)
            
            # Дополнительные настройки
            self.autoload_var.set(config.get("autoload", True))
            self.autosave_var.set(config.get("autosave", True))
            self.log_level_menu.set(config.get("log_level", "INFO"))
            self._on_log_level_change(config.get("log_level", "INFO"))
            
            # Удаляем существующие вкладки
            for tab_name in list(self.home_frame.tabview._tab_dict.keys()):
                self.home_frame.tabview.delete(tab_name)
            
            # Создаем вкладки из конфигурации
            tabs = config.get("tabs", [])
            if not tabs:
                # Если вкладок нет, создаем дефолтные
                logger.debug("В конфигурации нет вкладок, создаём дефолтные")
                for i in range(1, 4):
                    tab_name = f"Сервер {i}"
                    tab = self.home_frame.tabview.add(tab_name)
                    TabHomeFrame(tab, tab_name, self.parent, load_from_config=False).pack(fill="both", expand=True)
            else:
                # Создаем вкладки из конфигурации
                for tab_data in tabs:
                    tab = self.home_frame.tabview.add(tab_data["tab_name"])
                    tab_frame = TabHomeFrame(
                        tab,
                        tab_data["tab_name"],
                        self.parent,
                        load_from_config=True,
                        config_data=tab_data
                    )
                    tab_frame.pack(fill="both", expand=True)
                    
                    # Восстанавливаем данные таблиц
                    for session in tab_data.get("sessions", []):
                        tab_frame.tree.insert("", "end", values=session)
                    
                    for group in tab_data.get("groups", []):
                        tab_frame.group_tree.insert("", "end", values=group)
                    
                    for printer in tab_data.get("printers", []):
                        tab_frame.printer_manager.tree.insert("", "end", values=printer)
            
            logger.info("Настройки успешно загружены")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}", exc_info=True)
            # При ошибке создаем дефолтные вкладки
            for i in range(1, 4):
                tab_name = f"Сервер {i}"
                tab = self.home_frame.tabview.add(tab_name)
                TabHomeFrame(tab, tab_name, self.parent, load_from_config=False).pack(fill="both", expand=True)
    
    def _get_theme_english_name(self) -> str:
        """Получение английского названия темы."""
        current = self.appearance_mode_menu.get()
        theme_map = {
            "Светлая": "Light",
            "Тёмная": "Dark",
            "Системная": "System"
        }
        return theme_map.get(current, "System")
    
    def _get_theme_russian_name(self, english_name: str) -> str:
        """Получение русского названия темы."""
        theme_map = {
            "Light": "Светлая",
            "Dark": "Тёмная",
            "System": "Системная"
        }
        return theme_map.get(english_name, "Системная")