# build_script.py
"""
Скрипт для сборки RDP Manager в исполняемый файл Windows.
Использует PyInstaller для создания standalone EXE.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import PyInstaller.__main__
import json

def clean_build_dirs():
    """Очистка директорий от предыдущих сборок."""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✅ Очищена директория: {dir_name}")
    
    # Удаление .spec файла
    spec_file = 'RDPManager.spec'
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"✅ Удален файл: {spec_file}")

def check_requirements():
    """Проверка наличия необходимых файлов."""
    required_files = [
        'main.py',
        'app.py',
        'config.json',
        'users.json',
        'gui/navigation.py',
        'gui/home_frame.py',
        'gui/settings_frame.py',
        'utils/auth.py',
        'utils/ad_utils.py',
        'utils/printer_utils.py',
        'utils/config.py',
        'utils/password_manager.py',
        'test_images/printers.json'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ Отсутствуют необходимые файлы:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    print("✅ Все необходимые файлы найдены")
    return True

def check_dependencies():
    """Проверка установленных зависимостей."""
    required_packages = [
        'customtkinter',
        'pyinstaller',
        'requests',
        'cryptography',
        'pywin32',
        'ldap3',
        'pillow'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Отсутствуют необходимые пакеты:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nУстановите их командой:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ Все необходимые пакеты установлены")
    return True

def create_version_file():
    """Создание файла с информацией о версии."""
    version_content = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'IT Department'),
        StringStruct(u'FileDescription', u'RDP Manager - Управление RDP сессиями'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'RDPManager'),
        StringStruct(u'LegalCopyright', u'© 2024 IT Department'),
        StringStruct(u'OriginalFilename', u'RDPManager.exe'),
        StringStruct(u'ProductName', u'RDP Manager'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    
    with open('version.txt', 'w', encoding='utf-8') as f:
        f.write(version_content)
    
    print("✅ Создан файл версии")
    return 'version.txt'

def validate_config_files():
    """Проверка корректности JSON файлов."""
    json_files = ['config.json', 'users.json', 'test_images/printers.json']
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json.load(f)
            print(f"✅ {json_file} - корректный JSON")
        except json.JSONDecodeError as e:
            print(f"❌ {json_file} - ошибка JSON: {e}")
            return False
        except FileNotFoundError:
            print(f"❌ {json_file} - файл не найден")
            return False
    
    return True

def build_exe():
    """Сборка исполняемого файла."""
    print("\n🔨 Начинаем сборку RDP Manager...\n")
    
    # Очистка старых файлов
    clean_build_dirs()
    
    # Проверка зависимостей
    if not check_dependencies():
        print("\n❌ Сборка прервана из-за отсутствующих зависимостей")
        return False
    
    # Проверка файлов
    if not check_requirements():
        print("\n❌ Сборка прервана из-за отсутствующих файлов")
        return False
    
    # Проверка JSON файлов
    if not validate_config_files():
        print("\n❌ Сборка прервана из-за некорректных JSON файлов")
        return False
    
    # Создание файла версии
    version_file = create_version_file()
    
    # Параметры для PyInstaller
    args = [
        'main.py',                           # Главный файл
        '--name=RDPManager',                 # Имя исполняемого файла
        '--onefile',                         # Один файл вместо папки
        '--windowed',                        # Без консоли
        '--clean',                           # Очистка временных файлов
        '--noconfirm',                       # Без подтверждений
        '--optimize=2',                      # Максимальная оптимизация
        
        # Иконка (если есть)
        '--icon=assets/icon.ico' if os.path.exists('assets/icon.ico') else '--icon=NONE',
        
        # Версия
        f'--version-file={version_file}',
        
        # Добавление данных - ФАЙЛЫ ВСТРОЕНЫ В EXE
        '--add-data=config.json;.',
        '--add-data=users.json;.',
        '--add-data=test_images;test_images',
        
        # Скрытые импорты для Windows
        '--hidden-import=win32timezone',
        '--hidden-import=win32api',
        '--hidden-import=win32cred',
        '--hidden-import=win32com.client',
        '--hidden-import=pywintypes',
        '--hidden-import=pythoncom',
        
        # Скрытые импорты для GUI
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=pkg_resources.py2_warn',
        '--hidden-import=tkinter.filedialog',
        '--hidden-import=tkinter.messagebox',
        
        # Скрытые импорты для сетевых библиотек
        '--hidden-import=ldap3',
        '--hidden-import=requests',
        '--hidden-import=urllib3',
        
        # Сбор всех данных из пакетов
        '--collect-all=customtkinter',
        '--collect-all=PIL',
        
        # Исключения для уменьшения размера
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=tensorflow',
        '--exclude-module=torch',
        '--exclude-module=jupyter',
        '--exclude-module=notebook',
        '--exclude-module=IPython',
        '--exclude-module=zmq',
        '--exclude-module=test',
        '--exclude-module=unittest',
        '--exclude-module=pydoc',
        '--exclude-module=doctest',
        
        # Дополнительные пути
        '--paths=.',
        '--paths=gui',
        '--paths=utils',
    ]
    
    # Добавляем папку assets если она существует
    if os.path.exists('assets'):
        args.append('--add-data=assets;assets')
    
    print("📦 Запуск PyInstaller с параметрами:")
    for arg in args:
        if arg.startswith('--'):
            print(f"   {arg}")
    
    print("\n⏳ Сборка может занять несколько минут...\n")
    
    try:
        # Запуск PyInstaller
        PyInstaller.__main__.run(args)
        
        # Проверка результата
        exe_path = Path('dist/RDPManager.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n✅ Сборка завершена успешно!")
            print(f"📄 Файл: {exe_path}")
            print(f"📊 Размер: {size_mb:.2f} МБ")
            
            # Очистка временных файлов
            if os.path.exists(version_file):
                os.remove(version_file)
            
            # Проверка запуска (опционально)
            print(f"\n🧪 Хотите протестировать запуск? (y/n): ", end="")
            test_response = input().lower()
            if test_response == 'y':
                print("🚀 Запуск тестирования...")
                try:
                    subprocess.Popen([str(exe_path)], cwd=exe_path.parent)
                    print("✅ Приложение запущено для тестирования")
                except Exception as e:
                    print(f"❌ Ошибка запуска: {e}")
            
            return True
        else:
            print("\n❌ Ошибка: исполняемый файл не создан")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка при сборке: {e}")
        return False

def create_installer_script():
    """Создание скрипта для Inno Setup (опционально)."""
    inno_script = f"""
