# -*- coding: utf-8 -*-
"""
CSV 去重服务层

封装双文件合并去重的完整流程，供 GUI 的 DedupWorker 和 tools/评论CSV去重工具.py 调用。
核心去重算法：基于 rpid + 爬取时间，保留爬取时间更晚的版本。

主要函数：
    run_dedup(file_a, file_b, output_dir, cb) -> dict
"""

import csv
import os
from datetime import datetime
from typing import Optional, Callable

from ..callbacks import TaskCallbacks, make_cli_callbacks

try:
    import pandas as pd
except ImportError:
    pd = None


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _extract_crawl_time(comment: dict) -> int:
    """从评论字典中解析爬取时间戳，解析失败时回退到评论时间戳。"""
    crawl_time_str = comment.get("爬取时间", "")
    if crawl_time_str:
        try:
            dt = datetime.strptime(crawl_time_str, "%Y年%m月%d日_%H时%M分%S秒")
            return int(dt.timestamp())
        except Exception:
            pass
    return int(comment.get("时间戳", 0) or 0)


def _deduplicate_by_rpid(comments: list, source_label: str) -> tuple:
    """
    基于 rpid 去重，保留爬取时间更晚的条目。

    Returns:
        (deduped: list, duplicates: list)
    """
    rpid_map = {}
    duplicates = []

    for comment in comments:
        rpid = str(comment.get("rpid", "")).strip()
        if not rpid:
            continue
        if rpid in rpid_map:
            existing_t = _extract_crawl_time(rpid_map[rpid])
            current_t  = _extract_crawl_time(comment)
            if current_t > existing_t:
                old = rpid_map[rpid].copy()
                old["重复来源"] = source_label
                duplicates.append(old)
                rpid_map[rpid] = comment
            else:
                dup = comment.copy()
                dup["重复来源"] = source_label
                duplicates.append(dup)
        else:
            rpid_map[rpid] = comment

    return list(rpid_map.values()), duplicates


def _load_csv(path: str) -> list:
    """读取 CSV 文件，返回 dict 列表；编码自动尝试 utf-8-sig / gbk。"""
    if pd is not None:
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                df = pd.read_csv(path, encoding=enc, dtype=str)
                return df.fillna("").to_dict("records")
            except Exception:
                continue
        raise IOError(f"无法读取文件（尝试了 utf-8-sig / utf-8 / gbk）：{path}")
    else:
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    reader = csv.DictReader(f)
                    return [row for row in reader]
            except Exception:
                continue
        raise IOError(f"无法读取文件：{path}")


def _save_csv(records: list, path: str, label: str = "") -> None:
    """将 dict 列表写入 CSV，使用 utf-8-sig 编码（Excel 可直接打开）。"""
    if not records:
        # 即使为空，也写一个空文件（含表头）
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("")
        return

    fieldnames = list(records[0].keys())
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def run_dedup(
    file_a: str,
    file_b: str,
    output_dir: str,
    cb: Optional[TaskCallbacks] = None,
    prefer_a: bool = True,
) -> dict:
    """
    执行双文件合并去重，生成 4 份输出文件。

    Args:
        file_a:     CSV 文件 A 的路径
        file_b:     CSV 文件 B 的路径
        output_dir: 输出目录（不存在则自动创建）
        cb:         回调三件套；不传时使用 CLI 默认实现
        prefer_a:   True 时 A 字段优先（爬取时间相同时保留 A 的版本）

    Returns:
        dict: {
            "merged":    合并去重结果文件路径,
            "duplicates": 重复评论文件路径,
            "only_a":    A 独有评论文件路径,
            "only_b":    B 独有评论文件路径,
            "stats": {
                "count_a": int,
                "count_b": int,
                "merged":  int,
                "duplicates": int,
                "only_a": int,
                "only_b": int,
            }
        }

    Raises:
        FileNotFoundError: 输入文件不存在
        ValueError: 文件缺少必要列（rpid）
    """
    if cb is None:
        cb = make_cli_callbacks()

    # 参数校验
    if not os.path.exists(file_a):
        raise FileNotFoundError(f"文件 A 不存在：{file_a}")
    if not os.path.exists(file_b):
        raise FileNotFoundError(f"文件 B 不存在：{file_b}")

    os.makedirs(output_dir, exist_ok=True)

    # 1. 读取文件
    cb.log("INFO", f"读取文件 A：{os.path.basename(file_a)}")
    comments_a = _load_csv(file_a)
    cb.log("INFO", f"文件 A：{len(comments_a)} 条记录")

    if cb.is_aborted():
        cb.log("WARNING", "操作已中止")
        return {}

    cb.log("INFO", f"读取文件 B：{os.path.basename(file_b)}")
    comments_b = _load_csv(file_b)
    cb.log("INFO", f"文件 B：{len(comments_b)} 条记录")

    cb.progress(1, 5)

    # 2. 各自去重
    cb.log("INFO", "对文件 A 进行内部去重...")
    deduped_a, dup_a = _deduplicate_by_rpid(comments_a, "文件A")

    cb.log("INFO", "对文件 B 进行内部去重...")
    deduped_b, dup_b = _deduplicate_by_rpid(comments_b, "文件B")

    cb.progress(2, 5)

    # 3. 合并去重（A 在前，优先保留 A 的版本）
    cb.log("INFO", "合并两个文件并去重...")
    if prefer_a:
        combined = deduped_a + deduped_b
    else:
        combined = deduped_b + deduped_a
    merged, dup_merge = _deduplicate_by_rpid(combined, "合并")
    all_duplicates = dup_a + dup_b + dup_merge

    cb.progress(3, 5)

    # 4. 找出独有数据
    rpids_a = {str(c.get("rpid", "")).strip() for c in deduped_a}
    rpids_b = {str(c.get("rpid", "")).strip() for c in deduped_b}
    rpids_merged = {str(c.get("rpid", "")).strip() for c in merged}

    only_a = [c for c in deduped_a if str(c.get("rpid", "")).strip() not in rpids_b]
    only_b = [c for c in deduped_b if str(c.get("rpid", "")).strip() not in rpids_a]

    cb.progress(4, 5)

    # 5. 保存输出文件
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    merged_path     = os.path.join(output_dir, f"合并去重结果_{ts}.csv")
    dup_path        = os.path.join(output_dir, f"重复评论列表_{ts}.csv")
    only_a_path     = os.path.join(output_dir, f"A独有评论_{ts}.csv")
    only_b_path     = os.path.join(output_dir, f"B独有评论_{ts}.csv")

    _save_csv(merged,        merged_path,  "合并去重结果")
    _save_csv(all_duplicates, dup_path,    "重复评论列表")
    _save_csv(only_a,         only_a_path, "A独有评论")
    _save_csv(only_b,         only_b_path, "B独有评论")

    cb.progress(5, 5)

    stats = {
        "count_a":    len(comments_a),
        "count_b":    len(comments_b),
        "merged":     len(merged),
        "duplicates": len(all_duplicates),
        "only_a":     len(only_a),
        "only_b":     len(only_b),
    }

    cb.log("INFO", (
        f"去重完成：A={stats['count_a']} 条，B={stats['count_b']} 条，"
        f"合并={stats['merged']} 条，重复={stats['duplicates']} 条，"
        f"A独有={stats['only_a']} 条，B独有={stats['only_b']} 条"
    ))

    return {
        "merged":     merged_path,
        "duplicates": dup_path,
        "only_a":     only_a_path,
        "only_b":     only_b_path,
        "stats":      stats,
    }
