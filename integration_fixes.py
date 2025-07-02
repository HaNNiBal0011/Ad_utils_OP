# integration_fixes.py
"""
Минорные исправления для лучшей интеграции всех компонентов.
"""

import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)

def fix_password_status_colors(tab_frame):
    """Исправляет цвета статуса пароля для текущей темы."""
    
    def update_password_status_color():
        """Обновляет цвет текста в зависимости от содержимого."""
        status_text = tab_frame.password_status_entry.get()
        
        if not status_text:
            return
        
        # Определяем тему
        appearance_mode = ctk.get_appearance_mode()
        
        # Базовые цвета для разных тем
        if appearance_mode == "Dark":
            color_success = "#4ade80"  # Светло-зеленый
            color_warning = "#fb923c"  # Светло-оранжевый
            color_error = "#f87171"    # Светло-красный
            color_default = "#e5e5e5"  # Светло-серый
        else:
            color_success = "#16a34a"  # Темно-зеленый
            color_warning = "#ea580c"  # Темно-оранжевый
            color_error = "#dc2626"    # Темно-красный
            color_default = "#171717"  # Темно-серый
        
        # Применяем цвет в зависимости от статуса
        if "Истёк" in status_text or "Ошибка" in status_text:
            tab_frame.password_status_entry.configure(text_color=color_error)
        elif "Истекает" in status_text or "⚠️" in status_text:
            tab_frame.password_status_entry.configure(text_color=color_warning)
        elif "Действителен" in status_text or "не истекает" in status_text:
            tab_frame.password_status_entry.configure(text_color=color_success)
        else:
            tab_frame.password_status_entry.configure(text_color=color_default)
    
    # Привязываем обновление к изменению текста
    original_update = tab_frame.password_status_entry._textvariable.trace_add
    tab_frame.password_status_entry._textvariable.trace_add("write", lambda *args: update_password_status_color())

def add_tooltips(tab_frame):
    """Добавляет всплывающие подсказки к элементам интерфейса."""
    
    try:
        from tktooltip import ToolTip
        
        # Подсказки для основных элементов
        ToolTip(tab_frame.server_entry, msg="Введите имя сервера терминалов (например: TS-IT0)", delay=0.5)
        ToolTip(tab_frame.refresh_button, msg="Обновить список RDP сессий на сервере", delay=0.5)
        ToolTip(tab_frame.combobox_domain, msg="Выберите домен Active Directory", delay=0.5)
        ToolTip(tab_frame.password_status_entry, msg="Статус пароля выбранного пользователя", delay=0.5)
        ToolTip(tab_frame.group_search_entry, msg="Введите логин для поиска групп и проверки пароля", delay=0.5)
        ToolTip(tab_frame.search_groups_button, msg="Найти группы пользователя и проверить пароль", delay=0.5)
        
        # Подсказки для кнопок вкладок
        ToolTip(tab_frame.add_tab_button, msg="Добавить новую вкладку", delay=0.5)
        ToolTip(tab_frame.delete_tab_button, msg="Удалить текущую вкладку", delay=0.5)
        ToolTip(tab_frame.rename_tab_button, msg="Переименовать текущую вкладку", delay=0.5)
        
        logger.debug("Подсказки добавлены")
        
    except ImportError:
        logger.debug("Модуль tktooltip не установлен, подсказки пропущены")

def improve_printer_search(tab_frame):
    """Улучшает поиск принтеров - добавляет очистку и счетчик."""
    
    # Добавляем кнопку очистки в поле поиска
    def clear_search():
        tab_frame.printer_manager.search_entry.delete(0, "end")
        tab_frame.printer_manager.refresh_printers()
    
    # Создаем кнопку очистки
    clear_button = ctk.CTkButton(
        tab_frame.printer_manager.search_entry.master,
        text="✕",
        width=20,
        height=20,
        command=clear_search,
        fg_color="transparent",
        hover_color=("gray80", "gray20")
    )
    
    # Показываем/скрываем кнопку в зависимости от содержимого
    def update_clear_button(*args):
        if tab_frame.printer_manager.search_entry.get():
            clear_button.place(relx=0.95, rely=0.5, anchor="e")
        else:
            clear_button.place_forget()
    
    tab_frame.printer_manager.search_entry.bind("<KeyRelease>", update_clear_button)

