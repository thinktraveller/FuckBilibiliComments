#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评论时间精细统计工具（薄壳入口）

本脚本现在是一个轻量级入口，核心统计逻辑已迁移到：
    FuckBilibiliComments/services/stats_service.py
    FuckBilibiliComments/stats.py（generate_restructured_time_statistics）

功能：
    读取评论 CSV 文件，根据时间跨度自动选择统计粒度（天/小时/分钟），
    生成折线图和统计报告。

使用方法：
    直接双击运行（交互式），或：
    python 评论时间精细统计工具.py <CSV路径> [输出目录] [BV号]

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
    from FuckBilibiliComments.services.stats_service import run_stats
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
    print("评论时间精细统计工具")
    print("=" * 40)

    # 命令行参数模式
    if len(sys.argv) >= 2:
        csv_path = sys.argv[1]
        out_dir  = sys.argv[2] if len(sys.argv) >= 3 else os.path.dirname(csv_path) or "."
        bvid     = sys.argv[3] if len(sys.argv) >= 4 else None
    else:
        # 交互式输入
        print("\n请输入评论 CSV 文件路径。")
        print("提示：可将文件直接拖入此窗口获取路径。\n")

        while True:
            csv_path = input("CSV 文件路径：").strip().strip("\"'")
            if not csv_path:
                print("[ERROR] 路径不能为空")
                continue
            if not os.path.exists(csv_path):
                print(f"[ERROR] 文件不存在：{csv_path}")
                continue
            if not csv_path.lower().endswith(".csv"):
                print("[WARNING] 文件不是 .csv 格式，是否继续？(y/N) ", end="")
                if input().strip().lower() != "y":
                    continue
            break

        out_dir = input(
            f"输出目录（直接回车使用 CSV 文件所在目录）：\n  默认：{os.path.dirname(os.path.abspath(csv_path))}\n> "
        ).strip().strip("\"'")
        if not out_dir:
            out_dir = os.path.dirname(os.path.abspath(csv_path))

        bvid = input("BV 号（可选，用于获取视频发布时间，直接回车跳过）：").strip() or None

    # 执行统计
    print(f"\nCSV 文件：{csv_path}")
    print(f"输出目录：{out_dir}")
    if bvid:
        print(f"BV 号：{bvid}")
    print()

    cb = make_cli_callbacks()

    try:
        result = run_stats(
            csv_path=csv_path,
            output_dir=out_dir,
            cb=cb,
            bvid=bvid,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 统计过程中发生异常：{e}")
        sys.exit(1)

    if not result:
        print("[WARNING] 统计被中止")
        sys.exit(0)

    # 输出结果
    stats = result.get("stats", {})
    files = result.get("files", [])
    print("\n" + "=" * 40)
    print("统计完成！结果汇总：")
    print(f"  评论总数：{stats.get('count', 0)} 条")
    print(f"  时间跨度：{stats.get('time_span', '未知')}")
    print(f"  生成文件：{len(files)} 个")
    for f in files:
        print(f"    - {f}")
    print("=" * 40)

    input("\n按回车键退出...")


if __name__ == "__main__":
    main()
