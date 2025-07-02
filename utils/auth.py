# utils/auth.py
from tkinter import messagebox
import os
import logging
from typing import List, Optional
from functools import wraps
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AuthManager:
    """Менеджер аутентификации и авторизации."""
    
    def __init__(self):
        """Инициализация менеджера аутентификации."""
        self._session_token = None
        self._session_expiry = None
        self._current_user = None
        
    def check_user_permission(self, current_username: str, allowed_users: List[str]) -> bool:
        """
        Проверяет, есть ли у текущего пользователя разрешение на запуск приложения.
        
        Args:
            current_username: Имя текущего пользователя
            allowed_users: Список разрешенных пользователей
        
        Returns:
            bool: True если пользователь разрешен, False иначе
        """
        # Приводим к нижнему регистру для сравнения
        username_lower = current_username.lower()
        allowed_lower = [user.lower() for user in allowed_users]
        
        if username_lower not in allowed_lower:
            logger.warning(f"Попытка доступа от неавторизованного пользователя: {current_username}")
            messagebox.showerror(
                "Доступ запрещен",
                f"Пользователь '{current_username}' не имеет доступа к приложению.\n\n"
                "Обратитесь к администратору для получения доступа."
            )
            return False
        
        # Сохраняем информацию о текущем пользователе
        self._current_user = current_username
        self._create_session()
        
        logger.info(f"Успешная авторизация пользователя: {current_username}")
        return True
    
    def _create_session(self):
        """Создание сессии пользователя."""
        # Генерируем токен сессии
        session_data = f"{self._current_user}:{datetime.now().isoformat()}"
        self._session_token = hashlib.sha256(session_data.encode()).hexdigest()
        
        # Устанавливаем время истечения сессии (8 часов)
        self._session_expiry = datetime.now() + timedelta(hours=8)
        
        logger.debug(f"Создана сессия для пользователя {self._current_user}")
    
    def is_session_valid(self) -> bool:
        """Проверка валидности текущей сессии."""
        if not self._session_token or not self._session_expiry:
            return False
        
        if datetime.now() > self._session_expiry:
            logger.info("Сессия истекла")
            self._clear_session()
            return False
        
        return True
    
    def _clear_session(self):
        """Очистка данных сессии."""
        self._session_token = None
        self._session_expiry = None
        self._current_user = None
    
    def get_current_user(self) -> Optional[str]:
        """Получение имени текущего пользователя."""
        if self.is_session_valid():
            return self._current_user
        return None
    
    def extend_session(self):
        """Продление времени сессии."""
        if self.is_session_valid():
            self._session_expiry = datetime.now() + timedelta(hours=8)
            logger.debug("Сессия продлена")
    
    def logout(self):
        """Выход из системы."""
        user = self._current_user
        self._clear_session()
        logger.info(f"Пользователь {user} вышел из системы")


# Глобальный экземпляр менеджера аутентификации
auth_manager = AuthManager()


def check_user_permission(current_username: str, allowed_users: List[str]) -> bool:
    """
    Проверяет, есть ли у текущего пользователя разрешение на запуск приложения.
    
    Args:
        current_username: Имя текущего пользователя
        allowed_users: Список разрешенных пользователей
    
    Returns:
        bool: True если пользователь разрешен, False иначе
    """
    return auth_manager.check_user_permission(current_username, allowed_users)


def require_auth(func):
    """
    Декоратор для проверки авторизации перед выполнением функции.
    
    Usage:
        @require_auth
        def sensitive_function():
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not auth_manager.is_session_valid():
            logger.error(f"Попытка вызова {func.__name__} без авторизации")
            messagebox.showerror(
                "Ошибка авторизации",
                "Сессия истекла. Перезапустите приложение."
            )
            return None
        
        # Продлеваем сессию при активности
        auth_manager.extend_session()
        
        return func(*args, **kwargs)
    
    return wrapper


def get_user_home_dir() -> str:
    """
    Получение домашней директории текущего пользователя.
    
    Returns:
        Путь к домашней директории
    """
    return os.path.expanduser("~")


def get_user_documents_dir() -> str:
    """
    Получение директории документов пользователя.
    
    Returns:
        Путь к директории документов
    """
    if os.name == 'nt':  # Windows
        import winreg
        sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                documents_path = winreg.QueryValueEx(key, 'Personal')[0]
                return documents_path
        except:
            pass
    
    # Fallback
    return os.path.join(get_user_home_dir(), "Documents")


def is_admin() -> bool:
    """
    Проверка, запущено ли приложение с правами администратора.
    
    Returns:
        True если есть права администратора
    """
    if os.name == 'nt':  # Windows
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:  # Unix/Linux
        return os.getuid() == 0


def request_admin_rights():
    """Запрос прав администратора для Windows."""
    if os.name != 'nt':
        return
    
    if not is_admin():
        logger.info("Запрос прав администратора...")
        
        try:
            import sys
            import ctypes
            
            # Перезапуск с правами администратора
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                " ".join(sys.argv),
                None,
                1
            )
            sys.exit(0)
        except Exception as e:
            logger.error(f"Не удалось получить права администратора: {e}")
            messagebox.showerror(
                "Ошибка",
                "Не удалось получить права администратора.\n"
                "Некоторые функции могут быть недоступны."
            )