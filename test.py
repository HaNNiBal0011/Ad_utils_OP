import os
import getpass  # Добавлен импорт модуля getpass
from ldap3 import Server, Connection, ALL, NTLM

def get_ad_user_info(server_address, domain):
    # Получаем имя текущего пользователя
    username = getpass.getuser()
    # Запрашиваем пароль у пользователя
    password = getpass.getpass(f"Введите пароль для {username}: ")
    
    # Создаем подключение с введенными учетными данными
    server = Server(server_address, get_info=ALL)
    conn = Connection(
        server,
        user=f'{domain}\\{username}',
        password=password,
        authentication=NTLM,
        auto_bind=True
    )
    
    search_base = f"DC={domain.replace('.', ',DC=')}"
    search_filter = f"(sAMAccountName={username})"
    attributes = ['cn', 'msDS-UserPasswordExpiryTimeComputed']
    
    conn.search(search_base, search_filter, attributes=attributes)
    
    if conn.entries:
        entry = conn.entries[0]
        name = entry.cn.value
        
        # Проверка на истечение пароля
        password_expiry_timestamp = int(entry['msDS-UserPasswordExpiryTimeComputed'].value) if entry['msDS-UserPasswordExpiryTimeComputed'].value else 0
        password_expired = password_expiry_timestamp == 0
        
        return {"Name": name, "PasswordExpired": password_expired}
    else:
        return None

# Пример использования
try:
    server_address = 'corp.local'
    domain = 'corp.local'
    
    user_info = get_ad_user_info(server_address, domain)
    if user_info:
        print(f"Имя: {user_info['Name']}")
        print(f"Пароль истек: {user_info['PasswordExpired']}")
    else:
        print("Пользователь не найден")
except Exception as e:
    print(f"Произошла ошибка: {str(e)}")