[Setup]
AppName=RDP Manager
AppVersion=1.0.0
AppPublisher=IT Department
AppPublisherURL=http://internal.company.com
DefaultDirName={{autopf}}\\RDPManager
DefaultGroupName=RDP Manager
UninstallDisplayIcon={{app}}\\RDPManager.exe
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=RDPManager_Setup_v1.0.0
SetupIconFile=assets\\icon.ico
WizardImageFile=assets\\installer_banner.bmp
WizardSmallImageFile=assets\\installer_icon.bmp

[Files]
Source: "dist\\RDPManager.exe"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\RDP Manager"; Filename: "{{app}}\\RDPManager.exe"; WorkingDir: "{{app}}"
Name: "{{group}}\\Удалить RDP Manager"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\RDP Manager"; Filename: "{{app}}\\RDPManager.exe"; WorkingDir: "{{app}}"

[Run]
Filename: "{{app}}\\RDPManager.exe"; Description: "Запустить RDP Manager"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\\RDPManager"; ValueType: string; ValueName: "InstallPath"; ValueData: "{{app}}"
"""
    
    with open('installer.iss', 'w', encoding='utf-8') as f:
        f.write(inno_script)
    
    print("\n📝 Создан скрипт для Inno Setup: installer.iss")
    print("   Используйте Inno Setup Compiler для создания установщика")

def show_final_info():
    """Показать финальную информацию."""
    print("\n" + "=" * 60)
    print("🎉 СБОРКА RDP MANAGER ЗАВЕРШЕНА!")
    print("=" * 60)
    
    exe_path = Path('dist/RDPManager.exe')
    if exe_path.exists():
        print(f"\n📍 Расположение: {exe_path.absolute()}")
        print(f"📊 Размер: {exe_path.stat().st_size / (1024 * 1024):.2f} МБ")
        
        print(f"\n📋 Встроенные файлы:")
        print(f"   ✅ config.json")
        print(f"   ✅ users.json")
        print(f"   ✅ test_images/printers.json")
        print(f"   ✅ GUI модули")
        print(f"   ✅ Utils модули")
        
        print(f"\n🚀 Готово к развертыванию!")
        print(f"   • Просто скопируйте RDPManager.exe на целевые машины")
        print(f"   • Все конфигурации встроены в исполняемый файл")
        print(f"   • Дополнительные файлы не требуются")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    print("=" * 60)
    print("🔨 RDP MANAGER - СКРИПТ СБОРКИ")
    print("=" * 60)
    
    # Проверка наличия PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__} найден")
    except ImportError:
        print("❌ PyInstaller не установлен!")
        print("   Установите его командой: pip install pyinstaller")
        sys.exit(1)
    
    # Выполнение сборки
    if build_exe():
        show_final_info()
        
        # Предложение создать установщик
        print(f"\nСоздать скрипт для установщика? (y/n): ", end="")
        response = input().lower()
        if response == 'y':
            create_installer_script()
            
    else:
        print("\n" + "=" * 60)
        print("❌ СБОРКА ЗАВЕРШИЛАСЬ С ОШИБКАМИ")
        print("=" * 60)
        print("\n🔍 Проверьте:")
        print("   • Все файлы проекта на месте")
        print("   • Установлены все зависимости")
        print("   • JSON файлы корректны")
        print("   • Нет синтаксических ошибок в коде")
        sys.exit(1)
