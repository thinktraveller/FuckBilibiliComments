# -*- coding: utf-8 -*-
"""
评论爬取 Tab

功能：
  - 视频输入与解析（BV 号 / 视频链接）
  - 爬取参数配置（模式、间隔、子评论等）
  - 后台 QThread 爬取，主线程不阻塞
  - 实时日志 + 进度条 + 统计面板
  - 历史记录联动
"""

import os
import time
import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QRadioButton, QButtonGroup, QCheckBox,
    QSpinBox, QDoubleSpinBox,
    QProgressBar, QPlainTextEdit,
    QSplitter, QMessageBox, QSizePolicy,
    QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from PySide6.QtGui import QFont, QColor, QTextCursor

from FuckBilibiliComments.services import account_service, history_service
from FuckBilibiliComments.services.crawl_service import (
    resolve_video,
    CrawlParams,
    run_crawl,
)
from FuckBilibiliComments.callbacks import TaskCallbacks


# ---------------------------------------------------------------------------
# 后台解析 Worker
# ---------------------------------------------------------------------------

class _ResolveWorker(QObject):
    """在 QThread 中调用 resolve_video()，避免阻塞主线程。"""
    finished = Signal(object, object, object)  # (oid, bv_id, video_info)
    error    = Signal(str)

    def __init__(self, bv_or_url: str):
        super().__init__()
        self._input = bv_or_url

    def run(self):
        try:
            oid, bv_id, video_info = resolve_video(self._input)
            self.finished.emit(oid, bv_id, video_info)
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# 后台爬取 Worker
# ---------------------------------------------------------------------------

class _CrawlWorker(QObject):
    """在 QThread 中执行 run_crawl()，通过信号向主线程汇报进度与日志。"""

    log_signal      = Signal(str, str)   # (level, message)
    progress_signal = Signal(int, int)   # (current, total)
    finished        = Signal(dict)       # 返回结果字典

    def __init__(self, params: CrawlParams, abort_event: threading.Event):
        super().__init__()
        self._params = params
        self._abort_event = abort_event

    def run(self):
        cb = TaskCallbacks(
            log=lambda level, msg: self.log_signal.emit(level, msg),
            progress=lambda cur, tot: self.progress_signal.emit(cur, tot),
            prompt=lambda q: "",          # GUI 模式暂不支持交互询问
            is_aborted=lambda: self._abort_event.is_set(),
        )
        result = run_crawl(self._params, cb)
        self.finished.emit(result)


# ---------------------------------------------------------------------------
# 评论爬取 Tab 主体
# ---------------------------------------------------------------------------

