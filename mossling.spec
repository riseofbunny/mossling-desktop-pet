# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: build the MosslingDesktopPet portable bundle.

Run from the repository root after exporting the assets:
    pyinstaller mossling.spec --distpath dist --workpath build/pyinstaller

Produces dist/MosslingDesktopPet/ with MosslingDesktopPet.exe, _internal/
(PySide6 + numpy runtime) and the bundled manifest.json + frames/.

⚠ The distpath must NOT be inside MosslingDesktopPet/: COLLECT wipes its
target directory.
"""
import os
from pathlib import Path

HERE = Path(SPECPATH) / 'MosslingDesktopPet'

datas = [
    (str(HERE / 'manifest.json'), '.'),
    (str(HERE / 'frames'), 'frames'),
    (str(HERE / 'start_pet.bat'), '.'),
]

a = Analysis(
    [str(HERE / 'launcher.py')],
    pathex=[str(HERE)],
    binaries=[],
    datas=datas,
    hiddenimports=['PySide6.QtSvg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MosslingDesktopPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(HERE / 'app.ico') if (HERE / 'app.ico').is_file() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MosslingDesktopPet',
)
