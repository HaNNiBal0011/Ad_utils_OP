# utils/config.py
import json
import os
import sys
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)

class ConfigManager:
    """Централизованный менеджер конфигурации приложения."""
    
    # Ключ шифрования - в продакшене должен генерироваться и храниться безопасно
    _ENCRYPTION_KEY = b'k9_jL-pXqWvR2mT5bYxN8cF4aZ0eH6uQ'
    
    def __init__(self):
        """Инициализация менеджера конфигурации."""
        self.config_dir = Path(os.getenv("APPDATA")) / "RDPManager"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "config.json"
        self.users_file = self.config_dir / "users.json"
        
        # Инициализация шифровщика
        self.cipher = Fernet(base64.urlsafe_b64encode(self._ENCRYPTION_KEY))
        
        # Путь к ресурсам
        if getattr(sys, 'frozen', False):
            self.resource_dir = Path(sys._MEIPASS)
        else:
            self.resource_dir = Path(__file__).parent.parent
    
    def get_resource_path(self, relative_path: str) -> Path:
        """
        Получение пути к ресурсу.
        
        Args:
            relative_path: Относительный путь к ресурсу
            
        Returns:
            Абсолютный путь к ресурсу
        """
        return self.resource_dir / relative_path
    
    def config_exists(self) -> bool:
        """Проверка существования файла конфигурации."""
        return self.config_file.exists()
    
    def load_config(self) -> Dict[str, Any]:
        """
        Загрузка конфигурации из файла.
        
        Returns:
            Словарь с конфигурацией
        """
        if not self.config_file.exists():
            return self._get_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Валидация и очистка конфигурации
            config = self._validate_config(config)
            
            return config
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return self._get_default_config()
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидация и очистка конфигурации.
        
        Args:
            config: Загруженная конфигурация
            
        Returns:
            Очищенная конфигурация
        """
        # Проверяем основные поля
        default = self._get_default_config()
        
        for key in default:
            if key not in config:
                config[key] = default[key]
        
        # Проверяем вкладки
        if "tabs" in config:
            for tab in config["tabs"]:
                # Проверяем группы на наличие данных принтеров
                if "groups" in tab and tab["groups"]:
                    cleaned_groups = []
                    for group in tab["groups"]:
                        # Группа должна быть кортежем с одним элементом (имя группы)
                        if isinstance(group, (list, tuple)) and len(group) == 1:
                            cleaned_groups.append(group)
                        elif isinstance(group, str):
                            cleaned_groups.append([group])
                        # Пропускаем элементы с несколькими полями (вероятно принтеры)
                        elif isinstance(group, (list, tuple)) and len(group) > 2:
                            logger.warning(f"Удален некорректный элемент из групп: {group}")
                    
                    tab["groups"] = cleaned_groups
                
                # Удаляем сохраненные принтеры и сессии (они должны загружаться динамически)
                tab.pop("printers", None)
                tab.pop("sessions", None)
        
        return config
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        Сохранение конфигурации в файл.
        
        Args:
            config: Словарь с конфигурацией
            
        Returns:
            True при успешном сохранении
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Получение конфигурации по умолчанию."""
        return {
            "ui_scaling": "100%",
            "appearance_mode": "System",
            "storage_method": "Credential Manager",
            "autoload": True,
            "autosave": True,
            "log_level": "INFO",
            "tabs": [
                {
                    "tab_name": "Сервер 1",
                    "server": "TS-IT0",
                    "domain": "nd.lan",
                    "password_status": "",
                    "group_search": "",
                    "groups": [],  # Пустой список групп
                    "session_tree_columns": {},
                    "group_tree_columns": {"GroupName": 338},
                    "printer_tree_columns": {"Printer": 180, "IP": 120, "Server": 100, "Status": 100}
                }
            ]
        }
    
    def get_allowed_users(self) -> List[str]:
        """
        Получение списка разрешенных пользователей.
        
        Returns:
            Список логинов пользователей
        """
        # Сначала проверяем файл с пользователями
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [user.lower() for user in data.get("allowed_users", [])]
            except Exception as e:
                logger.error(f"Ошибка загрузки списка пользователей: {e}")
        
        # Если файла нет или ошибка - используем встроенный список
        default_users = ["suprund", "ad-rozhkoa", "zheleznyakp"]
        
        # Сохраняем дефолтный список для будущего использования
        self._save_default_users(default_users)
        
        return default_users
    
    def _save_default_users(self, users: List[str]):
        """Сохранение списка пользователей по умолчанию."""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump({"allowed_users": users}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.warning(f"Не удалось сохранить список пользователей: {e}")
    
    def add_allowed_user(self, username: str) -> bool:
        """
        Добавление пользователя в список разрешенных.
        
        Args:
            username: Логин пользователя
            
        Returns:
            True при успешном добавлении
        """
        try:
            users = self.get_allowed_users()
            username_lower = username.lower()
            
            if username_lower not in users:
                users.append(username_lower)
                
                with open(self.users_file, 'w', encoding='utf-8') as f:
                    json.dump({"allowed_users": users}, f, ensure_ascii=False, indent=4)
                
                logger.info(f"Пользователь {username} добавлен в список разрешенных")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    def remove_allowed_user(self, username: str) -> bool:
        """
        Удаление пользователя из списка разрешенных.
        
        Args:
            username: Логин пользователя
            
        Returns:
            True при успешном удалении
        """
        try:
            users = self.get_allowed_users()
            username_lower = username.lower()
            
            if username_lower in users:
                users.remove(username_lower)
                
                with open(self.users_file, 'w', encoding='utf-8') as f:
                    json.dump({"allowed_users": users}, f, ensure_ascii=False, indent=4)
                
                logger.info(f"Пользователь {username} удален из списка разрешенных")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя: {e}")
            return False
    
    def encrypt_data(self, data: str) -> str:
        """
        Шифрование данных.
        
        Args:
            data: Строка для шифрования
            
        Returns:
            Зашифрованная строка
        """
        try:
            return self.cipher.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            raise
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Расшифровка данных.
        
        Args:
            encrypted_data: Зашифрованная строка
            
        Returns:
            Расшифрованная строка
        """
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка расшифровки: {e}")
            raise
    
    def get_printer_config_path(self) -> Path:
        """Получение пути к файлу конфигурации принтеров."""
        return self.get_resource_path("test_images/printers.json")
    
    def load_printer_config(self) -> List[Dict[str, str]]:
        """
        Загрузка конфигурации принтеров.
        
        Returns:
            Список принтеров
        """
        printer_file = self.get_printer_config_path()
        
        if not printer_file.exists():
            logger.warning("Файл конфигурации принтеров не найден")
            return []
        
        try:
            with open(printer_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации принтеров: {e}")
            return []