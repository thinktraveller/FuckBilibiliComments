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
from .video import extract_id_from_url, get_video_title_quick, parse_video_input, validate_bv

def get_user_input():
    """
    获取用户输入的B站视频网址，提取BV号并转换为oid
    
    Returns:
        tuple: (oid, mode, ps, delay_ms, max_pages, test_sort_mode, iteration_config) 或 (None, None, None, None, None, None, None) 如果输入无效
    """
    print("=== B站评论爬虫 ===")
    print("支持综合模式、测试模式和迭代模式")
    print()
    print("请输入B站视频网址，程序将自动提取其中的BV号")
    print("示例：https://www.bilibili.com/video/BV1kJ411N7AB")
    print()
    
    # 获取视频网址并转换为oid
    video_input = input("请输入B站视频网址: ").strip()
    
    if not video_input:
        print("❌ 输入不能为空")
        print("程序退出")
        return None, None, None, None, None, None, None
    
    # 解析用户输入的网址
    result = parse_video_input(video_input)
    
    if result is None:
        print(f"❌ 输入网址错误: {video_input}")
        print("未能在网址中找到合法的BV号")
        print("BV号格式要求：BV + 10位数字和字母组合（不包含斜杠等特殊符号）")
        print("程序退出")
        return None, None, None, None, None, None, None
    
    oid, video_info = result
    
    # 显示转换结果
    id_type, bv_id = extract_id_from_url(video_input)
    
    # 验证BV号是否有效
    if not bv_id or not validate_bv(bv_id):
        print(f"❌ BV号格式无效: {bv_id}")
        print("程序退出")
        return None, None, None, None, None, None, None
    
    if id_type == 'bv':
        print(f"✅ 网址解析成功: {bv_id} → oid: {oid}")
    
    # 显示视频信息并让用户确认
    print("\n🔍 视频信息获取完成")
    try:
        # 使用已获取的视频信息
        if video_info and video_info.get('title'):
            video_title = video_info['title']
            print(f"📺 视频标题: {video_title}")
            
            # 让用户确认视频信息
            while True:
                confirm = input("\n请确认这是您要爬取的视频吗？(y/n，直接回车默认确认): ").strip().lower()
                if not confirm or confirm in ['y', 'yes', '是']:
                    print("✅ 视频信息确认完成")
                    break
                elif confirm in ['n', 'no', '否']:
                    print("❌ 用户取消操作")
                    print("程序退出")
                    return None, None, None, None, None, None, None, video_info
                else:
                    print("❌ 请输入 y 或 n")
        else:
            # 如果通过API获取的信息不完整，尝试只获取标题
            video_title = get_video_title_quick(bv_id)
            if video_title:
                print(f"📺 视频标题: {video_title}")
                print("[WARNING] 无法获取完整视频信息，但将继续执行爬取")
                
                # 让用户确认视频信息
                while True:
                    confirm = input("\n请确认这是您要爬取的视频吗？(y/n，直接回车默认确认): ").strip().lower()
                    if not confirm or confirm in ['y', 'yes', '是']:
                        print("✅ 视频信息确认完成")
                        break
                    elif confirm in ['n', 'no', '否']:
                        print("❌ 用户取消操作")
                        print("程序退出")
                        return None, None, None, None, None, None, None, video_info
                    else:
                        print("❌ 请输入 y 或 n")
            else:
                print("❌ 无法获取视频标题，程序终止")
                print("程序退出")
                return None, None, None, None, None, None, None, video_info
            
    except Exception as e:
        print(f"❌ 显示视频信息失败: {e}")
        print("❌ 程序终止")
        print("程序退出")
        return None, None, None, None, None, None, None, None
    
    # 选择爬取模式
    print("\n请选择爬取模式：")
    print("系统基于热度爬取和时间爬取两种基础功能，提供以下三种运行方式：")
    print("1. 综合模式 - 先进行热度爬取，再进行时间爬取，自动去重优化，可爬取上限在15000条左右")
    print("2. 测试模式 - 单独测试热度或时间爬取功能，可自定义参数")
    print("3. 迭代模式 - 优先用于新发出的、且评论数很可能超过15000条的视频，持续追踪新评论的出现并迭代评论数据，以热度爬取-时间爬取进行循环，可自定义迭代时间或最高重复率（当新一轮评论与上一轮评论的重复率高于设定重复率时停止迭代）")
    
    iteration_config = None  # 初始化迭代配置
    
    while True:
        mode_choice = input("请选择模式 (1/2/3，直接回车默认选择1): ").strip()
        
        if not mode_choice or mode_choice == '1':
            # 综合模式
            mode = 'comprehensive'
            mode_name = "综合模式"
            max_pages = None
            test_sort_mode = None
            print(f"\n✅ 使用{mode_name}：智能组合热度和时间爬取，基于rpid和时间戳去重")
            break
        elif mode_choice == '2':
            # 测试模式
            mode = 'test'
            mode_name = "测试模式"
            
            # 选择基础爬取功能
            print("\n请选择要测试的基础爬取功能：")
            print("1. 热度爬取 - 按点赞数排序获取热门评论")
            print("2. 时间爬取 - 按发布时间排序获取最新评论")
            
            while True:
                sort_choice = input("请选择排序方式 (1/2): ").strip()
                if sort_choice == '1':
                    test_sort_mode = 1  # 热度排序
                    sort_name = "热度爬取"
                    break
                elif sort_choice == '2':
                    test_sort_mode = 0  # 时间排序
                    sort_name = "时间爬取"
                    break
                else:
                    print("❌ 请输入1或2")
            
            # 设置爬取页数
            while True:
                pages_input = input("请输入要爬取的页数（1-50，直接回车默认5页）: ").strip()
                
                if not pages_input:
                    max_pages = 5
                    break
                
                try:
                    max_pages = int(pages_input)
                    if max_pages < 1:
                        print("❌ 页数不能小于1，请重新输入")
                        continue
                    elif max_pages > 50:
                        print("❌ 页数不能超过50，请重新输入")
                        continue
                    break
                except ValueError:
                    print("❌ 请输入有效的数字")
            
            print(f"\n✅ 使用{mode_name}：单独测试{sort_name}功能，爬取{max_pages}页")
            break
        elif mode_choice == '3':
            # 迭代模式
            mode = 'iteration'
            mode_name = "迭代模式"
            max_pages = None
            test_sort_mode = None
            
            # 选择迭代策略
            print("\n请选择迭代策略：")
            print("1. 时间迭代 - 在指定时间内交替执行热度和时间爬取")
            print("2. 重复率迭代 - 基于重复率阈值自动停止交替爬取")
            
            while True:
                iteration_type_choice = input("请选择迭代类型 (1/2): ").strip()
                if iteration_type_choice == '1':
                    # 时间迭代
                    iteration_type = 'time'
                    
                    while True:
                        time_input = input("请输入迭代时间（小时，建议1-24小时）: ").strip()
                        try:
                            iteration_hours = float(time_input)
                            if iteration_hours <= 0:
                                print("❌ 迭代时间必须大于0，请重新输入")
                                continue
                            elif iteration_hours > 72:
                                print("❌ 迭代时间过长（超过72小时），请重新输入")
                                continue
                            break
                        except ValueError:
                            print("❌ 请输入有效的数字")
                    
                    iteration_config = {
                        'type': 'time',
                        'hours': iteration_hours
                    }
                    print(f"\n✅ 使用{mode_name}：时间迭代，持续{iteration_hours}小时")
                    break
                    
                elif iteration_type_choice == '2':
                    # 重复率迭代
                    iteration_type = 'duplicate_rate'
                    
                    # 获取热度爬取重复率阈值
                    while True:
                        hot_rate_input = input("请输入热度爬取重复率阈值（0-100%，建议85-95）: ").strip()
                        try:
                            hot_duplicate_rate = float(hot_rate_input)
                            if hot_duplicate_rate <= 0 or hot_duplicate_rate >= 100:
                                print("❌ 重复率必须大于0且小于100，请重新输入")
                                continue
                            break
                        except ValueError:
                            print("❌ 请输入有效的数字")
                    
                    # 获取时间爬取重复率阈值
                    while True:
                        time_rate_input = input("请输入时间爬取重复率阈值（0-100%，建议60-80）: ").strip()
                        try:
                            time_duplicate_rate = float(time_rate_input)
                            if time_duplicate_rate <= 0 or time_duplicate_rate >= 100:
                                print("❌ 重复率必须大于0且小于100，请重新输入")
                                continue
                            break
                        except ValueError:
                            print("❌ 请输入有效的数字")
                    
                    iteration_config = {
                        'type': 'duplicate_rate',
                        'hot_rate_threshold': hot_duplicate_rate,
                        'time_rate_threshold': time_duplicate_rate
                    }
                    print(f"\n✅ 使用{mode_name}：重复率迭代，热度阈值{hot_duplicate_rate}%，时间阈值{time_duplicate_rate}%")
                    break
                else:
                    print("❌ 请输入1或2")
            break
        else:
            print("❌ 请输入1、2或3")
    
    # 使用固定的每页评论数量
    ps = 20  # 固定使用20作为每页评论数量
    print(f"\n✅ 每页评论数量已设置为: {ps}")
    
    # 获取延时设置
    print("\n请设置请求延时（防止被限制）：")
    while True:
        delay_input = input("请输入每次请求后的等待时间（秒，建议1-5秒，直接回车使用默认3秒）: ").strip()
        
        if not delay_input:  # 使用默认值
            delay_seconds = 3
            break
        
        try:
            delay_seconds = float(delay_input)
            if delay_seconds < 0:
                print("❌ 延时不能为负数，请重新输入")
                continue
            elif delay_seconds > 30:
                print("❌ 延时过长（超过30秒），请重新输入")
                continue
            break
        except ValueError:
            print("❌ 请输入有效的数字")
    
    # 转换为毫秒供内部使用
    delay_ms = int(delay_seconds * 1000)
    
    print(f"\n✅ 配置完成！oid: {oid}, 排序: {mode_name}, 每页数量: {ps}, 延时: {delay_seconds}秒")
    print(f"开始爬取评论...\n")
    
    # 获取视频标题用于文件命名
    video_title = None
    try:
        video_title = get_video_title_quick(bv_id)
    except:
        pass  # 如果获取失败，使用默认命名
    
    return oid, mode, ps, delay_ms, max_pages, test_sort_mode, iteration_config, video_title, video_info
