# rdp_manager.spec
import os

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('gui/*.py', 'gui'),
        ('utils/*.py', 'utils'),
        ('test_images/*', 'test_images'),
        ('config.json', '.'),  # Добавляем config.json в корень сборки
    ],
    hiddenimports=['customtkinter', 'pyad', 'PIL', 'win32com', 'ldap3', 'pytz','win32timezone', 'win32api', 'win32security'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RDPManager',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,  # Можно установить False для скрытия консоли
    onefile=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)