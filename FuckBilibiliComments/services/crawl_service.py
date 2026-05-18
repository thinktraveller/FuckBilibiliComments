# -*- coding: utf-8 -*-
"""
爬取服务层

封装"从 BV 号/URL 到完整爬取结果"的流程编排，供 GUI 的 CrawlWorker 和 CLI 的 main.py 调用。
核心业务函数（crawl.py / processing.py 等）均通过 TaskCallbacks 汇报进度与日志。

主要函数：
    resolve_video(bv_or_url)        -> (oid, bv_id, video_info)
    run_crawl(params, cb)           -> dict
"""

import os
from typing import Optional, Tuple

from ..callbacks import TaskCallbacks, make_cli_callbacks
from ..cookie import get_request_headers, load_config
from ..errors import CookieBannedException, handle_cookie_banned_error
from ..io_utils import create_output_folder, setup_logging
from ..processing import process_and_organize_data
from ..reports import generate_folder_structure_md
from ..stats import generate_restructured_time_statistics
from ..video import parse_video_input, get_video_info, get_video_info_from_api, get_video_title_quick
from ..crawl import (
    crawl_comprehensive_mode_comments,
    crawl_iteration_mode_comments,
    process_comprehensive_mode_data,
)


# ---------------------------------------------------------------------------
# 视频解析
# ---------------------------------------------------------------------------

def resolve_video(bv_or_url: str) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    """
    解析 BV 号或视频 URL，返回 (oid, bv_id, video_info)。

    Args:
        bv_or_url: BV 号（如 BV1xx...）或完整视频 URL

    Returns:
        (oid: str | None, bv_id: str | None, video_info: dict | None)
        解析失败时三者均为 None
    """
    try:
        result = parse_video_input(bv_or_url.strip())
        if result is None:
            return None, None, None
        oid, video_info = result
        bv_id = video_info.get("bvid") if video_info else None
        if not bv_id:
            # 回退：从 oid(av) 转 bvid
            temp = get_video_info_from_api(str(oid), "av")
            bv_id = temp.get("bvid") if temp else None
        return str(oid), bv_id, video_info
    except Exception:
        return None, None, None


# ---------------------------------------------------------------------------
# 爬取参数数据结构
# ---------------------------------------------------------------------------

class CrawlParams:
    """
    爬取参数容器，供 CLI / GUI 统一构造后传给 run_crawl。

    Attributes:
        oid              视频 av id（字符串）
        bv_id            视频 BV 号
        video_info       视频信息字典
        video_title      视频标题
        mode             爬取模式：'comprehensive' / 'iteration'
        ps               每页数量（固定 20）
        delay_ms         请求延时（毫秒）
        request_headers  完整请求头字典
        output_dir       指定输出目录；为 None 时自动生成
        iteration_config 迭代模式配置字典（仅 mode=='iteration' 时有效）
    """

    def __init__(
        self,
        oid: str,
        bv_id: str,
        video_info: Optional[dict] = None,
        video_title: Optional[str] = None,
        mode: str = "comprehensive",
        ps: int = 20,
        delay_ms: int = 3000,
        request_headers: Optional[dict] = None,
        output_dir: Optional[str] = None,
        iteration_config: Optional[dict] = None,
    ):
        self.oid              = oid
        self.bv_id            = bv_id
        self.video_info       = video_info or {}
        self.video_title      = video_title or bv_id
        self.mode             = mode
        self.ps               = ps
        self.delay_ms         = delay_ms
        self.request_headers  = request_headers or {}
        self.output_dir       = output_dir
        self.iteration_config = iteration_config or {}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_crawl(params: CrawlParams, cb: Optional[TaskCallbacks] = None) -> dict:
    """
    执行一次完整爬取任务。

    Args:
        params: CrawlParams 实例
        cb:     回调三件套；不传时使用 CLI 默认实现

    Returns:
        dict: {
            "success":    bool,
            "output_dir": str,
            "mode":       str,
            "stats": {
                "comments":    int,   # 最终唯一评论数
                "pages":       int,   # 爬取页数（综合/测试）
            },
            "error_msg":  str | None,
        }

    Note:
        该函数不会调用 sys.exit()，所有错误通过返回值和 cb.log 汇报。
        CookieBannedException 由此函数内部捕获并在返回值中体现。
    """
    if cb is None:
        cb = make_cli_callbacks()

    result = {
        "success":    False,
        "output_dir": "",
        "mode":       params.mode,
        "stats":      {"comments": 0, "pages": 0},
        "error_msg":  None,
    }

    try:
        # 确定 mode_type（用于文件夹命名）
        mode_type = _get_mode_type(params)

        # 创建输出目录
        if params.output_dir:
            output_folder = params.output_dir
            os.makedirs(output_folder, exist_ok=True)
        else:
            output_folder = create_output_folder(params.bv_id, params.video_title, mode_type)

        result["output_dir"] = output_folder
        cb.log("INFO", f"输出目录：{output_folder}")

        # 设置日志
        logger, _ = setup_logging(params.bv_id, output_folder)

        # 分发到各模式
        if params.mode == "comprehensive":
            _run_comprehensive(params, output_folder, logger, cb, result)
        elif params.mode == "iteration":
            _run_iteration(params, output_folder, logger, cb, result)
        else:
            raise ValueError(f"不支持的爬取模式：{params.mode}")

    except CookieBannedException as e:
        msg = f"Cookie 被封禁：{e}"
        cb.log("ERROR", msg)
        result["error_msg"] = msg
        result["success"]   = False
    except Exception as e:
        msg = f"爬取异常：{e}"
        cb.log("ERROR", msg)
        result["error_msg"] = msg
        result["success"]   = False

    return result


