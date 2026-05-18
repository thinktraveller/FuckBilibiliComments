# -*- coding: utf-8 -*-
"""
CSV 去重 Tab

允许用户选择两个评论 CSV 文件（文件 A / 文件 B），
点击"开始去重"后在后台线程中调用 dedup_service.run_dedup()，
完成后展示去重统计摘要（A条数、B条数、合并条数、重复数、A独有、B独有）
并提供"打开输出文件夹"按钮。
"""

import os
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QPlainTextEdit, QFileDialog,
    QGroupBox, QGridLayout, QFrame,
)
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QFont

from FuckBilibiliComments.callbacks import TaskCallbacks
from FuckBilibiliComments.services.dedup_service import run_dedup


# ---------------------------------------------------------------------------
# 后台 Worker
# ---------------------------------------------------------------------------

class _DedupWorker(QObject):
    log_signal      = Signal(str, str)   # (level, message)
    progress_signal = Signal(int, int)   # (current, total)
    finished        = Signal(dict)       # 结果字典

    def __init__(self, file_a: str, file_b: str, output_dir: str,
                 abort_event: threading.Event):
        super().__init__()
        self._file_a      = file_a
        self._file_b      = file_b
        self._output_dir  = output_dir
        self._abort_event = abort_event

    def run(self):
        cb = TaskCallbacks(
            log=lambda level, msg: self.log_signal.emit(level, msg),
            progress=lambda cur, tot: self.progress_signal.emit(cur, tot),
            prompt=lambda q: "",
            is_aborted=lambda: self._abort_event.is_set(),
        )
        result = {"error": None}
        try:
            result.update(run_dedup(
                file_a=self._file_a,
                file_b=self._file_b,
                output_dir=self._output_dir,
                cb=cb,
            ))
        except Exception as e:
            result["error"] = str(e)
            cb.log("ERROR", f"去重失败：{e}")
        self.finished.emit(result)


# ---------------------------------------------------------------------------
# 去重 Tab
# ---------------------------------------------------------------------------

