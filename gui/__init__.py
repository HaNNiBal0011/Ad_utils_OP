# gui/__init__.py
"""
GUI пакет для RDP Manager.
Содержит все модули пользовательского интерфейса.
"""

from .navigation import NavigationFrame
from .home_frame import HomeFrame, TabHomeFrame
from .settings_frame import SettingsFrame


__all__ = [
    'NavigationFrame',
    'HomeFrame',
    'TabHomeFrame',
    'SettingsFrame'
]

# Версия GUI модуля
__version__ = '1.0.0'
