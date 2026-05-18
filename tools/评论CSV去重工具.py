#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评论 CSV 去重工具（薄壳入口）

本脚本现在是一个轻量级入口，核心去重逻辑已迁移到：
    FuckBilibiliComments/services/dedup_service.py

功能：
    合并去重两个评论 CSV 文件（基于 rpid + 爬取时间），生成：
    - 合并去重结果
    - 重复评论列表
    - A 独有评论
    - B 独有评论

使用方法：
    直接双击运行（交互式），或：
    python 评论CSV去重工具.py <文件A> <文件B> [输出目录]

Python 版本要求：3.9+
"""

import sys
import os

# ---------------------------------------------------------------------------
# 路径修正：使项目根目录可导入
# ---------------------------------------------------------------------------
_HERE    = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

# ---------------------------------------------------------------------------
# 导入服务层
# ---------------------------------------------------------------------------
try:
    from FuckBilibiliComments.services.dedup_service import run_dedup
    from FuckBilibiliComments.callbacks import make_cli_callbacks
except ImportError as _e:
    print(f"[ERROR] 无法导入核心模块：{_e}")
    print("请确认在项目根目录（FuckBilibiliComments 文件夹的父目录）中运行本脚本，")
    print("且已安装所有依赖（pip install -r requirements.txt）")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main() -> None:
    print("CSV 文件去重工具")
    print("=" * 40)

    # 命令行参数模式
    if len(sys.argv) >= 3:
        file_a   = sys.argv[1]
        file_b   = sys.argv[2]
        out_dir  = sys.argv[3] if len(sys.argv) >= 4 else os.path.dirname(file_a) or "."
    else:
        # 交互式输入
        print("\n请输入要去重的两个 CSV 文件路径。")
        print("提示：可将文件直接拖入此窗口获取路径。\n")

        while True:
            file_a = input("文件 A 路径：").strip().strip("\"'")
            if not file_a:
                print("[ERROR] 路径不能为空")
                continue
            if not os.path.exists(file_a):
                print(f"[ERROR] 文件不存在：{file_a}")
                continue
            break

        while True:
            file_b = input("文件 B 路径：").strip().strip("\"'")
            if not file_b:
                print("[ERROR] 路径不能为空")
                continue
            if not os.path.exists(file_b):
                print(f"[ERROR] 文件不存在：{file_b}")
                continue
            break

        out_dir = input(
            f"输出目录（直接回车使用文件 A 所在目录）：\n  默认：{os.path.dirname(os.path.abspath(file_a))}\n> "
        ).strip().strip("\"'")
        if not out_dir:
            out_dir = os.path.dirname(os.path.abspath(file_a))

    # 执行去重
    print(f"\n文件 A：{file_a}")
    print(f"文件 B：{file_b}")
    print(f"输出目录：{out_dir}\n")

    cb = make_cli_callbacks()

    try:
        result = run_dedup(file_a, file_b, out_dir, cb=cb)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 去重过程中发生异常：{e}")
        sys.exit(1)

    if not result:
        print("[WARNING] 去重被中止，未生成输出文件")
        sys.exit(0)

    # 输出结果
    stats = result.get("stats", {})
    print("\n" + "=" * 40)
    print("去重完成！结果汇总：")
    print(f"  文件 A：{stats.get('count_a', 0)} 条")
    print(f"  文件 B：{stats.get('count_b', 0)} 条")
    print(f"  合并去重结果：{stats.get('merged', 0)} 条  ->  {result.get('merged', '')}")
    print(f"  重复评论列表：{stats.get('duplicates', 0)} 条  ->  {result.get('duplicates', '')}")
    print(f"  A 独有评论：  {stats.get('only_a', 0)} 条  ->  {result.get('only_a', '')}")
    print(f"  B 独有评论：  {stats.get('only_b', 0)} 条  ->  {result.get('only_b', '')}")
    print("=" * 40)

    input("\n按回车键退出...")


if __name__ == "__main__":
    main()
