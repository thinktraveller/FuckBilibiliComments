# -*- coding: utf-8 -*-
"""
主窗口

QMainWindow 子类，包含：
  - 顶部 QTabWidget（6 个 Tab）
  - 底部状态栏（左侧状态文字 + 右侧当前账号名）

M1 阶段：账号管理 Tab 完整实现，其余 Tab 为占位。
后续里程碑将逐步填充各 Tab 内容。
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QLabel,
    QVBoxLayout, QStatusBar,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont

from gui.tabs.account_tab import AccountTab
from gui.tabs.crawl_tab import CrawlTab
from gui.tabs.dedup_tab import DedupTab
from gui.tabs.history_tab import HistoryTab


# ---------------------------------------------------------------------------
# 占位 Tab 工厂
# ---------------------------------------------------------------------------

def _make_placeholder_tab(text: str) -> QWidget:
    """返回一个显示提示文字的空白 QWidget，用作未实现 Tab 的占位。"""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setAlignment(Qt.AlignCenter)
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setFont(QFont("", 14))
    label.setStyleSheet("color: #bdc3c7;")
    layout.addWidget(label)
    return widget


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """FuckBilibiliComments 主窗口。"""

    TITLE = "FuckBilibiliComments"
    DEFAULT_WIDTH = 1200
    DEFAULT_HEIGHT = 800
    MIN_WIDTH = 1000
    MIN_HEIGHT = 700

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setWindowTitle(self.TITLE)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)

        # 中央区域：TabWidget
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(False)
        self._tab_widget.setTabPosition(QTabWidget.North)
        self.setCentralWidget(self._tab_widget)

        self._setup_tabs()
        self._setup_status_bar()
        # 切换到历史记录 Tab 时自动刷新
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

    def _setup_tabs(self):
        """向 TabWidget 添加 6 个 Tab。"""
        # Tab 1：评论爬取（M2 实现）
        self._crawl_tab = CrawlTab()
        self._tab_widget.addTab(self._crawl_tab, "评论爬取")

        # Tab 2：CSV 去重（M3 实现）
        self._dedup_tab = DedupTab()
        self._tab_widget.addTab(self._dedup_tab, "CSV 去重")

        # Tab 3：历史记录（M4 实现）
        self._history_tab = HistoryTab()
        self._tab_widget.addTab(self._history_tab, "历史记录")

        # Tab 4：账号管理（M1 完整实现）
        self._account_tab = AccountTab()
        self._account_tab.current_account_changed.connect(self._on_current_account_changed)
        self._tab_widget.addTab(self._account_tab, "账号管理")

        # Tab 5：帮助教程（M5 实现）
        help_tab = _make_placeholder_tab("帮助教程\n\n（将在 M5 阶段实现）")
        self._tab_widget.addTab(help_tab, "帮助教程")

    def _setup_status_bar(self):
        """配置底部状态栏。"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # 左侧：状态文字
        self._status_label = QLabel("就绪")
        status_bar.addWidget(self._status_label)

        # 右侧：当前账号名
        self._account_label = QLabel()
        self._account_label.setStyleSheet("color: #2980b9; margin-right: 8px;")
        status_bar.addPermanentWidget(self._account_label)

        # 初始化账号显示
        self._refresh_account_status()

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def set_status(self, message: str):
        """更新左侧状态文字（供各 Tab 调用）。"""
        self._status_label.setText(message)

    def _refresh_account_status(self):
        """从 account_service 读取当前账号并更新状态栏右侧。"""
        try:
            from FuckBilibiliComments.services import account_service
            acc = account_service.get_selected_account()
            name = acc["name"] if acc else "（无账号）"
        except Exception:
            name = "（读取失败）"
        self._account_label.setText(f"当前账号：{name}")

    # ------------------------------------------------------------------
    # 槽函数
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        """切换到历史记录 Tab（索引 2）时自动刷新记录列表。"""
        if index == 2 and hasattr(self, "_history_tab"):
            self._history_tab.refresh()

    def _on_current_account_changed(self, name: str):
        """响应账号管理 Tab 发出的账号变更信号，更新状态栏并通知爬取 Tab。"""
        self._account_label.setText(f"当前账号：{name}")
        # 通知爬取 Tab 同步账号显示
        if hasattr(self, "_crawl_tab"):
            self._crawl_tab._refresh_account_display()
