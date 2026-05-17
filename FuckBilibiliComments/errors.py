# -*- coding: utf-8 -*-
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

# === 跨模块显式 imports（由 _refactor_explicit.py 生成）===
from .cookie import try_switch_to_next_cookie

class CookieBannedException(Exception):
    """Cookie被封禁时抛出的异常"""
    pass

def cleanup_output_files(output_folder, logger=None):
    """
    清理输出文件夹中的所有文件
    
    Args:
        output_folder (str): 输出文件夹路径
        logger: 日志记录器
    """
    try:
        if os.path.exists(output_folder):
            # 删除整个输出文件夹
            shutil.rmtree(output_folder)
            if logger:
                logger.info(f"已删除输出文件夹: {output_folder}")
            print(f"🗑️  已删除所有输出文件: {output_folder}")
        else:
            if logger:
                logger.warning(f"输出文件夹不存在: {output_folder}")
            print(f"[WARNING] 输出文件夹不存在: {output_folder}")
    except Exception as e:
        if logger:
            logger.error(f"删除输出文件失败: {e}")
        print(f"❌ 删除输出文件失败: {e}")

def handle_cookie_banned_error(output_folder, logger=None, auto_switch=True):
    """
    处理Cookie被封禁的错误
    
    Args:
        output_folder (str): 输出文件夹路径
        logger: 日志记录器
        auto_switch (bool): 是否尝试自动切换cookie
    
    Returns:
        dict: 如果成功切换cookie则返回新的配置，否则返回None
    """
    print("\n" + "="*60)
    print("🚫 检测到Cookie被暂时封禁（412错误）")
    print("="*60)
    
    if auto_switch:
        print("\n🔄 尝试自动切换到其他可用账号...")
        new_config = try_switch_to_next_cookie(logger)
        
        if new_config:
            print("✅ Cookie切换成功，继续爬取...")
            if logger:
                logger.info("Cookie自动切换成功，继续执行爬取任务")
            return new_config
        else:
            print("❌ 没有其他可用的账号配置")
    
    print("\n📋 错误说明:")
    print("   当前使用的Cookie已被B站暂时封禁（412错误）")
    print("   这通常是由于请求频率过高或其他反爬机制触发")
    
    print("\n🔧 解决方案:")
    print("   1. 添加更多账号配置（推荐）")
    print("      - 重新登录B站获取新的Cookie")
    print("      - 在config.json中添加多个账号配置")
    print("   2. 等待一段时间后重试")
    print("      - 建议等待30分钟到2小时")
    print("      - 下次运行时适当延长等待时间")
    
    print("\n[WARNING] 建议措施:")
    print("   - 增加请求间隔时间（delay_ms参数）")
    print("   - 避免短时间内频繁运行脚本")
    print("   - 配置多个不同的账号Cookie轮换使用")
    
    # 清理已生成的文件
    print("\n🗑️  正在清理已生成的文件...")
    cleanup_output_files(output_folder, logger)
    
    print("\n" + "="*60)
    print("程序已安全退出，请按照上述建议处理后重试")
    print("="*60)
    
    return None
