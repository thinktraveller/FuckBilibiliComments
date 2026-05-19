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

def generate_safe_filename(video_title, bv_id, suffix="", file_type="original"):
    """
    生成安全的文件名，基于视频标题和时间戳
    
    Args:
        video_title (str): 视频标题
        bv_id (str): 视频BV号
        suffix (str): 文件名后缀
        file_type (str): 文件类型 - "original", "final", "stats", "log"
    
    Returns:
        str: 安全的文件名
    """
    # 使用YYYYMMDD格式的日期和HHMMSS格式的时间
    date_str = datetime.now().strftime('%Y%m%d')
    time_str = datetime.now().strftime('%H%M%S')
    
    if video_title:
        # 清理视频标题中的非法字符
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
        # 限制标题长度避免路径过长
        if len(safe_title) > 30:
            safe_title = safe_title[:30] + '...'
        
        # 根据文件类型生成不同的命名格式
        if file_type == "original":
            # 原始数据文件：评论爬取原始数据_{描述}_{视频标题}_{BV号}_{时分秒}_{日期}
            if suffix:
                base_name = f"评论爬取原始数据_{suffix}_{safe_title}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取原始数据_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif file_type == "final":
            # 最终文件：评论爬取_{排序方式}_{视频标题}_{BV号}_{时分秒}_{日期}
            if suffix:
                base_name = f"评论爬取_{suffix}_{safe_title}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif file_type == "stats":
            # 统计文件：评论爬取统计结果_{统计类型}_{视频标题}_{BV号}_{时分秒}_{日期}
            if suffix:
                base_name = f"评论爬取_{suffix}_{safe_title}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif file_type == "log":
            # 日志文件：评论爬取日志_{视频标题}_{BV号}_{时分秒}_{日期}_{页面信息}
            if suffix:
                base_name = f"评论爬取日志_{safe_title}_{bv_id}_{time_str}_{date_str}_{suffix}"
            else:
                base_name = f"评论爬取日志_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif file_type == "other":
            # 其他类型文件（如文档、说明等）
            if suffix:
                base_name = f"评论爬取_{suffix}_{safe_title}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取_其他文件_{safe_title}_{bv_id}_{time_str}_{date_str}"
        else:
            # 默认格式
            base_name = f"{safe_title}_{bv_id}_{time_str}_{date_str}"
    else:
        # 当video_title为空时，仍然根据file_type生成正确的文件名格式
        
        # 根据文件类型生成不同的命名格式
        if file_type == "original":
            # 原始数据文件
            if suffix:
                base_name = f"评论爬取原始数据_{suffix}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取原始数据_{bv_id}_{time_str}_{date_str}"
        elif file_type == "final":
            # 最终文件
            if suffix:
                base_name = f"评论爬取_{suffix}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取_{bv_id}_{time_str}_{date_str}"
        elif file_type == "stats":
            # 统计文件
            if suffix:
                base_name = f"评论爬取统计结果_{suffix}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取统计结果_{bv_id}_{time_str}_{date_str}"
        elif file_type == "log":
            # 日志文件
            if suffix:
                base_name = f"评论爬取日志_{bv_id}_{time_str}_{date_str}_{suffix}"
            else:
                base_name = f"评论爬取日志_{bv_id}_{time_str}_{date_str}"
        elif file_type == "other":
            # 其他类型文件（如文档、说明等）
            if suffix:
                base_name = f"评论爬取_{suffix}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取_其他文件_{bv_id}_{time_str}_{date_str}"
        else:
            # 未知文件类型，使用通用格式
            if suffix:
                base_name = f"评论爬取_{file_type}_{suffix}_{bv_id}_{time_str}_{date_str}"
            else:
                base_name = f"评论爬取_{file_type}_{bv_id}_{time_str}_{date_str}"
    
    return base_name

def create_output_folder(bv_id, video_title=None, mode_type=None, base_dir=None):
    """
    创建输出文件夹
    
    Args:
        bv_id (str): 视频BV号，用于生成文件夹名
        video_title (str, optional): 视频标题，用于生成文件夹名
        mode_type (str, optional): 运行模式类型，用于生成特定的文件夹名
            - "test_time": 测试模式时间排序
            - "test_popularity": 测试模式热度排序
            - "iteration_time": 迭代模式限定时间
            - "iteration_rate": 迭代模式限定重复率
            - "comprehensive": 综合模式
            - None: 默认模式
    
    Returns:
        str: 创建的文件夹路径（日志文件直接保存在此文件夹下）
    """
    date_str = datetime.now().strftime('%Y%m%d')
    time_str = datetime.now().strftime('%H%M%S')  # 添加时分秒格式
    
    if video_title:
        # 清理视频标题中的非法字符
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
        # 限制标题长度避免路径过长
        if len(safe_title) > 30:
            safe_title = safe_title[:30] + '...'
        
        # 根据模式类型生成不同的文件夹名
        if mode_type == "test_time":
            folder_name = f"评论爬取_测试模式时间排序_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif mode_type == "test_popularity":
            folder_name = f"评论爬取_测试模式热度排序_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif mode_type == "iteration_time":
            folder_name = f"评论爬取_迭代模式限定时间_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif mode_type == "iteration_rate":
            folder_name = f"评论爬取_迭代模式限定重复率_{safe_title}_{bv_id}_{time_str}_{date_str}"
        elif mode_type == "comprehensive":
            folder_name = f"评论爬取_综合模式_{safe_title}_{bv_id}_{time_str}_{date_str}"
        else:
            # 默认格式：评论爬取_视频标题_BV号_时分秒_日期
            folder_name = f"评论爬取_{safe_title}_{bv_id}_{time_str}_{date_str}"
    else:
        # 如果没有视频标题，使用简化格式
        # 仅在需要oid时才进行转换
        try:
            from urllib.parse import parse_qs, urlparse
            # 从BV号提取数字部分作为简化标识
            if bv_id.startswith('BV'):
                simple_id = bv_id[2:8]  # 取BV号的前6位作为标识
            else:
                simple_id = bv_id
            folder_name = f"bilibili_crawler_{simple_id}_{date_str}"
        except:
            folder_name = f"bilibili_crawler_{bv_id}_{date_str}"
    
    # 若指定了基础目录，将文件夹创建在其下
    if base_dir:
        folder_name = os.path.join(base_dir, folder_name)

    # 创建主文件夹
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    globals()['LAST_OUTPUT_FOLDER'] = folder_name

    return folder_name

