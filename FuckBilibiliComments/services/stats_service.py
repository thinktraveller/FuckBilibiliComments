# -*- coding: utf-8 -*-
"""
时间统计服务层

封装"对已有 CSV 文件进行时间统计并生成图表"的完整流程。
供 GUI 的 StatsWorker 和 tools/评论时间精细统计工具.py 调用。

主要函数：
    run_stats(csv_path, output_dir, granularity, cb, bvid, video_publish_timestamp) -> dict
"""

import csv
import os
from datetime import datetime, timedelta
from collections import Counter
from typing import Optional, List

from ..callbacks import TaskCallbacks, make_cli_callbacks
from ..stats import generate_restructured_time_statistics

try:
    import matplotlib
    matplotlib.use("Agg")  # 非 GUI 环境安全
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    _HAS_MATPLOTLIB = True
except ImportError:
    _HAS_MATPLOTLIB = False


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _load_comments_from_csv(path: str) -> list:
    """
    读取 CSV 文件，返回包含"发布时间"和"时间戳"字段的评论列表。
    兼容 utf-8-sig / utf-8 / gbk 编码。
    """
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                comments = []
                for row in reader:
                    # 统一时间字段
                    time_str = (
                        row.get("发布时间") or
                        row.get("评论发布时间") or
                        row.get("时间") or
                        row.get("发表时间") or
                        ""
                    ).strip()
                    if not time_str or time_str == "未知时间":
                        continue
                    try:
                        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        row["发布时间"] = time_str
                        row["时间戳"]   = int(dt.timestamp())
                        comments.append(row)
                    except ValueError:
                        continue
                return comments
        except (UnicodeDecodeError, Exception):
            continue
    return []


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def run_stats(
    csv_path: str,
    output_dir: str,
    cb: Optional[TaskCallbacks] = None,
    bvid: Optional[str] = None,
    video_publish_timestamp: Optional[int] = None,
    video_title: Optional[str] = None,
    video_info: Optional[dict] = None,
) -> dict:
    """
    对指定 CSV 文件执行时间统计，生成图表文件。

    核心统计逻辑复用 stats.generate_restructured_time_statistics()。
    该函数根据时间跨度自动选择天/小时/分钟粒度并生成多个文件。

    Args:
        csv_path:               评论 CSV 文件路径
        output_dir:             输出目录
        cb:                     回调三件套；不传时使用 CLI 默认实现
        bvid:                   视频 BV 号（用于获取发布时间）
        video_publish_timestamp: 视频发布时间戳；提供则跳过 API 请求
        video_title:            视频标题（用于图表标注）
        video_info:             完整视频信息字典（含 pubdate 等）

    Returns:
        dict: {
            "files":  生成的文件路径列表,
            "stats": {
                "count":      评论总数,
                "time_span":  时间跨度描述字符串,
            }
        }

    Raises:
        FileNotFoundError: CSV 文件不存在
        ValueError: CSV 文件中无有效时间数据
    """
    if cb is None:
        cb = make_cli_callbacks()

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV 文件不存在：{csv_path}")

    os.makedirs(output_dir, exist_ok=True)

    # 1. 读取评论
    cb.log("INFO", f"读取文件：{os.path.basename(csv_path)}")
    comments = _load_comments_from_csv(csv_path)

    if not comments:
        raise ValueError("CSV 文件中未找到有效时间数据（需要包含'发布时间'列且格式为 YYYY-MM-DD HH:MM:SS）")

    cb.log("INFO", f"成功读取 {len(comments)} 条有效评论")
    cb.progress(1, 3)

    if cb.is_aborted():
        cb.log("WARNING", "操作已中止")
        return {}

    # 2. 构造 video_info（如果没提供但有 publish_timestamp）
    if video_info is None and video_publish_timestamp:
        video_info = {"pubdate": video_publish_timestamp, "bvid": bvid or ""}

    # 3. 调用核心统计函数
    cb.log("INFO", "开始生成时间统计图表...")
    try:
        generated_files = generate_restructured_time_statistics(
            all_comments=comments,
            output_folder=output_dir,
            bvid=bvid,
            logger=None,            # 通过 cb.log 输出，不再传 logger
            video_title=video_title,
            video_info=video_info,
        )
    except Exception as e:
        cb.log("ERROR", f"时间统计失败：{e}")
        raise

    cb.progress(3, 3)

    # 统计时间跨度
    timestamps = [c.get("时间戳", 0) for c in comments if c.get("时间戳")]
    if timestamps:
        span_seconds = max(timestamps) - min(timestamps)
        span_days    = span_seconds // 86400
        time_span    = f"{span_days} 天" if span_days else f"{span_seconds // 3600} 小时"
    else:
        time_span = "未知"

    file_count = len(generated_files) if generated_files else 0
    cb.log("INFO", f"统计完成，生成 {file_count} 个文件，评论时间跨度：{time_span}")

    return {
        "files": generated_files or [],
        "stats": {
            "count":     len(comments),
            "time_span": time_span,
        },
    }
