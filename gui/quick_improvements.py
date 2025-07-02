# quick_improvements.py
"""
Патч с быстрыми улучшениями для RDP Manager.
Добавляет полезные функции без изменения основной структуры.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import subprocess
import datetime
import csv

def add_session_controls_to_tab(tab_frame):
    """Добавляет дополнительные элементы управления сессиями."""
    
    # Фрейм для дополнительных кнопок
    extra_controls = ctk.CTkFrame(tab_frame, fg_color="transparent")
    extra_controls.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    
    # Кнопка отключения всех сессий
    disconnect_all_btn = ctk.CTkButton(
        extra_controls,
        text="⚠️ Отключить все",
        command=lambda: disconnect_all_sessions(tab_frame),
        width=120,
        fg_color="darkred",
        hover_color="red"
    )
    disconnect_all_btn.pack(side="left", padx=(0, 5))
    
    # Кнопка экспорта сессий
    export_sessions_btn = ctk.CTkButton(
        extra_controls,
        text="📤 Экспорт",
        command=lambda: export_sessions(tab_frame),
        width=100
    )
    export_sessions_btn.pack(side="left", padx=(0, 5))
    
    # Чекбокс автообновления
    tab_frame.auto_refresh_var = ctk.BooleanVar(value=False)
    auto_refresh_cb = ctk.CTkCheckBox(
        extra_controls,
        text="Автообновление (30 сек)",
        variable=tab_frame.auto_refresh_var,
        command=lambda: toggle_auto_refresh(tab_frame)
    )
    auto_refresh_cb.pack(side="left", padx=(10, 0))

def disconnect_all_sessions(tab_frame):
    """Отключение всех сессий на сервере."""
    server = tab_frame.server_entry.get()
    if not server:
        messagebox.showerror("Ошибка", "Введите имя сервера")
        return
    
    # Подсчет сессий
    session_count = len(tab_frame.tree.get_children())
    if session_count == 0:
        messagebox.showinfo("Информация", "Нет активных сессий")
        return
    
    # Подтверждение
    confirm = messagebox.askyesno(
        "Подтверждение", 
        f"Вы уверены, что хотите отключить все {session_count} сессий на сервере {server}?\n\n"
        "Это действие прервет работу всех пользователей!"
    )
    
    if not confirm:
        return
    
    # Отключение сессий
    disconnected = 0
    errors = 0
    
    for item in tab_frame.tree.get_children():
        values = tab_frame.tree.item(item, "values")
        session_id = values[2]
        username = values[1]
        
        try:
            # Пропускаем консольную сессию
            if session_id == "1" or username == "console":
                continue
                
            result = subprocess.run(
                f"logoff {session_id} /server:{server}",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                disconnected += 1
            else:
                errors += 1
                
        except Exception as e:
            errors += 1
    
    # Обновляем список
    tab_frame.refresh_sessions()
    
    # Показываем результат
    message = f"Отключено сессий: {disconnected}"
    if errors > 0:
        message += f"\nОшибок: {errors}"
    
    messagebox.showinfo("Результат", message)

def export_sessions(tab_frame):
    """Экспорт списка сессий в CSV файл."""
    server = tab_frame.server_entry.get()
    
    # Выбор файла
    filename = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
        initialfile=f"sessions_{server}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    
    if not filename:
        return
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            
            # Заголовок
            writer.writerow(["Сервер", "Имя сессии", "Пользователь", "ID сессии", "Статус", "Время экспорта"])
            
            # Данные
            export_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in tab_frame.tree.get_children():
                values = list(tab_frame.tree.item(item, "values"))
                row = [server] + values + [export_time]
                writer.writerow(row)
        
        messagebox.showinfo("Успех", f"Сессии экспортированы в:\n{filename}")
        
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось экспортировать сессии:\n{e}")

def toggle_auto_refresh(tab_frame):
    """Включение/выключение автообновления."""
    if tab_frame.auto_refresh_var.get():
        # Включаем автообновление
        start_auto_refresh(tab_frame)
    else:
        # Выключаем автообновление
        stop_auto_refresh(tab_frame)

def start_auto_refresh(tab_frame):
    """Запуск автообновления."""
    def auto_refresh():
        if hasattr(tab_frame, '_auto_refresh_job') and tab_frame.auto_refresh_var.get():
            tab_frame.refresh_sessions()
            tab_frame._auto_refresh_job = tab_frame.after(30000, auto_refresh)  # 30 секунд
    
    # Первое обновление через 1 секунду
    tab_frame._auto_refresh_job = tab_frame.after(1000, auto_refresh)

def stop_auto_refresh(tab_frame):
    """Остановка автообновления."""
    if hasattr(tab_frame, '_auto_refresh_job'):
        tab_frame.after_cancel(tab_frame._auto_refresh_job)
        delattr(tab_frame, '_auto_refresh_job')

def add_group_controls(tab_frame):
    """Добавляет дополнительные элементы управления группами."""
    
    # Фрейм для кнопок групп
    group_controls = ctk.CTkFrame(tab_frame, fg_color="transparent")
    group_controls.grid(row=3, column=3, padx=5, pady=5, sticky="w")
    
    # Кнопка экспорта групп
    export_groups_btn = ctk.CTkButton(
        group_controls,
        text="📤 Экспорт групп",
        command=lambda: export_groups(tab_frame),
        width=120
    )
    export_groups_btn.pack(side="left", padx=(0, 5))
    
    # Кнопка копирования всех групп
    copy_all_groups_btn = ctk.CTkButton(
        group_controls,
        text="📋 Копировать все",
        command=lambda: copy_all_groups(tab_frame),
        width=120
    )
    copy_all_groups_btn.pack(side="left")

def export_groups(tab_frame):
    """Экспорт групп пользователя."""
    user = tab_frame.group_search_entry.get()
    if not user:
        messagebox.showwarning("Предупреждение", "Сначала выполните поиск пользователя")
        return
    
    # Выбор файла
    filename = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Текстовые файлы", "*.txt"), ("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
        initialfile=f"groups_{user}_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
    )
    
    if not filename:
        return
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Группы пользователя: {user}\n")
            f.write(f"Домен: {tab_frame.combobox_domain.get()}\n")
            f.write(f"Дата: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 50 + "\n\n")
            
            groups = []
            for item in tab_frame.group_tree.get_children():
                group = tab_frame.group_tree.item(item, "values")[0]
                groups.append(group)
                f.write(f"{group}\n")
            
            f.write(f"\n\nВсего групп: {len(groups)}")
        
        messagebox.showinfo("Успех", f"Группы экспортированы в:\n{filename}")
        
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось экспортировать группы:\n{e}")

def copy_all_groups(tab_frame):
    """Копирование всех групп в буфер обмена."""
    groups = []
    for item in tab_frame.group_tree.get_children():
        group = tab_frame.group_tree.item(item, "values")[0]
        groups.append(group)
    
    if not groups:
        messagebox.showinfo("Информация", "Нет групп для копирования")
        return
    
    # Формируем текст
    text = "\n".join(groups)
    
    # Копируем в буфер
    tab_frame.clipboard_clear()
    tab_frame.clipboard_append(text)
    tab_frame.update()
    
    messagebox.showinfo("Успех", f"Скопировано групп: {len(groups)}")

def add_search_to_sessions(tab_frame):
    """Добавляет поиск в таблицу сессий."""
    
    # Поле поиска
    search_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
    search_frame.grid(row=0, column=2, padx=5, pady=5, sticky="e")
    
    search_label = ctk.CTkLabel(search_frame, text="Поиск:")
    search_label.pack(side="left", padx=(0, 5))
    
    search_entry = ctk.CTkEntry(search_frame, width=150, placeholder_text="Имя или ID...")
    search_entry.pack(side="left")
    search_entry.bind("<KeyRelease>", lambda e: filter_sessions(tab_frame, search_entry.get()))
    
    # Сохраняем ссылку
    tab_frame.session_search_entry = search_entry

def filter_sessions(tab_frame, search_text):
    """Фильтрация сессий по тексту."""
    # Сброс тегов
    for item in tab_frame.tree.get_children():
        tab_frame.tree.item(item, tags=())
    
    if not search_text:
        return
    
    # Поиск и выделение
    search_lower = search_text.lower()
    found_items = []
    
    for item in tab_frame.tree.get_children():
        values = tab_frame.tree.item(item, "values")
        if any(search_lower in str(v).lower() for v in values):
            tab_frame.tree.item(item, tags=('found',))
            found_items.append(item)
        else:
            tab_frame.tree.item(item, tags=('notfound',))
    
    # Настройка тегов
    tab_frame.tree.tag_configure('found', background='#1a472a')
    tab_frame.tree.tag_configure('notfound', foreground='gray50')
    
    # Прокрутка к первому найденному
    if found_items:
        tab_frame.tree.see(found_items[0])
        tab_frame.tree.selection_set(found_items[0])

def add_printer_ping(tab_frame):
    """Добавляет функцию пинга принтера."""
    
    def ping_printer():
        selected = tab_frame.printer_manager.tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите принтер")
            return
        
        ip = tab_frame.printer_manager.tree.item(selected[0], "values")[1]
        
        try:
            result = subprocess.run(
                f"ping -n 1 -w 1000 {ip}",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if "TTL=" in result.stdout:
                messagebox.showinfo("Ping", f"Принтер {ip} доступен!")
            else:
                messagebox.showwarning("Ping", f"Принтер {ip} не отвечает")
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось выполнить ping:\n{e}")
    
    # Добавляем пункт в контекстное меню
    tab_frame.context_menu.add_separator()
    tab_frame.context_menu.add_command(label="Ping принтер", command=ping_printer)

# Функция применения всех улучшений
def apply_improvements_to_tab(tab_frame):
    """Применяет все улучшения к вкладке."""
    add_session_controls_to_tab(tab_frame)
    add_group_controls(tab_frame)
    add_search_to_sessions(tab_frame)
    add_printer_ping(tab_frame)

# Для использования:
# 1. Импортируйте этот файл в home_frame.py
# 2. Вызовите apply_improvements_to_tab(self) в конце __init__ класса TabHomeFrame