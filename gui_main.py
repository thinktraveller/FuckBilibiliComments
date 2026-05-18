#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FuckBilibiliComments GUI 入口

用法：
    python gui_main.py

原 CLI 入口 FuckBilibiliComments.py 不受影响，可并行使用：
    python FuckBilibiliComments.py
"""

import sys
import os

# 强制 Matplotlib 使用非交互式 Agg 后端，避免在 QThread 中调用时产生
# "Starting a Matplotlib GUI outside of the main thread" 警告
os.environ.setdefault("MPLBACKEND", "Agg")

# 确保工作目录为项目根目录（脚本所在目录），
# 以保证 config.json、history.json 等路径解析正确。
_script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_script_dir)

# 屏蔽 Qt 在 Windows 上枚举旧式 GDI 字体（MS Sans Serif）时的 DirectWrite 警告
# 该警告无害，仅因系统存在 DirectWrite 无法处理的位图字体而触发
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")

# 将项目根目录加入 sys.path（支持从任意目录启动）
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

if sys.version_info < (3, 10):
    print(f"[ERROR] 需要 Python 3.10 或更高版本，当前版本：{sys.version}")
    sys.exit(1)

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("[ERROR] 未找到 PySide6，请先安装：")
    print("    pip install \"PySide6>=6.8\"")
    sys.exit(1)

from gui.app import run_gui

if __name__ == "__main__":
    sys.exit(run_gui())
