#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性构建脚本：把 FuckBilibiliComments.py 切分为 FuckBilibiliComments/ 包。

策略：
1. 解析原文件，找出所有顶层 def/class/常量定义的行范围
2. 按预定义的 mapping 把每个定义分配到目标模块
3. 每个目标模块文件包含：公共 imports 头 + 该模块的定义切片
4. __init__.py 进行"命名空间注入"：把所有模块的顶层名字互相注入，
   保证函数体内的跨模块调用能找到符号（不改动原代码逻辑）
5. 顶层 FuckBilibiliComments.py 改为薄入口
"""

import re
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "FuckBilibiliComments.py.bak"
PKG = ROOT / "FuckBilibiliComments"

# ---- 模块分配表：name -> module_basename ----
ASSIGN = {
    # bootstrap
    "check_and_install_dependencies": "bootstrap",
    # tree
    "CommentTreeBuilder": "tree",
    # video / url parsing
    "extract_id_from_url": "video",
    "get_video_info_from_api": "video",
    "parse_video_input": "video",
    "get_video_info": "video",
    "get_video_title_quick": "video",
    "validate_bv": "video",
    # errors
    "CookieBannedException": "errors",
    "cleanup_output_files": "errors",
    "try_switch_to_next_cookie": "errors",
    "handle_cookie_banned_error": "errors",
    # config
    "load_config": "config",
    "select_account": "config",
    "add_new_account": "config",
    "save_config": "config",
    "get_request_headers": "config",
    # io_utils
    "generate_safe_filename": "io_utils",
    "create_output_folder": "io_utils",
    "setup_logging": "io_utils",
    "create_page_logger": "io_utils",
    "save_comments_to_csv": "io_utils",
    "prompt_delete_logs": "io_utils",
    # cli
    "get_user_input": "cli",
    # api
    "DEFAULT_HEADERS": "api",
    "get_response": "api",
    "generate_w_rid": "api",
    "get_bilibili_comments": "api",
    "get_all_sub_replies": "api",
    "get_additional_sub_replies": "api",
    # processing
    "process_comments_page": "processing",
    "process_single_comment": "processing",
    "process_reply_relationships": "processing",
    "process_and_organize_data": "processing",
    "sort_comments_by_popularity": "processing",
    "sort_comments_by_time": "processing",
    "merge_and_deduplicate_comments": "processing",
    "calculate_duplicate_rate": "processing",
    "perform_iteration_deduplication": "processing",
    # stats
    "generate_restructured_time_statistics": "stats",
    "generate_time_stats_by_granularity": "stats",
    "save_restructured_time_statistics": "stats",
    "generate_time_trend_chart": "stats",
    "generate_smart_time_statistics": "stats",
    "generate_statistics": "stats",
    # crawl
    "crawl_comprehensive_mode_comments": "crawl",
    "crawl_test_mode_comments": "crawl",
    "process_comprehensive_mode_data": "crawl",
    "crawl_all_comments_with_reason": "crawl",
    "crawl_all_comments": "crawl",
    "crawl_iteration_mode_comments": "crawl",
    "crawl_time_iteration": "crawl",
    "crawl_duplicate_rate_iteration": "crawl",
    "generate_iteration_statistics": "crawl",
    # reports
    "generate_folder_structure_md": "reports",
}

# 公共 imports（每个模块都加上）
COMMON_HEADER = '''# -*- coding: utf-8 -*-
"""
自动生成模块：由 _refactor_build.py 从 FuckBilibiliComments.py 切分而来。
"""
import sys
import subprocess
import importlib
import requests
import json
import csv
from datetime import datetime
import time
import hashlib
import re
import logging
import os
from collections import Counter, defaultdict
import shutil
import colorsys
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    pass
try:
    import pandas as pd
except ImportError:
    pass

'''


def parse_top_level(source: str):
    """返回 [(name, start_line, end_line)] 顶层定义列表（1-based, end inclusive）。"""
    lines = source.splitlines()
    # 匹配顶层 def/class/常量赋值（列 0 开头）
    pattern = re.compile(
        r"^(?:def\s+(\w+)|class\s+(\w+)|([A-Z_][A-Z_0-9]*)\s*=)"
    )
    starts = []
    for i, line in enumerate(lines, 1):
        m = pattern.match(line)
        if m:
            name = m.group(1) or m.group(2) or m.group(3)
            starts.append((name, i))

    defs = []
    for idx, (name, start) in enumerate(starts):
        end = starts[idx + 1][1] - 1 if idx + 1 < len(starts) else len(lines)
        defs.append((name, start, end))
    return defs, lines


def main():
    if not SRC.exists():
        raise SystemExit(f"找不到源文件：{SRC}")

    source = SRC.read_text(encoding="utf-8")
    defs, lines = parse_top_level(source)

    print(f"[INFO] 解析得到 {len(defs)} 个顶层定义")

    # 检查 ASSIGN 覆盖完整性
    found_names = {n for n, _, _ in defs}
    missing = found_names - set(ASSIGN.keys())
    extra = set(ASSIGN.keys()) - found_names
    if missing:
        print(f"[WARN] 未分配的顶层定义（将被忽略）: {missing}")
    if extra:
        print(f"[WARN] 分配表里多余的名字（不存在于源）: {extra}")

    # 按目标模块聚合定义
    mod_to_blocks: dict[str, list[tuple[int, int, str]]] = {}
    for name, start, end in defs:
        target = ASSIGN.get(name)
        if not target:
            continue
        block = "\n".join(lines[start - 1:end])
        mod_to_blocks.setdefault(target, []).append((start, end, block))

    # 准备包目录
    if PKG.exists():
        shutil.rmtree(PKG)
    PKG.mkdir()

    # 写每个模块
    for mod_name, blocks in mod_to_blocks.items():
        blocks.sort(key=lambda x: x[0])  # 保持源文件顺序
        body = "\n\n".join(b[2] for b in blocks)
        path = PKG / f"{mod_name}.py"
        path.write_text(COMMON_HEADER + body + "\n", encoding="utf-8")
        print(f"[OK] {path.name} ({sum(b[1]-b[0]+1 for b in blocks)} lines from source)")

    # 写 main.py：把原 __main__ 块 (line 5386+) 包成 main() 函数
    main_block_start = next(
        (i for i, line in enumerate(lines, 1) if line.startswith('if __name__ ==')),
        None
    )
    if main_block_start is None:
        raise SystemExit("找不到 __main__ 块")

    main_body_lines = lines[main_block_start:]  # 跳过 if __name__ 行本身
    # 去掉每行一层缩进（4 空格）
    dedented = []
    for ln in main_body_lines:
        if ln.startswith("    "):
            dedented.append(ln[4:])
        elif ln.strip() == "":
            dedented.append("")
        else:
            dedented.append(ln)
    main_body = "\n".join(dedented)

    main_module = COMMON_HEADER + f"""

