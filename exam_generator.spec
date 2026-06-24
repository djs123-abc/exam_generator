# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置
运行方式: pyinstaller exam_generator.spec
"""

import sys
import os
from pathlib import Path

block_cipher = None

SRC_DIR   = os.path.abspath('src')
DOCX_DIR  = os.path.abspath('docx_gen')

a = Analysis(
    [os.path.join(SRC_DIR, 'app.py')],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[
        # Node.js 生成脚本和依赖
        (DOCX_DIR, 'docx_gen'),
    ],
    hiddenimports=[
        # PyQt6
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
        # 文档处理
        'fitz', 'docx', 'docx2txt', 'pptx', 'openpyxl',
        'chardet', 'bs4', 'lxml',
        # 网络
        'httpx', 'httpcore', 'certifi',
        # 图像
        'PIL', 'PIL.Image',
        # PaddleOCR (按需加载，不强制)
        'paddleocr', 'paddle',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'notebook', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='智能出卷系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # 不显示黑框
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 可替换为 icon.ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='智能出卷系统',
)
