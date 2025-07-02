import customtkinter as ctk
from tkinter import ttk, messagebox, Menu
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM
import os
import logging
from tkinter.ttk import Notebook

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ADManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app
        self.ldap_password = None  # Храним пароль для AD

        # Основной контейнер с двумя колонками
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Левая панель (древовидная структура)
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ns")
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.treeview_left = ttk.Treeview(self.left_frame, show="tree")
        self.treeview_left.grid(row=0, column=0, sticky="nsew")
        self.treeview_left.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Правая панель (список объектов и управление)
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.right_frame.grid_rowconfigure(2, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        # Поле ввода логина и кнопка свойств
        self.login_entry = ctk.CTkEntry(self.right_frame, width=200, placeholder_text="Введите логин")
        self.login_entry.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.properties_button = ctk.CTkButton(self.right_frame, text="Свойства", command=self.show_user_properties)
        self.properties_button.grid(row=0, column=0, padx=(210, 5), pady=5, sticky="w")

        # Поле ввода и кнопки поиска
        self.search_entry = ctk.CTkEntry(self.right_frame, width=200, placeholder_text="Поиск по имени или группе")
        self.search_entry.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.search_button = ctk.CTkButton(self.right_frame, text="🔍", width=30, command=self.search_ad_objects)
        self.search_button.grid(row=1, column=0, padx=(210, 5), pady=5, sticky="w")
        self.refresh_button = ctk.CTkButton(self.right_frame, text="Обновить", command=self.refresh_ad_objects)
        self.refresh_button.grid(row=1, column=0, padx=(250, 5), pady=5, sticky="w")

        # Treeview для объектов
        self.ad_tree = ttk.Treeview(self.right_frame, columns=("Name", "Type", "DN"), show="headings", height=15)
        self.ad_tree.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
        self.setup_treeview()

        # Контекстное меню
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Редактировать", command=self.edit_selected_object)
        self.context_menu.add_command(label="Удалить", command=self.delete_selected_object)
        self.ad_tree.bind("<Button-3>", self.show_context_menu)
        self.ad_tree.bind("<Double-1>", self.edit_selected_object)

        self.update_treeview_style(ctk.get_appearance_mode())
        # Не вызываем load_ad_structure здесь, перенесём в refresh_ad_objects

    def setup_treeview(self):
        self.ad_tree.heading("Name", text="Имя")
        self.ad_tree.heading("Type", text="Тип")
        self.ad_tree.heading("DN", text="DN")
        self.ad_tree.column("Name", width=200, stretch=True)
        self.ad_tree.column("Type", width=100, stretch=True)
        self.ad_tree.column("DN", width=300, stretch=True)

    def update_treeview_style(self, appearance_mode):
        style = ttk.Style()
        style.theme_use("clam")
        if appearance_mode == "Dark":
            style.configure("Treeview", background="#2e2e2e", foreground="white", fieldbackground="#2e2e2e")
            style.configure("Treeview.Heading", background="#3c3c3c", foreground="white")
            style.map("Treeview", background=[('selected', '#5f5f5f')])
        else:
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
            style.configure("Treeview.Heading", background="lightgray", foreground="black")
            style.map("Treeview", background=[('selected', '#cfcfcf')])
        self.ad_tree.configure(style="Treeview")
        self.treeview_left.configure(style="Treeview")

    def get_ldap_connection(self):
        """Получает соединение с AD, используя пароль, введённый после входа на Frame 2."""
        domain = "corp.local"  # Значение по умолчанию
        if hasattr(self.app, 'home_frame') and hasattr(self.app.home_frame, 'combobox_domain'):
            domain = self.app.home_frame.combobox_domain.get()

        # Проверяем, есть ли сохранённый пароль для AD
        if not self.ldap_password:
            self.request_ldap_password()  # Запрашиваем пароль для AD
            return None

        current_username = os.getlogin()
        ldap_server = f"ldap://{domain}"
        server = Server(ldap_server, get_info=ALL)
        try:
            conn = Connection(
                server,
                user=f"{domain}\\{current_username}",
                password=self.ldap_password,
                authentication=NTLM,
                auto_bind=True
            )
            return conn
        except Exception as e:
            logger.error(f"Ошибка подключения к LDAP: {e}")
            messagebox.showerror("Ошибка", f"Не удалось подключиться к AD: {e}")
            self.ldap_password = None  # Сбрасываем пароль при ошибке
            return None

    def request_ldap_password(self):
        """Создаёт окно для ввода пароля для AD."""
        password_window = ctk.CTkToplevel(self)
        password_window.title("Введите пароль для AD")
        password_window.geometry("300x150")
        password_window.transient(self)
        password_window.grab_set()

        ctk.CTkLabel(password_window, text="Введите пароль для доступа к AD:").pack(pady=10)
        password_entry = ctk.CTkEntry(password_window, show="*", width=200)
        password_entry.pack(pady=5)

        def save_password():
            self.ldap_password = password_entry.get().strip()
            password_window.destroy()
            self.refresh_ad_objects()  # Пробуем загрузить данные после ввода пароля

        ctk.CTkButton(password_window, text="Сохранить", command=save_password).pack(pady=10)
        password_entry.bind("<Return>", lambda event: save_password())

    def load_ad_structure(self):
        """Загружает иерархическую структуру AD в левую панель."""
        self.treeview_left.delete(*self.treeview_left.get_children())
        conn = self.get_ldap_connection()
        if not conn:
            return

        domain = conn.user.split('\\')[0]
        base_dn = ','.join([f"DC={part}" for part in domain.split('.')])
        root_id = self.treeview_left.insert("", "end", text=domain, open=True, tags=("domain",))

        try:
            conn.search(base_dn, '(objectClass=organizationalUnit)', SUBTREE, attributes=['distinguishedName', 'name'])
            for entry in conn.entries:
                ou_dn = entry.distinguishedName.value
                ou_name = entry.name.value
                parent_dn = ','.join(ou_dn.split(',')[1:]) if ou_dn.count(',') > 1 else base_dn
                parent_id = self.find_or_create_parent(self.treeview_left, parent_dn, domain)
                self.treeview_left.insert(parent_id, "end", text=ou_name, tags=("ou",))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить структуру AD: {e}")
            logger.error(f"Ошибка при загрузке структуры AD: {e}")
        finally:
            conn.unbind()

    def find_or_create_parent(self, tree, dn, domain):
        """Находит или создаёт родительский узел для OU."""
        if dn == ','.join([f"DC={part}" for part in domain.split('.')]):
            return ""
        parts = dn.split(',')
        for i in range(len(parts) - 1, -1, -1):
            parent_dn = ','.join(parts[i:])
            if parent_dn == ','.join([f"DC={part}" for part in domain.split('.')]):
                return ""
            for child in tree.get_children():
                if tree.item(child, "text") == parent_dn.split('=')[1].split(',')[0]:
                    return child
        return ""

    def on_tree_select(self, event):
        """Обновляет правую панель при выборе узла в левой панели."""
        selected_item = self.treeview_left.selection()
        if not selected_item:
            return
        dn = self.treeview_left.item(selected_item[0])["text"]
        self.refresh_ad_objects(dn)

    def refresh_ad_objects(self, base_dn=None):
        """Обновляет список объектов в правой панели и загружает структуру AD."""
        self.load_ad_structure()  # Загружаем структуру при первом вызове
        self.ad_tree.delete(*self.ad_tree.get_children())
        conn = self.get_ldap_connection()
        if not conn:
            return

        domain = conn.user.split('\\')[0]
        base_dn = base_dn or ','.join([f"DC={part}" for part in domain.split('.')])
        try:
            conn.search(base_dn, '(|(objectClass=user)(objectClass=group))',
                       SUBTREE, attributes=['cn', 'objectClass', 'distinguishedName'])
            for entry in conn.entries:
                name = entry.cn.value
                obj_type = "User" if "user" in entry.objectClass else "Group"
                dn = entry.distinguishedName.value
                self.ad_tree.insert("", "end", values=(name, obj_type, dn))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить объекты AD: {e}")
            logger.error(f"Ошибка при загрузке объектов AD: {e}")
        finally:
            conn.unbind()

    def search_ad_objects(self):
        search_text = self.search_entry.get().strip().lower()
        if not search_text:
            self.refresh_ad_objects()
            return

        self.ad_tree.delete(*self.ad_tree.get_children())
        conn = self.get_ldap_connection()
        if not conn:
            return

        domain = conn.user.split('\\')[0]
        base_dn = ','.join([f"DC={part}" for part in domain.split('.')])
        try:
            conn.search(base_dn, f'(|(cn=*{search_text}*)(objectClass=user)(objectClass=group))',
                       SUBTREE, attributes=['cn', 'objectClass', 'distinguishedName'])
            for entry in conn.entries:
                name = entry.cn.value
                obj_type = "User" if "user" in entry.objectClass else "Group"
                dn = entry.distinguishedName.value
                self.ad_tree.insert("", "end", values=(name, obj_type, dn))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось выполнить поиск: {e}")
            logger.error(f"Ошибка при поиске объектов AD: {e}")
        finally:
            conn.unbind()

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def edit_selected_object(self, event=None):
        selected_item = self.ad_tree.selection()
        if not selected_item:
            return
        values = self.ad_tree.item(selected_item, "values")
        name, obj_type, dn = values

        edit_window = ctk.CTkToplevel(self)
        edit_window.title(f"Редактировать {obj_type}: {name}")
        edit_window.geometry("300x150")

        ctk.CTkLabel(edit_window, text="Имя:").pack(pady=5)
        name_entry = ctk.CTkEntry(edit_window, width=200)
        name_entry.insert(0, name)
        name_entry.pack(pady=5)

        def save_changes():
            new_name = name_entry.get().strip()
            if new_name and new_name != name:
                conn = self.get_ldap_connection()
                if conn:
                    try:
                        conn.modify(dn, {'cn': [(ldap3.MODIFY_REPLACE, [new_name])]})
                        if conn.result['result'] == 0:
                            self.refresh_ad_objects()
                            messagebox.showinfo("Успех", "Объект успешно обновлён")
                        else:
                            messagebox.showerror("Ошибка", "Не удалось обновить объект")
                    except Exception as e:
                        messagebox.showerror("Ошибка", f"Ошибка при редактировании: {e}")
                        logger.error(f"Ошибка при редактировании объекта: {e}")
                    finally:
                        conn.unbind()
            edit_window.destroy()

        ctk.CTkButton(edit_window, text="Сохранить", command=save_changes).pack(pady=10)

    def delete_selected_object(self):
        selected_item = self.ad_tree.selection()
        if not selected_item:
            return
        values = self.ad_tree.item(selected_item, "values")
        name, obj_type, dn = values

        confirm = messagebox.askyesno("Подтверждение", f"Удалить {obj_type}: {name}?")
        if confirm:
            conn = self.get_ldap_connection()
            if conn:
                try:
                    conn.delete(dn)
                    if conn.result['result'] == 0:
                        self.refresh_ad_objects()
                        messagebox.showinfo("Успех", "Объект успешно удалён")
                    else:
                        messagebox.showerror("Ошибка", "Не удалось удалить объект")
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Ошибка при удалении: {e}")
                    logger.error(f"Ошибка при удалении объекта: {e}")
                finally:
                    conn.unbind()

    def show_user_properties(self):
        """Открывает окно свойств пользователя по введённому логину."""
        login = self.login_entry.get().strip()
        if not login:
            messagebox.showwarning("Предупреждение", "Введите логин пользователя")
            return

        conn = self.get_ldap_connection()
        if not conn:
            return

        domain = conn.user.split('\\')[0]
        base_dn = ','.join([f"DC={part}" for part in domain.split('.')])
        try:
            conn.search(base_dn, f'(&(objectClass=user)(sAMAccountName={login}))',
                       SUBTREE, attributes=['cn', 'displayName', 'sAMAccountName', 'mail', 'telephoneNumber',
                                          'distinguishedName', 'userPrincipalName', 'pwdLastSet', 'memberOf'])
            if not conn.entries:
                messagebox.showerror("Ошибка", f"Пользователь {login} не найден")
                return
            entry = conn.entries[0]
            self.open_properties_window(entry)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить данные пользователя: {e}")
            logger.error(f"Ошибка при получении данных пользователя: {e}")
        finally:
            conn.unbind()

    def open_properties_window(self, entry):
        """Открывает окно свойств пользователя с вкладками."""
        properties_window = ctk.CTkToplevel(self)
        properties_window.title(f"Свойства: {entry.cn.value}")
        properties_window.geometry("500x600")
        properties_window.transient(self)
        properties_window.grab_set()

        # Создаём вкладки
        notebook = Notebook(properties_window)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Вкладка "Общая"
        general_frame = ctk.CTkFrame(notebook)
        notebook.add(general_frame, text="Общая")
        ctk.CTkLabel(general_frame, text="Имя:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkLabel(general_frame, text=entry.cn.value or "").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(general_frame, text="Отображаемое имя:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkLabel(general_frame, text=entry.displayName.value if 'displayName' in entry else "").grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(general_frame, text="Логин:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkLabel(general_frame, text=entry.sAMAccountName.value or "").grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(general_frame, text="E-mail:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkLabel(general_frame, text=entry.mail.value if 'mail' in entry else "").grid(row=3, column=1, padx=5, pady=5, sticky="w")

        # Вкладка "Адрес"
        address_frame = ctk.CTkFrame(notebook)
        notebook.add(address_frame, text="Адрес")
        ctk.CTkLabel(address_frame, text="Телефон:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkLabel(address_frame, text=entry.telephoneNumber.value if 'telephoneNumber' in entry else "").grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Вкладка "Учетная запись"
        account_frame = ctk.CTkFrame(notebook)
        notebook.add(account_frame, text="Учетная запись")
        ctk.CTkLabel(account_frame, text="DN:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkLabel(account_frame, text=entry.distinguishedName.value or "").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(account_frame, text="UPN:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkLabel(account_frame, text=entry.userPrincipalName.value if 'userPrincipalName' in entry else "").grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Вкладка "Группы"
        groups_frame = ctk.CTkFrame(notebook)
        notebook.add(groups_frame, text="Группы")
        groups_tree = ttk.Treeview(groups_frame, columns=("Group"), show="headings", height=15)
        groups_tree.heading("Group", text="Группа")
        groups_tree.column("Group", width=300, stretch=True)
        groups_tree.pack(fill="both", expand=True, padx=5, pady=5)

        # Заполняем таблицу групп
        member_of = entry.memberOf.value if 'memberOf' in entry else []
        if isinstance(member_of, str):
            member_of = [member_of]
        for group_dn in member_of:
            group_name = group_dn.split(',')[0].replace('CN=', '').strip()
            groups_tree.insert("", "end", values=(group_name,))

        # Кнопка OK
        ctk.CTkButton(properties_window, text="OK", command=properties_window.destroy).pack(pady=10)