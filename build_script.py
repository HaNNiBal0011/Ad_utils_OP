# build.py
"""
Скрипт для сборки RDP Manager в исполняемый файл Windows.
Использует PyInstaller для создания standalone EXE.
"""

import os
import sys
import shutil
from pathlib import Path
import PyInstaller.__main__

def clean_build_dirs():
    """Очистка директорий от предыдущих сборок."""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Очищена директория: {dir_name}")
    
    # Удаление .spec файла
    spec_file = 'RDPManager.spec'
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"Удален файл: {spec_file}")

def check_requirements():
    """Проверка наличия необходимых файлов."""
    required_files = [
        'main.py',
        'app.py',
        'config.json',
        'gui/navigation.py',
        'gui/home_frame.py',
        'gui/settings_frame.py',
        'utils/auth.py',
        'utils/ad_utils.py',
        'utils/printer_utils.py',
        'utils/config.py',
        'utils/password_manager.py'
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

def build_exe():
    """Сборка исполняемого файла."""
    print("\n🔨 Начинаем сборку RDP Manager...\n")
    
    # Очистка старых файлов
    clean_build_dirs()
    
    # Проверка файлов
    if not check_requirements():
        print("\n❌ Сборка прервана из-за отсутствующих файлов")
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
        
        # Иконка (если есть)
        '--icon=assets/icon.ico' if os.path.exists('assets/icon.ico') else '--icon=NONE',
        
        # Версия
        f'--version-file={version_file}',
        
        # Добавление данных
        '--add-data=config.json;.',
        '--add-data=test_images;test_images',
        
        # Скрытые импорты
        '--hidden-import=win32timezone',
        '--hidden-import=win32api',
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=pkg_resources.py2_warn',
        
        # Сбор всех данных из пакетов
        '--collect-all=customtkinter',
        '--collect-all=pyad',
        
        # Исключения (уменьшение размера)
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=tkinter.test',
        
        # Оптимизация
        '--optimize=2',
    ]
    
    # Добавляем папку assets если она существует
    if os.path.exists('assets'):
        args.append('--add-data=assets;assets')
    
    print("📦 Запуск PyInstaller с параметрами:")
    for arg in args:
        if arg.startswith('--'):
            print(f"   {arg}")
    
    print("\n⏳ Это может занять несколько минут...\n")
    
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
            
            return True
        else:
            print("\n❌ Ошибка: исполняемый файл не создан")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка при сборке: {e}")
        return False

def create_installer_script():
    """Создание скрипта для Inno Setup (опционально)."""
    inno_script = """
[Setup]
AppName=RDP Manager
AppVersion=1.0.0
AppPublisher=IT Department
AppPublisherURL=http://internal.company.com
DefaultDirName={autopf}\RDPManager
DefaultGroupName=RDP Manager
UninstallDisplayIcon={app}\RDPManager.exe
Compression=lzma2
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=RDPManager_Setup

[Files]
Source: "dist\RDPManager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\RDP Manager"; Filename: "{app}\RDPManager.exe"
Name: "{group}\Удалить RDP Manager"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RDP Manager"; Filename: "{app}\RDPManager.exe"

[Run]
Filename: "{app}\RDPManager.exe"; Description: "Запустить RDP Manager"; Flags: nowait postinstall skipifsilent
"""
    
    with open('installer.iss', 'w', encoding='utf-8') as f:
        f.write(inno_script)
    
    print("\n📝 Создан скрипт для Inno Setup: installer.iss")
    print("   Используйте Inno Setup Compiler для создания установщика")

if __name__ == "__main__":
    print("=" * 50)
    print("RDP Manager - Сборка исполняемого файла")
    print("=" * 50)
    
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
        print("\n" + "=" * 50)
        print("🎉 Готово! Вы можете найти RDPManager.exe в папке 'dist'")
        print("=" * 50)
        
        # Предложение создать установщик
        response = input("\nСоздать скрипт для установщика? (y/n): ").lower()
        if response == 'y':
            create_installer_script()
    else:
        print("\n" + "=" * 50)
        print("❌ Сборка завершилась с ошибками")
        print("=" * 50)
        sys.exit(1)
