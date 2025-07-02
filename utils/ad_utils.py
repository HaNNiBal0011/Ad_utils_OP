# utils/ad_utils.py
import win32com.client
import os
import sys
from tkinter import messagebox
import datetime
import logging
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM
import threading
import queue
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import pythoncom



logger = logging.getLogger(__name__)

def get_resource_path(relative_path: str) -> Path:
    """Получение абсолютного пути к ресурсу."""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent
    return base_path / relative_path

class ADManager:
    """Менеджер для работы с Active Directory."""
    
    def __init__(self):
        """Инициализация AD менеджера."""
        self.connection = None
        self.domain_controllers = {
            "corp.local": ["corp.local", "corp.local"],
            "nd.lan": ["nd.lan", "nd.lan"]
        }
        
        # Кэш для хранения результатов
        self._cache = {}
        self._cache_timeout = 300  # 5 минут
    
    def _get_ldap_connection(self, domain: str, username: str, password: str) -> Optional[Connection]:
        """Создание LDAP соединения с обработкой failover."""
        controllers = self.domain_controllers.get(domain, [f"dc.{domain}"])
        
        for dc in controllers:
            try:
                server = Server(f"ldap://{dc}", get_info=ALL)
                conn = Connection(
                    server,
                    user=f"{domain}\\{username}",
                    password=password,
                    authentication=NTLM,
                    auto_bind=True,
                    raise_exceptions=True
                )
                logger.info(f"Успешное подключение к {dc}")
                return conn
            except Exception as e:
                logger.warning(f"Не удалось подключиться к {dc}: {e}")
                continue
        
        return None
    
    def close_connection(self):
        """Закрытие LDAP соединения."""
        if self.connection:
            try:
                self.connection.unbind()
            except:
                pass
            self.connection = None

def search_groups(home_frame, app):
    """Асинхронный поиск групп пользователя."""
    user_login = home_frame.group_search_entry.get().strip()
    domain = home_frame.combobox_domain.get()
    
    if not user_login:
        app.show_warning("Предупреждение", "Введите логин пользователя")
        return
    
    # Очищаем таблицу
    for item in home_frame.group_tree.get_children():
        home_frame.group_tree.delete(item)
    
    # Показываем индикатор загрузки через изменение placeholder
    original_placeholder = home_frame.group_search_entry.cget("placeholder_text")
    home_frame.group_search_entry.configure(placeholder_text="Поиск групп...")
    
    def worker():
        """Рабочая функция для выполнения в отдельном потоке."""
        try:
            groups = _search_groups_sync(user_login, domain)
            
            # Обновляем UI в главном потоке
            home_frame.async_queue.put(
                lambda: _update_groups_tree(home_frame, groups)
            )
            
            # Восстанавливаем placeholder
            home_frame.async_queue.put(
                lambda: home_frame.group_search_entry.configure(placeholder_text=original_placeholder)
            )
            
        except Exception as e:
            error_msg = str(e)
            home_frame.async_queue.put(
                lambda: _handle_groups_error(home_frame, app, error_msg)
            )
            # Восстанавливаем placeholder
            home_frame.async_queue.put(
                lambda: home_frame.group_search_entry.configure(placeholder_text=original_placeholder)
            )
    
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

