#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构脚本（二期）：
1. 合并 cookie 相关代码到独立 cookie.py 模块
   - 原 config.py 的所有函数
   - 原 errors.py 的 try_switch_to_next_cookie
   - 原 api.py 的 DEFAULT_HEADERS（cookie 字段清空）
2. 用 AST 分析每个模块对兄弟模块顶层名字的引用
3. 在每个模块顶部生成显式 `from .X import Y` imports
4. 重写 __init__.py，去除名字注入

读取源：FuckBilibiliComments.py.bak（原始单文件）
"""

import ast
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "FuckBilibiliComments.py.bak"
PKG = ROOT / "FuckBilibiliComments"

# ---- 模块分配表 ----
ASSIGN = {
    # bootstrap
    "check_and_install_dependencies": "bootstrap",
    # tree
    "CommentTreeBuilder": "tree",
    # video
    "extract_id_from_url": "video",
    "get_video_info_from_api": "video",
    "parse_video_input": "video",
    "get_video_info": "video",
    "get_video_title_quick": "video",
    "validate_bv": "video",
    # errors（去除 cookie 切换相关）
    "CookieBannedException": "errors",
    "cleanup_output_files": "errors",
    "handle_cookie_banned_error": "errors",
    # cookie（新合并模块）
    "DEFAULT_HEADERS": "cookie",
    "load_config": "cookie",
    "save_config": "cookie",
    "select_account": "cookie",
    "add_new_account": "cookie",
    "get_request_headers": "cookie",
    "try_switch_to_next_cookie": "cookie",
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

STDLIB_HEADER = '''# -*- coding: utf-8 -*-
"""
自动生成模块：由 _refactor_explicit.py 从 FuckBilibiliComments.py 切分而来。
顶部 imports 由脚本计算，请勿手动编辑；如需更改请改 _refactor_explicit.py 后重跑。
"""
import sys
import subprocess
import importlib
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
    import requests
except ImportError:
    pass
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
    """用 AST 解析顶层 def/class/常量赋值。返回 [(name, start_line, end_line)]（1-based, inclusive）。

    跳过：顶层 If/Expr/Import 等"副作用"语句和 docstring。
    """
    tree = ast.parse(source)
    defs = []
    for node in tree.body:
        end = getattr(node, "end_lineno", node.lineno)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append((node.name, node.lineno, end))
        elif isinstance(node, ast.ClassDef):
            defs.append((node.name, node.lineno, end))
        elif isinstance(node, ast.Assign):
            # 仅捕获顶层常量赋值（单个全大写目标名）
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id.isupper()
            ):
                defs.append((node.targets[0].id, node.lineno, end))
        # 其余（Import、If、Expr 等）一律忽略
    return defs, source.splitlines()


def find_references(body: str) -> set[str]:
    """用 AST 找到模块体内所有 Name 引用。"""
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", body))
    refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs.add(node.id)
        elif isinstance(node, ast.Attribute):
            # capture root of attribute chain: a.b.c -> 'a'
            n = node
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                refs.add(n.id)
    return refs


def clear_cookie_field(body: str) -> str:
    """清空 DEFAULT_HEADERS 里的 Cookie 字段。

    Cookie 字符串里包含 `\\'` 转义引号，需用兼容转义的正则匹配单引号串。
    """
    pattern = r"'Cookie':\s*'(?:[^'\\]|\\.)*'"
    return re.sub(pattern, "'Cookie': ''", body, count=1)


def build_main_module(lines: list[str], defines_by_name: dict) -> tuple[str, set[str]]:
    """从原 __main__ 块构造 main() 函数体。返回 (function_source, names_referenced)。"""
    start = next(
        (i for i, ln in enumerate(lines, 1) if ln.startswith("if __name__ ==")),
        None,
    )
    if start is None:
        raise SystemExit("找不到 __main__ 块")
    body_lines = lines[start:]
    dedented = [ln[4:] if ln.startswith("    ") else ln for ln in body_lines]
    body = "\n".join(dedented)
    refs = find_references(body)
    indented = "\n".join("    " + ln if ln else "" for ln in dedented)
    func = "\ndef main():\n" + indented + "\n"
    return func, refs


def main():
    if not SRC.exists():
        raise SystemExit(f"找不到源文件：{SRC}")
    source = SRC.read_text(encoding="utf-8")
    defs, lines = parse_top_level(source)
    print(f"[INFO] 解析得到 {len(defs)} 个顶层定义")

    # 聚合 module -> [(start, end, name, body)]
    mod_blocks: dict[str, list[tuple[int, int, str, str]]] = {}
    for name, start, end in defs:
        target = ASSIGN.get(name)
        if not target:
            continue
        block = "\n".join(lines[start - 1:end])
        mod_blocks.setdefault(target, []).append((start, end, name, block))

    # 每模块定义的名字
    mod_defines = {m: {b[2] for b in bs} for m, bs in mod_blocks.items()}

    # 各模块体
    mod_bodies: dict[str, str] = {}
    for m, bs in mod_blocks.items():
        bs.sort(key=lambda x: x[0])
        mod_bodies[m] = "\n\n".join(b[3] for b in bs)

    # 处理 cookie 模块：清空 DEFAULT_HEADERS 的 Cookie 字段
    if "cookie" in mod_bodies:
        mod_bodies["cookie"] = clear_cookie_field(mod_bodies["cookie"])

    # 处理 main 模块（__main__ 包成 main()）
    main_func, main_refs = build_main_module(lines, mod_defines)
    mod_bodies["main"] = main_func
    mod_defines["main"] = {"main"}

    # name -> source module
    name_to_mod = {n: m for m, ns in mod_defines.items() for n in ns}

    # 每模块的跨模块引用
    mod_imports: dict[str, dict[str, list[str]]] = {}
    for m, body in mod_bodies.items():
        refs = find_references(body) if m != "main" else main_refs
        own = mod_defines[m]
        needed = {r for r in refs if r in name_to_mod and name_to_mod[r] != m}
        by_src: dict[str, list[str]] = {}
        for n in needed:
            src_mod = name_to_mod[n]
            by_src.setdefault(src_mod, []).append(n)
        mod_imports[m] = {k: sorted(v) for k, v in by_src.items()}

    # 输出每个模块
    PKG.mkdir(exist_ok=True)
    # 清空旧模块文件
    for old in PKG.glob("*.py"):
        old.unlink()
    if (PKG / "__pycache__").exists():
        shutil.rmtree(PKG / "__pycache__")

    for m, body in mod_bodies.items():
        path = PKG / f"{m}.py"
        imp_block_lines = ["", "# === 跨模块显式 imports（由 _refactor_explicit.py 生成）==="]
        for src_mod, names in sorted(mod_imports[m].items()):
            imp_block_lines.append(
                f"from .{src_mod} import " + ", ".join(names)
            )
        imp_block_lines.append("")
        header = STDLIB_HEADER + "\n".join(imp_block_lines) + "\n"

        # cookie 模块的注释说明
        extra_note = ""
        if m == "cookie":
            extra_note = (
                "\n# 本模块汇总所有 cookie 相关读写与调用：\n"
                "#   - DEFAULT_HEADERS: 兜底请求头（Cookie 字段须保持为空）\n"
                "#   - load_config / save_config / add_new_account: 配置文件读写\n"
                "#   - select_account: 多账户选择\n"
                "#   - get_request_headers: 由配置构造实际请求头\n"
                "#   - try_switch_to_next_cookie: 封禁时自动切换\n\n"
            )
        elif m == "bootstrap":
            extra_note = (
                "\n# 启动期依赖检测，仅由薄入口 FuckBilibiliComments.py 调用。\n\n"
            )

        path.write_text(header + extra_note + body + "\n", encoding="utf-8")
        print(f"[OK] {path.name}  defs={len(mod_defines[m])}  cross-imports="
              f"{sum(len(v) for v in mod_imports[m].values())}")

    # __init__.py：显式 import 所有子模块，导出 main
    all_mods = sorted(mod_bodies.keys())
    init_lines = [
        "# -*- coding: utf-8 -*-",
        '"""FuckBilibiliComments 包初始化。"""',
        "from . import " + ", ".join(all_mods),
        "from .main import main",
        "",
        "__all__ = [\"main\"]",
        "",
    ]
    (PKG / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8")
    print("[OK] __init__.py")

    # 顶层薄入口
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

from FuckBilibiliComments.bootstrap import check_and_install_dependencies
check_and_install_dependencies()

from FuckBilibiliComments import main

if __name__ == "__main__":
    main()
'''
    (ROOT / "FuckBilibiliComments.py").write_text(shim, encoding="utf-8")
    print("[OK] FuckBilibiliComments.py (shim)")

    # 输出依赖图，便于排查循环
    print("\n[INFO] 模块依赖图（A -> B 表示 A 引用 B 的符号）:")
    for m in sorted(mod_imports):
        deps = sorted(mod_imports[m].keys())
        print(f"  {m} -> {deps}")


if __name__ == "__main__":
    main()
