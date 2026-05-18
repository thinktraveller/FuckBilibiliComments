# -*- coding: utf-8 -*-
"""
回调接口抽象模块

定义 TaskCallbacks 数据类，统一 CLI 和 GUI 之间的交互接口。
核心业务层（crawl.py / processing.py / stats.py 等）不依赖任何 UI 库，
所有进度汇报、日志输出、用户询问均通过此回调进行。

用法：
    CLI：使用 make_cli_callbacks() 生成默认回调，内部调用 print / input
    GUI：由 QThread Worker 注入信号 emit 版本的回调
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class TaskCallbacks:
    """
    任务回调三件套，所有核心业务函数均以此对象作为统一通信接口。

    Attributes:
        log:        (level: str, msg: str) -> None
                    level 取值：'DEBUG' / 'INFO' / 'WARNING' / 'ERROR'
        progress:   (current: int, total: int) -> None
                    current == total 时表示完成；total == 0 表示不确定进度
        prompt:     (question: str) -> str
                    向用户询问确认或选项，返回用户答复字符串
                    CLI 实现调用 input()；GUI 实现弹出 QInputDialog
        is_aborted: () -> bool
                    业务层在每个页面/步骤结束后调用，返回 True 则优雅退出
    """
    log:        Callable[[str, str], None]
    progress:   Callable[[int, int], None]
    prompt:     Callable[[str], str]
    is_aborted: Callable[[], bool]


# ---------------------------------------------------------------------------
# CLI 默认实现
# ---------------------------------------------------------------------------

def _make_default_logger() -> logging.Logger:
    """返回一个向 stderr 输出的简单 logger，CLI 默认使用"""
    logger = logging.getLogger("FuckBilibiliComments.cli_callback")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger


def make_cli_callbacks(
    logger: Optional[logging.Logger] = None,
    silent: bool = False,
) -> TaskCallbacks:
    """
    构造 CLI 使用的默认回调实现。

    Args:
        logger:  可选的 logging.Logger；不传时自动创建一个向 stderr 输出的 logger
        silent:  为 True 时 log 回调不向 stdout/stderr 打印（仍写 logger）

    Returns:
        TaskCallbacks 实例
    """
    _logger = logger or _make_default_logger()

    def _log(level: str, msg: str) -> None:
        level_upper = level.upper()
        log_fn = {
            'DEBUG':   _logger.debug,
            'INFO':    _logger.info,
            'WARNING': _logger.warning,
            'ERROR':   _logger.error,
        }.get(level_upper, _logger.info)
        log_fn(msg)
        if not silent:
            # 向终端也输出一份，保留原有 CLI 体验
            prefix_map = {
                'DEBUG':   '[DEBUG]',
                'INFO':    '[INFO]',
                'WARNING': '[WARNING]',
                'ERROR':   '[ERROR]',
            }
            prefix = prefix_map.get(level_upper, '[INFO]')
            print(f"{prefix} {msg}")

    def _progress(current: int, total: int) -> None:
        if total > 0:
            pct = int(current / total * 100)
            _logger.debug(f"进度: {current}/{total} ({pct}%)")
        else:
            _logger.debug(f"进度: {current}/未知")

    def _prompt(question: str) -> str:
        return input(question)

    def _is_aborted() -> bool:
        return False  # CLI 模式不支持中止，始终返回 False

    return TaskCallbacks(
        log=_log,
        progress=_progress,
        prompt=_prompt,
        is_aborted=_is_aborted,
    )


# ---------------------------------------------------------------------------
# 空操作（测试用）
# ---------------------------------------------------------------------------

def make_noop_callbacks() -> TaskCallbacks:
    """
    构造什么都不做的回调实现，主要用于单元测试。
    """
    return TaskCallbacks(
        log=lambda level, msg: None,
        progress=lambda current, total: None,
        prompt=lambda question: "",
        is_aborted=lambda: False,
    )