def main():
{chr(10).join('    ' + ln if ln else '' for ln in dedented)}
"""
    (PKG / "main.py").write_text(main_module, encoding="utf-8")
    print(f"[OK] main.py")

    # 写 __init__.py：导入所有模块并互相注入名字
    modules_list = sorted(set(ASSIGN.values()) | {"main"})
    init_src = '''# -*- coding: utf-8 -*-
"""
FuckBilibiliComments 包初始化。

为保持原单文件的行为（所有顶层名字共享一个全局命名空间），
此文件在导入所有子模块后，把每个子模块的顶层名字互相注入，
使跨模块函数调用无需逐个 import。
"""
from . import ''' + ", ".join(modules_list) + '''

_modules = [''' + ", ".join(modules_list) + ''']

# 收集所有公开顶层名字
_shared = {}
for _m in _modules:
    for _name in dir(_m):
        if _name.startswith("_"):
            continue
        _shared[_name] = getattr(_m, _name)

# 注入到每个子模块的 globals
for _m in _modules:
    for _name, _obj in _shared.items():
        if not hasattr(_m, _name):
            setattr(_m, _name, _obj)

from .main import main  # noqa: E402
'''
    (PKG / "__init__.py").write_text(init_src, encoding="utf-8")
    print(f"[OK] __init__.py")

    # 顶层 FuckBilibiliComments.py 改为薄入口
    shim = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站评论爬取工具 - 薄入口

实际逻辑已拆分到 FuckBilibiliComments/ 包内。
保留此文件以兼容 `python FuckBilibiliComments.py` 的调用方式。
"""
import sys

if sys.version_info < (3, 7):
    print("[ERROR] 此脚本需要 Python 3.7 或更高版本")
    print(f"当前 Python 版本：{sys.version}")
    sys.exit(1)

# 依赖检测放在最前面，避免 import 包时缺依赖报错
from FuckBilibiliComments.bootstrap import check_and_install_dependencies
check_and_install_dependencies()

from FuckBilibiliComments import main

if __name__ == "__main__":
    main()
'''
    (ROOT / "FuckBilibiliComments.py").write_text(shim, encoding="utf-8")
    print(f"[OK] FuckBilibiliComments.py (shim)")


if __name__ == "__main__":
    main()
