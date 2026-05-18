# -*- coding: utf-8 -*-
"""
历史记录服务层

负责 history.json 的读写操作，记录每次爬取/统计/去重任务的结果。
所有写操作使用"先写 .tmp，再 os.replace"原子策略，防止 JSON 损坏。

history.json 数据结构（数组）：
[
  {
    "task_id":    "20260518-143012-BV1xx",
    "type":       "crawl",               # crawl / stats / dedup
    "bv":         "BV1xx",
    "title":      "视频标题",
    "up_name":    "UP昵称",
    "start_time": "2026-05-18T14:30:12",
    "end_time":   "2026-05-18T14:45:01",
    "status":     "success",             # success / failed / aborted / running
    "mode":       "热度",
    "params":     {...},
    "output_dir": "outputs/...",
    "stats":      {"comments": 1234, "subcomments": 567, "pages": 42},
    "error_msg":  null
  }
]
"""

import json
import os
from datetime import datetime
from typing import Optional, List

_HISTORY_PATH = "history.json"


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _load_raw() -> list:
    """读取 history.json；文件不存在或损坏时返回空列表并备份损坏文件。"""
    if not os.path.exists(_HISTORY_PATH):
        return []
    try:
        with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, IOError):
        # 损坏时备份并重置
        backup = _HISTORY_PATH + ".bak"
        try:
            import shutil
            shutil.copy2(_HISTORY_PATH, backup)
        except Exception:
            pass
        return []


def _save_raw(records: list) -> None:
    """原子写入 history.json。"""
    tmp = _HISTORY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _HISTORY_PATH)


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def generate_task_id(bv: str = "") -> str:
    """
    生成唯一任务 ID。

    格式：YYYYMMDD-HHMMSS-{bv}

    Args:
        bv: BV 号（可为空）

    Returns:
        str: 任务 ID
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = bv if bv else "task"
    return f"{ts}-{suffix}"


def add_task(
    task_id: str,
    task_type: str,
    bv: str = "",
    title: str = "",
    up_name: str = "",
    mode: str = "",
    params: Optional[dict] = None,
    output_dir: str = "",
) -> dict:
    """
    新增一条任务记录（状态为 running）。

    Args:
        task_id:   任务唯一 ID
        task_type: 任务类型（crawl / stats / dedup）
        bv:        BV 号
        title:     视频标题
        up_name:   UP 主昵称
        mode:      爬取模式描述
        params:    参数字典（不含 Cookie 本体，仅存账号名）
        output_dir: 输出目录路径

    Returns:
        dict: 新建的任务记录
    """
    record = {
        "task_id":    task_id,
        "type":       task_type,
        "bv":         bv,
        "title":      title,
        "up_name":    up_name,
        "start_time": datetime.now().isoformat(timespec="seconds"),
        "end_time":   None,
        "status":     "running",
        "mode":       mode,
        "params":     params or {},
        "output_dir": output_dir,
        "stats":      {},
        "error_msg":  None,
    }
    records = _load_raw()
    records.append(record)
    _save_raw(records)
    return record


def update_task(
    task_id: str,
    status: str,
    stats: Optional[dict] = None,
    error_msg: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Optional[dict]:
    """
    更新任务状态（任务结束时调用）。

    Args:
        task_id:   任务 ID
        status:    新状态（success / failed / aborted）
        stats:     统计数据（如 comments / pages 等）
        error_msg: 错误信息（失败时提供）
        output_dir: 如果输出目录在运行中才确定，可在此更新

    Returns:
        dict | None: 更新后的记录；未找到时返回 None
    """
    records = _load_raw()
    for record in records:
        if record.get("task_id") == task_id:
            record["status"]   = status
            record["end_time"] = datetime.now().isoformat(timespec="seconds")
            if stats is not None:
                record["stats"] = stats
            if error_msg is not None:
                record["error_msg"] = error_msg
            if output_dir is not None:
                record["output_dir"] = output_dir
            _save_raw(records)
            return record
    return None


def get_all(
    status_filter: Optional[str] = None,
    task_type_filter: Optional[str] = None,
    limit: int = 500,
) -> List[dict]:
    """
    查询历史记录列表（内存过滤）。

    Args:
        status_filter:    按状态过滤（success / failed / aborted / running）
        task_type_filter: 按类型过滤（crawl / stats / dedup）
        limit:            最多返回条数（默认 500，按时间倒序）

    Returns:
        list[dict]: 符合条件的记录列表
    """
    records = _load_raw()
    # 倒序（最新在前）
    records = list(reversed(records))

    if status_filter:
        records = [r for r in records if r.get("status") == status_filter]
    if task_type_filter:
        records = [r for r in records if r.get("type") == task_type_filter]

    return records[:limit]


def get_task(task_id: str) -> Optional[dict]:
    """
    按 task_id 查询单条记录。

    Returns:
        dict | None
    """
    for record in _load_raw():
        if record.get("task_id") == task_id:
            return record
    return None


def delete_task(task_id: str) -> bool:
    """
    删除指定任务记录（仅删除 JSON 条目，不删除输出文件夹）。

    Returns:
        bool: 是否删除成功
    """
    records = _load_raw()
    new_records = [r for r in records if r.get("task_id") != task_id]
    if len(new_records) == len(records):
        return False
    _save_raw(new_records)
    return True
