# -*- coding: utf-8 -*-
"""
帮助教程 Tab

布局：左侧 QTreeWidget 目录树 + 右侧 QTextBrowser 渲染 HTML 帮助文档。
帮助文档以 HTML 文件形式存放在 gui/resources/help/ 目录下，
通过 QTextBrowser 直接渲染（无需外部 Markdown 库）。
"""

import os

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTextBrowser,
    QLabel, QVBoxLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


# ---------------------------------------------------------------------------
# 章节定义：(显示名称, HTML 文件名)
# ---------------------------------------------------------------------------

_CHAPTERS = [
    ("快速上手",             "01_quick_start.html"),
    ("Cookie 获取（Chrome/Edge）", "02_cookie_chrome.html"),
    ("Cookie 获取（Firefox）",     "03_cookie_firefox.html"),
    ("User-Agent 获取",            "04_user_agent.html"),
    ("爬取模式说明",               "05_crawl_modes.html"),
    ("常见错误",                   "06_common_errors.html"),
    ("隐私与免责",                 "07_privacy.html"),
]


def _help_dir() -> str:
    """返回 gui/resources/help 目录的绝对路径。"""
    # 本文件位于 gui/tabs/help_tab.py，资源目录为 gui/resources/help/
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "resources", "help"))


def _load_html(filename: str) -> str:
    """读取并返回指定 HTML 文件的内容；读取失败时返回友好的错误提示。"""
    path = os.path.join(_help_dir(), filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            f"<html><body style='font-family:sans-serif;color:#c0392b;padding:20px;'>"
            f"<h2>文件未找到</h2>"
            f"<p>帮助文档文件不存在：</p>"
            f"<code>{path}</code>"
            f"</body></html>"
        )
    except Exception as e:
        return (
            f"<html><body style='font-family:sans-serif;color:#c0392b;padding:20px;'>"
            f"<h2>读取失败</h2><p>{e}</p>"
            f"</body></html>"
        )


# ---------------------------------------------------------------------------
# 帮助教程 Tab
# ---------------------------------------------------------------------------

class HelpTab(QWidget):
    """帮助教程 Tab：左侧目录树 + 右侧文档浏览器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        # 默认选中第一章节
        if self._tree.topLevelItemCount() > 0:
            first_item = self._tree.topLevelItem(0)
            self._tree.setCurrentItem(first_item)
            self._load_chapter(0)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        # 左侧：目录树
        left_widget = self._make_left_panel()
        splitter.addWidget(left_widget)

        # 右侧：文档浏览器
        right_widget = self._make_right_panel()
        splitter.addWidget(right_widget)

        splitter.setSizes([220, 780])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _make_left_panel(self) -> QWidget:
        container = QWidget()
        container.setMaximumWidth(280)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)

        # 标题
        title = QLabel("帮助目录")
        title.setFont(QFont("", 11, QFont.Bold))
        title.setStyleSheet(
            "color: #2c3e50; padding: 4px 0; border-bottom: 1px solid #dee2e6;"
        )
        layout.addWidget(title)

        # 目录树
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setStyleSheet(
            "QTreeWidget {"
            "  border: 1px solid #dee2e6;"
            "  border-radius: 4px;"
            "  background: #fafbfc;"
            "  outline: none;"
            "}"
            "QTreeWidget::item {"
            "  padding: 7px 10px;"
            "  border-radius: 3px;"
            "}"
            "QTreeWidget::item:selected {"
            "  background-color: #d0e8f8;"
            "  color: #1a1a1a;"
            "}"
            "QTreeWidget::item:hover:!selected {"
            "  background-color: #eef4fa;"
            "}"
        )
        self._tree.setFont(QFont("", 12))

        # 填充章节
        for i, (name, _filename) in enumerate(_CHAPTERS):
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.UserRole, i)   # 存储章节索引
            self._tree.addTopLevelItem(item)

        self._tree.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree, 1)

        return container

    def _make_right_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(
            "QTextBrowser {"
            "  border: 1px solid #dee2e6;"
            "  border-radius: 4px;"
            "  background: #ffffff;"
            "  padding: 4px;"
            "}"
        )
        layout.addWidget(self._browser)

        return container

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_item_changed(self, current: QTreeWidgetItem, _previous):
        if current is None:
            return
        index = current.data(0, Qt.UserRole)
        if index is not None:
            self._load_chapter(index)

    def _load_chapter(self, index: int):
        """加载指定索引的章节内容到 QTextBrowser。"""
        if 0 <= index < len(_CHAPTERS):
            _name, filename = _CHAPTERS[index]
            html = _load_html(filename)
            self._browser.setHtml(html)
            # 滚动到顶部
            self._browser.verticalScrollBar().setValue(0)
