import customtkinter as ctk
import os
import sys
from PIL import Image
from pathlib import Path
import logging
from typing import Dict, Callable

logger = logging.getLogger(__name__)

class NavigationFrame(ctk.CTkFrame):
    """Фрейм навигации с кнопками для переключения между разделами."""
    
    def __init__(self, parent, select_frame_callback: Callable):
        super().__init__(parent, corner_radius=0)
        
        self.select_frame_callback = select_frame_callback
        self.buttons: Dict[str, ctk.CTkButton] = {}
        self.active_button = None
        
        # Настройка сетки
        self.grid_rowconfigure(10, weight=1)  # Пустое пространство внизу
        
        # Загрузка изображений
        self._load_images()
        
        # Создание элементов навигации
        self._create_header()
        self._create_navigation_buttons()
        self._create_footer()
        
        # Установка начальной активной кнопки
        self.set_active_button("home")
    
    def _load_images(self):
        """Загрузка изображений для кнопок."""
        # Определяем путь к изображениям
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent
        
        image_path = base_path / "test_images"
        
        # Размер изображений
        icon_size = (20, 20)
        
        # Загрузка изображений с обработкой ошибок
        try:
            self.home_image = self._load_image(image_path, "home", icon_size)
            self.chat_image = self._load_image(image_path, "chat", icon_size)
            self.settings_image = self._load_image(image_path, "add_user", icon_size)
            self.vnc_image = self._load_image(image_path, "vnc", icon_size)
        except Exception as e:
            logger.error(f"Ошибка загрузки изображений: {e}")
            # Создаем пустые изображения как fallback
            self._create_fallback_images(icon_size)
    
    def _load_image(self, base_path: Path, name: str, size: tuple) -> ctk.CTkImage:
        """Загрузка одного изображения."""
        light_path = base_path / f"{name}_dark.png"
        dark_path = base_path / f"{name}_light.png"
        
        # Проверяем существование файлов
        if not light_path.exists() or not dark_path.exists():
            logger.warning(f"Изображения {name} не найдены, используется заглушка")
            return self._create_placeholder_image(size)
        
        return ctk.CTkImage(
            light_image=Image.open(light_path),
            dark_image=Image.open(dark_path),
            size=size
        )
    
    def _create_placeholder_image(self, size: tuple) -> ctk.CTkImage:
        """Создание изображения-заглушки."""
        placeholder = Image.new('RGBA', size, (128, 128, 128, 255))
        return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=size)
    
    def _create_fallback_images(self, size: tuple):
        """Создание заглушек для всех изображений."""
        self.home_image = self._create_placeholder_image(size)
        self.chat_image = self._create_placeholder_image(size)
        self.settings_image = self._create_placeholder_image(size)
        self.powershell_image = self._create_placeholder_image(size)
    
    def _create_header(self):
        """Создание заголовка навигационной панели."""
        # Логотип/заголовок
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=10, pady=(20, 10), sticky="ew")
        
        self.logo_label = ctk.CTkLabel(
            self.header_frame, 
            text="RDP Manager", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.logo_label.pack()
        
        # Разделитель
        self.separator = ctk.CTkFrame(self, height=2, fg_color=("gray70", "gray30"))
        self.separator.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
    
    def _create_navigation_buttons(self):
        """Создание кнопок навигации."""
        button_config = [
            ("home", "Shadow RDP", self.home_image, 2),
            ("frame_3", "Настройки", self.settings_image, 3),
            ("vnc", "VNC Viewer", self.vnc_image, 4),  # Добавляем VNC
            # ("powershell", "PowerShell", self.powershell_image, 5),  # Закомментировано
        ]
        
        for name, text, image, row in button_config:
            button = self._create_button(name, text, image, row)
            self.buttons[name] = button
    
    def _create_button(self, name: str, text: str, image: ctk.CTkImage, row: int) -> ctk.CTkButton:
        """Создание одной кнопки навигации."""
        button = ctk.CTkButton(
            self,
            corner_radius=6,
            height=40,
            border_spacing=10,
            text=text,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            image=image,
            anchor="w",
            command=lambda: self._on_button_click(name)
        )
        button.grid(row=row, column=0, sticky="ew", padx=10, pady=2)
        return button
    
    def _create_footer(self):
        """Создание нижней части навигационной панели."""
        # Информация о пользователе
        self.user_info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.user_info_frame.grid(row=9, column=0, padx=10, pady=10, sticky="ew")
        
        # Имя пользователя
        username = os.getenv("USERNAME", "Пользователь")
        self.user_label = ctk.CTkLabel(
            self.user_info_frame,
            text=f"👤 {username}",
            font=ctk.CTkFont(size=12)
        )
        self.user_label.pack()
        
        # Версия приложения
        self.version_label = ctk.CTkLabel(
            self,
            text="v1.0.0",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60")
        )
        self.version_label.grid(row=10, column=0, padx=10, pady=(0, 10), sticky="s")
    
    def _on_button_click(self, frame_name: str):
        """Обработка клика по кнопке навигации."""
        self.select_frame_callback(frame_name)
        self.set_active_button(frame_name)
    
    def set_active_button(self, name: str):
        """Установка активной кнопки."""
        # Сброс стиля предыдущей активной кнопки
        if self.active_button and self.active_button in self.buttons:
            self.buttons[self.active_button].configure(
                fg_color="transparent",
                text_color=("gray10", "gray90")
            )
        
        # Установка стиля новой активной кнопки
        if name in self.buttons:
            self.buttons[name].configure(
                fg_color=("gray75", "gray25"),
                text_color=("gray10", "gray90")
            )
            self.active_button = name
    
    def add_custom_button(self, name: str, text: str, image: ctk.CTkImage = None, 
                         position: int = None) -> ctk.CTkButton:
        """
        Добавление пользовательской кнопки навигации.
        
        Args:
            name: Уникальное имя кнопки
            text: Текст кнопки
            image: Изображение кнопки (опционально)
            position: Позиция кнопки (row в сетке)
            
        Returns:
            Созданная кнопка
        """
        if name in self.buttons:
            logger.warning(f"Кнопка с именем {name} уже существует")
            return self.buttons[name]
        
        # Определяем позицию
        if position is None:
            position = len(self.buttons) + 2
        
        # Используем placeholder если изображение не предоставлено
        if image is None:
            image = self._create_placeholder_image((20, 20))
        
        # Создаем кнопку
        button = self._create_button(name, text, image, position)
        self.buttons[name] = button
        
        logger.info(f"Добавлена кнопка навигации: {name}")
        return button
    
    def remove_button(self, name: str):
        """Удаление кнопки навигации."""
        if name not in self.buttons:
            logger.warning(f"Кнопка {name} не найдена")
            return
        
        button = self.buttons[name]
        button.destroy()
        del self.buttons[name]
        
        # Если удаляемая кнопка была активной
        if self.active_button == name:
            self.active_button = None
            # Активируем home если доступна
            if "home" in self.buttons:
                self.set_active_button("home")
                self.select_frame_callback("home")
        
        logger.info(f"Удалена кнопка навигации: {name}")
    
    def update_button_text(self, name: str, new_text: str):
        """Обновление текста кнопки."""
        if name in self.buttons:
            self.buttons[name].configure(text=new_text)
    
    def update_button_image(self, name: str, new_image: ctk.CTkImage):
        """Обновление изображения кнопки."""
        if name in self.buttons:
            self.buttons[name].configure(image=new_image)
    
    def set_button_state(self, name: str, state: str):
        """
        Установка состояния кнопки.
        
        Args:
            name: Имя кнопки
            state: "normal" или "disabled"
        """
        if name in self.buttons:
            self.buttons[name].configure(state=state)