class DedupTab(QWidget):
    """CSV 去重 Tab：将两个评论 CSV 合并去重，输出 4 份结果文件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker      = None
        self._thread      = None
        self._abort_event = threading.Event()
        self._output_dir  = ""
        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 12, 16, 12)

        root.addWidget(self._make_input_group())
        root.addWidget(self._make_output_group())
        root.addWidget(self._make_control_row())
        root.addWidget(self._make_progress_group())
        root.addWidget(self._make_log_group())

    # --- 输入区 ---
    def _make_input_group(self) -> QGroupBox:
        box = QGroupBox("输入文件")
        grid = QGridLayout(box)
        grid.setColumnStretch(1, 1)
        grid.setSpacing(8)

        # 说明横幅
        notice = QLabel(
            "⚠ 请使用爬取输出文件夹（原始数据）下含有 rpid 列的 CSV 文件，"
            "其他来源的 CSV 文件可能缺少 rpid 列导致去重失败。"
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "color: #c0392b; background: #fdf3f2; "
            "border: 1px solid #e0b0aa; border-radius: 4px; "
            "padding: 6px 8px; font-size: 12px;"
        )
        grid.addWidget(notice, 0, 0, 1, 3)

        # 文件 A
        grid.addWidget(QLabel("文件 A："), 1, 0, Qt.AlignRight)
        self._file_a_edit = QLineEdit()
        self._file_a_edit.setPlaceholderText("选择含 rpid 列的评论 CSV 文件 A…")
        self._file_a_edit.setReadOnly(True)
        grid.addWidget(self._file_a_edit, 1, 1)
        btn_a = QPushButton("浏览…")
        btn_a.setFixedWidth(70)
        btn_a.clicked.connect(lambda: self._browse_file(self._file_a_edit, "A"))
        grid.addWidget(btn_a, 1, 2)

        # 文件 B
        grid.addWidget(QLabel("文件 B："), 2, 0, Qt.AlignRight)
        self._file_b_edit = QLineEdit()
        self._file_b_edit.setPlaceholderText("选择含 rpid 列的评论 CSV 文件 B…")
        self._file_b_edit.setReadOnly(True)
        grid.addWidget(self._file_b_edit, 2, 1)
        btn_b = QPushButton("浏览…")
        btn_b.setFixedWidth(70)
        btn_b.clicked.connect(lambda: self._browse_file(self._file_b_edit, "B"))
        grid.addWidget(btn_b, 2, 2)

        tip = QLabel("rpid 相同时保留爬取时间更晚的版本；时间相同时优先保留文件 A 的版本")
        tip.setStyleSheet("color: #888; font-size: 11px;")
        grid.addWidget(tip, 3, 0, 1, 3)

        return box

    # --- 输出区 ---
    def _make_output_group(self) -> QGroupBox:
        box = QGroupBox("输出目录")
        row = QHBoxLayout(box)
        row.setSpacing(8)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("默认：与文件 A 同目录下的 dedup_output 子目录")
        self._output_edit.setReadOnly(True)
        row.addWidget(self._output_edit)

        btn = QPushButton("浏览…")
        btn.setFixedWidth(70)
        btn.clicked.connect(self._browse_output)
        row.addWidget(btn)

        return box

    # --- 控制按钮行 ---
    def _make_control_row(self) -> QWidget:
        frame = QWidget()
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch()

        self._btn_start = QPushButton("开始去重")
        self._btn_start.setFixedWidth(100)
        self._btn_start.clicked.connect(self._on_start)
        row.addWidget(self._btn_start)

        self._btn_abort = QPushButton("中止")
        self._btn_abort.setFixedWidth(70)
        self._btn_abort.setEnabled(False)
        self._btn_abort.clicked.connect(self._on_abort)
        row.addWidget(self._btn_abort)

        self._btn_open = QPushButton("打开输出文件夹")
        self._btn_open.setFixedWidth(120)
        self._btn_open.setEnabled(False)
        self._btn_open.clicked.connect(self._open_output_folder)
        row.addWidget(self._btn_open)

        return frame

    # --- 进度区 ---
    def _make_progress_group(self) -> QWidget:
        frame = QWidget()
        col = QVBoxLayout(frame)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        col.addWidget(self._progress_bar)

        # 统计摘要：两行网格
        stats_frame = QFrame()
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(24)

        def _stat(label: str) -> QLabel:
            lbl = QLabel(f"{label}：—")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #2980b9; min-width: 100px;")
            return lbl

        self._lbl_a      = _stat("文件 A")
        self._lbl_b      = _stat("文件 B")
        self._lbl_merged = _stat("合并结果")
        self._lbl_dup    = _stat("重复评论")
        self._lbl_only_a = _stat("A 独有")
        self._lbl_only_b = _stat("B 独有")

        for lbl in (self._lbl_a, self._lbl_b, self._lbl_merged,
                    self._lbl_dup, self._lbl_only_a, self._lbl_only_b):
            stats_layout.addWidget(lbl)

        col.addWidget(stats_frame)
        return frame

    # --- 日志区 ---
    def _make_log_group(self) -> QGroupBox:
        box = QGroupBox("运行日志")
        col = QVBoxLayout(box)
        col.setSpacing(4)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(3000)
        self._log_view.setFont(QFont("Consolas", 9))
        self._log_view.setStyleSheet(
            "QPlainTextEdit { background:#1e1e1e; color:#d4d4d4; border:none; }"
        )
        col.addWidget(self._log_view)

        btn_clear = QPushButton("清空日志")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(self._log_view.clear)
        col.addWidget(btn_clear, alignment=Qt.AlignRight)

        return box

    # ------------------------------------------------------------------
    # 槽函数
    # ------------------------------------------------------------------

    def _browse_file(self, edit: QLineEdit, label: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"选择文件 {label}", "", "CSV 文件 (*.csv);;所有文件 (*)"
        )
        if path:
            edit.setText(path)
            # 文件 A 选定后自动推断输出目录
            if label == "A" and not self._output_edit.text():
                default_out = os.path.join(os.path.dirname(path), "dedup_output")
                self._output_edit.setText(default_out)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", "")
        if path:
            self._output_edit.setText(path)

    def _on_start(self):
        file_a = self._file_a_edit.text().strip()
        file_b = self._file_b_edit.text().strip()

        if not file_a or not os.path.exists(file_a):
            self._append_log("ERROR", "请先选择有效的文件 A")
            return
        if not file_b or not os.path.exists(file_b):
            self._append_log("ERROR", "请先选择有效的文件 B")
            return

        output_dir = self._output_edit.text().strip()
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(file_a), "dedup_output")
            self._output_edit.setText(output_dir)

        self._output_dir = output_dir

        # 重置 UI
        self._log_view.clear()
        self._progress_bar.setValue(0)
        self._btn_open.setEnabled(False)
        for lbl, label in (
            (self._lbl_a,      "文件 A"),
            (self._lbl_b,      "文件 B"),
            (self._lbl_merged, "合并结果"),
            (self._lbl_dup,    "重复评论"),
            (self._lbl_only_a, "A 独有"),
            (self._lbl_only_b, "B 独有"),
        ):
            lbl.setText(f"{label}：—")
        self._set_running(True)
        self._abort_event.clear()

        # 启动 Worker
        self._thread = QThread(self)
        self._worker = _DedupWorker(file_a, file_b, output_dir, self._abort_event)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_abort(self):
        self._abort_event.set()
        self._append_log("WARNING", "正在中止…")
        self._btn_abort.setEnabled(False)

    def _on_progress(self, cur: int, tot: int):
        if tot > 0:
            self._progress_bar.setValue(int(cur / tot * 100))

    def _on_finished(self, result: dict):
        self._set_running(False)
        self._progress_bar.setValue(100)

        if result.get("error"):
            self._append_log("ERROR", f"去重失败：{result['error']}")
            return

        stats = result.get("stats", {})
        pairs = (
            (self._lbl_a,      "文件 A",   "count_a"),
            (self._lbl_b,      "文件 B",   "count_b"),
            (self._lbl_merged, "合并结果", "merged"),
            (self._lbl_dup,    "重复评论", "duplicates"),
            (self._lbl_only_a, "A 独有",   "only_a"),
            (self._lbl_only_b, "B 独有",   "only_b"),
        )
        for lbl, label, key in pairs:
            lbl.setText(f"{label}：{stats.get(key, 0)} 条")

        if self._output_dir and os.path.isdir(self._output_dir):
            self._btn_open.setEnabled(True)

    def _open_output_folder(self):
        if self._output_dir and os.path.isdir(self._output_dir):
            os.startfile(self._output_dir)

    def _append_log(self, level: str, msg: str):
        color = {"ERROR": "#f44", "WARNING": "#fa4", "INFO": "#d4d4d4"}.get(level, "#d4d4d4")
        self._log_view.appendHtml(
            f'<span style="color:{color};">[{level}] {msg}</span>'
        )

    def _set_running(self, running: bool):
        self._btn_start.setEnabled(not running)
        self._btn_abort.setEnabled(running)
        self._file_a_edit.setEnabled(not running)
        self._file_b_edit.setEnabled(not running)
        self._output_edit.setEnabled(not running)
