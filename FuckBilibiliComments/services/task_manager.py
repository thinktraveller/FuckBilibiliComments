# -*- coding: utf-8 -*-
"""
任务管理器

在内存中维护当前运行中的任务列表，供底部状态栏和历史记录联动使用。
GUI 阶段将升级为线程安全版本（QMutex），CLI 阶段为简单字典。

任务生命周期：
    register(worker / task_id) -> task_id
    get(task_id)               -> dict | None
    list_running()             -> list[dict]
    mark_done(task_id, ok)
    abort(task_id)
"""

import threading
from datetime import datetime
from typing import Optional, Callable, Dict, List

# ---------------------------------------------------------------------------
# 任务状态常量
# ---------------------------------------------------------------------------

STATUS_RUNNING  = "running"
STATUS_SUCCESS  = "success"
STATUS_FAILED   = "failed"
STATUS_ABORTED  = "aborted"


class _Task:
    """内部任务记录（轻量级，不对外暴露）。"""
    __slots__ = (
        "task_id", "task_type", "bv", "title",
        "status", "start_time", "end_time",
        "progress_current", "progress_total",
        "error_msg",
        "_abort_flag",
        "_on_state_change",
    )

    def __init__(self, task_id: str, task_type: str, bv: str = "", title: str = "",
                 on_state_change: Optional[Callable] = None):
        self.task_id          = task_id
        self.task_type        = task_type
        self.bv               = bv
        self.title            = title
        self.status           = STATUS_RUNNING
        self.start_time       = datetime.now().isoformat(timespec="seconds")
        self.end_time         = None
        self.progress_current = 0
        self.progress_total   = 0
        self.error_msg        = None
        self._abort_flag      = False
        self._on_state_change = on_state_change

    def to_dict(self) -> dict:
        return {
            "task_id":          self.task_id,
            "type":             self.task_type,
            "bv":               self.bv,
            "title":            self.title,
            "status":           self.status,
            "start_time":       self.start_time,
            "end_time":         self.end_time,
            "progress_current": self.progress_current,
            "progress_total":   self.progress_total,
            "error_msg":        self.error_msg,
        }

    def request_abort(self) -> None:
        self._abort_flag = True

    def is_aborted(self) -> bool:
        return self._abort_flag


class TaskManager:
    """
    单例任务管理器。

    线程安全：使用 threading.Lock 保护所有写操作。
    GUI 阶段将替换为 QMutex，接口保持一致。
    """

    def __init__(self):
        self._tasks: Dict[str, _Task] = {}
        self._lock  = threading.Lock()
        self._state_change_callbacks: List[Callable] = []

    # ------------------------------------------------------------------
    # 状态变更通知
    # ------------------------------------------------------------------

    def on_state_change(self, callback: Callable[[str, str], None]) -> None:
        """
        注册全局状态变更监听器。

        Args:
            callback: (task_id: str, new_status: str) -> None
        """
        self._state_change_callbacks.append(callback)

    def _notify(self, task_id: str, status: str) -> None:
        for cb in self._state_change_callbacks:
            try:
                cb(task_id, status)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 任务注册与查询
    # ------------------------------------------------------------------

    def register(
        self,
        task_id: str,
        task_type: str = "crawl",
        bv: str = "",
        title: str = "",
    ) -> str:
        """
        注册一个新任务，返回 task_id。

        Args:
            task_id:   由 history_service.generate_task_id() 生成
            task_type: crawl / stats / dedup
            bv:        BV 号
            title:     视频标题

        Returns:
            str: task_id
        """
        task = _Task(task_id=task_id, task_type=task_type, bv=bv, title=title)
        with self._lock:
            self._tasks[task_id] = task
        self._notify(task_id, STATUS_RUNNING)
        return task_id

    def get(self, task_id: str) -> Optional[dict]:
        """按 task_id 查询任务（返回 dict 快照）。"""
        with self._lock:
            task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    def list_running(self) -> List[dict]:
        """返回所有 running 状态任务的快照列表。"""
        with self._lock:
            tasks = [t for t in self._tasks.values() if t.status == STATUS_RUNNING]
        return [t.to_dict() for t in tasks]

    def list_all(self) -> List[dict]:
        """返回所有任务的快照列表（内存中，重启后清空）。"""
        with self._lock:
            tasks = list(self._tasks.values())
        return [t.to_dict() for t in tasks]

    # ------------------------------------------------------------------
    # 任务控制
    # ------------------------------------------------------------------

    def update_progress(self, task_id: str, current: int, total: int) -> None:
        """更新任务进度，供 worker 的 progress_callback 调用。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.progress_current = current
                task.progress_total   = total

    def abort(self, task_id: str) -> bool:
        """
        请求中止任务（设置 abort flag，业务层轮询 is_aborted()）。

        Returns:
            bool: 是否找到并标记成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == STATUS_RUNNING:
                task.request_abort()
                return True
        return False

    def is_aborted(self, task_id: str) -> bool:
        """业务层调用：检查 task_id 是否已被请求中止。"""
        with self._lock:
            task = self._tasks.get(task_id)
        return task.is_aborted() if task else False

    def mark_done(self, task_id: str, success: bool, error_msg: str = "") -> None:
        """
        标记任务完成。

        Args:
            task_id:   任务 ID
            success:   True = 成功，False = 失败
            error_msg: 失败时的错误信息
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                if task._abort_flag:
                    task.status = STATUS_ABORTED
                elif success:
                    task.status = STATUS_SUCCESS
                else:
                    task.status = STATUS_FAILED
                task.end_time  = datetime.now().isoformat(timespec="seconds")
                task.error_msg = error_msg or None
                new_status = task.status

        self._notify(task_id, new_status)

    def make_is_aborted_callback(self, task_id: str) -> Callable[[], bool]:
        """
        为指定任务创建 is_aborted 回调函数，注入到 TaskCallbacks。

        Returns:
            () -> bool
        """
        def _check() -> bool:
            return self.is_aborted(task_id)
        return _check

    def make_progress_callback(self, task_id: str) -> Callable[[int, int], None]:
        """
        为指定任务创建 progress 回调函数，注入到 TaskCallbacks。

        Returns:
            (current, total) -> None
        """
        def _update(current: int, total: int) -> None:
            self.update_progress(task_id, current, total)
        return _update


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_manager: Optional[TaskManager] = None


def get_manager() -> TaskManager:
    """获取全局 TaskManager 单例。"""
    global _manager
    if _manager is None:
        _manager = TaskManager()
    return _manager
