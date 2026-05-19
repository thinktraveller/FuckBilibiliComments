# -*- coding: utf-8 -*-
"""
历史记录 Tab

功能：
  - 展示 history.json 中的全部爬取/去重任务记录
  - 支持按状态、类型筛选，支持关键词搜索（BV 号 / 标题）
  - 点击行显示详情面板（标题、BV 号、爬取时间、评论数、输出目录等）
  - "打开输出文件夹"按钮（仅当目录存在时可用）
  - "删除记录"按钮（仅删除 JSON 条目，不删除文件）
  - "刷新"按钮手动重新读取 history.json
"""

import os
import shutil
import subprocess
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QFormLayout,
    QFrame, QAbstractItemView, QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from FuckBilibiliComments.services import history_service


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_STATUS_LABELS = {
    "success": "成功",
    "failed":  "失败",
    "aborted": "已中止",
    "running": "运行中",
}

_STATUS_COLORS = {
    "success": "#27ae60",
    "failed":  "#e74c3c",
    "aborted": "#e67e22",
    "running": "#2980b9",
}

_TYPE_LABELS = {
    "crawl": "爬取",
    "dedup": "去重",
    "stats": "统计",
}

# 表格列定义：(列头, 宽度提示)
# 宽度提示：None = 自动拉伸，否则为固定/初始宽度（像素）
_COLUMNS = [
    ("时间",     140),
    ("BV 号",    100),
    ("标题",     None),   # 拉伸列
    ("类型",     60),
    ("模式",     70),
    ("评论数",   70),
    ("状态",     60),
    ("日志大小", 75),
]

_COL_LOG_SIZE = 7   # "日志大小"列索引


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_logs_dir(output_dir: str) -> str:
    """返回 output_dir 下的 logs 子目录路径。"""
    return os.path.join(output_dir, "logs") if output_dir else ""


def _calc_log_size(output_dir: str) -> int:
    """计算 logs/ 目录的总字节数，目录不存在时返回 -1。"""
    logs_dir = _get_logs_dir(output_dir)
    if not logs_dir or not os.path.isdir(logs_dir):
        return -1
    total = 0
    for entry in os.scandir(logs_dir):
        if entry.is_file():
            total += entry.stat().st_size
    return total


