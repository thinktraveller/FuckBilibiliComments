# -*- coding: utf-8 -*-
"""
GUI 应用入口

提供 run_gui() 函数，负责创建 QApplication 和主窗口。
由 gui_main.py 调用。
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gui.main_window import MainWindow


def run_gui() -> int:
    """
    启动 GUI 应用。

    Returns:
        int: 应用退出码（传递给 sys.exit）
    """
    # 高 DPI 支持（必须在 QApplication 实例化之前设置）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("FuckBilibiliComments")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("thinktraveller")

    # 设置全局字体（Windows 下 Microsoft YaHei 对中文更友好）
    from PySide6.QtGui import QFont
    default_font = QFont("Microsoft YaHei UI", 9)
    default_font.setFallback(True)
    app.setFont(default_font)

    window = MainWindow()
    window.show()

    return app.exec()
