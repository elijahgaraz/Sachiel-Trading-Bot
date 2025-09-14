# sachiel_trading.spec
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath(os.getcwd())],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('gui', 'gui'),
        ('trading', 'trading'),
        ('ai', 'ai'),
    ],
    hiddenimports=[
        'sklearn.ensemble',
        'sklearn.tree',
        'sklearn.preprocessing',
        'ta',
        'ta.trend',
        'ta.momentum',
        'ta.volatility',
        'ta.volume',
        'numpy',
        'pandas',
        'mplfinance',
        'alpaca',
        'alpaca.trading',
        'alpaca.data',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SachielTrading',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icon.icns' if os.path.exists('icon.icns') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SachielTrading'
)

app = BUNDLE(
    coll,
    name='SachielTrading.app',
    icon='icon.icns' if os.path.exists('icon.icns') else None,
    bundle_identifier='com.sachieltrading.app',
    info_plist={
        'CFBundleDisplayName': 'Sachiel Trading',
        'CFBundleGetInfoString': "Trading bot with AI capabilities",
        'CFBundleIdentifier': "com.sachieltrading.app",
        'CFBundleName': "Sachiel Trading",
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': 'True',
    },
)