def _fmt_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读字符串；-1 表示无日志目录。"""
    if size_bytes < 0:
        return "—"
    if size_bytes == 0:
        return "0 B"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 / 1024:.1f} MB"


# ---------------------------------------------------------------------------
# 详情面板
# ---------------------------------------------------------------------------

class _DetailPanel(QFrame):
    """右侧记录详情面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; }"
        )
        self._build_ui()
        self._clear()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title_lbl = QLabel("记录详情")
        title_lbl.setFont(QFont("", 11, QFont.Bold))
        title_lbl.setStyleSheet("color: #2c3e50; border: none;")
        layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #dee2e6; border: none; border-top: 1px solid #dee2e6;")
        layout.addWidget(sep)

        # 表单区
        form_widget = QWidget()
        form_widget.setStyleSheet("background: transparent; border: none;")
        form = QFormLayout(form_widget)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setContentsMargins(0, 0, 0, 0)

        def _field(placeholder: str = "—") -> QLabel:
            lbl = QLabel(placeholder)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lbl.setStyleSheet("color: #2c3e50; font-size: 11px; background: transparent; border: none;")
            return lbl

        def _key(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "color: #7f8c8d; font-size: 11px; font-weight: bold; background: transparent; border: none;"
            )
            return lbl

        self._f_title      = _field()
        self._f_bv         = _field()
        self._f_up         = _field()
        self._f_type       = _field()
        self._f_mode       = _field()
        self._f_status     = _field()
        self._f_start      = _field()
        self._f_end        = _field()
        self._f_comments   = _field()
        self._f_output     = _field()
        self._f_error      = _field()

        form.addRow(_key("标题："),      self._f_title)
        form.addRow(_key("BV 号："),     self._f_bv)
        form.addRow(_key("UP 主："),     self._f_up)
        form.addRow(_key("类型："),      self._f_type)
        form.addRow(_key("模式："),      self._f_mode)
        form.addRow(_key("状态："),      self._f_status)
        form.addRow(_key("开始时间："),  self._f_start)
        form.addRow(_key("结束时间："),  self._f_end)
        form.addRow(_key("评论数："),    self._f_comments)
        form.addRow(_key("输出目录："),  self._f_output)
        form.addRow(_key("错误信息："),  self._f_error)

        layout.addWidget(form_widget)
        layout.addStretch()

        # 操作按钮区
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self._open_dir_btn = QPushButton("打开输出文件夹")
        self._open_dir_btn.setFixedHeight(34)
        self._open_dir_btn.setEnabled(False)
        self._open_dir_btn.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background-color: #3498db; }"
            "QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }"
        )
        self._open_dir_btn.clicked.connect(self._on_open_dir)
        btn_layout.addWidget(self._open_dir_btn)

        self._delete_btn = QPushButton("删除记录")
        self._delete_btn.setFixedHeight(34)
        self._delete_btn.setEnabled(False)
        self._delete_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
            "QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }"
        )
        btn_layout.addWidget(self._delete_btn)

        layout.addLayout(btn_layout)

        # 当前显示的任务 ID 和输出目录
        self._current_task_id: str | None = None
        self._current_output_dir: str | None = None

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def load_record(self, record: dict):
        """将一条历史记录填充到详情面板。"""
        self._current_task_id    = record.get("task_id")
        self._current_output_dir = record.get("output_dir", "")

        # 标题
        self._f_title.setText(record.get("title") or "（未知）")

        # BV 号
        self._f_bv.setText(record.get("bv") or "—")

        # UP 主
        self._f_up.setText(record.get("up_name") or "—")

        # 类型
        raw_type = record.get("type", "")
        self._f_type.setText(_TYPE_LABELS.get(raw_type, raw_type) or "—")

        # 模式
        self._f_mode.setText(record.get("mode") or "—")

        # 状态
        raw_status = record.get("status", "")
        status_text = _STATUS_LABELS.get(raw_status, raw_status)
        color = _STATUS_COLORS.get(raw_status, "#2c3e50")
        self._f_status.setText(status_text)
        self._f_status.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold; background: transparent; border: none;"
        )

        # 开始/结束时间
        self._f_start.setText(self._fmt_time(record.get("start_time")))
        self._f_end.setText(self._fmt_time(record.get("end_time")))

        # 评论数
        stats = record.get("stats") or {}
        comments = stats.get("comments")
        if comments is not None:
            self._f_comments.setText(f"{int(comments):,} 条")
        else:
            self._f_comments.setText("—")

        # 输出目录
        output_dir = record.get("output_dir") or ""
        self._f_output.setText(output_dir if output_dir else "—")

        # 错误信息
        err = record.get("error_msg")
        self._f_error.setText(err if err else "—")
        self._f_error.setStyleSheet(
            ("color: #e74c3c;" if err else "color: #27ae60;")
            + " font-size: 11px; background: transparent; border: none;"
        )

        # 按钮状态
        dir_exists = bool(output_dir) and os.path.isdir(output_dir)
        self._open_dir_btn.setEnabled(dir_exists)
        self._delete_btn.setEnabled(True)

    def clear(self):
        """清空详情面板（无选中行时调用）。"""
        self._clear()

    def set_delete_callback(self, callback):
        """设置删除按钮回调（由父 Tab 传入）。"""
        self._delete_btn.clicked.connect(callback)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _clear(self):
        self._current_task_id    = None
        self._current_output_dir = None

        for lbl in (
            self._f_title, self._f_bv, self._f_up,
            self._f_type, self._f_mode, self._f_status,
            self._f_start, self._f_end,
            self._f_comments, self._f_output, self._f_error,
        ):
            lbl.setText("—")
            lbl.setStyleSheet(
                "color: #2c3e50; font-size: 11px; background: transparent; border: none;"
            )

        self._open_dir_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

    @staticmethod
    def _fmt_time(iso_str: str | None) -> str:
        if not iso_str:
            return "—"
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_str

    def _on_open_dir(self):
        d = self._current_output_dir
        if d and os.path.isdir(d):
            subprocess.Popen(["explorer", os.path.normpath(d)])
        else:
            QMessageBox.warning(
                self, "目录不存在",
                f"输出目录不存在或已被移动：\n{d}"
            )

    @property
    def current_task_id(self) -> str | None:
        return self._current_task_id


# ---------------------------------------------------------------------------
# 历史记录 Tab 主体
# ---------------------------------------------------------------------------