def add_keyboard_shortcuts(tab_frame):
    """Добавляет горячие клавиши."""
    
    # F5 - обновить сессии
    tab_frame.bind_all("<F5>", lambda e: tab_frame.refresh_sessions())
    
    # Ctrl+F - фокус на поиск сессий (если добавлен)
    if hasattr(tab_frame, 'session_search_entry'):
        tab_frame.bind_all("<Control-f>", lambda e: tab_frame.session_search_entry.focus())
    
    # Ctrl+G - фокус на поиск групп
    tab_frame.bind_all("<Control-g>", lambda e: tab_frame.group_search_entry.focus())
    
    # Ctrl+P - фокус на поиск принтеров
    tab_frame.bind_all("<Control-p>", lambda e: tab_frame.printer_manager.search_entry.focus())
    
    # Escape - очистить выделение
    def clear_selections(event):
        tab_frame.tree.selection_remove(tab_frame.tree.selection())
        tab_frame.group_tree.selection_remove(tab_frame.group_tree.selection())
        tab_frame.printer_manager.tree.selection_remove(tab_frame.printer_manager.tree.selection())
    
    tab_frame.bind_all("<Escape>", clear_selections)

def improve_error_messages(app):
    """Улучшает сообщения об ошибках."""
    
    # Сохраняем оригинальные методы
    original_show_error = app.show_error
    original_show_warning = app.show_warning
    original_show_info = app.show_info
    
    # Улучшенные версии
    def better_show_error(title, message):
        # Добавляем время к сообщению
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Логируем ошибку
        logger.error(f"[{timestamp}] {title}: {message}")
        
        # Показываем с временем
        original_show_error(f"{title} [{timestamp}]", message)
    
    def better_show_warning(title, message):
        logger.warning(f"{title}: {message}")
        original_show_warning(title, message)
    
    def better_show_info(title, message):
        logger.info(f"{title}: {message}")
        original_show_info(title, message)
    
    # Заменяем методы
    app.show_error = better_show_error
    app.show_warning = better_show_warning
    app.show_info = better_show_info

def optimize_treeview_performance(tab_frame):
    """Оптимизирует производительность таблиц."""
    
    # Отключаем сортировку при массовых операциях
    def batch_insert(tree, items):
        """Массовая вставка элементов с отключенной сортировкой."""
        # Сохраняем состояние
        tree.configure(height=0)  # Скрываем для ускорения
        
        # Вставляем элементы
        for item in items:
            tree.insert("", "end", values=item)
        
        # Восстанавливаем
        tree.configure(height=10)
    
    # Добавляем метод к таблицам
    tab_frame.tree.batch_insert = lambda items: batch_insert(tab_frame.tree, items)
    tab_frame.group_tree.batch_insert = lambda items: batch_insert(tab_frame.group_tree, items)
    tab_frame.printer_manager.tree.batch_insert = lambda items: batch_insert(tab_frame.printer_manager.tree, items)

def add_status_bar(app):
    """Добавляет статусную строку в главное окно."""
    
    # Создаем фрейм для статусной строки
    status_frame = ctk.CTkFrame(app, height=25, corner_radius=0)
    status_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
    status_frame.grid_columnconfigure(0, weight=1)
    
    # Метка статуса
    status_label = ctk.CTkLabel(
        status_frame,
        text="Готов к работе",
        font=ctk.CTkFont(size=12),
        anchor="w"
    )
    status_label.grid(row=0, column=0, padx=10, sticky="w")
    
    # Метка времени
    time_label = ctk.CTkLabel(
        status_frame,
        text="",
        font=ctk.CTkFont(size=12),
        anchor="e"
    )
    time_label.grid(row=0, column=1, padx=10, sticky="e")
    
    # Обновление времени
    def update_time():
        from datetime import datetime
        time_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        app.after(1000, update_time)
    
    update_time()
    
    # Сохраняем ссылки
    app.status_label = status_label
    app.time_label = time_label
    
    # Метод для обновления статуса
    def set_status(text):
        app.status_label.configure(text=text)
        # Автоматический сброс через 5 секунд
        app.after(5000, lambda: app.status_label.configure(text="Готов к работе"))
    
    app.set_status = set_status

# Функция применения всех исправлений
def apply_integration_fixes(app, tab_frame):
    """Применяет все исправления интеграции."""
    try:
        fix_password_status_colors(tab_frame)
        add_tooltips(tab_frame)
        improve_printer_search(tab_frame)
        add_keyboard_shortcuts(tab_frame)
        optimize_treeview_performance(tab_frame)
        
        # Эти применяются только к главному окну
        if hasattr(app, 'show_error') and not hasattr(app, '_error_improved'):
            improve_error_messages(app)
            app._error_improved = True
        
        if not hasattr(app, 'status_label'):
            add_status_bar(app)
        
        logger.debug("Исправления интеграции применены")
        
    except Exception as e:
        logger.warning(f"Ошибка применения исправлений: {e}")

# Использование:
# В TabHomeFrame.__init__ добавьте:
# from integration_fixes import apply_integration_fixes
# apply_integration_fixes(self.app, self)