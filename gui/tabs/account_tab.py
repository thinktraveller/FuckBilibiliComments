# -*- coding: utf-8 -*-
"""
账号管理 Tab

提供账号的新增 / 编辑 / 删除 / 设为当前账号功能。
所有数据操作均委托给 services/account_service.py，
GUI 层只负责信号槽绑定和界面更新。
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QTextEdit, QPushButton, QGroupBox,
    QFormLayout, QMessageBox, QSplitter, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor

from FuckBilibiliComments.services import account_service


_COOKIE_HELP_HTML = (
    '如何获取 Cookie：<br>'
    '1. 安装浏览器扩展 '
    '<a href="https://cookie-editor.com/">Cookie-Editor</a>'
    '（支持 Chrome / Edge / Firefox）<br>'
    '2. 在浏览器中<b>登录 B 站</b>，然后点击扩展图标<br>'
    '3. 点击右下角 <b>Export → Header String</b>，复制全部内容粘贴到上方输入框'
)

_UA_HELP_HTML = (
    '如何获取当前浏览器的 User-Agent：<br>'
    '&bull; <b>Chrome</b>：地址栏输入 <code>chrome://version</code> → 找"用户代理"<br>'
    '&bull; <b>Edge</b>：地址栏输入 <code>edge://version</code> → 找"用户代理"<br>'
    '&bull; <b>Firefox</b>：地址栏输入 <code>about:support</code> → 找"用户代理"<br>'
    '复制完整字符串粘贴到上方输入框'
)


# ---------------------------------------------------------------------------
# 后台验证 Worker
# ---------------------------------------------------------------------------

class _ValidateWorker(QObject):
    """在 QThread 中调用 account_service.validate_account()，避免阻塞主线程。"""
    finished = Signal(dict)  # 验证结果字典

    def __init__(self, cookie: str, user_agent: str):
        super().__init__()
        self._cookie = cookie
        self._user_agent = user_agent

    def run(self):
        result = account_service.validate_account(self._cookie, self._user_agent)
        self.finished.emit(result)


# ---------------------------------------------------------------------------
# 账号管理 Tab 主体
# ---------------------------------------------------------------------------

class AccountTab(QWidget):
    """账号管理 Tab，包含左侧列表 + 右侧编辑区。"""

    # 当当前账号发生变化时，向主窗口发送信号（携带账号名）
    current_account_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_edit_index: int = -1   # -1 表示新增模式
        self._validate_thread: QThread | None = None
        self._validate_worker: _ValidateWorker | None = None

        self._build_ui()
        self._refresh_list()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        # ---- 左侧：账号列表 ----
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        list_label = QLabel("账号列表")
        list_label.setFont(QFont("", 10, QFont.Bold))
        left_layout.addWidget(list_label)

        self._list_widget = QListWidget()
        self._list_widget.setMinimumWidth(180)
        self._list_widget.currentRowChanged.connect(self._on_list_selection_changed)
        left_layout.addWidget(self._list_widget)

        # 列表下方按钮行
        list_btn_layout = QHBoxLayout()
        list_btn_layout.setSpacing(6)

        self._btn_new = QPushButton("新增")
        self._btn_new.setToolTip("新增一个账号")
        self._btn_new.clicked.connect(self._on_new_account)
        list_btn_layout.addWidget(self._btn_new)

        self._btn_set_current = QPushButton("设为当前")
        self._btn_set_current.setToolTip("将选中账号设为当前使用的账号")
        self._btn_set_current.clicked.connect(self._on_set_current)
        list_btn_layout.addWidget(self._btn_set_current)

        self._btn_delete = QPushButton("删除")
        self._btn_delete.setToolTip("删除选中账号")
        self._btn_delete.setStyleSheet("QPushButton { color: #c0392b; }")
        self._btn_delete.clicked.connect(self._on_delete_account)
        list_btn_layout.addWidget(self._btn_delete)

        left_layout.addLayout(list_btn_layout)
        splitter.addWidget(left_panel)

        # ---- 右侧：详情 / 编辑区 ----
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self._edit_title_label = QLabel("账号详情")
        self._edit_title_label.setFont(QFont("", 10, QFont.Bold))
        right_layout.addWidget(self._edit_title_label)

        # 表单
        form_group = QGroupBox()
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(12, 16, 12, 12)

        # 账号名称
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("例如：主号、备用号")
        form_layout.addRow("账号名称：", self._name_edit)

        # Cookie 输入（多行）
        self._cookie_edit = QTextEdit()
        self._cookie_edit.setPlaceholderText(
            "粘贴完整 Cookie 字符串（推荐用 Cookie-Editor 扩展导出）\n"
            "保存后此处将自动显示脱敏版本"
        )
        self._cookie_edit.setMinimumHeight(100)
        self._cookie_edit.setMaximumHeight(150)
        self._cookie_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_layout.addRow("Cookie：", self._cookie_edit)

        # Cookie 脱敏提示（查看模式显示）
        self._cookie_masked_label = QLabel()
        self._cookie_masked_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        self._cookie_masked_label.setWordWrap(True)
        self._cookie_masked_label.hide()
        form_layout.addRow("", self._cookie_masked_label)

        # Cookie 获取教程
        cookie_help_label = QLabel(_COOKIE_HELP_HTML)
        cookie_help_label.setWordWrap(True)
        cookie_help_label.setOpenExternalLinks(True)
        cookie_help_label.setStyleSheet(
            "color: #555; font-size: 11px; "
            "background: #f0f4f8; border-radius: 4px; padding: 6px 8px;"
        )
        form_layout.addRow("", cookie_help_label)

        # UA 纯手动输入
        self._ua_edit = QLineEdit()
        self._ua_edit.setPlaceholderText("粘贴你的浏览器 User-Agent（必填，见下方说明）")
        form_layout.addRow("User-Agent：", self._ua_edit)

        # UA 获取教程
        ua_help_label = QLabel(_UA_HELP_HTML)
        ua_help_label.setWordWrap(True)
        ua_help_label.setStyleSheet(
            "color: #555; font-size: 11px; "
            "background: #f0f4f8; border-radius: 4px; padding: 6px 8px;"
        )
        form_layout.addRow("", ua_help_label)

        right_layout.addWidget(form_group)

        # 验证结果提示
        self._validate_result_label = QLabel()
        self._validate_result_label.setWordWrap(True)
        self._validate_result_label.setStyleSheet("font-size: 12px; padding: 4px 0;")
        self._validate_result_label.hide()
        right_layout.addWidget(self._validate_result_label)

        # 操作按钮行
        action_btn_layout = QHBoxLayout()
        action_btn_layout.setSpacing(8)

        self._btn_validate = QPushButton("测试账号有效性")
        self._btn_validate.setToolTip("调用 B 站接口验证当前 Cookie 是否有效")
        self._btn_validate.clicked.connect(self._on_validate)
        action_btn_layout.addWidget(self._btn_validate)

        action_btn_layout.addStretch()

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.clicked.connect(self._on_cancel)
        action_btn_layout.addWidget(self._btn_cancel)

        self._btn_save = QPushButton("保存")
        self._btn_save.setDefault(True)
        self._btn_save.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; padding: 4px 16px; }"
            "QPushButton:hover { background-color: #3498db; }"
            "QPushButton:disabled { background-color: #bdc3c7; }"
        )
        self._btn_save.clicked.connect(self._on_save)
        action_btn_layout.addWidget(self._btn_save)

        right_layout.addLayout(action_btn_layout)
        right_layout.addStretch()

        splitter.addWidget(right_panel)
        splitter.setSizes([220, 580])

        # 初始状态：右侧置为空白
        self._set_right_panel_enabled(False)

    # ------------------------------------------------------------------
    # 数据刷新
    # ------------------------------------------------------------------

    def _refresh_list(self):
        """重新从 account_service 加载账号列表并更新 QListWidget。"""
        selected_idx = account_service.get_selected_index()
        accounts = account_service.get_accounts_masked()

        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        for acc in accounts:
            text = acc["name"]
            if acc["index"] == selected_idx:
                text += " [当前]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, acc["index"])
            if acc["index"] == selected_idx:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor("#2980b9"))
            self._list_widget.addItem(item)
        self._list_widget.blockSignals(False)

        # 更新状态栏账号名
        selected_acc = account_service.get_selected_account()
        name = selected_acc["name"] if selected_acc else "（无账号）"
        self.current_account_changed.emit(name)

        self._update_button_states()

    def _update_button_states(self):
        has_selection = self._list_widget.currentRow() >= 0
        self._btn_set_current.setEnabled(has_selection)
        self._btn_delete.setEnabled(has_selection)

    # ------------------------------------------------------------------
    # 右侧面板 helpers
    # ------------------------------------------------------------------

    def _set_right_panel_enabled(self, enabled: bool):
        self._name_edit.setEnabled(enabled)
        self._cookie_edit.setEnabled(enabled)
        self._ua_edit.setEnabled(enabled)
        self._btn_save.setEnabled(enabled)
        self._btn_cancel.setEnabled(enabled)
        self._btn_validate.setEnabled(enabled)

    def _fill_right_panel(self, index: int):
        """用指定索引的账号填充右侧编辑区（展示模式：Cookie 脱敏）。"""
        accounts_full = account_service.get_accounts()
        accounts_masked = account_service.get_accounts_masked()

        if index < 0 or index >= len(accounts_full):
            return

        full = accounts_full[index]
        masked = accounts_masked[index]

        self._current_edit_index = index
        self._edit_title_label.setText(f"编辑账号：{full['name']}")

        self._name_edit.setText(full["name"])

        # Cookie：编辑框留空，脱敏信息用 label 展示
        self._cookie_edit.setPlaceholderText(
            "如需修改 Cookie，请在此粘贴完整字符串（留空则保持原 Cookie 不变）"
        )
        self._cookie_edit.clear()
        self._cookie_masked_label.setText(f"当前 Cookie（脱敏）：{masked['cookie_masked']}")
        self._cookie_masked_label.show()

        # UA
        ua = full.get("user_agent", "")
        self._ua_edit.setText(ua)

        self._validate_result_label.hide()
        self._set_right_panel_enabled(True)

    def _clear_right_panel_for_new(self):
        """清空右侧表单，进入新增模式。"""
        self._current_edit_index = -1
        self._edit_title_label.setText("新增账号")
        self._name_edit.clear()
        self._cookie_edit.clear()
        self._cookie_edit.setPlaceholderText(
            "粘贴完整 Cookie 字符串（推荐用 Cookie-Editor 扩展导出）"
        )
        self._cookie_masked_label.hide()
        self._ua_edit.clear()
        self._validate_result_label.hide()
        self._set_right_panel_enabled(True)
        self._name_edit.setFocus()

    def _get_current_ua(self) -> str:
        return self._ua_edit.text().strip()

    def _get_current_cookie(self) -> str:
        """返回当前 Cookie 输入框的内容（trim 后）。"""
        return self._cookie_edit.toPlainText().strip()

    # ------------------------------------------------------------------
    # 槽函数
    # ------------------------------------------------------------------

    def _on_list_selection_changed(self, row: int):
        if row < 0:
            self._set_right_panel_enabled(False)
            self._update_button_states()
            return
        item = self._list_widget.item(row)
        if item is None:
            return
        index = item.data(Qt.UserRole)
        self._fill_right_panel(index)
        self._update_button_states()

    def _on_new_account(self):
        self._list_widget.clearSelection()
        self._clear_right_panel_for_new()

    def _on_set_current(self):
        row = self._list_widget.currentRow()
        if row < 0:
            return
        item = self._list_widget.item(row)
        index = item.data(Qt.UserRole)
        try:
            account_service.set_selected(index)
            self._refresh_list()
        except (IndexError, ValueError) as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _on_delete_account(self):
        row = self._list_widget.currentRow()
        if row < 0:
            return
        item = self._list_widget.item(row)
        index = item.data(Qt.UserRole)
        accounts = account_service.get_accounts()
        name = accounts[index]["name"] if index < len(accounts) else "?"

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除账号「{name}」吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            account_service.delete_account(index)
            self._refresh_list()
            self._set_right_panel_enabled(False)
            self._edit_title_label.setText("账号详情")
        except (IndexError, ValueError) as e:
            QMessageBox.warning(self, "删除失败", str(e))

    def _on_save(self):
        name = self._name_edit.text().strip()
        cookie_input = self._get_current_cookie()
        ua = self._get_current_ua()

        if not name:
            QMessageBox.warning(self, "验证失败", "账号名称不能为空。")
            self._name_edit.setFocus()
            return

        try:
            if self._current_edit_index == -1:
                # 新增模式
                if not cookie_input:
                    QMessageBox.warning(self, "验证失败", "新增账号时 Cookie 不能为空。")
                    self._cookie_edit.setFocus()
                    return
                account_service.add_account(name, cookie_input, ua)
            else:
                # 编辑模式：若 Cookie 留空，保持原 Cookie
                if cookie_input:
                    final_cookie = cookie_input
                else:
                    accounts = account_service.get_accounts()
                    final_cookie = accounts[self._current_edit_index].get("cookie", "")
                account_service.update_account(self._current_edit_index, name, final_cookie, ua)
        except (ValueError, IndexError) as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return

        self._refresh_list()
        # 保存成功后，重新加载该账号的编辑视图
        accounts = account_service.get_accounts()
        # 找到刚保存的账号的实际索引
        new_index = next((i for i, a in enumerate(accounts) if a["name"] == name), -1)
        if new_index >= 0:
            # 在列表中定位并选中
            for row in range(self._list_widget.count()):
                item = self._list_widget.item(row)
                if item and item.data(Qt.UserRole) == new_index:
                    self._list_widget.setCurrentRow(row)
                    break
        QMessageBox.information(self, "保存成功", f"账号「{name}」已保存。")

    def _on_cancel(self):
        row = self._list_widget.currentRow()
        if row >= 0:
            item = self._list_widget.item(row)
            self._fill_right_panel(item.data(Qt.UserRole))
        else:
            self._set_right_panel_enabled(False)
            self._edit_title_label.setText("账号详情")

    def _on_validate(self):
        # 防止重复点击
        if self._validate_thread and self._validate_thread.isRunning():
            return

        cookie = self._get_current_cookie()
        # 若输入框为空且处于编辑模式，取原始 Cookie
        if not cookie and self._current_edit_index >= 0:
            accounts = account_service.get_accounts()
            cookie = accounts[self._current_edit_index].get("cookie", "")

        if not cookie:
            QMessageBox.warning(self, "验证失败", "请先填写 Cookie。")
            return

        ua = self._get_current_ua()

        self._btn_validate.setEnabled(False)
        self._btn_validate.setText("验证中...")
        self._validate_result_label.setText("正在连接 B 站接口，请稍候...")
        self._validate_result_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self._validate_result_label.show()

        # 在 QThread 中运行，避免阻塞主线程
        self._validate_worker = _ValidateWorker(cookie, ua)
        self._validate_thread = QThread()
        self._validate_worker.moveToThread(self._validate_thread)
        self._validate_thread.started.connect(self._validate_worker.run)
        self._validate_worker.finished.connect(self._on_validate_finished)
        self._validate_worker.finished.connect(self._validate_thread.quit)
        self._validate_thread.start()

    def _on_validate_finished(self, result: dict):
        self._btn_validate.setEnabled(True)
        self._btn_validate.setText("测试账号有效性")

        if result.get("valid"):
            self._validate_result_label.setText(f"[有效]  {result.get('message', '')}")
            self._validate_result_label.setStyleSheet(
                "color: #27ae60; font-size: 12px; font-weight: bold;"
            )
        else:
            self._validate_result_label.setText(f"[无效]  {result.get('message', '')}")
            self._validate_result_label.setStyleSheet(
                "color: #c0392b; font-size: 12px; font-weight: bold;"
            )
        self._validate_result_label.show()
