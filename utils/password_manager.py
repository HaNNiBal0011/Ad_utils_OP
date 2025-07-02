# utils/password_manager.py
import logging
import winreg
import win32cred
import pywintypes
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from typing import Optional

logger = logging.getLogger(__name__)

class PasswordManager:
    """Менеджер для безопасного хранения паролей."""
    
    def __init__(self):
        """Инициализация менеджера паролей."""
        # Генерируем ключ шифрования на основе уникальных данных системы
        self.cipher = self._create_cipher()
        
        # Константы для Credential Manager
        self.CRED_NAME = "RDPManager_ADPassword"
        self.CRED_TYPE = win32cred.CRED_TYPE_GENERIC
        
        # Константы для реестра
        self.REG_PATH = r"Software\RDPManager"
        self.REG_KEY = "ADPassword"
    
    def _create_cipher(self) -> Fernet:
        """Создание шифровщика с динамическим ключом."""
        # Используем комбинацию системных параметров для генерации ключа
        try:
            # Получаем уникальные данные системы
            username = os.getenv("USERNAME", "default")
            computername = os.getenv("COMPUTERNAME", "default")
            
            # Создаем соль на основе системных данных
            salt = f"{username}:{computername}:RDPManager".encode()
            
            # Генерируем ключ с помощью PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            # Базовый ключ (в продакшене должен храниться безопасно)
            base_key = b'RDPManager_Base_Key_2024'
            key = base64.urlsafe_b64encode(kdf.derive(base_key))
            
            return Fernet(key)
            
        except Exception as e:
            logger.error(f"Ошибка создания шифровщика: {e}")
            # Fallback к статическому ключу
            static_key = base64.urlsafe_b64encode(b'k9_jL-pXqWvR2mT5bYxN8cF4aZ0eH6uQ')
            return Fernet(static_key)
    
    def save_password(self, password: str, method: str) -> bool:
        """
        Сохранение пароля выбранным методом.
        
        Args:
            password: Пароль для сохранения
            method: Метод хранения ("Credential Manager" или "Реестр (зашифрованный)")
            
        Returns:
            True при успешном сохранении
        """
        if not password:
            logger.warning("Попытка сохранить пустой пароль")
            return False
        
        try:
            if method == "Credential Manager":
                return self._save_to_credential_manager(password)
            else:
                return self._save_to_registry(password)
        except Exception as e:
            logger.error(f"Ошибка сохранения пароля: {e}")
            return False
    
    def load_password(self, method: str) -> Optional[str]:
        """
        Загрузка пароля выбранным методом.
        
        Args:
            method: Метод хранения
            
        Returns:
            Пароль или None
        """
        try:
            if method == "Credential Manager":
                return self._load_from_credential_manager()
            else:
                return self._load_from_registry()
        except Exception as e:
            logger.error(f"Ошибка загрузки пароля: {e}")
            return None
    
    def clear_password(self, method: str) -> bool:
        """
        Удаление пароля выбранным методом.
        
        Args:
            method: Метод хранения
            
        Returns:
            True при успешном удалении
        """
        try:
            if method == "Credential Manager":
                return self._clear_from_credential_manager()
            else:
                return self._clear_from_registry()
        except Exception as e:
            logger.error(f"Ошибка удаления пароля: {e}")
            return False
    
    def _save_to_credential_manager(self, password: str) -> bool:
        """Сохранение пароля в Credential Manager."""
        try:
            creds = {
                "Type": self.CRED_TYPE,
                "TargetName": self.CRED_NAME,
                "UserName": os.getenv("USERNAME", "User"),
                "CredentialBlob": password,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                "Comment": "Пароль для подключения к Active Directory в RDP Manager"
            }
            
            win32cred.CredWrite(creds, 0)
            logger.info("Пароль сохранён в Credential Manager")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в Credential Manager: {e}")
            return False
    
    def _load_from_credential_manager(self) -> Optional[str]:
        """Загрузка пароля из Credential Manager."""
        try:
            creds = win32cred.CredRead(self.CRED_NAME, self.CRED_TYPE)
            password = creds["CredentialBlob"]
            
            # Преобразование если необходимо
            if isinstance(password, bytes):
                password = password.decode('utf-16-le')
            
            logger.debug("Пароль загружен из Credential Manager")
            return password
            
        except pywintypes.error as e:
            if e.winerror == 1168:  # ERROR_NOT_FOUND
                logger.debug("Пароль в Credential Manager не найден")
            else:
                logger.error(f"Ошибка загрузки из Credential Manager: {e}")
            return None
    
    def _clear_from_credential_manager(self) -> bool:
        """Удаление пароля из Credential Manager."""
        try:
            win32cred.CredDelete(self.CRED_NAME, self.CRED_TYPE)
            logger.info("Пароль удалён из Credential Manager")
            return True
            
        except pywintypes.error as e:
            if e.winerror == 1168:  # ERROR_NOT_FOUND
                logger.debug("Пароль в Credential Manager отсутствует")
                return True
            else:
                logger.error(f"Ошибка удаления из Credential Manager: {e}")
                return False
    
    def _save_to_registry(self, password: str) -> bool:
        """Сохранение зашифрованного пароля в реестре."""
        try:
            # Шифруем пароль
            encrypted_password = self.cipher.encrypt(password.encode()).decode()
            
            # Создаем/открываем ключ реестра
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.REG_PATH)
            
            # Сохраняем зашифрованный пароль
            winreg.SetValueEx(key, self.REG_KEY, 0, winreg.REG_SZ, encrypted_password)
            
            # Сохраняем метку времени
            import time
            winreg.SetValueEx(key, "LastModified", 0, winreg.REG_SZ, str(time.time()))
            
            winreg.CloseKey(key)
            logger.info("Зашифрованный пароль сохранён в реестре")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в реестр: {e}")
            return False
    
    def _load_from_registry(self) -> Optional[str]:
        """Загрузка и расшифровка пароля из реестра."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ)
            encrypted_password, _ = winreg.QueryValueEx(key, self.REG_KEY)
            winreg.CloseKey(key)
            
            # Расшифровываем пароль
            decrypted_password = self.cipher.decrypt(encrypted_password.encode()).decode()
            logger.debug("Пароль загружен и расшифрован из реестра")
            return decrypted_password
            
        except FileNotFoundError:
            logger.debug("Пароль в реестре не найден")
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки из реестра: {e}")
            return None
    
    def _clear_from_registry(self) -> bool:
        """Удаление пароля из реестра."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                self.REG_PATH, 
                0, 
                winreg.KEY_ALL_ACCESS
            )
            
            # Удаляем значение
            winreg.DeleteValue(key, self.REG_KEY)
            
            # Пытаемся удалить метку времени
            try:
                winreg.DeleteValue(key, "LastModified")
            except:
                pass
            
            winreg.CloseKey(key)
            
            # Пытаемся удалить сам ключ если он пустой
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.REG_PATH)
            except:
                pass
            
            logger.info("Пароль удалён из реестра")
            return True
            
        except FileNotFoundError:
            logger.debug("Пароль в реестре отсутствует")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления из реестра: {e}")
            return False
    
    def check_password_exists(self, method: str) -> bool:
        """
        Проверка существования сохраненного пароля.
        
        Args:
            method: Метод хранения
            
        Returns:
            True если пароль существует
        """
        return self.load_password(method) is not None
    
    def migrate_password(self, from_method: str, to_method: str) -> bool:
        """
        Миграция пароля между методами хранения.
        
        Args:
            from_method: Исходный метод хранения
            to_method: Целевой метод хранения
            
        Returns:
            True при успешной миграции
        """
        try:
            # Загружаем пароль старым методом
            password = self.load_password(from_method)
            if not password:
                logger.warning("Нет пароля для миграции")
                return False
            
            # Сохраняем новым методом
            if self.save_password(password, to_method):
                # Удаляем старый
                self.clear_password(from_method)
                logger.info(f"Пароль мигрирован из {from_method} в {to_method}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка миграции пароля: {e}")
            return False