import os
import sys
import logging
from pathlib import Path
from app import App
from utils.auth import check_user_permission
from utils.config import ConfigManager

# Настройка логирования с ротацией
from logging.handlers import RotatingFileHandler

# Создаем директорию для логов
log_dir = Path(os.getenv("APPDATA")) / "RDPManager" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# Настройка логирования с ротацией файлов
log_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Файловый обработчик с ротацией
file_handler = RotatingFileHandler(
    log_dir / "rdp_manager.log",
    maxBytes=5*1024*1024,  # 5MB
    backupCount=3
)
file_handler.setFormatter(log_formatter)

# Консольный обработчик
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

# Корневой логгер
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)  # Изменено с DEBUG на INFO для продакшена
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

def main():
    """Главная функция запуска приложения."""
    try:
        # Загружаем конфигурацию пользователей из файла
        config_manager = ConfigManager()
        allowed_users = config_manager.get_allowed_users()
        
        # Получаем текущего пользователя
        current_username = os.getenv("USERNAME", "").lower()
        
        logger.info(f"Запуск приложения пользователем: {current_username}")
        
        # Проверка прав доступа
        if not check_user_permission(current_username, allowed_users):
            logger.error(f"Пользователь {current_username} не имеет доступа к приложению")
            sys.exit(1)
        
        # Запуск приложения
        logger.info("Инициализация приложения RDP Manager")
        app = App()
        
        # Регистрируем обработчик закрытия
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # Запуск главного цикла
        logger.info("Запуск главного цикла приложения")
        app.mainloop()
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()