# ---------------------------------------------------------------------------
# 各模式内部实现
# ---------------------------------------------------------------------------

def _get_mode_type(params: CrawlParams) -> str:
    if params.mode == "iteration":
        it_type = params.iteration_config.get("type", "time")
        return "iteration_time" if it_type == "time" else "iteration_rate"
    return "comprehensive"


def _run_comprehensive(params, output_folder, logger, cb, result):
    """综合模式爬取流程。"""
    cb.log("INFO", "启动综合模式爬取")

    crawl_result = crawl_comprehensive_mode_comments(
        oid=params.oid,
        bv_id=params.bv_id,
        ps=params.ps,
        delay_ms=params.delay_ms,
        test_mode=False,
        logger=logger,
        output_folder=output_folder,
        request_headers=params.request_headers,
    )

    if not crawl_result:
        raise RuntimeError("综合模式爬取返回空结果")

    pop_comments, time_comments, merged, duplicates, end_reason = crawl_result
    cb.log("INFO", f"热度爬取结束原因：{end_reason}，合并后 {len(merged)} 条唯一评论")

    # 生成原始数据文档
    raw_data_folder, doc_paths = process_comprehensive_mode_data(
        params.oid, params.bv_id,
        pop_comments, time_comments, merged, duplicates,
        output_folder, logger, params.video_title,
    )

    # 双重整理
    cb.log("INFO", "按热度排序整理数据...")
    _, _, stats_file = process_and_organize_data(
        merged, output_folder, params.bv_id, logger,
        params.video_title, sort_by_popularity=True,
        video_info=params.video_info, mode="comprehensive", generate_stats=True,
    )

    # 时间统计
    cb.log("INFO", "生成时间统计分析...")
    time_files = generate_restructured_time_statistics(
        merged, output_folder, params.bv_id, logger,
        params.video_title, params.video_info,
    )
    if time_files:
        cb.log("INFO", f"生成 {len(time_files)} 个时间统计文件")

    # 文件夹结构文档
    generate_folder_structure_md(output_folder, params.oid, params.video_title, logger, params.bv_id)

    result["success"]           = True
    result["stats"]["comments"] = len(merged)
    cb.log("INFO", "爬取任务已结束！")


def _run_iteration(params, output_folder, logger, cb, result):
    """迭代模式爬取流程。"""
    cb.log("INFO", "启动迭代模式爬取")

    ok = crawl_iteration_mode_comments(
        oid=params.oid,
        bv_id=params.bv_id,
        ps=params.ps,
        delay_ms=params.delay_ms,
        iteration_config=params.iteration_config,
        logger=logger,
        output_folder=output_folder,
        video_title=params.video_title,
        video_info=params.video_info,
        request_headers=params.request_headers,
    )

    result["success"] = bool(ok)
    if ok:
        cb.log("INFO", "迭代模式爬取完成")
    else:
        raise RuntimeError("迭代模式爬取失败")
