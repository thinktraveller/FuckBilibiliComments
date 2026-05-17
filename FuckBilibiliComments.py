#!/usr/bin/env python3
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
