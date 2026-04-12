# -*- mode: python ; coding: utf-8 -*-
#
# OllaBridge PyInstaller Spec File
# Builds a single self-contained binary — no Python installation required.
#
# Build commands:
#   Linux/macOS:  pyinstaller ollabridge.spec
#   Windows:      pyinstaller ollabridge.spec  (run in Windows)
#
# Output: dist/ollabridge  (Linux/macOS)  or  dist/ollabridge.exe  (Windows)

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['ollabridge.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Bundle the config and modules packages
        ('config',   'config'),
        ('modules',  'modules'),
    ],
    hiddenimports=[
        'ollama',
        'rich',
        'rich.console',
        'rich.panel',
        'rich.table',
        'rich.prompt',
        'rich.progress',
        'requests',
        'sqlite3',
        'configparser',
        'base64',
        'tempfile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ollabridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,              # compress binary (optional, needs upx installed)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # headless CLI — no GUI window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # add an .ico file here for Windows
)
