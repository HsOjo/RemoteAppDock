# -*- mode: python ; coding: utf-8 -*-

import glob
import os


project_root = os.path.abspath(os.path.dirname(SPECPATH))
i18n_files = glob.glob(os.path.join(project_root, 'remoteappdock', 'i18n', '*.qm'))
datas = [(qm, 'remoteappdock/i18n') for qm in i18n_files]


a = Analysis(
    ['remoteappdock\\main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RemoteAppDock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\app-icon.ico',
)