def _search_groups_sync(user_login: str, domain: str) -> List[str]:
    """Синхронный поиск групп пользователя."""
    groups = []
    
    try:
        # Sanitize user_login to escape special characters
        user_login = user_login.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').replace('*', '\\*')
        logger.debug(f"Searching groups for user: {user_login}, domain: {domain}")
        
        # Initialize COM for the thread
        pythoncom.CoInitialize()
        
        # Bind to RootDSE
        logger.debug(f"Attempting to bind to LDAP://{domain}/RootDSE")
        try:
            obj_root = win32com.client.GetObject(f'LDAP://{domain}/RootDSE')
        except Exception as e:
            logger.error(f"Failed to bind to LDAP://{domain}/RootDSE: {e}")
            raise Exception(f"Cannot connect to LDAP://{domain}/RootDSE: {e}")
        
        # Get defaultNamingContext
        logger.debug("Retrieving defaultNamingContext")
        try:
            naming_context = obj_root.Get('defaultNamingContext')
            logger.debug(f"naming_context: {naming_context}")
        except Exception as e:
            logger.error(f"Failed to get defaultNamingContext: {e}")
            raise Exception(f"Cannot retrieve defaultNamingContext: {e}")
        
        # Initialize COM objects
        logger.debug("Initializing ADODB.Connection")
        try:
            connection = win32com.client.Dispatch('ADODB.Connection')
        except Exception as e:
            logger.error(f"Failed to dispatch ADODB.Connection: {e}")
            raise Exception(f"Cannot initialize ADODB.Connection: {e}")
        
        logger.debug("Initializing ADODB.Recordset")
        try:
            recordset = win32com.client.Dispatch('ADODB.Recordset')
        except Exception as e:
            logger.error(f"Failed to dispatch ADODB.Recordset: {e}")
            raise Exception(f"Cannot initialize ADODB.Recordset: {e}")
        
        # Set up connection
        logger.debug("Setting up ADsDSOObject provider")
        try:
            connection.Provider = 'ADsDSOObject'
            connection.Open("Active Directory Provider")
        except Exception as e:
            logger.error(f"Failed to open ADODB connection: {e}")
            raise Exception(f"Cannot open ADODB connection: {e}")
        
        # Construct LDAP query
        query = (
            f"<LDAP://{domain}/{naming_context}>;"
            f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={user_login}));"
            f"distinguishedName,memberOf,displayName,mail;"
            f"subtree"
        )
        logger.debug(f"Executing LDAP query: {query}")
        
        # Execute query
        try:
            recordset.Open(query, connection, 1, 3)
        except Exception as e:
            logger.error(f"Failed to execute LDAP query: {e}")
            raise Exception(f"LDAP query failed: {e}")
        
        if not recordset.EOF:
            member_of = recordset.Fields['memberOf'].Value
            
            if member_of:
                group_list = list(member_of) if isinstance(member_of, tuple) else [member_of]
                for group_dn in group_list:
                    if group_dn and "CN=" in group_dn:
                        group_name = group_dn.split(',')[0].replace('CN=', '').strip()
                        groups.append(group_name)
        
        recordset.Close()
        connection.Close()
        
    except Exception as e:
        logger.error(f"Ошибка поиска групп: {e}", exc_info=True)
        raise Exception(f"Не удалось выполнить поиск групп: {e}")
    
    finally:
        # Clean up COM
        try:
            if 'connection' in locals():
                connection.Close()
        except:
            pass
        pythoncom.CoUninitialize()
    
    return sorted(groups)

def _update_groups_tree(home_frame, groups: List[str]):
    """Обновление таблицы групп."""
    # Очищаем таблицу
    for item in home_frame.group_tree.get_children():
        home_frame.group_tree.delete(item)
    
    if not groups:
        home_frame.group_tree.insert("", "end", values=("Пользователь не состоит в группах",))
    else:
        # Добавляем группы с выделением важных
        for group in groups:
            tags = []
            # Выделяем группы с доступом к серверам
            if "TS-" in group:
                tags.append("server_group")
            elif "Admin" in group or "Администратор" in group:
                tags.append("admin_group")
            
            home_frame.group_tree.insert("", "end", values=(group,), tags=tags)
        
        # Настройка тегов для выделения
        home_frame.group_tree.tag_configure("server_group", foreground="#00a000")
        home_frame.group_tree.tag_configure("admin_group", foreground="#ff6600")
    
    logger.info(f"Найдено {len(groups)} групп для пользователя")

def _handle_groups_error(home_frame, app, error_msg: str):
    """Обработка ошибок поиска групп."""
    # Очищаем таблицу
    for item in home_frame.group_tree.get_children():
        home_frame.group_tree.delete(item)
    
    # Показываем ошибку через messagebox, а не в таблице
    app.show_error("Ошибка", f"Не удалось найти группы: {error_msg}")

def check_password_ldap_with_auth(home_frame, app):
    """Асинхронная проверка статуса пароля пользователя."""
    target_user_login = home_frame.group_search_entry.get().strip()
    domain = home_frame.combobox_domain.get()
    status_entry = home_frame.password_status_entry
    
    if not target_user_login:
        _update_password_status(status_entry, "Введите логин пользователя для проверки")
        return
    
    # Показываем статус загрузки
    _update_password_status(status_entry, "Проверка пароля...")
    
    def worker():
        """Рабочая функция для выполнения в отдельном потоке."""
        try:
            # Получаем главное приложение через parent
            main_app = home_frame.app
            
            status = _check_password_sync(target_user_login, domain, main_app)
            
            # Обновляем UI в главном потоке
            home_frame.async_queue.put(
                lambda: _update_password_status(status_entry, status)
            )
            
        except Exception as e:
            error_msg = f"Ошибка проверки: {str(e)}"
            logger.error(f"Ошибка в check_password_ldap_with_auth: {e}", exc_info=True)
            home_frame.async_queue.put(
                lambda: _update_password_status(status_entry, error_msg)
            )
    
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