class HistoryTab(QWidget):
    """历史记录 Tab。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 当前显示的记录列表（与表格行一一对应）
        self._records: list[dict] = []
        self._build_ui()
        # 首次加载
        self._refresh_records()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 工具栏（搜索 + 筛选 + 刷新）
        toolbar = self._make_toolbar()
        root_layout.addWidget(toolbar)

        # 主体：左侧列表 + 右侧详情
        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        # 左侧：表格
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._table = self._make_table()

        # 空状态提示（叠加在表格上方，内容为空时可见）
        # 用 QWidget 容器实现叠加效果
        table_container = QWidget()
        table_container.setMinimumHeight(80)
        table_stack_layout = QVBoxLayout(table_container)
        table_stack_layout.setContentsMargins(0, 0, 0, 0)
        table_stack_layout.addWidget(self._table)

        self._empty_label = QLabel("暂无记录")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: #bdc3c7; font-size: 16px; padding: 40px;"
        )
        self._empty_label.setVisible(False)
        table_stack_layout.addWidget(self._empty_label)

        # 记录"筛选结果为空"与"全量为空"的不同提示，在 _update_empty_state 中更新文字
        left_layout.addWidget(table_container, 1)

        # 记录总数标签
        self._count_label = QLabel("共 0 条记录")
        self._count_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        left_layout.addWidget(self._count_label)

        splitter.addWidget(left_widget)

        # 右侧：详情面板
        self._detail_panel = _DetailPanel()
        self._detail_panel.set_delete_callback(self._on_delete_record)
        self._detail_panel.setMinimumWidth(280)
        splitter.addWidget(self._detail_panel)

        splitter.setSizes([700, 320])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

    def _make_toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setStyleSheet(
            "QFrame { background: #f0f4f8; border: 1px solid #d5dde5; border-radius: 4px; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        # 搜索框
        layout.addWidget(QLabel("搜索："))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("BV 号 / 视频标题")
        self._search_edit.setFixedWidth(220)
        self._search_edit.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self._search_edit)

        # 状态筛选
        layout.addWidget(QLabel("状态："))
        self._status_combo = QComboBox()
        self._status_combo.addItems(["全部", "成功", "失败", "已中止", "运行中"])
        self._status_combo.setFixedWidth(90)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._status_combo)

        # 类型筛选
        layout.addWidget(QLabel("类型："))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["全部", "爬取", "去重", "统计"])
        self._type_combo.setFixedWidth(80)
        self._type_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._type_combo)

        layout.addStretch()

        # 全选按钮
        self._select_all_btn = QPushButton("全选")
        self._select_all_btn.setFixedWidth(55)
        self._select_all_btn.clicked.connect(self._on_select_all)
        layout.addWidget(self._select_all_btn)

        # 清理日志按钮
        self._clean_logs_btn = QPushButton("清理日志")
        self._clean_logs_btn.setFixedWidth(75)
        self._clean_logs_btn.setEnabled(False)
        self._clean_logs_btn.setStyleSheet(
            "QPushButton { background-color: #e67e22; color: white; border-radius: 4px; }"
            "QPushButton:hover { background-color: #f39c12; }"
            "QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }"
        )
        self._clean_logs_btn.clicked.connect(self._on_clean_logs)
        layout.addWidget(self._clean_logs_btn)

        # 刷新按钮
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setFixedWidth(60)
        self._refresh_btn.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3498db; }"
        )
        self._refresh_btn.clicked.connect(self._refresh_records)
        layout.addWidget(self._refresh_btn)

        return bar

    def _make_table(self) -> QTableWidget:
        col_count = len(_COLUMNS)
        table = QTableWidget(0, col_count)
        table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])

        # 外观
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 多选
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setStyleSheet(
            "QTableWidget { border: 1px solid #d5dde5; border-radius: 4px; }"
            "QTableWidget::item { padding: 4px 8px; }"
            "QTableWidget::item:selected { background-color: #d0e8f8; color: #1a1a1a; }"
            "QHeaderView::section { background-color: #edf2f7; padding: 6px 8px; "
            "  border: none; border-bottom: 1px solid #c5cdd8; font-weight: bold; }"
        )

        # 列宽
        header = table.horizontalHeader()
        for i, (_, width) in enumerate(_COLUMNS):
            if width is None:
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.Interactive)
                table.setColumnWidth(i, width)

        # 行高
        table.verticalHeader().setDefaultSectionSize(28)

        # 双击打开文件夹
        table.doubleClicked.connect(self._on_row_double_clicked)

        # 选中行切换详情
        table.itemSelectionChanged.connect(self._on_selection_changed)

        return table

    # ------------------------------------------------------------------
    # 数据加载与过滤
    # ------------------------------------------------------------------

    def _refresh_records(self):
        """从 history_service 重新读取全量记录，再应用当前过滤条件。"""
        # 读取全部记录（最多 1000 条，倒序最新优先）
        try:
            self._all_records: list[dict] = history_service.get_all(limit=1000)
        except Exception as e:
            self._all_records = []
            QMessageBox.warning(self, "读取失败", f"无法读取历史记录：{e}")

        self._apply_filters()

    def _on_filter_changed(self):
        self._apply_filters()

    def _apply_filters(self):
        """根据搜索框和下拉框过滤 _all_records，然后填充表格。"""
        keyword = self._search_edit.text().strip().lower()

        # 状态映射（界面文字 → 英文 key）
        status_map = {
            "全部":  None,
            "成功":  "success",
            "失败":  "failed",
            "已中止": "aborted",
            "运行中": "running",
        }
        type_map = {
            "全部":  None,
            "爬取":  "crawl",
            "去重":  "dedup",
            "统计":  "stats",
        }

        status_filter = status_map.get(self._status_combo.currentText())
        type_filter   = type_map.get(self._type_combo.currentText())

        filtered = []
        for r in self._all_records:
            if status_filter and r.get("status") != status_filter:
                continue
            if type_filter and r.get("type") != type_filter:
                continue
            if keyword:
                bv    = (r.get("bv") or "").lower()
                title = (r.get("title") or "").lower()
                if keyword not in bv and keyword not in title:
                    continue
            filtered.append(r)

        self._records = filtered
        self._fill_table(filtered)

    def _fill_table(self, records: list[dict]):
        """将记录列表渲染到表格。"""
        self._table.setRowCount(0)
        self._detail_panel.clear()

        for row, r in enumerate(records):
            self._table.insertRow(row)
            self._set_row(row, r)

        self._count_label.setText(f"共 {len(records)} 条记录")
        self._update_empty_state(records)

    def _update_empty_state(self, records: list[dict]):
        """根据记录数量控制表格和空状态标签的可见性。"""
        is_empty = len(records) == 0
        self._table.setVisible(not is_empty)
        self._empty_label.setVisible(is_empty)
        if is_empty:
            # 根据是否有过滤条件显示不同提示
            has_filter = bool(
                self._search_edit.text().strip()
                or self._status_combo.currentIndex() != 0
                or self._type_combo.currentIndex() != 0
            )
            if has_filter:
                self._empty_label.setText("未找到匹配的记录")
            else:
                self._empty_label.setText("暂无记录")

    def _set_row(self, row: int, record: dict):
        """填充一行。"""
        # 时间
        start_raw = record.get("start_time") or ""
        try:
            dt = datetime.fromisoformat(start_raw)
            time_text = dt.strftime("%m-%d %H:%M")
        except Exception:
            time_text = start_raw[:16] if start_raw else "—"

        # 评论数
        stats = record.get("stats") or {}
        comments = stats.get("comments")
        comments_text = f"{int(comments):,}" if comments is not None else "—"

        # 状态
        raw_status  = record.get("status", "")
        status_text = _STATUS_LABELS.get(raw_status, raw_status)
        status_color = _STATUS_COLORS.get(raw_status, "#2c3e50")

        # 类型
        raw_type  = record.get("type", "")
        type_text = _TYPE_LABELS.get(raw_type, raw_type)

        # 日志大小
        output_dir = record.get("output_dir") or ""
        log_size_bytes = _calc_log_size(output_dir)
        log_size_text = _fmt_size(log_size_bytes)

        cells = [
            time_text,
            record.get("bv") or "—",
            record.get("title") or "—",
            type_text,
            record.get("mode") or "—",
            comments_text,
            status_text,
            log_size_text,
        ]

        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            # 状态列着色
            if col == 6:
                item.setForeground(QColor(status_color))
                item.setFont(QFont("", -1, QFont.Bold))

            # 日志大小列：有内容时用橙色提示
            if col == _COL_LOG_SIZE and log_size_bytes > 0:
                item.setForeground(QColor("#e67e22"))

            self._table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # 选中行 / 双击
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        selected_rows = list({idx.row() for idx in self._table.selectedIndexes()})
        # 更新"清理日志"按钮可用性：选中行中至少有一个存在 logs/ 目录
        has_logs = any(
            _calc_log_size(self._records[r].get("output_dir") or "") >= 0
            for r in selected_rows
            if 0 <= r < len(self._records)
        )
        self._clean_logs_btn.setEnabled(bool(selected_rows) and has_logs)

        if len(selected_rows) == 1:
            row = selected_rows[0]
            if 0 <= row < len(self._records):
                self._detail_panel.load_record(self._records[row])
        else:
            self._detail_panel.clear()

    def _on_row_double_clicked(self, index):
        """双击行 = 直接打开输出文件夹（若目录存在）。"""
        row = index.row()
        if 0 <= row < len(self._records):
            output_dir = self._records[row].get("output_dir", "")
            if output_dir and os.path.isdir(output_dir):
                subprocess.Popen(["explorer", os.path.normpath(output_dir)])
            else:
                QMessageBox.information(
                    self, "无法打开",
                    "该记录没有有效的输出目录，或目录已被移动/删除。"
                )

    # ------------------------------------------------------------------
    # 全选 / 清理日志
    # ------------------------------------------------------------------

    def _on_select_all(self):
        self._table.selectAll()

    def _on_clean_logs(self):
        selected_rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        targets = []
        for r in selected_rows:
            if 0 <= r < len(self._records):
                output_dir = self._records[r].get("output_dir") or ""
                logs_dir = _get_logs_dir(output_dir)
                if logs_dir and os.path.isdir(logs_dir):
                    targets.append((r, logs_dir))

        if not targets:
            QMessageBox.information(self, "无日志", "选中的记录中没有可清理的日志目录。")
            return

        total_size = sum(_calc_log_size(self._records[r].get("output_dir") or "") for r, _ in targets)
        reply = QMessageBox.question(
            self,
            "确认清理日志",
            f"将删除 {len(targets)} 条记录的 logs/ 目录（共约 {_fmt_size(total_size)}）。\n\n"
            "此操作不可恢复，历史记录条目本身不会被删除。\n确认继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        errors = []
        for r, logs_dir in targets:
            try:
                shutil.rmtree(logs_dir)
            except Exception as e:
                errors.append(f"{logs_dir}：{e}")

        # 刷新表格中的日志大小列
        for r, _ in targets:
            item = QTableWidgetItem("—")
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self._table.setItem(r, _COL_LOG_SIZE, item)

        if errors:
            QMessageBox.warning(self, "部分失败", "以下目录清理失败：\n" + "\n".join(errors))
        else:
            QMessageBox.information(
                self, "清理完成",
                f"已成功清理 {len(targets)} 条记录的日志目录。"
            )

        self._clean_logs_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # 删除记录
    # ------------------------------------------------------------------

    def _on_delete_record(self):
        task_id = self._detail_panel.current_task_id
        if not task_id:
            return

        row = self._table.currentRow()
        record = self._records[row] if 0 <= row < len(self._records) else {}
        title      = record.get("title", task_id) or task_id
        output_dir = record.get("output_dir") or ""
        logs_dir   = _get_logs_dir(output_dir)

        # 构建确认对话框，提供三种删除范围
        box = QMessageBox(self)
        box.setWindowTitle("确认删除记录")
        box.setText(f"确定要删除以下历史记录吗？\n\n{title}")
        box.setIcon(QMessageBox.Question)

        btn_record_only = box.addButton("不删除任何本地文件", QMessageBox.ActionRole)
        btn_with_logs   = box.addButton("仅同时删除日志",     QMessageBox.ActionRole)
        btn_with_all    = box.addButton("同时删除本地文件",   QMessageBox.DestructiveRole)
        btn_cancel      = box.addButton("取消",               QMessageBox.RejectRole)

        # 仅当目录存在时才启用对应按钮
        btn_with_logs.setEnabled(bool(logs_dir) and os.path.isdir(logs_dir))
        btn_with_all.setEnabled(bool(output_dir) and os.path.isdir(output_dir))

        box.setDefaultButton(btn_cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is btn_cancel or clicked is None:
            return

        # 删除历史记录条目
        ok = history_service.delete_task(task_id)
        if not ok:
            QMessageBox.warning(self, "删除失败", f"未找到任务记录：{task_id}")
            return

        # 按选择删除本地文件
        if clicked is btn_with_logs:
            try:
                shutil.rmtree(logs_dir)
            except Exception as e:
                QMessageBox.warning(self, "删除日志失败", f"历史记录已删除，但日志目录删除失败：\n{e}")
        elif clicked is btn_with_all:
            try:
                shutil.rmtree(output_dir)
            except Exception as e:
                QMessageBox.warning(self, "删除文件失败", f"历史记录已删除，但输出目录删除失败：\n{e}")

        # 从本地缓存中移除并刷新
        self._all_records = [r for r in self._all_records if r.get("task_id") != task_id]
        self._apply_filters()

    # ------------------------------------------------------------------
    # 供外部调用的公开接口
    # ------------------------------------------------------------------

    def refresh(self):
        """供主窗口或其他 Tab 主动触发刷新（如爬取完成后）。"""
        self._refresh_records()
