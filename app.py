import customtkinter as ctk
from gui.navigation import NavigationFrame
from gui.home_frame import HomeFrame
from gui.settings_frame import SettingsFrame
from utils.config import ConfigManager
import logging
import os
import sys
from pathlib import Path
import json

# Настройка логирования
logger = logging.getLogger(__name__)

class App(ctk.CTk):
    """Главное окно приложения RDP Manager."""
    
    def __init__(self):
        super().__init__()
        
        # Конфигурация окна
        self.title("RDP Manager")
        self.geometry("1400x800")  # ИСПРАВЛЕНИЕ: Увеличили размер окна
        self.minsize(1300, 700)    # ИСПРАВЛЕНИЕ: Увеличили минимальный размер
        
        # Установка иконки приложения
        self._set_window_icon()
        
        # Инициализация менеджера конфигурации
        self.config_manager = ConfigManager()
        
        # ИСПРАВЛЕНИЕ: Правильная настройка сетки главного окна
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # Навигация - фиксированная ширина
        self.grid_columnconfigure(1, weight=1)  # Основное содержимое - растягивается
        
        # Загрузка темы из конфигурации
        self._load_theme()
        
        # Инициализация фреймов
        self._initialize_frames()
        
        # Загрузка настроек
        self._load_settings()
        
        # Выбор начального фрейма
        self.select_frame_by_name("home")
        
        # ИСПРАВЛЕНИЕ: Поэтапная инициализация для корректного отображения
        self.after(50, self._post_init_stage1)
        self.after(150, self._post_init_stage2)
        self.after(300, self._post_init_final)
        
    def _set_window_icon(self):
        """Установка иконки окна."""
        try:
            if sys.platform == "win32":
                icon_path = self.config_manager.get_resource_path("assets/icon.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Не удалось установить иконку: {e}")
    
    def _load_theme(self):
        """Загрузка темы из конфигурации."""
        try:
            config = self.config_manager.load_config()
            theme = config.get("appearance_mode", "System")
            ctk.set_appearance_mode(theme)
        except Exception as e:
            logger.error(f"Ошибка загрузки темы: {e}")
            ctk.set_appearance_mode("System")
    
    def _initialize_frames(self):
        """Инициализация всех фреймов приложения."""
        try:
            # Проверяем наличие сохраненной конфигурации
            self.config_exists = self.config_manager.config_exists()
            logger.debug(f"Конфигурация существует: {self.config_exists}")
            
            # Навигационный фрейм
            self.navigation_frame = NavigationFrame(self, self.select_frame_by_name)
            self.navigation_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
            
            # Главный фрейм
            self.home_frame = HomeFrame(
                self, 
                self, 
                load_from_config=self.config_exists
            )
            
            # Фрейм настроек
            self.settings_frame = SettingsFrame(
                self, 
                self.home_frame, 
                load_from_config=self.config_exists
            )
            
        except Exception as e:
            logger.error(f"Ошибка инициализации фреймов: {e}", exc_info=True)
            raise
    
    def _load_settings(self):
        """Загрузка всех настроек приложения."""
        if self.config_exists:
            try:
                self.settings_frame.load_all_settings()
                logger.info("Настройки успешно загружены")
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {e}")
    
    def _post_init_stage1(self):
        """Этап 1: Принудительное обновление и центрирование."""
        try:
            # Центрирование окна
            self.center_window()
            
            # Принудительное обновление
            self.update_idletasks()
            
            # Обновляем все дочерние элементы
            for child in self.winfo_children():
                child.update_idletasks()
                
        except Exception as e:
            logger.debug(f"Ошибка этапа 1 инициализации: {e}")
    
    def _post_init_stage2(self):
        """Этап 2: Обновление фреймов."""
        try:
            # Обновляем home_frame если он активен
            if hasattr(self, 'home_frame') and self.home_frame.winfo_viewable():
                self.home_frame.update_idletasks()
                
        except Exception as e:
            logger.debug(f"Ошибка этапа 2 инициализации: {e}")
    
    def _post_init_final(self):
        """Финальный этап инициализации."""
        try:
            # Финальное обновление всех элементов
            self.update_idletasks()
            self.update()
            
            logger.debug("Инициализация главного окна завершена")
            
        except Exception as e:
            logger.debug(f"Ошибка финального этапа инициализации: {e}")
    
    def center_window(self):
        """Центрирование окна на экране."""
        self.update_idletasks()
        
        # Получаем размеры окна
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        
        # Получаем размеры экрана
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Вычисляем позицию
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Устанавливаем позицию
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def select_frame_by_name(self, name: str):
        """
        Переключение между фреймами.
        
        Args:
            name: Имя фрейма для отображения
        """
        # Скрываем все фреймы
        self.home_frame.grid_forget()
        self.settings_frame.grid_forget()
        
        # Отображаем выбранный фрейм
        if name == "home":
            self.home_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5), pady=5)
        elif name == "settings" or name == "frame_3":  # Поддержка обоих имен
            self.settings_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5), pady=5)
        else:
            logger.warning(f"Неизвестный фрейм: {name}")
            # По умолчанию показываем home
            self.home_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5), pady=5)
        
        # Обновляем выделение в навигации
        self.navigation_frame.set_active_button(name)
    
    def on_closing(self):
        """Обработчик закрытия приложения."""
        try:
            logger.info("Закрытие приложения...")
            
            # Сохраняем настройки
            self.settings_frame.save_all_settings()
            logger.info("Настройки сохранены")
            
            # Очистка ресурсов
            self._cleanup_resources()
            
        except Exception as e:
            logger.error(f"Ошибка при закрытии приложения: {e}")
        finally:
            self.destroy()
    
    def _cleanup_resources(self):
        """Очистка ресурсов перед закрытием."""
        try:
            # Закрываем соединения с AD если есть
            if hasattr(self.home_frame, 'cleanup'):
                self.home_frame.cleanup()
        except Exception as e:
            logger.error(f"Ошибка очистки ресурсов: {e}")
    
    def show_error(self, title: str, message: str):
        """
        Отображение сообщения об ошибке.
        
        Args:
            title: Заголовок сообщения
            message: Текст сообщения
        """
        from tkinter import messagebox
        messagebox.showerror(title, message)
    
    def show_info(self, title: str, message: str):
        """
        Отображение информационного сообщения.
        
        Args:
            title: Заголовок сообщения
            message: Текст сообщения
        """
        from tkinter import messagebox
        messagebox.showinfo(title, message)
    
    def show_warning(self, title: str, message: str):
        """
        Отображение предупреждения.
        
        Args:
            title: Заголовок сообщения
            message: Текст сообщения
        """
        from tkinter import messagebox
        messagebox.showwarning(title, message)