def setup_logging(bv_id, output_folder):
    """
    设置日志配置
    
    Args:
        bv_id (str): 视频BV号，用于生成日志文件名
        output_folder (str): 输出文件夹路径
    
    Returns:
        tuple: (配置好的日志记录器, 主日志文件路径)
    """
    # 创建logs子文件夹
    logs_folder = os.path.join(output_folder, 'logs')
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
    
    # 生成主日志文件名，保存到logs文件夹
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    main_log_filename = os.path.join(logs_folder, f'{timestamp}_bilibili_crawler_{bv_id}_main.log')
    
    # 禁用requests和urllib3的DEBUG日志，避免干扰我们的自定义日志
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)
    
    # 配置日志格式
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(main_log_filename, encoding='utf-8'),
            # 不添加控制台处理器，避免在终端显示详细日志
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"开始爬取视频 bv_id={bv_id} 的评论")
    logger.info(f"主日志文件: {main_log_filename}")
    logger.info(f"每页请求日志将保存在: {logs_folder}")
    
    return logger, main_log_filename

def create_page_logger(output_folder, bv_id, page_num):
    """
    为每页请求创建单独的日志记录器
    
    Args:
        output_folder (str): 输出文件夹路径
        bv_id (str): 视频BV号
        page_num (int): 页码
    
    Returns:
        tuple: (页面日志记录器, 页面日志文件路径)
    """
    # 确保logs子文件夹存在
    logs_folder = os.path.join(output_folder, 'logs')
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒
    page_log_filename = os.path.join(logs_folder, f'{timestamp}_page_{page_num:04d}_{bv_id}.log')
    
    # 创建页面专用的日志记录器
    page_logger = logging.getLogger(f'page_{page_num}_{bv_id}')
    page_logger.setLevel(logging.DEBUG)
    
    # 清除之前的处理器
    page_logger.handlers.clear()
    
    # 添加文件处理器
    page_handler = logging.FileHandler(page_log_filename, encoding='utf-8')
    page_handler.setLevel(logging.DEBUG)
    page_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    page_handler.setFormatter(page_formatter)
    page_logger.addHandler(page_handler)
    
    # 防止日志传播到父记录器
    page_logger.propagate = False
    
    page_logger.info(f"开始记录第 {page_num} 页的请求和响应")
    page_logger.info(f"视频BV号: {bv_id}")
    
    return page_logger, page_log_filename

def save_comments_to_csv(comments, file_path, data_type):
    """
    保存评论数据到CSV文件
    
    Args:
        comments (list): 评论数据列表
        file_path (str): 文件路径
        data_type (str): 数据类型标识
    """
    if not comments:
        # 创建空文件
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['数据类型', '主楼序号', '楼中楼序号', '用户名称', '用户ID', '评论内容', '回复对象', '点赞数', '回复数', 'rpid', 'parent', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间'])
        return
    
    # 为评论添加数据类型标识
    comments_with_type = []
    for comment in comments:
        comment_with_type = comment.copy()
        comment_with_type['数据类型'] = data_type
        comments_with_type.append(comment_with_type)
    
    # 保存到CSV
    fieldnames = ['数据类型', '主楼序号', '楼中楼序号', '用户名称', '用户ID', '评论内容', '回复对象', '点赞数', '回复数', 'rpid', 'parent', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间']
    
    # 如果是重复评论，添加额外字段
    if comments_with_type and '重复来源' in comments_with_type[0]:
        fieldnames.extend(['重复来源', '原始评论来源'])
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comments_with_type)

def prompt_delete_logs(output_folder=None):
    folder = output_folder or globals().get('LAST_OUTPUT_FOLDER')
    if not folder:
        return
    try:
        choice = input("是否删除logs文件夹？输入 y 确认，其他键取消: ").strip().lower()
    except Exception:
        return
    if choice in ('y', 'yes'):
        try:
            logging.shutdown()
        except Exception:
            pass
        logs_folder = os.path.join(folder, 'logs')
        if os.path.exists(logs_folder):
            try:
                shutil.rmtree(logs_folder)
                print(f"🗑️ 已删除logs文件夹: {logs_folder}")
            except Exception as e:
                print(f"[WARNING] 删除logs失败: {e}")
        else:
            print(f"[WARNING] 未找到logs文件夹: {logs_folder}")
    else:
        print("已保留logs文件夹")