def _check_password_sync(target_user_login: str, domain: str, app) -> str:
    """Синхронная проверка статуса пароля."""
    try:
        # Получаем текущего пользователя
        current_username = os.getlogin()
        logger.debug(f"Проверка пароля для {target_user_login} от имени {current_username}")
        
        # Получаем сохраненный пароль
        if not hasattr(app, 'settings_frame') or not hasattr(app.settings_frame, 'password_entry'):
            logger.error("settings_frame или password_entry не найдены")
            return "Ошибка: Настройки недоступны"
        
        saved_password = app.settings_frame.password_entry.get().strip()
        logger.debug(f"Длина сохраненного пароля: {len(saved_password) if saved_password else 0}")
        
        if not saved_password:
            # Пытаемся загрузить пароль из хранилища
            logger.debug("Пароль не введен, пытаемся загрузить из хранилища")
            app.settings_frame.load_password()
            saved_password = app.settings_frame.password_entry.get().strip()
            
            if not saved_password:
                return "Введите пароль в настройках"
        
        # Подключаемся к AD
        ad_manager = ADManager()
        conn = ad_manager._get_ldap_connection(domain, current_username, saved_password)
        
        if not conn:
            logger.error("Не удалось создать подключение к AD")
            return "Ошибка подключения к AD (проверьте пароль)"
        
        try:
            # Базовый DN
            base_dn = f"DC={domain.split('.')[0]},DC={domain.split('.')[1]}"
            logger.debug(f"Base DN: {base_dn}")
            
            # Поиск пользователя
            search_filter = f"(&(objectClass=user)(sAMAccountName={target_user_login}))"
            logger.debug(f"Search filter: {search_filter}")
            
            conn.search(
                base_dn,
                search_filter,
                SUBTREE,
                attributes=['displayName', 'userAccountControl', 'pwdLastSet', 'accountExpires', 'distinguishedName']
            )
            
            if not conn.entries:
                logger.warning(f"Пользователь {target_user_login} не найден в домене {domain}")
                return f"Пользователь {target_user_login} не найден"
            
            entry = conn.entries[0]
            logger.debug(f"Найден пользователь: {entry.distinguishedName}")
            
            # Получаем имя пользователя
            display_name = entry.displayName.value if hasattr(entry, 'displayName') and entry.displayName.value else target_user_login
            
            # Проверяем флаги учетной записи
            uac = int(entry.userAccountControl.value) if hasattr(entry, 'userAccountControl') else 0
            logger.debug(f"userAccountControl: {uac}")
            
            # Проверка различных состояний
            if uac & 0x2:  # ACCOUNTDISABLE
                return f"{display_name}: Учетная запись отключена"
            
            if uac & 0x10:  # LOCKOUT
                return f"{display_name}: Учетная запись заблокирована"
            
            if uac & 0x10000:  # DONT_EXPIRE_PASSWD
                return f"{display_name}: Пароль не истекает"
            
            # Проверяем срок действия пароля
            pwd_last_set = entry.pwdLastSet.value if hasattr(entry, 'pwdLastSet') else None
            logger.debug(f"pwdLastSet: {pwd_last_set}")
            
            if not pwd_last_set or str(pwd_last_set) == '0':
                return f"{display_name}: Требуется смена пароля"
            
            # Преобразуем время
            if isinstance(pwd_last_set, datetime.datetime):
                last_set_date = pwd_last_set.replace(tzinfo=None)
            else:
                # Windows FILETIME to datetime
                try:
                    filetime = int(pwd_last_set)
                    last_set_date = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=filetime // 10)
                except Exception as e:
                    logger.error(f"Ошибка преобразования pwdLastSet: {e}")
                    return f"{display_name}: Ошибка определения даты пароля"
            
            logger.debug(f"Пароль установлен: {last_set_date}")
            
            # Получаем политику паролей
            max_pwd_age = _get_max_password_age(conn, base_dn, domain)
            logger.debug(f"Максимальный возраст пароля: {max_pwd_age}")
            
            # Вычисляем срок истечения
            expiration_date = last_set_date + max_pwd_age
            current_date = datetime.datetime.now()
            
            # Определяем статус
            if current_date > expiration_date:
                days_expired = (current_date - expiration_date).days
                return f"{display_name}: Истёк {days_expired} дн. назад"
            else:
                days_remaining = (expiration_date - current_date).days
                if days_remaining <= 7:
                    return f"{display_name}: Истекает через {days_remaining} дн. ⚠️"
                else:
                    return f"{display_name}: Действителен ({days_remaining} дн.)"
            
        finally:
            ad_manager.close_connection()
            
    except Exception as e:
        logger.error(f"Ошибка проверки пароля: {e}", exc_info=True)
        return f"Ошибка: {str(e)}"

