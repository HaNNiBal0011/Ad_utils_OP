# utils/__init__.py
"""
Утилиты для RDP Manager.
Содержит вспомогательные модули для работы с AD, принтерами, конфигурацией и т.д.
"""

from .auth import check_user_permission, auth_manager, require_auth
from .ad_utils import search_groups, check_password_ldap_with_auth, get_user_info
from .printer_utils import PrinterManager, Printer
from .config import ConfigManager
from .password_manager import PasswordManager

__all__ = [
    # Auth
    'check_user_permission',
    'auth_manager',
    'require_auth',
    
    # AD
    'search_groups',
    'check_password_ldap_with_auth',
    'get_user_info',
    
    # Printers
    'PrinterManager',
    'Printer',
    
    # Config
    'ConfigManager',
    
    # Password
    'PasswordManager'
]

# Версия utils модуля
__version__ = '1.0.0'