class CrawlTab(QWidget):
    """评论爬取 Tab。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 状态
        self._oid: str | None        = None
        self._bv_id: str | None      = None
        self._video_info: dict | None = None

        # 爬取线程
        self._crawl_thread: QThread | None  = None
        self._crawl_worker: _CrawlWorker | None = None
        self._abort_event: threading.Event | None = None

        # 解析线程
        self._resolve_thread: QThread | None = None
        self._resolve_worker: _ResolveWorker | None = None

        # 历史任务 ID
        self._task_id: str | None = None

        # 计时器（用于统计速率/耗时）
        self._crawl_start_time: float | None = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 顶部：账号状态栏
        self._account_bar = self._make_account_bar()
        root_layout.addWidget(self._account_bar)

        # 主体：上半（输入+参数）/ 下半（进度+日志）
        splitter = QSplitter(Qt.Vertical)
        root_layout.addWidget(splitter, 1)

        # ---- 上半 ----
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        top_layout.addWidget(self._make_input_group(), 1)
        top_layout.addWidget(self._make_params_group(), 1)
        top_layout.addWidget(self._make_control_group())

        splitter.addWidget(top_widget)

        # ---- 下半：进度+日志 ----
        bottom_widget = self._make_bottom_area()
        splitter.addWidget(bottom_widget)

        splitter.setSizes([320, 380])

        # 初始账号刷新
        self._refresh_account_display()
        # 参数区禁用（等待解析成功）
        self._set_params_enabled(False)

    # ---- 账号状态栏 ----

    def _make_account_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setStyleSheet(
            "QFrame { background: #eaf2fb; border: 1px solid #aed6f1; border-radius: 4px; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)

        lbl = QLabel("当前账号：")
        lbl.setFont(QFont("", 9))
        layout.addWidget(lbl)

        self._account_name_label = QLabel("（未设置）")
        self._account_name_label.setFont(QFont("", 9, QFont.Bold))
        self._account_name_label.setStyleSheet("color: #1a5276;")
        layout.addWidget(self._account_name_label)

        layout.addStretch()

        hint = QLabel("如需切换账号，请前往「账号管理」Tab")
        hint.setStyleSheet("color: #5d6d7e; font-size: 11px;")
        layout.addWidget(hint)

        return bar

    # ---- 视频输入区 ----

    def _make_input_group(self) -> QGroupBox:
        group = QGroupBox("视频输入")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        url_row = QHBoxLayout()
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("输入 BV 号或视频链接（如 BV1xx... 或完整 URL）")
        self._url_input.returnPressed.connect(self._on_resolve)
        url_row.addWidget(self._url_input)

        self._resolve_btn = QPushButton("解析视频")
        self._resolve_btn.setFixedWidth(90)
        self._resolve_btn.clicked.connect(self._on_resolve)
        url_row.addWidget(self._resolve_btn)

        layout.addLayout(url_row)

        # 视频信息卡片（初始隐藏）
        self._video_card = self._make_video_card()
        layout.addWidget(self._video_card)
        self._video_card.hide()

        # 错误提示
        self._resolve_error_label = QLabel()
        self._resolve_error_label.setWordWrap(True)
        self._resolve_error_label.setStyleSheet(
            "color: #c0392b; font-size: 11px; padding: 4px;"
        )
        self._resolve_error_label.hide()
        layout.addWidget(self._resolve_error_label)

        layout.addStretch()
        return group

    def _make_video_card(self) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(
            "QFrame { background: #f0faf0; border: 1px solid #82e0aa; border-radius: 4px; }"
        )
        form = QFormLayout(card)
        form.setContentsMargins(10, 8, 10, 8)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        self._vi_title  = self._card_value_label()
        self._vi_bvid   = self._card_value_label()
        self._vi_owner  = self._card_value_label()
        self._vi_pubdate = self._card_value_label()
        self._vi_replies = self._card_value_label()

        form.addRow(self._card_key_label("标题："),    self._vi_title)
        form.addRow(self._card_key_label("BV 号："),   self._vi_bvid)
        form.addRow(self._card_key_label("UP 主："),   self._vi_owner)
        form.addRow(self._card_key_label("发布时间："), self._vi_pubdate)
        form.addRow(self._card_key_label("评论总数："), self._vi_replies)

        return card

    @staticmethod
    def _card_key_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #1e8449; font-size: 11px; font-weight: bold;")
        return lbl

    @staticmethod
    def _card_value_label() -> QLabel:
        lbl = QLabel()
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #1c2833; font-size: 11px;")
        return lbl

    # ---- 爬取参数区 ----

    def _make_params_group(self) -> QGroupBox:
        group = QGroupBox("爬取参数")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # 爬取模式
        mode_box = QGroupBox("爬取模式")
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setSpacing(4)

        self._mode_group = QButtonGroup(self)

        self._rb_comprehensive = QRadioButton("综合模式（默认，先热度后时间）")
        self._rb_hot           = QRadioButton("仅热度排序")
        self._rb_time          = QRadioButton("仅时间排序")
        self._rb_iterative     = QRadioButton("迭代模式")

        self._rb_comprehensive.setChecked(True)

        for rb in (self._rb_comprehensive, self._rb_hot, self._rb_time, self._rb_iterative):
            self._mode_group.addButton(rb)
            mode_layout.addWidget(rb)

        # 迭代模式附加参数（初始隐藏）
        self._iter_params_widget = self._make_iter_params()
        mode_layout.addWidget(self._iter_params_widget)
        self._iter_params_widget.hide()

        self._rb_iterative.toggled.connect(
            lambda checked: self._iter_params_widget.setVisible(checked)
        )

        layout.addWidget(mode_box)

        # 爬取选项
        opts_box = QGroupBox("爬取选项")
        opts_layout = QVBoxLayout(opts_box)
        opts_layout.setSpacing(4)

        self._cb_replies  = QCheckBox("包含楼中楼回复")
        self._cb_charged  = QCheckBox("包含充电视频评论")
        self._cb_replies.setChecked(True)

        opts_layout.addWidget(self._cb_replies)
        opts_layout.addWidget(self._cb_charged)

        layout.addWidget(opts_box)

        # 请求间隔
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("请求间隔（ms）："))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(500, 10000)
        self._interval_spin.setValue(3000)
        self._interval_spin.setSingleStep(100)
        self._interval_spin.setFixedWidth(90)
        interval_row.addWidget(self._interval_spin)
        interval_row.addStretch()

        layout.addLayout(interval_row)
        layout.addStretch()

        return group

    def _make_iter_params(self) -> QWidget:
        """迭代模式附加参数控件。"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(16, 4, 0, 4)
        layout.setSpacing(6)

        # 停止条件选择
        stop_row = QHBoxLayout()
        self._iter_stop_group = QButtonGroup(self)
        self._rb_iter_time = QRadioButton("按时间限制（小时）")
        self._rb_iter_rate = QRadioButton("按重复率限制（%）")
        self._rb_iter_time.setChecked(True)
        self._iter_stop_group.addButton(self._rb_iter_time)
        self._iter_stop_group.addButton(self._rb_iter_rate)
        stop_row.addWidget(self._rb_iter_time)
        stop_row.addWidget(self._rb_iter_rate)
        layout.addRow("停止条件：", stop_row)

        # 时间输入
        self._iter_time_spin = QDoubleSpinBox()
        self._iter_time_spin.setRange(0.1, 720.0)
        self._iter_time_spin.setValue(24.0)
        self._iter_time_spin.setSuffix(" h")
        self._iter_time_spin.setFixedWidth(90)
        layout.addRow("限制时间：", self._iter_time_spin)

        # 重复率输入
        self._iter_rate_spin = QDoubleSpinBox()
        self._iter_rate_spin.setRange(1.0, 99.0)
        self._iter_rate_spin.setValue(80.0)
        self._iter_rate_spin.setSuffix(" %")
        self._iter_rate_spin.setFixedWidth(90)
        self._iter_rate_spin.setEnabled(False)
        layout.addRow("限制重复率：", self._iter_rate_spin)

        # 联动启用/禁用
        self._rb_iter_time.toggled.connect(
            lambda checked: (
                self._iter_time_spin.setEnabled(checked),
                self._iter_rate_spin.setEnabled(not checked),
            )
        )

        return widget

    # ---- 控制区 ----

    def _make_control_group(self) -> QWidget:
        widget = QWidget()
        widget.setFixedWidth(130)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._start_btn = QPushButton("开始爬取")
        self._start_btn.setFixedHeight(40)
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; font-size: 13px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3498db; }"
            "QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }"
        )
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start_crawl)
        layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setFixedHeight(34)
        self._stop_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; font-size: 12px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
            "QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }"
        )
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop_crawl)
        layout.addWidget(self._stop_btn)

        layout.addStretch()
        return widget

    # ---- 进度与日志区 ----

    def _make_bottom_area(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(20)
        layout.addWidget(self._progress_bar)

        # 统计面板
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        self._stat_crawled  = self._make_stat_label("已爬", "0 条")
        self._stat_unique   = self._make_stat_label("唯一", "—")
        self._stat_elapsed  = self._make_stat_label("耗时", "—")
        self._stat_rate     = self._make_stat_label("速率", "—")

        for lbl in (self._stat_crawled, self._stat_unique,
                    self._stat_elapsed, self._stat_rate):
            stats_row.addWidget(lbl)

        stats_row.addStretch()
        layout.addLayout(stats_row)

        # 日志窗口
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(5000)
        self._log_edit.setFont(QFont("Consolas", 9))
        self._log_edit.setStyleSheet(
            "QPlainTextEdit { background: #1e2328; color: #abb2bf; border: 1px solid #3a3f4b; }"
        )
        layout.addWidget(self._log_edit, 1)

        return widget

    @staticmethod
    def _make_stat_label(key: str, value: str) -> QLabel:
        lbl = QLabel(f"{key}：{value}")
        lbl.setStyleSheet(
            "color: #34495e; font-size: 11px; "
            "background: #ecf0f1; border-radius: 3px; padding: 2px 8px;"
        )
        lbl.setProperty("key", key)
        lbl.setProperty("val", value)
        return lbl

    def _set_stat(self, label: QLabel, value: str):
        key = label.property("key")
        label.setText(f"{key}：{value}")
        label.setProperty("val", value)

    # ------------------------------------------------------------------
    # 账号刷新
    # ------------------------------------------------------------------

    def _refresh_account_display(self):
        try:
            acc = account_service.get_selected_account()
            name = acc["name"] if acc else "（无账号，请先在账号管理 Tab 添加）"
        except Exception:
            name = "（读取失败）"
        self._account_name_label.setText(name)

    # ------------------------------------------------------------------
    # 参数区启用控制
    # ------------------------------------------------------------------

    def _set_params_enabled(self, enabled: bool):
        for w in (
            self._rb_comprehensive, self._rb_hot, self._rb_time, self._rb_iterative,
            self._cb_replies, self._cb_charged, self._interval_spin,
        ):
            w.setEnabled(enabled)

        if enabled:
            self._iter_params_widget.setEnabled(True)
        else:
            self._iter_params_widget.setEnabled(False)

        self._start_btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 解析视频
    # ------------------------------------------------------------------

    def _on_resolve(self):
        if self._resolve_thread and self._resolve_thread.isRunning():
            return

        url = self._url_input.text().strip()
        if not url:
            self._show_resolve_error("请输入 BV 号或视频链接。")
            return

        # 重置
        self._video_card.hide()
        self._resolve_error_label.hide()
        self._resolve_btn.setEnabled(False)
        self._resolve_btn.setText("解析中...")
        self._set_params_enabled(False)

        self._resolve_worker = _ResolveWorker(url)
        self._resolve_thread = QThread()
        self._resolve_worker.moveToThread(self._resolve_thread)
        self._resolve_thread.started.connect(self._resolve_worker.run)
        self._resolve_worker.finished.connect(self._on_resolve_finished)
        self._resolve_worker.error.connect(self._on_resolve_error)
        self._resolve_worker.finished.connect(self._resolve_thread.quit)
        self._resolve_worker.error.connect(self._resolve_thread.quit)
        self._resolve_thread.start()

    def _on_resolve_finished(self, oid, bv_id, video_info):
        self._resolve_btn.setEnabled(True)
        self._resolve_btn.setText("解析视频")

        if oid is None or bv_id is None:
            self._show_resolve_error(
                "解析失败：无法从输入中识别有效的视频 ID，请确认 BV 号或链接正确。"
            )
            return

        self._oid        = oid
        self._bv_id      = bv_id
        self._video_info = video_info or {}

        # 填充视频卡片
        title    = self._video_info.get("title", "（未知）")
        owner    = self._video_info.get("owner", {})
        owner_name = owner.get("name", "（未知）") if isinstance(owner, dict) else str(owner)
        pubdate_ts = self._video_info.get("pubdate", 0)
        try:
            pubdate_str = datetime.fromtimestamp(int(pubdate_ts)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pubdate_str = "（未知）"
        replies = self._video_info.get("stat", {}).get("reply", "—")
        if isinstance(replies, int):
            replies = f"{replies:,}"

        self._vi_title.setText(title)
        self._vi_bvid.setText(bv_id)
        self._vi_owner.setText(owner_name)
        self._vi_pubdate.setText(pubdate_str)
        self._vi_replies.setText(str(replies))

        self._video_card.show()
        self._resolve_error_label.hide()
        self._set_params_enabled(True)

    def _on_resolve_error(self, msg: str):
        self._resolve_btn.setEnabled(True)
        self._resolve_btn.setText("解析视频")
        self._show_resolve_error(f"解析出错：{msg}")

    def _show_resolve_error(self, msg: str):
        self._resolve_error_label.setText(msg)
        self._resolve_error_label.show()
        self._video_card.hide()

    # ------------------------------------------------------------------
    # 构造 CrawlParams
    # ------------------------------------------------------------------

    def _build_crawl_params(self) -> CrawlParams | None:
        """根据 UI 当前状态构造 CrawlParams，失败时弹窗并返回 None。"""
        # 获取账号
        acc = account_service.get_selected_account()
        if not acc:
            QMessageBox.warning(
                self, "无账号",
                "当前没有可用账号，请先在「账号管理」Tab 中添加并设为当前账号。"
            )
            return None

        cookie     = acc.get("cookie", "")
        user_agent = acc.get("user_agent", "")

        # 构造请求头
        request_headers = {
            "Cookie":          cookie,
            "User-Agent":      user_agent,
            "Referer":         "https://www.bilibili.com",
            "Accept":          "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

        # 确定模式
        if self._rb_comprehensive.isChecked():
            mode      = "comprehensive"
            test_sort = 1
            max_pages = 999
        elif self._rb_hot.isChecked():
            mode      = "test"
            test_sort = 1       # 热度排序
            max_pages = 999
        elif self._rb_time.isChecked():
            mode      = "test"
            test_sort = 0       # 时间排序
            max_pages = 999
        else:  # iterative
            mode      = "iteration"
            test_sort = 1
            max_pages = 999

        # 迭代模式配置
        iteration_config: dict = {}
        if mode == "iteration":
            if self._rb_iter_time.isChecked():
                iteration_config = {
                    "type":  "time",
                    "value": self._iter_time_spin.value(),
                }
            else:
                iteration_config = {
                    "type":  "rate",
                    "value": self._iter_rate_spin.value(),
                }

        return CrawlParams(
            oid             = self._oid,
            bv_id           = self._bv_id,
            video_info      = self._video_info,
            video_title     = self._video_info.get("title", self._bv_id),
            mode            = mode,
            test_sort       = test_sort,
            max_pages       = max_pages,
            ps              = 20,
            delay_ms        = self._interval_spin.value(),
            request_headers = request_headers,
            output_dir      = None,
            iteration_config= iteration_config,
        )

    # ------------------------------------------------------------------
    # 爬取控制
    # ------------------------------------------------------------------

    def _on_start_crawl(self):
        if self._crawl_thread and self._crawl_thread.isRunning():
            return

        self._refresh_account_display()

        params = self._build_crawl_params()
        if params is None:
            return

        # 记录历史（running）
        self._task_id = history_service.generate_task_id(self._bv_id or "")
        acc = account_service.get_selected_account()
        acc_name = acc.get("name", "") if acc else ""
        mode_label = {
            "comprehensive": "综合模式",
            "test":          "测试模式（热度）" if params.test_sort == 1 else "测试模式（时间）",
            "iteration":     "迭代模式",
        }.get(params.mode, params.mode)

        history_service.add_task(
            task_id   = self._task_id,
            task_type = "crawl",
            bv        = self._bv_id or "",
            title     = params.video_title,
            up_name   = self._video_info.get("owner", {}).get("name", "")
                        if isinstance(self._video_info.get("owner"), dict) else "",
            mode      = mode_label,
            params    = {"account": acc_name, "delay_ms": params.delay_ms},
        )

        # 重置 UI
        self._log_edit.clear()
        self._progress_bar.setValue(0)
        self._set_stat(self._stat_crawled, "0 条")
        self._set_stat(self._stat_unique,  "—")
        self._set_stat(self._stat_elapsed, "0 s")
        self._set_stat(self._stat_rate,    "— 条/min")

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._set_params_enabled(False)
        self._url_input.setEnabled(False)
        self._resolve_btn.setEnabled(False)

        # 启动计时
        self._crawl_start_time = time.monotonic()
        self._elapsed_timer.start()

        # 启动爬取线程
        self._abort_event = threading.Event()
        self._crawl_worker = _CrawlWorker(params, self._abort_event)
        self._crawl_thread = QThread()
        self._crawl_worker.moveToThread(self._crawl_thread)
        self._crawl_thread.started.connect(self._crawl_worker.run)
        self._crawl_worker.log_signal.connect(self._on_log)
        self._crawl_worker.progress_signal.connect(self._on_progress)
        self._crawl_worker.finished.connect(self._on_crawl_finished)
        self._crawl_worker.finished.connect(self._crawl_thread.quit)
        self._crawl_thread.start()

    def _on_stop_crawl(self):
        if self._abort_event:
            self._abort_event.set()
        self._stop_btn.setEnabled(False)
        self._append_log("WARNING", "用户已请求停止，等待当前页面完成后退出...")

    def _on_crawl_finished(self, result: dict):
        self._elapsed_timer.stop()

        # 恢复 UI
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._set_params_enabled(True)
        self._url_input.setEnabled(True)
        self._resolve_btn.setEnabled(True)

        success    = result.get("success", False)
        output_dir = result.get("output_dir", "")
        comments   = result.get("stats", {}).get("comments", 0)
        error_msg  = result.get("error_msg")

        # 更新统计
        self._set_stat(self._stat_unique, f"{comments:,} 条")

        # 确定最终状态
        if self._abort_event and self._abort_event.is_set():
            final_status = "aborted"
        elif success:
            final_status = "success"
        else:
            final_status = "failed"

        # 更新历史
        if self._task_id:
            history_service.update_task(
                task_id    = self._task_id,
                status     = final_status,
                stats      = {"comments": comments},
                error_msg  = error_msg,
                output_dir = output_dir,
            )

        # 弹出完成摘要
        self._show_finish_dialog(
            success    = success,
            aborted    = (final_status == "aborted"),
            comments   = comments,
            output_dir = output_dir,
            error_msg  = error_msg,
        )

    # ------------------------------------------------------------------
    # 进度 / 日志回调
    # ------------------------------------------------------------------

    def _on_log(self, level: str, msg: str):
        self._append_log(level, msg)

        # 简单地从日志中推断已爬条数（INFO 日志包含数字时更新）
        # 这是一种宽松的启发式更新，精确计数由 progress 回调负责
        if "条" in msg or "评论" in msg:
            pass  # progress_signal 会专门处理

    def _on_progress(self, current: int, total: int):
        if total > 0:
            pct = min(int(current / total * 100), 100)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(pct)
            self._progress_bar.setFormat(f"{current} / {total}  ({pct}%)")
        else:
            # 不确定总量：滚动进度条
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setFormat(f"已处理 {current} 条...")

        self._set_stat(self._stat_crawled, f"{current:,} 条")

        # 更新速率
        if self._crawl_start_time is not None:
            elapsed = time.monotonic() - self._crawl_start_time
            if elapsed > 0:
                rate = current / elapsed * 60
                self._set_stat(self._stat_rate, f"{rate:.1f} 条/min")

    def _update_elapsed(self):
        if self._crawl_start_time is not None:
            elapsed = int(time.monotonic() - self._crawl_start_time)
            h, rem  = divmod(elapsed, 3600)
            m, s    = divmod(rem, 60)
            if h > 0:
                self._set_stat(self._stat_elapsed, f"{h}h {m}m {s}s")
            elif m > 0:
                self._set_stat(self._stat_elapsed, f"{m}m {s}s")
            else:
                self._set_stat(self._stat_elapsed, f"{s} s")

    # ------------------------------------------------------------------
    # 日志追加
    # ------------------------------------------------------------------

    _LEVEL_COLORS = {
        "DEBUG":   "#6c9bcf",
        "INFO":    "#abb2bf",
        "WARNING": "#e5c07b",
        "ERROR":   "#e06c75",
    }

    def _append_log(self, level: str, msg: str):
        ts    = datetime.now().strftime("%H:%M:%S")
        color = self._LEVEL_COLORS.get(level.upper(), "#abb2bf")
        # 使用纯文本 + 颜色字段拼接（不依赖 HTML 以保持性能）
        line  = f"[{ts}] [{level:7s}] {msg}"

        # 追加到日志窗口
        self._log_edit.appendPlainText(line)

        # 滚动到底部
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._log_edit.setTextCursor(cursor)
        self._log_edit.ensureCursorVisible()

    # ------------------------------------------------------------------
    # 完成对话框
    # ------------------------------------------------------------------

    def _show_finish_dialog(
        self,
        success: bool,
        aborted: bool,
        comments: int,
        output_dir: str,
        error_msg: str | None,
    ):
        if aborted:
            title = "爬取已停止"
            icon  = QMessageBox.Warning
            text  = f"爬取已由用户停止。\n已获取 {comments:,} 条评论。"
        elif success:
            title = "爬取完成"
            icon  = QMessageBox.Information
            text  = f"爬取成功完成！\n共获取 {comments:,} 条唯一评论。"
        else:
            title = "爬取失败"
            icon  = QMessageBox.Critical
            text  = f"爬取过程中发生错误。\n{error_msg or ''}"

        if output_dir:
            text += f"\n\n输出目录：\n{output_dir}"

        msg_box = QMessageBox(icon, title, text, parent=self)

        if output_dir and os.path.isdir(output_dir):
            open_btn = msg_box.addButton("打开输出文件夹", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec()
            if msg_box.clickedButton() == open_btn:
                import subprocess
                subprocess.Popen(["explorer", output_dir])
        else:
            msg_box.exec()