def _get_max_password_age(conn: Connection, base_dn: str, domain: str) -> datetime.timedelta:
    """Получение максимального возраста пароля из политики домена."""
    try:
        # Поиск политики домена
        conn.search(
            base_dn,
            "(objectClass=domain)",
            SUBTREE,
            attributes=['maxPwdAge']
        )
        
        if conn.entries:
            max_pwd_age_value = conn.entries[0].maxPwdAge.value
            if isinstance(max_pwd_age_value, int) and max_pwd_age_value != 0:
                # Конвертируем из 100-наносекундных интервалов
                return datetime.timedelta(microseconds=abs(max_pwd_age_value) // 10)
    except Exception as e:
        logger.warning(f"Не удалось получить maxPwdAge: {e}")
    
    # Значения по умолчанию для разных доменов
    if domain == "nd.lan":
        return datetime.timedelta(days=180)
    else:
        return datetime.timedelta(days=90)

def _update_password_status(status_entry, status: str):
    """Обновление поля статуса пароля."""
    status_entry.configure(state="normal")
    status_entry.delete(0, "end")
    status_entry.insert(0, status)
    status_entry.configure(state="readonly")
    
    # Меняем цвет в зависимости от статуса
    if "Истёк" in status or "Ошибка" in status:
        status_entry.configure(text_color="red")
    elif "Истекает" in status or "⚠️" in status:
        status_entry.configure(text_color="orange")
    elif "Действителен" in status or "не истекает" in status:
        status_entry.configure(text_color="green")
    else:
        status_entry.configure(text_color=("black", "white"))

def get_user_info(username: str, domain: str, password: str) -> Optional[Dict]:
    """
    Получение расширенной информации о пользователе.
    
    Args:
        username: Логин пользователя для поиска
        domain: Домен
        password: Пароль для аутентификации
        
    Returns:
        Словарь с информацией о пользователе или None
    """
    try:
        ad_manager = ADManager()
        conn = ad_manager._get_ldap_connection(domain, os.getlogin(), password)
        
        if not conn:
            return None
        
        try:
            base_dn = f"DC={domain.split('.')[0]},DC={domain.split('.')[1]}"
            
            # Расширенный поиск с дополнительными атрибутами
            search_filter = f"(&(objectClass=user)(sAMAccountName={username}))"
            attributes = [
                'displayName', 'mail', 'telephoneNumber', 'department',
                'title', 'manager', 'whenCreated', 'lastLogon',
                'memberOf', 'userAccountControl', 'pwdLastSet'
            ]
            
            conn.search(base_dn, search_filter, SUBTREE, attributes=attributes)
            
            if not conn.entries:
                return None
            
            entry = conn.entries[0]
            
            # Собираем информацию
            user_info = {
                'username': username,
                'displayName': entry.displayName.value if hasattr(entry, 'displayName') else username,
                'email': entry.mail.value if hasattr(entry, 'mail') else None,
                'phone': entry.telephoneNumber.value if hasattr(entry, 'telephoneNumber') else None,
                'department': entry.department.value if hasattr(entry, 'department') else None,
                'title': entry.title.value if hasattr(entry, 'title') else None,
                'created': entry.whenCreated.value if hasattr(entry, 'whenCreated') else None,
                'groups': []
            }
            
            # Обработка групп
            if hasattr(entry, 'memberOf'):
                member_of = entry.memberOf.value
                if member_of:
                    groups = list(member_of) if isinstance(member_of, tuple) else [member_of]
                    for group_dn in groups:
                        if "CN=" in group_dn:
                            group_name = group_dn.split(',')[0].replace('CN=', '')
                            user_info['groups'].append(group_name)
            
            return user_info
            
        finally:
            ad_manager.close_connection()
            
    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе: {e}")
        return None

def validate_credentials(domain: str, username: str, password: str) -> bool:
    """
    Проверка учетных данных пользователя.
    
    Args:
        domain: Домен
        username: Логин
        password: Пароль
        
    Returns:
        True если учетные данные верны
    """
    try:
        ad_manager = ADManager()
        conn = ad_manager._get_ldap_connection(domain, username, password)
        
        if conn:
            ad_manager.close_connection()
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Ошибка проверки учетных данных: {e}")
        return False