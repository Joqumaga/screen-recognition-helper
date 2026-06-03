# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller 构建配置 — 屏幕识别点击助手（单文件模式）
#
# 用法:
#   pyinstaller build.spec
#   或双击 build.bat（推荐）
#
# 注意:
#   运行 exe 前需要安装 Tesseract OCR
#   winget install "UB-Mannheim.TesseractOCR"

import sys
from pathlib import Path

ROOT = Path.cwd()

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pytesseract",
        "pyautogui",
        "customtkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "unittest", "pdb", "http.server"],
    noarchive=False,
)

# 自动收集 NumPy、OpenCV、PIL、mss 的全部扩展模块
from PyInstaller.utils.hooks import collect_all

for pkg in ("numpy", "cv2", "PIL", "mss"):
    hi, bi, da = collect_all(pkg)
    a.binaries += bi
    a.datas += da
    a.hiddenimports += hi

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="屏幕识别点击助手",
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
    icon=None,
)
