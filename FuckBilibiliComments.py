#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站评论爬取工具

该脚本用于爬取B站视频评论，支持多种模式：
- 测试模式：快速测试爬取功能
- 迭代模式：持续爬取直到满足条件
- 综合模式：全面爬取并生成统计报告

Python版本要求：Python 3.7+

作者:thinktraveller
日期:2025年8月
版本:1.0
"""

# 依赖检测和自动安装
import sys
import subprocess
import importlib

def check_and_install_dependencies():
    """
    检测并自动安装必要的依赖包
    """
    required_packages = {
        'requests': 'requests>=2.25.1',
    }
    
    missing_packages = []
    
    print("🔍 检测依赖包...")
    
    for package_name, package_spec in required_packages.items():
        try:
            importlib.import_module(package_name)
            print(f"✅ {package_name} 已安装")
        except ImportError:
            print(f"❌ {package_name} 未安装")
            missing_packages.append(package_spec)
    
    if missing_packages:
        print(f"\n📦 发现 {len(missing_packages)} 个缺失的依赖包，开始自动安装...")
        
        for package in missing_packages:
            try:
                print(f"正在安装 {package}...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"✅ {package} 安装成功")
            except subprocess.CalledProcessError as e:
                print(f"❌ {package} 安装失败: {e}")
                print("请手动安装依赖包：")
                print(f"pip install {package}")
                sys.exit(1)
        
        print("\n🎉 所有依赖包安装完成！")
    else:
        print("\n✅ 所有依赖包已满足要求")

# 检查Python版本
if sys.version_info < (3, 7):
    print("❌ 错误：此脚本需要Python 3.7或更高版本")
    print(f"当前Python版本：{sys.version}")
    print("请升级Python版本后重试")
    sys.exit(1)

# 自动检测和安装依赖
check_and_install_dependencies()

# 导入所需模块
import requests
import json
import csv
from datetime import datetime
import time
import hashlib
import re
import logging
import os
from collections import Counter
import shutil


# 自定义异常类
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
            print(f"⚠️  输出文件夹不存在: {output_folder}")
    except Exception as e:
        if logger:
            logger.error(f"删除输出文件失败: {e}")
        print(f"❌ 删除输出文件失败: {e}")


def handle_cookie_banned_error(output_folder, logger=None):
    """
    处理Cookie被封禁的错误
    
    Args:
        output_folder (str): 输出文件夹路径
        logger: 日志记录器
    """
    print("\n" + "="*60)
    print("🚫 Cookie被暂时封禁 - 程序中断")
    print("="*60)
    print("\n📋 错误说明:")
    print("   当前使用的Cookie已被B站暂时封禁（412错误）")
    print("   这通常是由于请求频率过高或其他反爬机制触发")
    
    print("\n🔧 解决方案:")
    print("   1. 更换新的Cookie（推荐）")
    print("      - 重新登录B站获取新的Cookie")
    print("      - 更新config.json中的Cookie配置")
    print("   2. 等待一段时间后重试")
    print("      - 建议等待30分钟到2小时")
    print("      - 下次运行时适当延长等待时间")
    
    print("\n⚠️  建议措施:")
    print("   - 增加请求间隔时间（delay_ms参数）")
    print("   - 避免短时间内频繁运行脚本")
    print("   - 使用不同的账号Cookie轮换使用")
    
    # 清理已生成的文件
    print("\n🗑️  正在清理已生成的文件...")
    cleanup_output_files(output_folder, logger)
    
    print("\n" + "="*60)
    print("程序已安全退出，请按照上述建议处理后重试")
    print("="*60)


# BV号转换相关常量定义
XOR_CODE = 23442827791579
MASK_CODE = 2251799813685247
MAX_AID = 2251799813685248
MIN_AID = 1
BASE = 58
BV_LEN = 12

# Base58编码表
ALPHABET = 'FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf'

# 创建反向查找字典
REVERSE_DICT = {char: idx for idx, char in enumerate(ALPHABET)}

def bvid_to_aid(bvid):
    """
    将BV号转换为AV号（oid）
    
    Args:
        bvid (str): BV号
        
    Returns:
        int: AV号（oid），如果转换失败返回None
    """
    if not isinstance(bvid, str):
        return None
        
    # 检查BV号格式
    if len(bvid) != BV_LEN:
        return None
        
    if not (bvid.upper().startswith('BV1')):
        return None
    
    # 转换为列表便于操作
    bvid_list = list(bvid)
    
    # 位置交换（逆向操作）
    bvid_list[3], bvid_list[9] = bvid_list[9], bvid_list[3]
    bvid_list[4], bvid_list[7] = bvid_list[7], bvid_list[4]
    
    aid = 0
    
    # Base58解码
    for i in range(3, BV_LEN):
        char = bvid_list[i]
        if char not in REVERSE_DICT:
            return None
        aid = aid * BASE + REVERSE_DICT[char]
    
    # 检查范围
    if aid >= (MAX_AID << 1) or aid < MAX_AID:
        return None
    
    # 进行掩码和异或操作
    aid = (aid & MASK_CODE) ^ XOR_CODE
    
    return aid

def aid_to_bvid(aid):
    """
    将AV号（oid）转换为BV号
    
    Args:
        aid (int): AV号（oid）
        
    Returns:
        str: BV号，如果转换失败返回None
    """
    try:
        aid = int(aid)
    except (ValueError, TypeError):
        return None
        
    if aid < MIN_AID or aid >= MAX_AID:
        return None
    
    # 初始化BV号数组
    bvid = ['B', 'V', '1'] + [''] * 9
    
    # 进行异或和掩码操作
    aid = (MAX_AID | aid) ^ XOR_CODE
    
    # Base58编码
    for i in range(BV_LEN - 1, 2, -1):
        if aid == 0:
            break
        bvid[i] = ALPHABET[aid % BASE]
        aid //= BASE
    
    # 位置交换
    bvid[3], bvid[9] = bvid[9], bvid[3]
    bvid[4], bvid[7] = bvid[7], bvid[4]
    
    return ''.join(bvid)

def extract_id_from_url(url):
    """
    从B站URL中提取BV号，严格验证BV号格式
    
    Args:
        url (str): B站视频URL
        
    Returns:
        tuple: (id_type, id_value) 其中id_type为'bv'，id_value为BV号，如果没有找到合法BV号则返回(None, None)
    """
    if not isinstance(url, str):
        return None, None
    
    # 查找所有可能的BV位置
    bv_positions = []
    search_start = 0
    
    while True:
        # 查找下一个"bv"位置（不区分大小写）
        bv_pos = url.lower().find('bv', search_start)
        if bv_pos == -1:
            break
        bv_positions.append(bv_pos)
        search_start = bv_pos + 1
    
    # 检查每个BV位置后面是否有合法的10位字符
    for pos in bv_positions:
        # 确保BV后面有足够的字符
        if pos + 12 <= len(url):  # BV + 10位字符
            candidate = url[pos:pos + 12]  # 提取BV + 10位字符
            
            # 验证格式：BV + 10位数字和字母
            if candidate[:2].upper() == 'BV':
                remaining_10_chars = candidate[2:]
                
                # 检查后面10位是否只包含数字和大小写字母
                if len(remaining_10_chars) == 10 and remaining_10_chars.isalnum():
                    # 进一步检查是否包含非法字符（如斜杠等）
                    if all(c.isalnum() for c in remaining_10_chars):
                        return 'bv', candidate
    
    return None, None

def parse_video_input(user_input):
    """
    解析用户输入的B站URL，提取其中的BV号并转换为oid
    
    Args:
        user_input (str): 用户输入的B站URL
        
    Returns:
        int: 解析出的oid，如果解析失败返回None
    """
    if not user_input or not isinstance(user_input, str):
        return None
    
    user_input = user_input.strip()
    
    # 从URL提取BV号
    id_type, id_value = extract_id_from_url(user_input)
    
    if id_type == 'bv':
        # BV号转换为oid
        return bvid_to_aid(id_value)
    
    # 如果没有找到合法的BV号，返回None
    return None

def get_video_info(bvid, timeout=10):
    """
    通过BV号获取视频信息
    
    Args:
        bvid (str): 视频的BV号
        timeout (int): 请求超时时间，默认10秒
        
    Returns:
        dict: 视频信息字典，获取失败返回None
    """
    # B站视频信息API接口
    url = "https://api.bilibili.com/x/web-interface/view"
    
    # 请求参数
    params = {"bvid": bvid}
    
    # 设置请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.bilibili.com/"
    }
    
    try:
        # 发送请求
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # 解析JSON响应
        data = response.json()
        
        # 检查API返回状态
        if data.get("code") == 0:
            video_data = data.get("data", {})
            
            # 提取关键信息
            video_info = {
                "bvid": video_data.get("bvid", ""),
                "aid": video_data.get("aid", ""),
                "title": video_data.get("title", ""),
                "desc": video_data.get("desc", ""),
                "duration": video_data.get("duration", 0),
                "pubdate": video_data.get("pubdate", 0),
                "owner": {
                    "mid": video_data.get("owner", {}).get("mid", ""),
                    "name": video_data.get("owner", {}).get("name", ""),
                    "face": video_data.get("owner", {}).get("face", "")
                },
                "stat": {
                    "view": video_data.get("stat", {}).get("view", 0),
                    "danmaku": video_data.get("stat", {}).get("danmaku", 0),
                    "reply": video_data.get("stat", {}).get("reply", 0),
                    "favorite": video_data.get("stat", {}).get("favorite", 0),
                    "coin": video_data.get("stat", {}).get("coin", 0),
                    "share": video_data.get("stat", {}).get("share", 0),
                    "like": video_data.get("stat", {}).get("like", 0)
                },
                "pic": video_data.get("pic", ""),
                "tname": video_data.get("tname", "")
            }
            
            return video_info
            
        else:
            error_code = data.get('code')
            error_msg = data.get("message", "未知错误")
            print(f"API返回错误: {error_code} - {error_msg}")
            
            # 针对常见错误提供解决建议
            if error_code == -400:
                print("💡 可能的解决方案:")
                print("   1. 检查BV号是否正确")
                print("   2. 视频可能已被删除或设为私密")
                print("   3. 网络连接问题，请稍后重试")
                print("   4. B站API可能暂时不可用")
            elif error_code == -403:
                print("💡 访问被拒绝，可能需要登录或权限不足")
            elif error_code == -404:
                print("💡 视频不存在，请检查BV号是否正确")
            
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        return None
    except Exception as e:
        print(f"获取视频信息时发生未知错误: {e}")
        return None

def get_video_title_quick(bvid):
    """
    快速获取视频标题
    
    Args:
        bvid (str): 视频的BV号
        
    Returns:
        str: 视频标题，获取失败返回None
    """
    video_info = get_video_info(bvid)
    if video_info:
        return video_info.get("title")
    return None

def load_config():
    """
    加载配置文件，如果配置为空则提示用户输入
    
    Returns:
        dict: 包含cookie和user_agent的配置字典
    """
    config_file = 'config.json'
    
    # 尝试读取配置文件
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"❌ 配置文件 {config_file} 不存在，将创建默认配置文件")
        config = {
            "cookie": "",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "description": {
                "cookie": "从浏览器开发者工具中复制的完整Cookie字符串",
                "user_agent": "浏览器的User-Agent字符串，用于模拟真实浏览器请求"
            }
        }
        save_config(config)
    except json.JSONDecodeError:
        print(f"❌ 配置文件 {config_file} 格式错误，将重新创建")
        config = {
            "cookie": "",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "description": {
                "cookie": "从浏览器开发者工具中复制的完整Cookie字符串",
                "user_agent": "浏览器的User-Agent字符串，用于模拟真实浏览器请求"
            }
        }
        save_config(config)
    
    # 检查cookie是否为空
    if not config.get('cookie', '').strip():
        print("\n=== 配置Cookie信息 ===")
        print("检测到Cookie为空，需要配置Cookie才能正常爬取评论")
        print("请按以下步骤获取Cookie：")
        print("1. 打开浏览器，访问 https://www.bilibili.com")
        print("2. 登录你的B站账号")
        print("3. 按F12打开开发者工具")
        print("4. 切换到Network(网络)标签")
        print("5. 刷新页面，找到任意请求")
        print("6. 在请求头中找到Cookie字段，复制完整的Cookie值")
        print()
        
        while True:
            cookie_input = input("请粘贴完整的Cookie字符串（直接回车跳过，但可能影响爬取效果）: ").strip()
            if cookie_input:
                config['cookie'] = cookie_input
                save_config(config)
                print("✅ Cookie配置已保存")
                break
            else:
                confirm = input("确定要跳过Cookie配置吗？这可能导致爬取失败 (y/N): ").strip().lower()
                if confirm == 'y':
                    print("⚠️ 已跳过Cookie配置，如果爬取失败请重新配置")
                    break
    
    # 检查user_agent是否需要更新
    if not config.get('user_agent', '').strip():
        config['user_agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
        save_config(config)
    
    return config

def save_config(config):
    """
    保存配置文件
    
    Args:
        config (dict): 配置字典
    """
    config_file = 'config.json'
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ 保存配置文件失败: {e}")

def get_request_headers(config):
    """
    根据配置生成请求头
    
    Args:
        config (dict): 配置字典
    
    Returns:
        dict: 请求头字典
    """
    return {
        'Cookie': config.get('cookie', ''),
        'User-Agent': config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'),
        'Referer': 'https://www.bilibili.com',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

def generate_safe_filename(video_title, oid, suffix="", file_type="original"):
    """
    生成安全的文件名，基于视频标题和时间戳
    
    Args:
        video_title (str): 视频标题
        oid (str): 视频oid
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
        
        # 获取BV号
        try:
            bv_id = aid_to_bvid(int(oid))
        except:
            bv_id = f"AV{oid}"
        
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
        try:
            bv_id = aid_to_bvid(int(oid))
        except:
            bv_id = f"AV{oid}"
        
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

def create_output_folder(oid, video_title=None, mode_type=None):
    """
    创建输出文件夹
    
    Args:
        oid (str): 视频oid，用于生成文件夹名
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
        
        # 获取BV号
        try:
            bv_id = aid_to_bvid(int(oid))
        except:
            bv_id = f"AV{oid}"
        
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
        try:
            bv_id = aid_to_bvid(int(oid))
        except:
            bv_id = f"AV{oid}"
        folder_name = f"bilibili_crawler_{oid}_{date_str}"
    
    # 创建主文件夹
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    
    return folder_name

def setup_logging(oid, output_folder):
    """
    设置日志配置
    
    Args:
        oid (str): 视频oid，用于生成日志文件名
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
    main_log_filename = os.path.join(logs_folder, f'{timestamp}_bilibili_crawler_{oid}_main.log')
    
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
    logger.info(f"开始爬取视频 oid={oid} 的评论")
    logger.info(f"主日志文件: {main_log_filename}")
    logger.info(f"每页请求日志将保存在: {logs_folder}")
    
    return logger, main_log_filename

def create_page_logger(output_folder, oid, page_num):
    """
    为每页请求创建单独的日志记录器
    
    Args:
        output_folder (str): 输出文件夹路径
        oid (str): 视频oid
        page_num (int): 页码
    
    Returns:
        tuple: (页面日志记录器, 页面日志文件路径)
    """
    # 确保logs子文件夹存在
    logs_folder = os.path.join(output_folder, 'logs')
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒
    page_log_filename = os.path.join(logs_folder, f'{timestamp}_page_{page_num:04d}_{oid}.log')
    
    # 创建页面专用的日志记录器
    page_logger = logging.getLogger(f'page_{page_num}_{oid}')
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
    page_logger.info(f"视频oid: {oid}")
    
    return page_logger, page_log_filename

def validate_oid(oid):
    """
    验证oid格式是否正确
    
    Args:
        oid (str): 输入的oid
    
    Returns:
        bool: 格式是否正确
    """
    # oid应该是纯数字
    return oid.isdigit() and len(oid) > 0

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
    oid = parse_video_input(video_input)
    
    if oid is None:
        print(f"❌ 输入网址错误: {video_input}")
        print("未能在网址中找到合法的BV号")
        print("BV号格式要求：BV + 10位数字和字母组合（不包含斜杠等特殊符号）")
        print("程序退出")
        return None, None, None, None, None, None, None
    
    # 验证oid是否有效
    if not isinstance(oid, int) or oid <= 0:
        print(f"❌ BV号转换后的oid无效: {oid}")
        print("程序退出")
        return None, None, None, None, None, None, None
    
    # 显示转换结果
    id_type, bv_id = extract_id_from_url(video_input)
    if id_type == 'bv':
        print(f"✅ 网址解析成功: {bv_id} → oid: {oid}")
    
    # 获取视频信息并让用户确认
    print("\n🔍 正在获取视频信息...")
    video_info = None
    try:
        # 获取完整的视频信息
        video_info = get_video_info(bv_id)
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
            # 如果获取完整信息失败，尝试只获取标题
            video_title = get_video_title_quick(bv_id)
            if video_title:
                print(f"📺 视频标题: {video_title}")
                print("⚠️  无法获取完整视频信息，但将继续执行爬取")
            else:
                print("❌ 无法获取视频标题，程序终止")
                print("程序退出")
                return None, None, None, None, None, None, None, video_info
            
    except Exception as e:
        print(f"❌ 获取视频信息失败: {e}")
        # 尝试获取标题作为备选
        try:
            video_title = get_video_title_quick(bv_id)
            if not video_title:
                print("❌ 无法获取视频标题，程序终止")
                print("程序退出")
                return None, None, None, None, None, None, None, None
        except:
            print("❌ 无法获取视频标题，程序终止")
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

# 统一的请求头配置
DEFAULT_HEADERS = {
    'Cookie': 'enable_web_push=DISABLE; buvid4=EF198646-5A11-454B-4282-A3DD7F2A1D3A91404-023112011-; buvid_fp_plain=undefined; PVID=1; buvid3=5E675ECD-B52A-B31A-EDB5-0117F2E3CA8B16806infoc; b_nut=1744450616; _uuid=CCBC10E18-9101E-5449-10DC6-E3E1217872FE19335infoc; enable_feed_channel=ENABLE; theme_style=light; theme-tip-show=SHOWED; fingerprint=d448c4404bf82931a120eb33d24a21f4; buvid_fp=d448c4404bf82931a120eb33d24a21f4; rpdid=|(k|k)~~~umm0J\'u~R~lkmYl); hit-dyn-v2=1; header_theme_version=OPEN; DedeUserID=3546372995287458; DedeUserID__ckMd5=b77446cbfee6faaf; theme-avatar-tip-show=SHOWED; theme-switch-show=SHOWED; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTU5NTkwNzYsImlhdCI6MTc1NTY5OTgxNiwicGx0IjotMX0.SsfNdmWtKhLYyEpQ2UI4-K-1l54Pa3E95nUqJNfORbE; bili_ticket_expires=1755959016; SESSDATA=3ba56d51%2C1771259398%2C5237d%2A82CjD7v3JJ-PIa1hdtFiye-sojBBhyazngSXqcZWjjSAvNhsxtvD7aKuvX9cwoCs7dpc4SVlRqRk53VjZvNElDTUVRanJIbDVfZzZhMnAzdVNjNEVpUnI4TENKdXhNajJDS0d4M0RaaDA0cmtKbVF1bVlXaXgtWGpuak9GeFNDNHVYMEdNajNWV0hBIIEC; bili_jct=f66114d94cef981ad6e98825c3287c87; sid=7jkya1il; CURRENT_QUALITY=0; CURRENT_FNVAL=4048; home_feed_column=5; browser_resolution=1883-864; b_lsid=810A10E189_198D1DE7272; bp_t_offset_3546372995287458=1103932343124492288',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"'
}

def get_response(url, data=None, method='GET'):
    """发送HTTP请求
    
    Args:
        url (str): 请求URL
        data (dict, optional): 请求数据
        method (str): 请求方法，默认为GET
    
    Returns:
        requests.Response: 响应对象
    """
    try:
        if method.upper() == 'POST':
            response = requests.post(url, data=data, headers=DEFAULT_HEADERS, timeout=10)
        else:
            response = requests.get(url, params=data, headers=DEFAULT_HEADERS, timeout=10)
        
        response.raise_for_status()  # 检查HTTP错误
        return response
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None

def generate_w_rid(params):
    """
    生成w_rid签名
    
    Args:
        params (dict): 包含所有参数的字典，除了w_rid外的所有参数
    
    Returns:
        str: 生成的32位w_rid
    """
    # 定义固定值a（尝试更新的值）
    a = "ea1db124af3c7062474693fa704f4ff8"
    
    # 从params中移除w_rid（如果存在）
    l = {k: v for k, v in params.items() if k != 'w_rid'}
    
    # 定义参数顺序，确保web_location在正确位置
    # 对于第一页：oid, type, sort, ps, seek_rpid(如果有), plat, web_location, wts
    # 对于其他页：oid, type, sort, ps, pn, plat, web_location, wts
    param_order = ['oid', 'type', 'sort', 'ps']
    
    # 添加分页相关参数
    if 'pn' in l:
        param_order.append('pn')
    if 'seek_rpid' in l:
        param_order.append('seek_rpid')
    
    # 添加固定参数
    param_order.extend(['plat', 'web_location', 'wts'])
    
    # 按照指定顺序构建参数字符串
    param_list = []
    for key in param_order:
        if key in l:
            param_list.append(f"{key}={l[key]}")
    
    # 添加任何剩余的参数（按字母顺序）
    remaining_keys = set(l.keys()) - set(param_order)
    for key in sorted(remaining_keys):
        param_list.append(f"{key}={l[key]}")
    
    v = "&".join(param_list)
    
    # 组合字符串：v + a
    string = v + a
    
    # 打印调试信息
    print(f"签名字符串: {string}")
    
    # 进行MD5加密
    w_rid = hashlib.md5(string.encode('utf-8')).hexdigest()
    
    print(f"生成的w_rid: {w_rid}")
    
    return w_rid

def get_bilibili_comments(oid, mode=1, ps=20, next_offset='', is_first_page=True, page_num=1, logger=None, output_folder=None):
    """
    获取B站视频评论
    
    Args:
        oid: 视频的oid（稿件avid）
        mode (int): 排序模式，根据B站API文档：0=按时间排序，1=按点赞数排序（热度），2=按回复数排序
        next_offset (str): 分页偏移量，用于获取下一页评论
        is_first_page (bool): 是否为第一页
        page_num (int): 页码
        logger: 主日志记录器
        output_folder: 输出文件夹路径，用于创建页面日志
    
    Returns:
        dict: 评论数据
    """
    # 创建页面专用日志记录器
    page_logger = None
    page_log_file = None
    if output_folder:
        print(f"🔍 调试：正在为第 {page_num} 页创建页面日志记录器...")
        page_logger, page_log_file = create_page_logger(output_folder, oid, page_num)
        print(f"🔍 调试：页面日志文件已创建: {os.path.basename(page_log_file)}")
    else:
        print(f"🔍 调试：output_folder 为空，跳过页面日志记录器创建")
    
    # 尝试使用不同的评论API接口
    # url = "https://api.bilibili.com/x/v2/reply/wbi/main"  # WBI接口
    url = "https://api.bilibili.com/x/v2/reply"  # 基础接口
    
    if logger:
        logger.info(f"开始请求第 {page_num} 页评论，API: {url}")
    if page_logger:
        page_logger.info(f"开始请求第 {page_num} 页评论")
        page_logger.info(f"API接口: {url}")
    
    # 使用配置文件中的请求头配置
    config = load_config()
    request_headers = get_request_headers(config)
    
    # 如果没有提供oid，使用默认值
    if oid is None:
        oid = "115066334743950"
    
    # 构建分页字符串
    if next_offset:
        pagination_str = f'{{"offset":"{next_offset}"}}'
    else:
        pagination_str = '{"offset":""}'
    
    # 生成当前时间戳
    wts = str(int(time.time()))
    
    # 构建基础参数（用于w_rid签名）
    sign_params = {
        'oid': str(oid),
        'type': '1',
        'sort': str(mode),
        'ps': str(ps),  # 用户设定的每页评论数量
        'plat': '1',  # 平台参数
        'web_location': '1315875',  # 新增的web_location参数
        'wts': wts  # 时间戳
    }
    
    # 添加分页参数
    if not is_first_page:
        sign_params['pn'] = str(page_num)
    else:
        # 第一页可能需要seek_rpid参数
        if next_offset:
            sign_params['seek_rpid'] = next_offset
    
    # 生成w_rid签名
    w_rid = generate_w_rid(sign_params)
    
    # 构建最终请求参数（按照指定顺序）
    params = {
        'oid': str(oid),
        'type': '1',
        'sort': str(mode),
        'ps': str(ps)
    }
    
    # 添加分页参数
    if not is_first_page:
        params['pn'] = str(page_num)
    else:
        if next_offset:
            params['seek_rpid'] = next_offset
    
    # 按照指定位置添加参数
    params['plat'] = '1'
    params['web_location'] = '1315875'
    params['w_rid'] = w_rid
    params['wts'] = wts
    
    # 记录详细的请求信息
    if logger:
        logger.info(f"=== 第 {page_num} 页请求开始 ===")
        logger.info(f"请求URL: {url}")
        logger.info(f"请求参数: {json.dumps(params, ensure_ascii=False, indent=2)}")
        logger.info(f"请求头: {json.dumps(request_headers, ensure_ascii=False, indent=2)}")
    
    if page_logger:
        page_logger.info(f"=== 第 {page_num} 页请求详情 ===")
        page_logger.info(f"请求时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        page_logger.info(f"请求URL: {url}")
        page_logger.info(f"请求参数: {json.dumps(params, ensure_ascii=False, indent=2)}")
        page_logger.info(f"请求头: {json.dumps(request_headers, ensure_ascii=False, indent=2)}")
    
    # 使用自定义请求头发送请求
    try:
        request_start_time = time.time()
        if page_logger:
            page_logger.info(f"开始发送GET请求...")
        
        response = requests.get(url, params=params, headers=request_headers, timeout=10)
        request_end_time = time.time()
        request_duration = round((request_end_time - request_start_time) * 1000, 2)  # 转换为毫秒
        
        response.raise_for_status()
        
        if response.status_code == 200:
            result = response.json()
            
            # 记录详细的响应信息
            if logger:
                logger.info(f"=== 第 {page_num} 页响应成功 ===")
                logger.info(f"响应状态码: {response.status_code}")
                logger.info(f"请求耗时: {request_duration}ms")
                logger.info(f"响应头: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}")
                logger.info(f"响应数据大小: {len(response.text)} 字符")
                if 'data' in result and 'replies' in result['data']:
                    replies_count = len(result['data']['replies']) if result['data']['replies'] else 0
                    logger.info(f"本页评论数量: {replies_count} 条")
                # 记录完整响应数据到主日志
                logger.info(f"完整响应数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
                logger.info(f"原始响应文本: {response.text}")
            
            if page_logger:
                page_logger.info(f"=== 第 {page_num} 页响应详情 ===")
                page_logger.info(f"响应时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                page_logger.info(f"响应状态码: {response.status_code}")
                page_logger.info(f"请求耗时: {request_duration}ms")
                page_logger.info(f"响应头: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}")
                page_logger.info(f"响应数据大小: {len(response.text)} 字符")
                if 'data' in result and 'replies' in result['data']:
                    replies_count = len(result['data']['replies']) if result['data']['replies'] else 0
                    page_logger.info(f"本页评论数量: {replies_count} 条")
                page_logger.info(f"完整响应数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
                page_logger.info(f"=== 第 {page_num} 页日志记录完成 ===")
            
            return result
        else:
            # 检查是否为412错误（Cookie被封禁）
            if response.status_code == 412:
                error_msg = f"❌ 检测到412错误 - Cookie可能被暂时封禁"
                if logger:
                    logger.error(f"=== 第 {page_num} 页遇到412错误 - 触发中断机制 ===")
                    logger.error(f"错误状态码: {response.status_code}")
                    logger.error(f"请求耗时: {request_duration}ms")
                    logger.error(f"响应头: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}")
                    logger.error(f"完整响应内容: {response.text}")
                    logger.error("即将触发程序中断和文件清理")
                if page_logger:
                    page_logger.error(f"=== 第 {page_num} 页遇到412错误详情 ===")
                    page_logger.error(f"失败时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    page_logger.error(f"错误状态码: {response.status_code}")
                    page_logger.error(f"请求耗时: {request_duration}ms")
                    page_logger.error(f"响应头: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}")
                    page_logger.error(f"完整响应内容: {response.text}")
                    page_logger.error(f"=== 第 {page_num} 页412错误日志记录完成 ===")
                print(f"\n{error_msg}")
                
                # 抛出特殊异常以触发中断机制
                raise CookieBannedException("Cookie被暂时封禁，触发程序中断")
            else:
                error_msg = f"获取评论失败，状态码: {response.status_code}"
                if logger:
                    logger.error(f"=== 第 {page_num} 页请求失败 ===")
                    logger.error(f"错误状态码: {response.status_code}")
                    logger.error(f"请求耗时: {request_duration}ms")
                    logger.error(f"响应头: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}")
                    logger.error(f"完整响应内容: {response.text}")
                if page_logger:
                    page_logger.error(f"=== 第 {page_num} 页请求失败详情 ===")
                    page_logger.error(f"失败时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    page_logger.error(f"错误状态码: {response.status_code}")
                    page_logger.error(f"请求耗时: {request_duration}ms")
                    page_logger.error(f"响应头: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}")
                    page_logger.error(f"完整响应内容: {response.text}")
                    page_logger.error(f"=== 第 {page_num} 页错误日志记录完成 ===")
                print(f"❌ {error_msg}")
                return None
    except requests.exceptions.RequestException as e:
        request_end_time = time.time()
        request_duration = round((request_end_time - request_start_time) * 1000, 2)
        error_msg = f"请求异常: {e}"
        if logger:
            logger.error(f"=== 第 {page_num} 页请求异常 ===")
            logger.error(f"异常类型: {type(e).__name__}")
            logger.error(f"异常信息: {str(e)}")
            logger.error(f"请求耗时: {request_duration}ms")
            # 如果异常包含响应信息，也记录下来
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"异常响应状态码: {e.response.status_code}")
                logger.error(f"异常响应头: {json.dumps(dict(e.response.headers), ensure_ascii=False, indent=2)}")
                logger.error(f"异常响应内容: {e.response.text}")
        if page_logger:
            page_logger.error(f"=== 第 {page_num} 页请求异常详情 ===")
            page_logger.error(f"异常时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            page_logger.error(f"异常类型: {type(e).__name__}")
            page_logger.error(f"异常信息: {str(e)}")
            page_logger.error(f"请求耗时: {request_duration}ms")
            # 如果异常包含响应信息，也记录下来
            if hasattr(e, 'response') and e.response is not None:
                page_logger.error(f"异常响应状态码: {e.response.status_code}")
                page_logger.error(f"异常响应头: {json.dumps(dict(e.response.headers), ensure_ascii=False, indent=2)}")
                page_logger.error(f"异常响应内容: {e.response.text}")
            page_logger.error(f"=== 第 {page_num} 页异常日志记录完成 ===")
        print(f"❌ {error_msg}")
        return None

def process_comments_page(replies, start_index=1, logger=None, oid=None):
    """
    处理单页评论数据，包括主楼评论和楼中楼回复
    
    Args:
        replies: 评论列表
        start_index: 起始序号
        logger: 日志记录器
        oid: 视频oid，用于获取更多楼中楼评论
    
    Returns:
        list: 处理后的评论数据列表
    """
    csv_data = []
    
    for i, reply in enumerate(replies, start_index):
        # 处理主楼评论
        main_comment = process_single_comment(reply, main_floor_num=i, sub_floor_num=0, logger=logger)
        csv_data.append(main_comment)
        
        # 检查是否有楼中楼回复需要处理
        reply_control = reply.get('reply_control', {})
        sub_reply_entry_text = reply_control.get('sub_reply_entry_text', '')
        sub_replies = reply.get('replies', [])
        sub_reply_count = reply.get('rcount', 0)  # 总回复数
        
        # 优先检查sub_reply_entry_text字段（按照实现指南）
        if sub_reply_entry_text and '条回复' in sub_reply_entry_text:
            # 从"共37条回复"中提取数字
            import re
            match = re.search(r'共(\d+)条回复', sub_reply_entry_text)
            if match:
                total_replies = int(match.group(1))
                if logger:
                    logger.info(f"主楼 {i} 检测到sub_reply_entry_text: {sub_reply_entry_text}，总共有 {total_replies} 条回复")
                
                # 舍弃原本采集的楼中楼评论，重新获取完整的楼中楼评论
                if logger:
                    logger.info(f"舍弃原本的 {len(sub_replies)} 条楼中楼评论，重新获取完整的 {total_replies} 条楼中楼评论")
                
                # 获取所有楼中楼评论
                all_sub_replies = get_all_sub_replies(reply.get('rpid'), oid, total_replies, logger)
                
                if all_sub_replies:
                    for j, sub_reply in enumerate(all_sub_replies, 1):
                        sub_comment = process_single_comment(sub_reply, main_floor_num=None, sub_floor_num=j, logger=logger, is_sub_reply=True)
                        csv_data.append(sub_comment)
                        
                        if logger:
                            logger.info(f"处理完整楼中楼回复 {i}.{j}: 用户={sub_comment.get('用户名称', sub_comment.get('用户名', ''))}, 点赞={sub_comment['点赞数']}")
        
        elif sub_replies:
            # 没有sub_reply_entry_text但有楼中楼回复，按原逻辑处理
            for j, sub_reply in enumerate(sub_replies, 1):
                sub_comment = process_single_comment(sub_reply, main_floor_num=None, sub_floor_num=j, logger=logger, is_sub_reply=True)
                csv_data.append(sub_comment)
                
                if logger:
                    logger.info(f"处理楼中楼回复 {i}.{j}: 用户={sub_comment.get('用户名称', sub_comment.get('用户名', ''))}, 点赞={sub_comment['点赞数']}")
            
            # 检查是否有更多楼中楼评论需要获取
            if sub_reply_count > len(sub_replies):
                if logger:
                    logger.info(f"主楼 {i} 有 {sub_reply_count} 条回复，当前只获取了 {len(sub_replies)} 条，尝试获取更多楼中楼评论")
                
                # 获取更多楼中楼评论
                additional_sub_replies = get_all_sub_replies(reply.get('rpid'), oid, sub_reply_count, logger, skip_count=len(sub_replies))
                
                if additional_sub_replies:
                    for k, additional_sub_reply in enumerate(additional_sub_replies, len(sub_replies) + 1):
                        sub_comment = process_single_comment(additional_sub_reply, main_floor_num=None, sub_floor_num=k, logger=logger, is_sub_reply=True)
                        csv_data.append(sub_comment)
                        
                        if logger:
                            logger.info(f"处理额外楼中楼回复 {i}.{k}: 用户={sub_comment.get('用户名称', sub_comment.get('用户名', ''))}, 点赞={sub_comment['点赞数']}")
        
        elif sub_reply_count > 0:
            # 主楼有回复但当前页面没有显示，尝试获取
            if logger:
                logger.info(f"主楼 {i} 有 {sub_reply_count} 条回复但未在当前页面显示，尝试获取楼中楼评论")
            
            all_sub_replies = get_all_sub_replies(reply.get('rpid'), oid, sub_reply_count, logger)
            
            if all_sub_replies:
                for j, sub_reply in enumerate(all_sub_replies, 1):
                    sub_comment = process_single_comment(sub_reply, main_floor_num=None, sub_floor_num=j, logger=logger, is_sub_reply=True)
                    csv_data.append(sub_comment)
                    
                    if logger:
                        logger.info(f"处理获取的楼中楼回复 {i}.{j}: 用户={sub_comment.get('用户名称', sub_comment.get('用户名', ''))}, 点赞={sub_comment['点赞数']}")
    
    return csv_data


def get_all_sub_replies(root_rpid, oid, total_replies, logger=None, skip_count=0):
    """
    获取指定主楼评论的所有楼中楼回复（支持多页迭代）
    
    Args:
        root_rpid: 主楼评论的rpid
        oid: 视频oid
        total_replies: 总回复数量
        logger: 日志记录器
        skip_count: 跳过的回复数量（已获取的回复数）
    
    Returns:
        list: 所有楼中楼回复列表
    """
    if not root_rpid or not oid or total_replies <= 0:
        return []
    
    all_replies = []
    page_size = 20  # B站每页最多20条回复
    
    # 计算需要获取的页数
    start_page = (skip_count // page_size) + 1
    total_pages = ((total_replies - skip_count - 1) // page_size) + 1
    
    if logger:
        logger.info(f"开始获取楼中楼回复: root_rpid={root_rpid}, 总回复数={total_replies}, 跳过={skip_count}, 需要获取页数={total_pages}")
    
    # B站楼中楼回复API
    url = "https://api.bilibili.com/x/v2/reply/reply"
    
    # 使用配置文件中的请求头配置
    config = load_config()
    request_headers = get_request_headers(config)
    
    for page in range(start_page, start_page + total_pages):
        # 构建请求参数
        params = {
            'oid': str(oid),
            'type': '1',
            'root': str(root_rpid),
            'ps': str(page_size),
            'pn': str(page)
        }
        
        try:
            if logger:
                logger.info(f"请求楼中楼回复第 {page} 页: root_rpid={root_rpid}")
            
            response = requests.get(url, params=params, headers=request_headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('code') == 0:
                replies_data = data.get('data', {})
                page_replies = replies_data.get('replies', [])
                
                if logger:
                    logger.info(f"第 {page} 页成功获取 {len(page_replies)} 条楼中楼回复")
                
                # 处理第一页的跳过逻辑
                if page == start_page and skip_count > 0:
                    skip_in_page = skip_count % page_size
                    page_replies = page_replies[skip_in_page:]
                    if logger:
                        logger.info(f"第 {page} 页跳过前 {skip_in_page} 条回复，实际获取 {len(page_replies)} 条")
                
                all_replies.extend(page_replies)
                
                # 如果这一页的回复数少于页面大小，说明已经是最后一页
                if len(page_replies) < page_size:
                    if logger:
                        logger.info(f"第 {page} 页回复数 {len(page_replies)} < {page_size}，已到达最后一页")
                    break
                    
            else:
                error_msg = f"获取楼中楼回复第 {page} 页失败: {data.get('message', '未知错误')}"
                if logger:
                    logger.warning(error_msg)
                break
                
        except requests.exceptions.RequestException as e:
            error_msg = f"请求楼中楼回复第 {page} 页异常: {e}"
            if logger:
                logger.error(error_msg)
            break
        except Exception as e:
            error_msg = f"处理楼中楼回复第 {page} 页数据异常: {e}"
            if logger:
                logger.error(error_msg)
            break
        
        # 添加请求间隔，避免请求过于频繁
        import time
        time.sleep(0.5)
    
    if logger:
        logger.info(f"楼中楼回复获取完成: 总共获取 {len(all_replies)} 条回复")
    
    return all_replies


def get_additional_sub_replies(root_rpid, oid, skip_count=0, logger=None):
    """
    获取指定主楼评论的更多楼中楼回复（兼容性函数，已废弃）
    
    Args:
        root_rpid: 主楼评论的rpid
        oid: 视频oid
        skip_count: 跳过的回复数量（已获取的回复数）
        logger: 日志记录器
    
    Returns:
        list: 额外的楼中楼回复列表
    """
    if logger:
        logger.warning("get_additional_sub_replies函数已废弃，请使用get_all_sub_replies函数")
    
    # 调用新函数，估算总回复数为skip_count + 20
    return get_all_sub_replies(root_rpid, oid, skip_count + 20, logger, skip_count)


def process_single_comment(reply, main_floor_num=None, sub_floor_num=None, logger=None, is_sub_reply=False):
    """
    处理单条评论数据
    
    Args:
        reply: 单条评论数据
        main_floor_num: 主楼序号（主楼评论时为数字，楼中楼回复时为None）
        sub_floor_num: 楼中楼序号（主楼评论时为0，楼中楼回复时为数字）
        logger: 日志记录器
        is_sub_reply: 是否为楼中楼回复
    
    Returns:
        dict: 处理后的评论数据
    """
    # 处理IP地区信息
    location = reply.get('reply_control', {}).get('location', '未知地区')
    if location.startswith('IP属地：'):
        location = location.replace('IP属地：', '')
    
    # 处理时间戳转换
    ctime = reply.get('ctime', 0)
    if ctime:
        formatted_time = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
    else:
        formatted_time = '未知时间'
    
    # 处理回复对象信息（楼中楼特有）
    reply_to = ''
    if is_sub_reply:
        parent_reply_member = reply.get('parent_reply_member', {})
        if parent_reply_member:
            reply_to = f"@{parent_reply_member.get('name', '未知用户')}"
    
    # 获取当前爬取时间
    current_crawl_time = datetime.now().strftime('%Y年%m月%d日_%H时%M分%S秒')
    
    # 创建评论字典
    comment_dict = {
        '主楼序号': main_floor_num if main_floor_num is not None else '',
        '楼中楼序号': sub_floor_num if sub_floor_num != 0 else (0 if not is_sub_reply else sub_floor_num),
        '用户名称': reply.get('member', {}).get('uname', '未知用户'),
        '评论内容': reply.get('content', {}).get('message', '无内容'),
        '回复对象': reply_to,
        '点赞数': reply.get('like', 0),
        '回复数': reply.get('rcount', 0),
        '发布时间': formatted_time,
        '时间戳': ctime,  # 添加时间戳字段，保留10位时间戳格式
        '用户等级': reply.get('member', {}).get('level_info', {}).get('current_level', 0),
        'IP地区': location,
        '性别': reply.get('member', {}).get('sex', '未知性别'),
        '评论类型': '楼中楼回复' if is_sub_reply else '主楼评论',
        'rpid': reply.get('rpid_str', reply.get('rpid', '')),  # 添加rpid字段，优先使用rpid_str，fallback到rpid
        'parent': reply.get('parent_str', reply.get('parent', 0)),  # 添加parent字段，优先使用parent_str，fallback到parent
        '爬取时间': current_crawl_time  # 添加爬取时间字段
    }
    
    # 记录到日志文件
    if logger:
        comment_type = '楼中楼回复' if is_sub_reply else '主楼评论'
        index_display = f"{main_floor_num}.{sub_floor_num}" if is_sub_reply else str(main_floor_num)
        logger.info(f"处理{comment_type} {index_display}: 用户={comment_dict['用户名称']}, 点赞={comment_dict['点赞数']}, 内容长度={len(comment_dict['评论内容'])}字符")
        logger.debug(f"评论详情 {index_display}: {comment_dict}")
    
    return comment_dict

def process_reply_relationships(comments, logger=None):
    """
    处理评论回复关系，为parent不为0的楼中楼评论创建新的回复对象栏
    
    Args:
        comments (list): 评论数据列表
        logger: 日志记录器
    
    Returns:
        list: 处理后的评论数据列表
    """
    if not comments:
        return comments
    
    # 创建rpid到评论的映射
    rpid_to_comment = {}
    for comment in comments:
        rpid = comment.get('rpid', '')
        if rpid:
            rpid_to_comment[str(rpid)] = comment
    
    processed_comments = []
    
    for comment in comments:
        processed_comment = {
            '主楼序号': comment['主楼序号'],
            '楼中楼序号': comment['楼中楼序号'],
            '用户名称': comment.get('用户名称', comment.get('用户名', '')),
            '评论内容': comment['评论内容'],
            '点赞数': comment['点赞数'],
            '回复数': comment.get('回复数', 0),
            '发布时间': comment.get('发布时间', ''),
            '用户等级': comment.get('用户等级', ''),
            'IP地区': comment.get('IP地区', ''),
            '性别': comment.get('性别', ''),
            '评论类型': comment.get('评论类型', '')
        }
        
        parent = comment.get('parent', 0)
        
        # 如果parent不为0（楼中楼评论），处理回复关系
        if parent != 0 and comment['楼中楼序号'] != 0:
            parent_comment = rpid_to_comment.get(str(parent))
            if parent_comment:
                target_username = parent_comment.get('用户名称', parent_comment.get('用户名', ''))
                current_username = comment.get('用户名称', comment.get('用户名', ''))
                
                # 创建回复对象栏，使用被回复评论的楼中楼序号
                target_floor_index = parent_comment['楼中楼序号']
                processed_comment['回复评论对象'] = f"@{target_username},{target_floor_index}"
                
                if logger:
                    logger.debug(f"处理回复关系: {current_username} 回复 {target_username}，楼中楼序号 {target_floor_index}")
            else:
                # 找不到对应的parent评论，使用原始回复对象
                processed_comment['回复评论对象'] = comment.get('回复对象', '')
                if logger:
                    logger.warning(f"未找到parent={parent}对应的评论，使用原始回复对象")
        else:
            # 主楼评论或parent为0的评论，不设置回复对象
            processed_comment['回复评论对象'] = ''
        
        processed_comments.append(processed_comment)
    
    if logger:
        logger.info(f"回复关系处理完成，共处理 {len(processed_comments)} 条评论")
    
    return processed_comments







def process_and_organize_data(all_comments, output_folder, oid, logger=None, video_title=None, sort_by_popularity=True, video_info=None, mode=None):
    """
    整理和统计评论数据
    
    Args:
        all_comments (list): 所有评论数据
        output_folder (str): 输出文件夹路径
        oid (str): 视频oid
        logger: 日志记录器
        sort_by_popularity (bool): 是否按热度排序整理数据
        video_info (dict): 视频信息
        mode (str): 运行模式，用于区分是否生成时间排序最终文件
    
    Returns:
        tuple: (None, 整理数据文件路径或None, 统计文件路径)
    """
    if not all_comments:
        return None, None, None
    
    # 生成整理数据文件（同时输出有楼中楼和无楼中楼版本）
    processed_filename = None
    main_floor_filename = None
    
    if sort_by_popularity:
        # 按热度排序整理数据
        sorted_comments = sort_comments_by_popularity(all_comments, logger)
        
        # 处理回复关系
        processed_comments = process_reply_relationships(sorted_comments, logger)
        main_floor_comments = []  # 只包含主楼评论的列表
        
        # 筛选主楼评论
        for comment in processed_comments:
            if comment['楼中楼序号'] == 0:
                main_floor_comments.append(comment)
        
        # 保存完整整理数据（包含楼中楼）
        filename = generate_safe_filename(video_title, oid, "最终数据_按热度排序", "final")
        processed_filename = os.path.join(output_folder, f'{filename}.csv')
        with open(processed_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if processed_comments:
                fieldnames = ['主楼序号', '楼中楼序号', '用户名称', '评论内容', '回复评论对象', '点赞数', '回复数', '发布时间', '用户等级', 'IP地区', '性别', '评论类型']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(processed_comments)
        
        # 保存只包含主楼评论的文件（无楼中楼）
        main_floor_name = generate_safe_filename(video_title, oid, "最终数据_按热度排序且无楼中楼", "final")
        main_floor_filename = os.path.join(output_folder, f'{main_floor_name}.csv')
        with open(main_floor_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if main_floor_comments:
                # 主楼评论文件包含发布时间和回复数字段
                fieldnames = ['主楼序号', '用户名称', '评论内容', '点赞数', '回复数', '发布时间']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # 过滤掉不需要的字段
                filtered_comments = []
                for comment in main_floor_comments:
                    filtered_comment = {key: comment[key] for key in fieldnames if key in comment}
                    filtered_comments.append(filtered_comment)
                
                writer.writerows(filtered_comments)
        
        if logger:
            logger.info(f"按热度排序整理完成，共 {len(processed_comments)} 条评论")
            logger.info(f"完整评论文件已保存: {processed_filename}")
            logger.info(f"主楼评论文件已保存: {main_floor_filename}，共 {len(main_floor_comments)} 条主楼评论")
    else:
        # 按时间排序整理数据 - 只有在测试模式时间排序下才生成最终文件
        if mode == "test_time":
            sorted_comments = sort_comments_by_time(all_comments, logger)
            
            # 处理回复关系
            processed_comments = process_reply_relationships(sorted_comments, logger)
            main_floor_comments = []  # 只包含主楼评论的列表
            
            # 筛选主楼评论
            for comment in processed_comments:
                if comment['楼中楼序号'] == 0:
                    main_floor_comments.append(comment)
            
            # 保存完整整理数据（包含楼中楼）
            filename = generate_safe_filename(video_title, oid, "最终数据_按时间排序", "final")
            processed_filename = os.path.join(output_folder, f'{filename}.csv')
            with open(processed_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                if processed_comments:
                    fieldnames = ['主楼序号', '楼中楼序号', '用户名称', '评论内容', '回复评论对象', '点赞数', '回复数', '发布时间', '用户等级', 'IP地区', '性别', '评论类型']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(processed_comments)
            
            # 保存只包含主楼评论的文件（无楼中楼）
            main_floor_name = generate_safe_filename(video_title, oid, "最终数据_按时间排序且无楼中楼", "final")
            main_floor_filename = os.path.join(output_folder, f'{main_floor_name}.csv')
            with open(main_floor_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                if main_floor_comments:
                    # 主楼评论文件包含发布时间和回复数字段
                    fieldnames = ['主楼序号', '用户名称', '评论内容', '点赞数', '回复数', '发布时间']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    # 过滤掉不需要的字段
                    filtered_comments = []
                    for comment in main_floor_comments:
                        filtered_comment = {key: comment[key] for key in fieldnames if key in comment}
                        filtered_comments.append(filtered_comment)
                    
                    writer.writerows(filtered_comments)
            
            if logger:
                logger.info(f"按时间排序整理完成，共 {len(processed_comments)} 条评论")
                logger.info(f"完整评论文件已保存: {processed_filename}")
                logger.info(f"主楼评论文件已保存: {main_floor_filename}，共 {len(main_floor_comments)} 条主楼评论")
        else:
            # 非测试模式时间排序，不生成最终文件，只用于统计
            processed_filename = None
            main_floor_filename = None
            if logger:
                logger.info(f"非测试模式时间排序，跳过最终文件生成，仅用于统计")
    
    # 生成统计文件（添加"统计结果"前缀）
    stats_name = generate_safe_filename(video_title, oid, "统计结果", "stats")
    stats_filename = os.path.join(output_folder, f'{stats_name}.txt')
    # 生成BV号
    bv_id = None
    if oid:
        try:
            bv_id = aid_to_bvid(int(oid))
        except:
            pass
    generate_statistics(all_comments, stats_filename, logger, oid, video_title, bv_id, video_info)
    
    # 时间统计将在主函数中统一处理，避免重复调用
    
    return None, processed_filename, stats_filename

def sort_comments_by_popularity(all_comments, logger=None):
    """
    按热度排序整理评论数据
    
    排序规则：
    1. 主楼评论按点赞数降序排序，点赞数相同时按发布时间升序排序
    2. 每个主楼的楼中楼评论按发布时间升序排序
    3. 重新分配序号：主楼序号从1开始，楼中楼序号在每个主楼内从1开始
    
    Args:
        all_comments (list): 所有评论数据
        logger: 日志记录器
    
    Returns:
        list: 按热度排序后的评论数据
    """
    if not all_comments:
        return []
    
    if logger:
        logger.info("开始按热度排序整理评论数据")
    
    # 分离主楼评论和楼中楼评论
    main_comments = []  # 主楼评论
    sub_comments_dict = {}  # 楼中楼评论，以原主楼序号为key
    
    for comment in all_comments:
        if comment['评论类型'] == '主楼评论':
            main_comments.append(comment)
            # 初始化该主楼的楼中楼列表
            original_main_index = comment['主楼序号']
            sub_comments_dict[original_main_index] = []
        elif comment['评论类型'] == '楼中楼回复':
            # 找到对应的主楼评论
            # 需要通过遍历找到对应的主楼
            for main_comment in main_comments:
                # 检查是否属于同一个主楼（通过用户名、时间等信息判断）
                # 这里我们需要一个更好的方法来关联楼中楼和主楼
                pass
    
    # 由于当前数据结构的限制，我们需要重新设计关联逻辑
    # 临时解决方案：按照评论在原始列表中的顺序来关联
    main_comments = []
    current_main_comment = None
    current_sub_comments = []
    sorted_result = []
    
    for comment in all_comments:
        if comment['评论类型'] == '主楼评论':
            # 如果之前有主楼评论，先处理之前的主楼和其楼中楼
            if current_main_comment is not None:
                main_comments.append({
                    'main': current_main_comment,
                    'subs': current_sub_comments.copy()
                })
            
            # 开始新的主楼
            current_main_comment = comment
            current_sub_comments = []
        elif comment['评论类型'] == '楼中楼回复':
            # 添加到当前主楼的楼中楼列表
            if current_main_comment is not None:
                current_sub_comments.append(comment)
    
    # 处理最后一个主楼
    if current_main_comment is not None:
        main_comments.append({
            'main': current_main_comment,
            'subs': current_sub_comments.copy()
        })
    
    if logger:
        logger.info(f"分离完成：{len(main_comments)} 个主楼评论")
    
    # 对主楼评论按热度排序
    def sort_key_main(comment_group):
        main_comment = comment_group['main']
        likes = main_comment['点赞数'] if isinstance(main_comment['点赞数'], int) else 0
        # 发布时间转换为时间戳用于排序（时间越早，时间戳越小）
        time_str = main_comment['发布时间']
        try:
            if time_str and time_str != '未知时间':
                time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                timestamp = time_obj.timestamp()
            else:
                timestamp = float('inf')  # 未知时间排在最后
        except:
            timestamp = float('inf')
        
        return (-likes, timestamp)  # 点赞数降序，时间戳升序
    
    main_comments.sort(key=sort_key_main)
    
    if logger:
        logger.info("主楼评论热度排序完成")
    
    # 重新组织数据并分配序号
    sorted_result = []
    
    for main_index, comment_group in enumerate(main_comments, 1):
        main_comment = comment_group['main'].copy()
        sub_comments = comment_group['subs']
        
        # 重新分配主楼序号
        main_comment['主楼序号'] = main_index
        main_comment['楼中楼序号'] = 0
        sorted_result.append(main_comment)
        
        # 对楼中楼评论按时间排序
        def sort_key_sub(comment):
            time_str = comment['发布时间']
            try:
                if time_str and time_str != '未知时间':
                    time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    return time_obj.timestamp()
                else:
                    return float('inf')
            except:
                return float('inf')
        
        sub_comments.sort(key=sort_key_sub)
        
        # 重新分配楼中楼序号
        for sub_index, sub_comment in enumerate(sub_comments, 1):
            sub_comment_copy = sub_comment.copy()
            sub_comment_copy['主楼序号'] = ''
            sub_comment_copy['楼中楼序号'] = sub_index
            sorted_result.append(sub_comment_copy)
    
    if logger:
        logger.info(f"热度排序完成，共整理 {len(sorted_result)} 条评论")
    
    return sorted_result

def sort_comments_by_time(all_comments, logger=None):
    """
    按时间排序整理评论数据
    
    排序规则：
    1. 主楼评论按发布时间升序排序
    2. 每个主楼的楼中楼评论按发布时间升序排序
    3. 重新分配序号：主楼序号从1开始，楼中楼序号在每个主楼内从1开始
    
    Args:
        all_comments (list): 所有评论数据
        logger: 日志记录器
    
    Returns:
        list: 按时间排序后的评论数据
    """
    if not all_comments:
        return []
    
    if logger:
        logger.info("开始按时间排序整理评论数据")
    
    # 临时解决方案：按照评论在原始列表中的顺序来关联
    main_comments = []
    current_main_comment = None
    current_sub_comments = []
    
    for comment in all_comments:
        if comment['评论类型'] == '主楼评论':
            # 如果之前有主楼评论，先处理之前的主楼和其楼中楼
            if current_main_comment is not None:
                main_comments.append({
                    'main': current_main_comment,
                    'subs': current_sub_comments.copy()
                })
            
            # 开始新的主楼
            current_main_comment = comment
            current_sub_comments = []
        elif comment['评论类型'] == '楼中楼回复':
            # 添加到当前主楼的楼中楼列表
            if current_main_comment is not None:
                current_sub_comments.append(comment)
    
    # 处理最后一个主楼
    if current_main_comment is not None:
        main_comments.append({
            'main': current_main_comment,
            'subs': current_sub_comments.copy()
        })
    
    if logger:
        logger.info(f"分离完成：{len(main_comments)} 个主楼评论")
    
    # 对主楼评论按时间排序
    def sort_key_main(comment_group):
        main_comment = comment_group['main']
        time_str = main_comment['发布时间']
        try:
            if time_str and time_str != '未知时间':
                time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                timestamp = time_obj.timestamp()
            else:
                timestamp = float('inf')  # 未知时间排在最后
        except:
            timestamp = float('inf')
        
        return timestamp  # 时间戳升序
    
    main_comments.sort(key=sort_key_main)
    
    if logger:
        logger.info("主楼评论时间排序完成")
    
    # 重新组织数据并分配序号
    sorted_result = []
    
    for main_index, comment_group in enumerate(main_comments, 1):
        main_comment = comment_group['main'].copy()
        sub_comments = comment_group['subs']
        
        # 重新分配主楼序号
        main_comment['主楼序号'] = main_index
        main_comment['楼中楼序号'] = 0
        sorted_result.append(main_comment)
        
        # 对楼中楼评论按时间排序
        def sort_key_sub(comment):
            time_str = comment['发布时间']
            try:
                if time_str and time_str != '未知时间':
                    time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    return time_obj.timestamp()
                else:
                    return float('inf')
            except:
                return float('inf')
        
        sub_comments.sort(key=sort_key_sub)
        
        # 重新分配楼中楼序号
        for sub_index, sub_comment in enumerate(sub_comments, 1):
            sub_comment_copy = sub_comment.copy()
            sub_comment_copy['主楼序号'] = ''
            sub_comment_copy['楼中楼序号'] = sub_index
            sorted_result.append(sub_comment_copy)
    
    if logger:
        logger.info(f"时间排序完成，共整理 {len(sorted_result)} 条评论")
    
    return sorted_result

# 备用函数已删除，不再需要

def generate_restructured_time_statistics(all_comments, output_folder, bvid, logger=None, video_title=None, video_info=None):
    """
    基于新设计思路重新设计的时间统计功能
    根据时间跨度生成多个粒度的统计文件，严格按照设计思路执行
    
    Args:
        all_comments (list): 所有评论数据
        output_folder (str): 输出文件夹路径
        bvid (str): 视频BV号
        logger: 日志记录器
        video_title (str): 视频标题
        video_info (dict): 视频信息，如果提供则不再重复获取
    
    Returns:
        list: 生成的统计文件路径列表
    """
    if not all_comments:
        return []
    
    # 获取视频信息（如果未提供）
    if not video_info:
        video_info = get_video_info(bvid)
        if not video_info:
            print("❌ 无法获取视频信息，无法进行按时间统计")
            print("⚠️  按时间统计需要视频发布时间信息，跳过统计")
            
            if logger:
                logger.warning("无法获取视频发布时间，跳过按时间统计")
                
            return []
    
    # 获取视频发布时间
    publish_timestamp = video_info.get('pubdate', 0)
    if publish_timestamp == 0:
        print("❌ 无法获取视频发布时间，使用现有时间统计方式")
        return []
    
    publish_datetime = datetime.fromtimestamp(publish_timestamp)
    
    # 获取所有有效评论时间戳
    valid_comments = [comment for comment in all_comments if comment.get('时间戳', 0) > 0]
    if not valid_comments:
        return []
    
    # 过滤掉发布时间之前的评论
    new_comments = [comment for comment in valid_comments if comment['时间戳'] >= publish_timestamp]
    if not new_comments:
        print("⚠️  没有找到视频发布后的评论")
        return []
    
    timestamps = [comment['时间戳'] for comment in new_comments]
    min_timestamp = min(timestamps)
    max_timestamp = max(timestamps)
    
    # 计算最新评论与视频发布时间的差值
    time_diff = max_timestamp - publish_timestamp
    
    # 获取最新和最旧评论的日期时间
    max_datetime = datetime.fromtimestamp(max_timestamp)
    
    # 根据设计思路的决策树判断需要生成的统计粒度（可能生成多个）
    granularities_to_generate = []
    
    # 判断是否跨年
    if publish_datetime.year != max_datetime.year:
        granularities_to_generate = ['year', 'month', 'day']
    # 判断是否同年不同月
    elif publish_datetime.month != max_datetime.month:
        granularities_to_generate = ['month', 'day']
    # 判断是否同年同月不同日
    elif publish_datetime.date() != max_datetime.date():
        if time_diff > 604800:  # 大于7天
            granularities_to_generate = ['day']
        else:  # 小于等于7天
            granularities_to_generate = ['day', 'hour']
    # 同年同月同日
    else:
        granularities_to_generate = ['hour', 'minute']
    
    if logger:
        logger.info(f"基于时间差值{time_diff}秒，需要生成统计粒度: {granularities_to_generate}")
    
    generated_files = []
    
    # 为每个需要的粒度生成统计文件和图表
    for granularity in granularities_to_generate:
        granularity_name = {'minute': '分钟', 'hour': '小时', 'day': '日', 'month': '月', 'year': '年'}[granularity]
        
        # 生成统计数据
        stats, time_points, counts = generate_time_stats_by_granularity(
            new_comments, granularity, publish_datetime, max_timestamp
        )
        
        # 保存统计结果到txt文件
        stats_file = save_restructured_time_statistics(
            stats, granularity_name, output_folder, bvid, publish_timestamp, max_timestamp, 
            logger, video_title, video_info, new_comments
        )
        generated_files.append(stats_file)
        
        # 生成折线图
        chart_file = generate_time_trend_chart(
            time_points, counts, granularity_name, output_folder, bvid, video_title, publish_datetime, max_timestamp
        )
        if chart_file:
            generated_files.append(chart_file)
    
    return generated_files

from datetime import timedelta

def generate_time_stats_by_granularity(comments, granularity, publish_datetime, max_timestamp):
    """
    根据指定粒度生成时间统计数据
    按分钟和小时统计时以视频发布时间为基准进行时间段划分
    
    Args:
        comments (list): 评论数据
        granularity (str): 统计粒度 ('minute', 'hour', 'day', 'month', 'year')
        publish_datetime (datetime): 视频发布时间
        max_timestamp (int): 最新评论时间戳
    
    Returns:
        tuple: (stats, time_points, counts)
    """
    stats = {}
    time_points = []
    counts = []
    
    if granularity == 'minute':
        # 按分钟统计 - 以视频发布时间为基准
        publish_timestamp = int(publish_datetime.timestamp())
        
        # 计算需要统计的分钟数
        total_minutes = int((max_timestamp - publish_timestamp) / 60) + 1
        
        for i in range(total_minutes):
            start_time = publish_timestamp + i * 60
            end_time = start_time + 60
            
            # 统计在这个时间段内的评论数量
            count = sum(1 for comment in comments 
                       if start_time <= comment['时间戳'] < end_time)
            
            # 生成显示用的时间段描述
            if i == 0:
                key = f"视频发布后0-1分钟内新增评论数量"
            else:
                key = f"视频发布后{i}-{i+1}分钟内新增评论数量"
            
            stats[key] = count
            time_points.append(datetime.fromtimestamp(start_time))
            counts.append(count)
            
    elif granularity == 'hour':
        # 按小时统计 - 以视频发布时间为基准
        publish_timestamp = int(publish_datetime.timestamp())
        
        # 计算需要统计的小时数
        total_hours = int((max_timestamp - publish_timestamp) / 3600) + 1
        
        for i in range(total_hours):
            start_time = publish_timestamp + i * 3600
            end_time = start_time + 3600
            
            # 统计在这个时间段内的评论数量
            count = sum(1 for comment in comments 
                       if start_time <= comment['时间戳'] < end_time)
            
            # 生成显示用的时间段描述
            if i == 0:
                key = f"视频发布后0-1小时内新增的评论数量"
            else:
                key = f"视频发布后{i}-{i+1}小时内新增的评论数量"
            
            stats[key] = count
            time_points.append(datetime.fromtimestamp(start_time))
            counts.append(count)
            
    elif granularity == 'day':
        # 按日统计 - 根据正常时间统计
        day_stats = {}
        for comment in comments:
            comment_dt = datetime.fromtimestamp(comment['时间戳'])
            day_key = comment_dt.strftime('%Y/%m/%d')
            day_stats[day_key] = day_stats.get(day_key, 0) + 1
        
        # 按日期排序
        for day_key in sorted(day_stats.keys()):
            key = f"{day_key}内新增的评论数"
            stats[key] = day_stats[day_key]
            # 解析日期用于图表
            year, month, day = map(int, day_key.split('/'))
            time_points.append(datetime(year, month, day))
            counts.append(day_stats[day_key])
            
    elif granularity == 'month':
        # 按月统计 - 根据正常时间统计
        month_stats = {}
        for comment in comments:
            comment_dt = datetime.fromtimestamp(comment['时间戳'])
            month_key = comment_dt.strftime('%Y/%m')
            month_stats[month_key] = month_stats.get(month_key, 0) + 1
        
        # 按月份排序
        for month_key in sorted(month_stats.keys()):
            key = f"{month_key}内新增的评论数"
            stats[key] = month_stats[month_key]
            # 解析月份用于图表
            year, month = map(int, month_key.split('/'))
            time_points.append(datetime(year, month, 1))
            counts.append(month_stats[month_key])
            
    elif granularity == 'year':
        # 按年统计 - 根据正常时间统计
        year_stats = {}
        for comment in comments:
            comment_dt = datetime.fromtimestamp(comment['时间戳'])
            year_key = comment_dt.strftime('%Y')
            year_stats[year_key] = year_stats.get(year_key, 0) + 1
        
        # 按年份排序
        for year_key in sorted(year_stats.keys()):
            key = f"{year_key}内新增的评论数"
            stats[key] = year_stats[year_key]
            # 解析年份用于图表
            year = int(year_key)
            time_points.append(datetime(year, 1, 1))
            counts.append(year_stats[year_key])
    
    return stats, time_points, counts

def save_restructured_time_statistics(stats, granularity_name, output_folder, bvid, 
                                    publish_timestamp, max_timestamp, logger=None, 
                                    video_title=None, video_info=None, comments=None):
    """
    保存重新设计的时间统计结果，严格按照设计思路格式
    """
    # 创建"按时间统计"文件夹
    time_stats_folder = os.path.join(output_folder, "按时间统计")
    if not os.path.exists(time_stats_folder):
        os.makedirs(time_stats_folder)
    
    # 生成文件名 - 严格按照设计思路要求的格式："评论爬取统计结果_按分钟/小时/日/月/年统计_{视频名称}_{视频BV号}"
    safe_title = "".join(c for c in (video_title or "") if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_title = safe_title[:30]  # 限制长度，避免文件名过长
    
    filename = f"评论爬取统计结果_按{granularity_name}统计_{safe_title}_{bvid}.txt"
    filepath = os.path.join(time_stats_folder, filename)
    
    # 计算统计汇总信息
    if comments:
        min_timestamp = min(comment['时间戳'] for comment in comments if comment.get('时间戳', 0) > 0)
    else:
        min_timestamp = publish_timestamp
    
    total_comments = sum(stats.values())
    total_periods = len(stats)
    
    # 找出最高峰和最低谷
    if stats:
        max_count = max(stats.values())
        min_count = min(stats.values())
        max_period = [k for k, v in stats.items() if v == max_count][0]
        min_period = [k for k, v in stats.items() if v == min_count][0]
        
        # 提取时间段描述
        max_period_desc = max_period.replace('内新增的评论数', '')
        min_period_desc = min_period.replace('内新增的评论数', '')
    else:
        max_count = min_count = 0
        max_period_desc = min_period_desc = "无数据"
    
    # 计算平均值
    avg_comments = total_comments / total_periods if total_periods > 0 else 0
    
    # 写入统计数据到文件
    with open(filepath, 'w', encoding='utf-8') as f:
        # 先记录最新评论与最旧评论的时间
        f.write(f"最新评论时间：{datetime.fromtimestamp(max_timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"最旧评论时间：{datetime.fromtimestamp(min_timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 统计汇总
        f.write("=== 统计汇总 ===\n")
        f.write(f"- 统计粒度: {granularity_name}\n")
        f.write(f"- 统计对象：{video_title or '未知视频'}\n")
        f.write(f"- 统计对象BV号：{bvid}\n")
        f.write(f"- 累计统计时间段数量: {total_periods}\n")
        f.write(f"- 总评论数: {total_comments}\n")
        f.write(f"- 平均每{granularity_name}: {avg_comments:.2f} 条评论\n")
        f.write(f"- 最高峰: {max_count} 条评论，出现在 {max_period_desc}\n")
        f.write(f"- 最低谷: {min_count} 条评论，出现在 {min_period_desc}\n\n")
        
        # 详细统计数据
        f.write("=== 详细统计 ===\n")
        # 按时间顺序排序输出
        sorted_stats = sorted(stats.items())
        for key, count in sorted_stats:
            f.write(f"{key}：{count}\n")
    
    if logger:
        logger.info(f"时间统计文件已保存: {filepath}")
    
    return filepath
    


def generate_time_trend_chart(time_points, counts, granularity_name, output_folder, 
                           bvid, video_title, publish_datetime, max_timestamp):
    """
    使用matplotlib生成评论数量变化趋势的折线图
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.font_manager import FontProperties
        
        # 创建图表
        plt.figure(figsize=(12, 6))
        
        # 绘制折线图
        plt.plot(time_points, counts, marker='o', linewidth=2, markersize=4)
        
        # 设置标题和标签
        try:
            font_prop = FontProperties(fname='C:\\Windows\\Fonts\\simhei.ttf')  # 假设系统有SimHei字体，需确认路径
            plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
            plt.rcParams['axes.unicode_minus'] = False
        except Exception as font_error:
            print(f"⚠️ 字体设置失败: {font_error}. 使用默认字体。")
            plt.rcParams['axes.unicode_minus'] = False
        
        # 计算最新评论时间
        max_comment_datetime = datetime.fromtimestamp(max_timestamp)
        
        plt.title(f'{video_title or "未知视频"} - {bvid} - 评论数量变化趋势\n视频发布时间：{publish_datetime.strftime("%Y-%m-%d %H:%M:%S")} - 最新评论时间：{max_comment_datetime.strftime("%Y-%m-%d %H:%M:%S")} - 按{granularity_name}统计', 
                 fontsize=14, fontweight='bold')
        plt.xlabel(f'时间（{granularity_name}）', fontsize=12)
        plt.ylabel('评论数量', fontsize=12)
        
        # 设置网格
        plt.grid(True, alpha=0.3)
        
        # 旋转x轴标签
        plt.xticks(rotation=45)
        
        # 根据统计粒度设置x轴格式
        if granularity_name == '分钟':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        elif granularity_name == '小时':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:00'))
        elif granularity_name == '日':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        elif granularity_name == '月':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        else:  # 年
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        
        plt.tight_layout()
        
        # 保存图表
        safe_title = "".join(c for c in (video_title or "") if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title[:30]  # 限制长度
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        chart_filename = f"评论爬取统计结果_按{granularity_name}统计_{bvid}_{safe_title}_{timestamp_str}_趋势图.png"
        chart_filepath = os.path.join(output_folder, "按时间统计", chart_filename)
        
        plt.savefig(chart_filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"📈 评论趋势图已生成: {chart_filepath}")
        return chart_filepath
        
    except ImportError:
        print("⚠️  matplotlib未安装，无法生成趋势图")
        return None
    except Exception as e:
        print(f"⚠️  生成趋势图时出错: {e}")
        return None

# 保持原有的时间统计函数作为备选
def generate_smart_time_statistics(all_comments, output_folder, oid, logger=None, video_title=None):
    """
    智能选择时间统计方式并生成对应的统计文件
    
    Args:
        all_comments (list): 所有评论数据
        output_folder (str): 输出文件夹路径
        oid (str): 视频oid
        logger: 日志记录器
        video_title (str): 视频标题
    
    Returns:
        list: 生成的统计文件路径列表
    """

def generate_statistics(all_comments, stats_filename, logger=None, oid=None, video_title=None, bv_id=None, video_info=None):
    """
    生成用户信息统计
    
    Args:
        all_comments (list): 所有评论数据
        stats_filename (str): 统计文件路径
        logger: 日志记录器
        oid (str): 视频OID
        video_title (str): 视频标题
        bv_id (str): 视频BV号
        video_info (dict): 视频信息，包含发布时间等
    """
    if not all_comments:
        return
    
    # 统计各项信息
    genders = [comment['性别'] for comment in all_comments if comment['性别']]
    locations = [comment['IP地区'] for comment in all_comments if comment['IP地区']]
    levels = [comment['用户等级'] for comment in all_comments if comment['用户等级']]
    comment_types = [comment['评论类型'] for comment in all_comments if comment['评论类型']]
    
    # 计算统计数据
    gender_stats = Counter(genders)
    location_stats = Counter(locations)
    level_stats = Counter(levels)
    type_stats = Counter(comment_types)
    
    # 计算总数和其他统计信息
    total_comments = len(all_comments)
    total_likes = sum(comment['点赞数'] for comment in all_comments if isinstance(comment['点赞数'], int))
    total_replies = sum(comment['回复数'] for comment in all_comments if isinstance(comment['回复数'], int))
    
    # 生成统计报告
    with open(stats_filename, 'w', encoding='utf-8') as f:
        f.write("=== B站评论数据统计报告 ===\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 插入视频发布时间
        if video_info and video_info.get('pubdate', 0) > 0:
            publish_time = datetime.fromtimestamp(video_info['pubdate']).strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"视频发布时间: {publish_time}\n")
        
        if bv_id:
            f.write(f"视频BV号: {bv_id}\n")
        if oid:
            f.write(f"视频OID: {oid}\n")
        if video_title:
            f.write(f"视频标题: {video_title}\n")
        f.write(f"总评论数: {total_comments} 条\n")
        f.write(f"总点赞数: {total_likes} 个\n")
        f.write(f"总回复数: {total_replies} 个\n\n")
        
        # 性别统计
        f.write("=== 用户性别分布 ===\n")
        for gender, count in gender_stats.most_common():
            percentage = (count / len(genders)) * 100 if genders else 0
            f.write(f"{gender}: {count} 名用户 ({percentage:.1f}%)\n")
        f.write("\n")
        
        # IP地区统计
        f.write("=== 用户IP地区分布 ===\n")
        for location, count in location_stats.most_common():
            percentage = (count / len(locations)) * 100 if locations else 0
            f.write(f"{location}: {count} 名用户 ({percentage:.1f}%)\n")
        f.write("\n")
        
        # 用户等级统计
        f.write("=== 用户等级分布 ===\n")
        for level, count in sorted(level_stats.items()):
            percentage = (count / len(levels)) * 100 if levels else 0
            f.write(f"LV{level}: {count} 名用户 ({percentage:.1f}%)\n")
        f.write("\n")
        
        # 评论类型统计
        f.write("=== 评论类型分布 ===\n")
        for comment_type, count in type_stats.most_common():
            percentage = (count / total_comments) * 100
            f.write(f"{comment_type}: {count} 条 ({percentage:.1f}%)\n")
        f.write("\n")
        
        # 热门评论统计（点赞数前10）
        f.write("=== 热门评论TOP10 ===\n")
        sorted_comments = sorted(all_comments, key=lambda x: x['点赞数'] if isinstance(x['点赞数'], int) else 0, reverse=True)
        for i, comment in enumerate(sorted_comments[:10], 1):
            f.write(f"{i}. 用户: {comment['用户名称']} | 点赞: {comment['点赞数']} | 内容: {comment['评论内容'][:50]}...\n")
    
    if logger:
        logger.info(f"统计信息已保存: {stats_filename}")
    
    print(f"📊 统计信息已生成: {stats_filename}")
    print(f"   - 总评论数: {total_comments} 条")
    print(f"   - 性别分布: {len(gender_stats)} 种")
    print(f"   - 地区分布: {len(location_stats)} 个地区")
    print(f"   - 等级分布: LV{min(levels) if levels else 0}-LV{max(levels) if levels else 0}")

def merge_and_deduplicate_comments(popularity_comments, time_comments, logger=None):
    """
    合并两个评论列表并去除重复评论（基于rpid和时间戳）
    
    Args:
        popularity_comments (list): 热度排序的评论列表
        time_comments (list): 时间排序的评论列表
        logger: 日志记录器
    
    Returns:
        tuple: (合并去重后的评论列表, 重复评论列表)
    """
    if logger:
        logger.info("开始合并和去重评论（基于rpid和时间戳）")
    
    # 使用基于爬取时间的去重逻辑
    def deduplicate_by_rpid(comments, comment_type):
        rpid_to_comment = {}
        duplicates = []
        
        def extract_crawl_time_from_filename(comment):
            """从评论数据的来源文件名中提取爬取时间"""
            # 尝试从评论数据中获取文件来源信息
            # 如果没有直接的文件名信息，使用时间戳作为备选
            crawl_time_str = comment.get('爬取时间', '')
            if crawl_time_str:
                try:
                    # 解析时间格式：YYYY年MM月DD日_HH时MM分SS秒
                    from datetime import datetime
                    dt = datetime.strptime(crawl_time_str, '%Y年%m月%d日_%H时%M分%S秒')
                    return int(dt.timestamp())
                except:
                    pass
            
            # 备选方案：使用评论的时间戳
            return comment.get('时间戳', 0)
        
        for comment in comments:
            rpid = comment.get('rpid', '')
            if rpid:
                # 如果已存在该rpid，比较爬取时间，保留爬取时间更晚的
                if rpid in rpid_to_comment:
                    existing_crawl_time = extract_crawl_time_from_filename(rpid_to_comment[rpid])
                    current_crawl_time = extract_crawl_time_from_filename(comment)
                    
                    if current_crawl_time > existing_crawl_time:
                        # 将旧评论标记为重复
                        old_comment = rpid_to_comment[rpid].copy()
                        old_comment['重复来源'] = comment_type
                        old_comment['原始评论来源'] = comment_type
                        duplicates.append(old_comment)
                        # 更新为新评论（保留动态属性：点赞数、回复数、时间戳等）
                        rpid_to_comment[rpid] = comment
                    else:
                        # 当前评论是重复的（爬取时间更早或相等）
                        duplicate_comment = comment.copy()
                        duplicate_comment['重复来源'] = comment_type
                        duplicate_comment['原始评论来源'] = comment_type
                        duplicates.append(duplicate_comment)
                else:
                    rpid_to_comment[rpid] = comment
        
        return list(rpid_to_comment.values()), duplicates
    
    # 第一步：对热度和时间爬取分别去重
    deduped_popularity, pop_duplicates = deduplicate_by_rpid(popularity_comments, "热度排序")
    deduped_time, time_duplicates = deduplicate_by_rpid(time_comments, "时间排序")
    
    # 第二步：合并两种爬取结果并去重
    all_comments = deduped_popularity + deduped_time
    final_comments, merge_duplicates = deduplicate_by_rpid(all_comments, "合并去重")
    
    # 合并所有重复评论
    all_duplicates = pop_duplicates + time_duplicates + merge_duplicates
    
    if logger:
        logger.info(f"合并完成：唯一评论 {len(final_comments)} 条，重复评论 {len(all_duplicates)} 条")
    
    return final_comments, all_duplicates

def crawl_comprehensive_mode_comments(oid, ps=20, delay_ms=1000, test_mode=False, logger=None, output_folder=None):
    """
    综合模式评论爬取：优先按热度爬取，如果不是因为reply为空而结束，则继续按时间爬取，最后合并去重
    
    Args:
        oid (str): 视频oid
        ps (int): 每页评论数量
        delay_ms (int): 请求延时（毫秒）
        test_mode (bool): 测试模式，只爬取一页
        logger: 日志记录器
        output_folder (str): 输出文件夹路径
    
    Returns:
        tuple: (热度爬取结果, 时间爬取结果, 合并去重结果, 重复评论列表, 热度爬取结束原因)
    """
    if logger:
        logger.info("开始综合模式爬取")
        logger.info("第一阶段：按热度排序爬取")
    
    print("\n=== 综合模式爬取 ===")
    print("📋 爬取策略：")
    print("   1️⃣ 优先按热度排序爬取所有评论")
    print("   2️⃣ 如果热度爬取未因评论耗尽而结束，则补充按时间排序爬取")
    print("   3️⃣ 合并数据并去除重复评论")
    print("   4️⃣ 按热度整理最终结果并生成统计")
    print()
    
    # 第一阶段：按热度排序爬取
    print("🔥 第一阶段：按热度排序爬取")
    popularity_comments, popularity_end_reason = crawl_all_comments_with_reason(
        oid=oid, 
        mode=1,  # 热度排序（按点赞数排序）
        ps=ps, 
        delay_ms=delay_ms, 
        test_mode=test_mode,
        logger=logger,
        output_folder=output_folder
    )
    
    if logger:
        logger.info(f"热度排序爬取完成，获得 {len(popularity_comments)} 条评论，结束原因：{popularity_end_reason}")
    print(f"✅ 热度排序爬取完成，共获得 {len(popularity_comments)} 条评论")
    print(f"📋 结束原因：{popularity_end_reason}")
    
    # 判断是否需要进行时间排序爬取
    time_comments = []
    need_time_crawl = popularity_end_reason != "评论已全部爬取完毕"
    
    if need_time_crawl:
        print("\n⏰ 第二阶段：补充按时间排序爬取")
        print(f"💡 由于热度爬取结束原因为'{popularity_end_reason}'，需要补充时间爬取以获取完整数据")
        time_comments, time_end_reason = crawl_all_comments_with_reason(
            oid=oid, 
            mode=0,  # 时间排序（按时间排序）
            ps=ps, 
            delay_ms=delay_ms, 
            test_mode=test_mode,
            logger=logger,
            output_folder=output_folder
        )
        
        if logger:
            logger.info(f"时间排序爬取完成，获得 {len(time_comments)} 条评论，结束原因：{time_end_reason}")
        print(f"✅ 时间排序爬取完成，共获得 {len(time_comments)} 条评论")
    else:
        print("\n⏭️ 跳过时间排序爬取")
        print("💡 热度爬取已获取所有评论，无需补充时间爬取")
        if logger:
            logger.info("跳过时间排序爬取，热度爬取已完整")
    
    # 第三阶段：合并和去重
    if time_comments:
        print("\n🔄 第三阶段：合并数据并去重")
        merged_comments, duplicate_comments = merge_and_deduplicate_comments(
            popularity_comments, time_comments, logger
        )
        
        if logger:
            logger.info(f"合并去重完成，最终获得 {len(merged_comments)} 条唯一评论，发现 {len(duplicate_comments)} 条重复评论")
        
        print(f"✅ 合并去重完成：")
        print(f"   📊 最终唯一评论：{len(merged_comments)} 条")
        print(f"   🔄 重复评论：{len(duplicate_comments)} 条")
        print(f"   📈 去重率：{len(duplicate_comments)/(len(popularity_comments)+len(time_comments))*100:.1f}%")
        print(f"   ✅ 数据验证：{len(merged_comments)} + {len(duplicate_comments)} = {len(merged_comments) + len(duplicate_comments)} (总爬取评论数)")
        print(f"   💡 说明：重复评论数高是因为两种排序模式返回了大量相同评论，这是B站API的特性")
    else:
        # 只有热度评论，无需去重
        merged_comments = popularity_comments
        duplicate_comments = []
        print("\n✅ 仅使用热度排序结果，无需去重")
        if logger:
            logger.info(f"仅使用热度排序结果，共 {len(merged_comments)} 条评论")
    
    return popularity_comments, time_comments, merged_comments, duplicate_comments, popularity_end_reason

def crawl_test_mode_comments(oid, sort_mode, ps=20, delay_ms=1000, max_pages=5, logger=None, output_folder=None):
    """
    测试模式爬取评论
    
    Args:
        oid (str): 视频oid
        sort_mode (int): 排序模式 (0=时间排序, 1=热度排序)
        ps (int): 每页评论数量
        delay_ms (int): 请求延时（毫秒）
        max_pages (int): 最大爬取页数
        logger: 日志记录器
        output_folder (str): 输出文件夹路径
    
    Returns:
        tuple: (评论列表, 结束原因)
    """
    if logger:
        logger.info(f"开始测试模式爬取，oid={oid}, sort_mode={sort_mode}, max_pages={max_pages}")
    
    sort_name = "热度排序" if sort_mode == 1 else "时间排序"
    print(f"🧪 测试模式爬取设置：")
    print(f"   📊 排序方式：{sort_name}")
    print(f"   📄 最大页数：{max_pages}")
    print(f"   📝 每页数量：{ps}")
    print(f"   ⏱️  请求延时：{delay_ms}ms")
    
    comments = []
    current_page = 1
    next_offset = ''
    
    while current_page <= max_pages:
        print(f"\n📄 正在爬取第 {current_page}/{max_pages} 页...")
        
        # 获取评论数据（页面日志记录器将在get_bilibili_comments函数内部创建）
        comments_data = get_bilibili_comments(oid, sort_mode, ps, next_offset, current_page == 1, current_page, logger, output_folder)
        
        if comments_data:
            data = comments_data.get('data', {})
            page_comments = data.get('replies', [])
            cursor = data.get('cursor', {})
            next_offset = cursor.get('next', '')
            has_more = cursor.get('is_end', False) == False
        else:
            page_comments = []
            next_offset = ''
            has_more = False
        
        if not page_comments:
            end_reason = "当前页无评论数据"
            print(f"⚠️  第 {current_page} 页无评论数据，停止爬取")
            if logger:
                logger.info(f"第 {current_page} 页无评论数据，爬取结束")
            break
        
        # 处理评论数据，转换为标准格式（不需要页面日志记录器，因为已在get_bilibili_comments中记录）
        processed_comments = process_comments_page(page_comments, start_index=len(comments)+1, logger=logger, oid=oid)
        comments.extend(processed_comments)
        print(f"✅ 第 {current_page} 页完成，获得 {len(page_comments)} 条评论")
        
        if logger:
            logger.info(f"第 {current_page} 页爬取完成，获得 {len(page_comments)} 条评论")
        
        # 检查是否还有更多页面
        if not has_more:
            end_reason = "评论已全部爬取完毕"
            print(f"✅ 所有评论已爬取完毕（共 {current_page} 页）")
            if logger:
                logger.info(f"所有评论已爬取完毕，共爬取 {current_page} 页")
            break
        
        current_page += 1
        
        # 请求延时
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
    
    # 如果达到最大页数限制
    if current_page > max_pages:
        end_reason = "已达到指定页数限制"
        if logger:
            logger.info(f"已达到指定页数限制 {max_pages}，爬取结束")
    
    print(f"\n🎯 测试模式爬取完成：")
    print(f"   📊 排序方式：{sort_name}")
    print(f"   📄 实际爬取：{current_page-1} 页")
    print(f"   💬 总评论数：{len(comments)} 条")
    print(f"   ⏹️  结束原因：{end_reason}")
    
    if logger:
        logger.info(f"测试模式爬取完成，共获得 {len(comments)} 条评论，结束原因：{end_reason}")
    
    return comments, end_reason

def process_comprehensive_mode_data(oid, popularity_comments, time_comments, merged_comments, duplicate_comments, output_folder, logger=None, video_title=None):
    """
    处理综合模式数据，生成4个文档
    
    Args:
        oid (str): 视频oid
        popularity_comments (list): 热度排序评论
        time_comments (list): 时间排序评论
        merged_comments (list): 合并去重评论
        duplicate_comments (list): 重复评论
        output_folder (str): 输出文件夹路径
        logger: 日志记录器
        video_title (str): 视频标题
    
    Returns:
        tuple: (原始数据文件夹路径, 4个文档路径列表)
    """
    # 创建原始数据文件夹
    raw_data_folder = os.path.join(output_folder, '原始数据')
    if not os.path.exists(raw_data_folder):
        os.makedirs(raw_data_folder)
    
    if logger:
        logger.info(f"创建原始数据文件夹: {raw_data_folder}")
    
    print(f"\n创建原始数据文件夹: {raw_data_folder}")
    
    # 生成4个文档
    doc_paths = []
    
    # 文档1：热度爬取结果
    doc1_filename = generate_safe_filename(video_title, oid, "热度排序爬取结果", "original")
    doc1_path = os.path.join(raw_data_folder, f'{doc1_filename}.csv')
    save_comments_to_csv(popularity_comments, doc1_path, '热度排序爬取结果')
    doc_paths.append(doc1_path)
    
    # 文档2：时间爬取结果
    doc2_filename = generate_safe_filename(video_title, oid, "时间排序爬取结果", "original")
    doc2_path = os.path.join(raw_data_folder, f'{doc2_filename}.csv')
    save_comments_to_csv(time_comments, doc2_path, '时间排序爬取结果')
    doc_paths.append(doc2_path)
    
    # 文档3：合并去重结果
    doc3_filename = generate_safe_filename(video_title, oid, "合并去重结果", "final")
    doc3_path = os.path.join(raw_data_folder, f'{doc3_filename}.csv')
    save_comments_to_csv(merged_comments, doc3_path, '合并去重结果')
    doc_paths.append(doc3_path)
    
    # 文档4：重复评论列表
    doc4_filename = generate_safe_filename(video_title, oid, "重复评论列表", "final")
    doc4_path = os.path.join(raw_data_folder, f'{doc4_filename}.csv')
    save_comments_to_csv(duplicate_comments, doc4_path, '重复评论列表')
    doc_paths.append(doc4_path)
    
    if logger:
        logger.info(f"生成4个原始数据文档完成")
        for i, path in enumerate(doc_paths, 1):
            logger.info(f"文档{i}: {path}")
    
    print("\n生成原始数据文档：")
    print(f"  1. 热度排序爬取结果: {len(popularity_comments)} 条评论")
    print(f"  2. 时间排序爬取结果: {len(time_comments)} 条评论")
    print(f"  3. 合并去重结果: {len(merged_comments)} 条评论")
    print(f"  4. 重复评论列表: {len(duplicate_comments)} 条评论")
    
    return raw_data_folder, doc_paths

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
            writer.writerow(['数据类型', '主楼序号', '楼中楼序号', '用户名称', '评论内容', '回复对象', '点赞数', '回复数', 'rpid', 'parent', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间'])
        return
    
    # 为评论添加数据类型标识
    comments_with_type = []
    for comment in comments:
        comment_with_type = comment.copy()
        comment_with_type['数据类型'] = data_type
        comments_with_type.append(comment_with_type)
    
    # 保存到CSV
    fieldnames = ['数据类型', '主楼序号', '楼中楼序号', '用户名称', '评论内容', '回复对象', '点赞数', '回复数', 'rpid', 'parent', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间']
    
    # 如果是重复评论，添加额外字段
    if comments_with_type and '重复来源' in comments_with_type[0]:
        fieldnames.extend(['重复来源', '原始评论来源'])
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comments_with_type)

def crawl_all_comments_with_reason(oid, mode=1, ps=20, delay_ms=1000, test_mode=False, logger=None, output_folder=None):
    """
    爬取所有评论并返回结束原因
    
    Args:
        oid: 视频的oid（稿件avid）
        mode (int): 排序模式，根据B站API文档：0=按时间排序，1=按点赞数排序（热度），2=按回复数排序
        ps (int): 每页评论数量
        delay_ms (int): 请求延时（毫秒）
        test_mode (bool): 是否为测试模式，测试模式只爬取一页
    
    Returns:
        tuple: (评论列表, 结束原因)
    """
    all_comments = []
    next_offset = ''
    page_count = 1
    total_comments = 0
    end_reason = "未知原因"
    
    # 定义排序模式名称映射
    mode_names = {0: '时间排序', 1: '热度排序', 2: '按回复数排序'}
    mode_name = mode_names.get(mode, f'未知模式({mode})')
    
    print(f"\n🚀 开始爬取评论 (oid: {oid})")
    print(f"📊 排序模式: {mode_name}")
    print(f"📄 每页数量: {ps}条")
    print(f"⏱️  延时设置: {delay_ms}ms")
    print(f"🧪 测试模式: {'是' if test_mode else '否'}")
    
    while True:
        print(f"\n📄 正在爬取第 {page_count} 页...")
        
        # 获取评论数据
        is_first_page = (page_count == 1)
        result = get_bilibili_comments(oid, mode, ps, next_offset, is_first_page, page_count, logger, output_folder)
        
        if not result:
            end_reason = "API请求失败"
            print(f"❌ {end_reason}，停止爬取")
            break
        
        # 检查响应状态
        if result.get('code') != 0:
            end_reason = f"API返回错误: {result.get('message', '未知错误')}"
            print(f"❌ {end_reason}")
            break
        
        # 获取评论数据
        data = result.get('data', {})
        replies = data.get('replies', [])
        
        if not replies:
            end_reason = "评论已全部爬取完毕"
            print(f"ℹ️  {end_reason}")
            break
        
        print(f"✅ 本页获取到 {len(replies)} 条评论")
        
        # 处理评论数据
        start_index = total_comments + 1
        page_comments = process_comments_page(replies, start_index, oid=oid)
        all_comments.extend(page_comments)
        total_comments += len(page_comments)
        
        print(f"📈 累计处理 {total_comments} 条评论")
        
        # 检查分页信息
        cursor = data.get('cursor', {})
        next_offset = cursor.get('next', '')
        
        # 测试模式只爬取一页
        if test_mode:
            end_reason = "测试模式限制"
            print(f"🧪 {end_reason}，停止爬取")
            break
        
        page_count += 1
        
        # 添加延时
        if delay_ms > 0:
            print(f"⏳ 等待 {delay_ms}ms...")
            time.sleep(delay_ms / 1000)
    
    print(f"\n🎉 评论爬取完成！")
    print(f"📊 总共爬取了 {page_count} 页，{total_comments} 条评论")
    print(f"🏁 结束原因：{end_reason}")
    
    return all_comments, end_reason

def crawl_all_comments(oid, mode=3, ps=20, delay_ms=1000, test_mode=False, video_title=None, video_info=None):
    """
    爬取所有评论（兼容性函数）
    
    Args:
        oid: 视频的oid（稿件avid）
        mode (int): 排序模式，3为热度排序，2为时间排序
        ps (int): 每页评论数量
        delay_ms (int): 请求延时（毫秒）
        test_mode (bool): 是否为测试模式，测试模式只爬取一页
    
    Returns:
        bool: 是否成功
    """
    # 确定模式类型
    if test_mode:
        mode_type = "test_time" if mode == 2 else "test_popularity"
    else:
        mode_type = None
    
    # 创建输出文件夹
    output_folder = create_output_folder(oid, video_title, mode_type)
    print(f"📁 输出文件夹已创建: {output_folder}")
    
    # 设置日志
    logger, main_log_file = setup_logging(oid, output_folder)
    print(f"📄 主日志文件: {os.path.basename(main_log_file)}")
    
    all_comments = []
    next_offset = ''
    page_count = 1
    total_comments = 0
    
    print(f"\n🚀 开始爬取评论 (oid: {oid})")
    print(f"📊 排序模式: {'热度排序' if mode == 3 else '时间排序'}")
    print(f"📄 每页数量: {ps}条")
    print(f"⏱️  延时设置: {delay_ms}ms")
    print(f"🧪 测试模式: {'是' if test_mode else '否'}")
    print(f"📄 停止条件: 当返回数据为空时自动停止")
    
    logger.info(f"开始爬取评论，oid: {oid}, 排序模式: {mode}, 延时: {delay_ms}ms, 测试模式: {test_mode}")
    
    while True:
        print(f"\n📄 正在爬取第 {page_count} 页...")
        logger.info(f"开始爬取第 {page_count} 页")
        
        # 获取评论数据
        is_first_page = (page_count == 1)
        result = get_bilibili_comments(oid, mode, ps, next_offset, is_first_page, page_count, logger, output_folder)
        
        if not result:
            error_msg = "获取评论失败，停止爬取"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            break
        
        # 检查响应状态
        if result.get('code') != 0:
            error_msg = f"API返回错误: {result.get('message', '未知错误')}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            break
        
        # 获取评论数据
        data = result.get('data', {})
        replies = data.get('replies', [])
        
        if not replies:
            info_msg = "没有更多评论了"
            print(f"ℹ️  {info_msg}")
            logger.info(info_msg)
            break
        
        print(f"✅ 本页获取到 {len(replies)} 条评论")
        logger.info(f"第 {page_count} 页获取到 {len(replies)} 条评论")
        
        # 处理评论数据
        start_index = total_comments + 1
        page_comments = process_comments_page(replies, start_index, logger, oid=oid)
        all_comments.extend(page_comments)
        total_comments += len(page_comments)
        
        print(f"📈 累计处理 {total_comments} 条评论")
        logger.info(f"第 {page_count} 页处理完成，累计 {total_comments} 条评论")
        
        # 检查分页信息
        cursor = data.get('cursor', {})
        logger.debug(f"分页信息: {cursor}")
        
        # 获取下一页的偏移量
        next_offset = cursor.get('next', '')
        is_end = cursor.get('is_end', False)
        has_next = cursor.get('has_next', False)
        
        logger.debug(f"next_offset: {next_offset}, is_end: {is_end}, has_next: {has_next}")
        
        # 判断是否继续 - 只有当replies为空时才停止
        if not replies:
            continue_reason = "返回数据为空，停止爬取"
            print(f"🏁 {continue_reason}")
            logger.info(f"分页判断: {continue_reason}")
            break
        
        # 如果有数据，继续爬取下一页
        logger.info(f"分页判断: 检测到评论数据，继续爬取下一页")
        
        # 测试模式只爬取一页
        if test_mode:
            print(f"🧪 测试模式，只爬取一页")
            logger.info("测试模式，停止爬取")
            break
        
        page_count += 1
        
        # 添加延时
        if delay_ms > 0:
            print(f"⏳ 等待 {delay_ms}ms...")
            logger.debug(f"延时 {delay_ms}ms")
            time.sleep(delay_ms / 1000)
    
    print(f"\n🎉 评论爬取完成！")
    print(f"📊 总共爬取了 {page_count} 页，{total_comments} 条评论")
    logger.info(f"爬取完成，总共 {page_count} 页，{total_comments} 条评论")
    
    # 整理和保存数据
    if all_comments:
        try:
            print(f"\n📊 开始整理和统计数据...")
            logger.info("开始数据整理和统计")
            
            # 调用数据整理和统计函数（按热度排序）
            _, processed_file, stats_file = process_and_organize_data(
                all_comments, output_folder, oid, logger, video_title, sort_by_popularity=True, video_info=video_info
            )
            
            # 如果是时间排序模式，生成按时间统计的文件
            time_stats_files = []
            if mode == 2:  # 时间排序模式
                print(f"\n⏰ 检测到时间排序模式，开始生成时间统计文件...")
                logger.info("开始生成按时间统计的文件")
                bv_id = aid_to_bvid(int(oid))
                time_stats_files = generate_restructured_time_statistics(all_comments, output_folder, bv_id, logger, video_title, video_info)
                
                if time_stats_files:
                    print(f"✅ 时间统计完成，生成了 {len(time_stats_files)} 个统计文件")
                    for file_path in time_stats_files:
                        print(f"📄 时间统计文件: {os.path.basename(file_path)}")
                    logger.info(f"时间统计文件生成完成，共 {len(time_stats_files)} 个文件")
                else:
                    print(f"⚠️  时间统计文件生成失败")
                    logger.warning("时间统计文件生成失败")
            
            print(f"\n✅ 数据处理完成！")
            print(f"📁 输出文件夹: {output_folder}")
            if processed_file:
                print(f"📄 整理数据（热度排序）: {os.path.basename(processed_file)}")
            print(f"📄 统计报告: {os.path.basename(stats_file)}")
            
            # 生成文件夹结构文档
            print("\n📋 生成文件夹结构文档...")
            # 生成BV号
            try:
                bv_id = aid_to_bvid(int(oid))
            except:
                bv_id = None
            structure_md_path = generate_folder_structure_md(output_folder, oid, video_title, logger, bv_id)
            if structure_md_path:
                print(f"📄 文件夹结构文档: {os.path.basename(structure_md_path)}")
            
            logger.info("数据处理和统计完成")
            return True
        except Exception as e:
            error_msg = f"数据处理失败: {e}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            return False
    else:
        error_msg = "没有获取到任何评论数据"
        print(f"❌ {error_msg}")
        logger.error(error_msg)
        return False

def crawl_iteration_mode_comments(oid, ps, delay_ms, iteration_config, logger, output_folder, video_title=None, video_info=None):
    """
    迭代模式爬取评论
    
    Args:
        oid: 视频oid
        ps: 每页评论数
        delay_ms: 请求延时
        iteration_config: 迭代配置
        logger: 日志记录器
        output_folder: 输出文件夹
    
    Returns:
        bool: 是否成功
    """
    try:
        iteration_type = iteration_config['type']
        
        if iteration_type == 'time':
            # 时间迭代模式
            iteration_hours = iteration_config['hours']
            print(f"🕐 时间迭代模式: {iteration_hours} 小时")
            logger.info(f"开始时间迭代模式，迭代时间: {iteration_hours} 小时")
            
            return crawl_time_iteration(oid, ps, delay_ms, iteration_hours, logger, output_folder, video_title, video_info)
            
        elif iteration_type == 'duplicate_rate':
            # 重复率迭代模式
            popularity_threshold = iteration_config['hot_rate_threshold']
            time_threshold = iteration_config['time_rate_threshold']
            print(f"📊 重复率迭代模式: 热度阈值={popularity_threshold}%, 时间阈值={time_threshold}%")
            logger.info(f"开始重复率迭代模式，热度阈值: {popularity_threshold}%, 时间阈值: {time_threshold}%")
            
            return crawl_duplicate_rate_iteration(oid, ps, delay_ms, popularity_threshold, time_threshold, logger, output_folder, video_title, video_info)
            
        else:
            logger.error(f"未知的迭代类型: {iteration_type}")
            return False
            
    except Exception as e:
        logger.error(f"迭代模式爬取失败: {e}")
        return False

def crawl_time_iteration(oid, ps, delay_ms, iteration_hours, logger, output_folder, video_title=None, video_info=None):
    """
    时间迭代模式：热度-时间交替爬取直到达到时间限制
    
    Args:
        oid: 视频oid
        ps: 每页评论数
        delay_ms: 请求延时
        iteration_hours: 迭代时间（小时）
        logger: 日志记录器
        output_folder: 输出文件夹
    
    Returns:
        bool: 是否成功
    """
    import time
    from datetime import datetime, timedelta
    
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=iteration_hours)
    
    # 创建迭代数据存储文件夹
    iteration_folder = os.path.join(output_folder, '原始数据')
    popularity_folder = os.path.join(iteration_folder, '热度爬取原始数据')
    time_folder = os.path.join(iteration_folder, '时间爬取原始数据')
    
    for folder in [iteration_folder, popularity_folder, time_folder]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    
    if logger:
        logger.info(f"创建迭代数据文件夹: {iteration_folder}")
        logger.info(f"创建热度爬取文件夹: {popularity_folder}")
        logger.info(f"创建时间爬取文件夹: {time_folder}")
    
    print(f"\n📁 创建迭代数据文件夹: {iteration_folder}")
    print(f"📁 热度爬取原始数据: {popularity_folder}")
    print(f"📁 时间爬取原始数据: {time_folder}")
    
    iteration_count = 0
    all_popularity_comments = []
    all_time_comments = []
    
    logger.info(f"时间迭代开始，预计结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    while datetime.now() < end_time:
        iteration_count += 1
        current_time = datetime.now()
        remaining_time = end_time - current_time
        
        print(f"\n🔄 第 {iteration_count} 轮迭代 (剩余时间: {str(remaining_time).split('.')[0]})")
        logger.info(f"开始第 {iteration_count} 轮迭代")
        
        # 热度排序爬取
        print(f"🔥 热度排序爬取...")
        popularity_comments, popularity_reason = crawl_all_comments_with_reason(
            oid=oid, mode=1, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder
        )
        
        if popularity_comments:
            # 保存热度爬取原始数据
            popularity_filename = generate_safe_filename(video_title, oid, f"第{iteration_count}次热度排序爬取结果", "original")
            popularity_file = os.path.join(popularity_folder, f'{popularity_filename}.csv')
            save_comments_to_csv(popularity_comments, popularity_file, f"第{iteration_count}次热度排序爬取结果")
            all_popularity_comments.extend(popularity_comments)
            
            print(f"   ✅ 热度爬取完成: {len(popularity_comments)} 条评论")
            print(f"   💾 已保存: {os.path.basename(popularity_file)}")
            logger.info(f"第 {iteration_count} 轮热度爬取完成: {len(popularity_comments)} 条评论")
            logger.info(f"热度爬取原始数据已保存: {popularity_file}")
        
        # 检查剩余时间
        if datetime.now() >= end_time:
            print("⏰ 时间已到，停止迭代")
            break
        
        # 时间排序爬取
        print(f"⏰ 时间排序爬取...")
        time_comments, time_reason = crawl_all_comments_with_reason(
            oid=oid, mode=0, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder
        )
        
        if time_comments:
            # 保存时间爬取原始数据
            time_filename = generate_safe_filename(video_title, oid, f"第{iteration_count}次时间排序爬取结果", "original")
            time_file = os.path.join(time_folder, f'{time_filename}.csv')
            save_comments_to_csv(time_comments, time_file, f"第{iteration_count}次时间排序爬取结果")
            all_time_comments.extend(time_comments)
            
            print(f"   ✅ 时间爬取完成: {len(time_comments)} 条评论")
            print(f"   💾 已保存: {os.path.basename(time_file)}")
            logger.info(f"第 {iteration_count} 轮时间爬取完成: {len(time_comments)} 条评论")
            logger.info(f"时间爬取原始数据已保存: {time_file}")
        
        # 检查是否还有时间进行下一轮
        if datetime.now() >= end_time:
            print("⏰ 时间已到，停止迭代")
            break
        
        # 轮次间隔
        time.sleep(2)
    
    # 执行迭代去重
    print(f"\n🔄 开始迭代去重处理...")
    deduped_popularity, deduped_time, merged_comments, duplicate_comments = perform_iteration_deduplication(
        all_popularity_comments, all_time_comments, logger
    )
    
    # 保存三份去重结果到原始数据文件夹
    popularity_filename = generate_safe_filename(video_title, oid, "按热度迭代去重结果", "final")
    time_filename = generate_safe_filename(video_title, oid, "按时间迭代去重结果", "final")
    final_filename = generate_safe_filename(video_title, oid, "合并去重结果", "final")
    
    popularity_file = os.path.join(iteration_folder, f'{popularity_filename}.csv')
    time_file = os.path.join(iteration_folder, f'{time_filename}.csv')
    final_file = os.path.join(iteration_folder, f'{final_filename}.csv')
    
    save_comments_to_csv(deduped_popularity, popularity_file, "按热度迭代去重结果")
    save_comments_to_csv(deduped_time, time_file, "按时间迭代去重结果")
    save_comments_to_csv(merged_comments, final_file, "合并去重结果")
    
    print(f"\n💾 按热度去重结果已保存: {os.path.basename(popularity_file)}")
    print(f"💾 按时间去重结果已保存: {os.path.basename(time_file)}")
    print(f"💾 合并去重结果已保存: {os.path.basename(final_file)}")
    logger.info(f"按热度去重结果已保存: {popularity_file}")
    logger.info(f"按时间去重结果已保存: {time_file}")
    logger.info(f"合并去重结果已保存: {final_file}")
    
    # 优化：不再生成热度排序和时间排序的原始数据文件
    # 只保存合并去重结果和重复评论列表
    print("\n=== 开始生成必要的原始数据文档 ===")
    
    # 创建原始数据文件夹
    raw_data_folder = os.path.join(output_folder, '原始数据')
    if not os.path.exists(raw_data_folder):
        os.makedirs(raw_data_folder)
    
    # 计算重复评论列表
    duplicate_comments = []
    all_rpids = set()
    for comment in all_popularity_comments + all_time_comments:
        rpid = comment.get('rpid', '')
        if rpid in all_rpids:
            duplicate_comments.append(comment)
        else:
            all_rpids.add(rpid)
    
    # 只保存重复评论列表（合并去重结果已在上面保存）
    duplicate_filename = generate_safe_filename(video_title, oid, "重复评论列表", "final")
    duplicate_file = os.path.join(raw_data_folder, f'{duplicate_filename}.csv')
    save_comments_to_csv(duplicate_comments, duplicate_file, '重复评论列表')
    
    print(f"💾 重复评论列表已保存: {os.path.basename(duplicate_file)}")
    logger.info(f"重复评论列表已保存: {duplicate_file}")
    
    print(f"✅ 优化完成：跳过生成热度排序和时间排序原始数据文件")
    print(f"   - 合并去重结果: {len(merged_comments)} 条评论")
    print(f"   - 重复评论列表: {len(duplicate_comments)} 条评论")
    
    # 对合并结果进行双重整理（与综合模式相同）
    print("\n=== 开始双重整理 ===")
    print("1. 按热度排序整理...")
    
    # 按热度排序整理（使用合并后的数据）
    _, popularity_organized_file, popularity_stats_file = process_and_organize_data(
        merged_comments, output_folder, oid, logger, video_title, sort_by_popularity=True, video_info=video_info, mode="iteration"
    )
    
    print("2. 按时间统计整理...")
    
    # 按时间统计整理（使用合并后的数据）- 不生成整理文件
    _, _, time_stats_file = process_and_organize_data(
        merged_comments, output_folder, oid, logger, video_title, sort_by_popularity=False, video_info=video_info, mode="iteration"
    )
    
    # 生成智能时间统计文件
    print("3. 生成时间统计分析...")
    bv_id = aid_to_bvid(int(oid))
    time_analysis_files = generate_restructured_time_statistics(
        merged_comments, output_folder, bv_id, logger, video_title, video_info
    )
    
    if time_analysis_files:
        print(f"   ✅ 已生成 {len(time_analysis_files)} 个时间统计文件")
        for file_path in time_analysis_files:
            print(f"      - {os.path.basename(file_path)}")
    else:
        print("   ⚠️  未生成时间统计文件（可能因为数据不足）")
    
    # 生成统计报告
    generate_iteration_statistics(
        all_popularity_comments, all_time_comments, merged_comments, 
        iteration_count, iteration_hours, output_folder, oid, logger,
        deduped_popularity=deduped_popularity, deduped_time=deduped_time,
        bv_id=bv_id, video_title=video_title
    )
    
    print(f"\n✅ 时间迭代完成: {iteration_count} 轮迭代，最终获得 {len(merged_comments)} 条唯一评论")
    logger.info(f"时间迭代完成: {iteration_count} 轮迭代，最终获得 {len(merged_comments)} 条唯一评论")
    
    # 生成文件夹结构文档
    try:
        # 生成BV号
        try:
            bv_id = aid_to_bvid(int(oid))
        except:
            bv_id = None
        structure_md_path = generate_folder_structure_md(output_folder, oid, video_title, logger, bv_id)
        print(f"📄 文件夹结构文档: {os.path.basename(structure_md_path)}")
    except Exception as e:
        logger.error(f"生成文件夹结构文档失败: {e}")
    
    return True

def crawl_duplicate_rate_iteration(oid, ps, delay_ms, popularity_threshold, time_threshold, logger, output_folder, video_title=None, video_info=None):
    """
    重复率迭代模式：根据重复率阈值决定停止条件
    
    Args:
        oid: 视频oid
        ps: 每页评论数
        delay_ms: 请求延时
        popularity_threshold: 热度爬取重复率阈值
        time_threshold: 时间爬取重复率阈值
        logger: 日志记录器
        output_folder: 输出文件夹
    
    Returns:
        bool: 是否成功
    """
    import time
    from datetime import datetime
    
    # 创建迭代数据存储文件夹
    iteration_folder = os.path.join(output_folder, '原始数据')
    popularity_folder = os.path.join(iteration_folder, '热度爬取原始数据')
    time_folder = os.path.join(iteration_folder, '时间爬取原始数据')
    
    for folder in [iteration_folder, popularity_folder, time_folder]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    
    if logger:
        logger.info(f"创建迭代数据文件夹: {iteration_folder}")
        logger.info(f"创建热度爬取文件夹: {popularity_folder}")
        logger.info(f"创建时间爬取文件夹: {time_folder}")
    
    print(f"\n📁 创建迭代数据文件夹: {iteration_folder}")
    print(f"📁 热度爬取原始数据: {popularity_folder}")
    print(f"📁 时间爬取原始数据: {time_folder}")
    
    iteration_count = 0
    all_popularity_comments = []
    all_time_comments = []
    
    # 存储每轮的rpid集合用于计算重复率
    popularity_rpid_history = []
    time_rpid_history = []
    
    # 存储每轮重复率数据
    popularity_duplicate_rates = []
    time_duplicate_rates = []
    
    # 控制爬取方式的继续状态
    popularity_continue = True
    time_continue = True
    
    logger.info(f"重复率迭代开始，热度阈值: {popularity_threshold}%, 时间阈值: {time_threshold}%")
    
    while popularity_continue or time_continue:
        iteration_count += 1
        print(f"\n🔄 第 {iteration_count} 轮迭代")
        logger.info(f"开始第 {iteration_count} 轮迭代")
        
        # 热度排序爬取（仅在未达到阈值时执行）
        if popularity_continue:
            print(f"🔥 热度排序爬取...")
            popularity_comments, popularity_reason = crawl_all_comments_with_reason(
                oid=oid, mode=1, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder
            )
            
            if popularity_comments:
                # 计算重复率
                current_rpids = set(comment.get('rpid', '') for comment in popularity_comments if comment.get('rpid'))
                popularity_rpid_history.append(current_rpids)
                
                if len(popularity_rpid_history) >= 2:
                    duplicate_rate = calculate_duplicate_rate(
                        popularity_rpid_history[-2], popularity_rpid_history[-1]
                    )
                    popularity_duplicate_rates.append(duplicate_rate)
                    print(f"   📊 热度爬取重复率: {duplicate_rate:.1f}%")
                    logger.info(f"第 {iteration_count} 轮热度爬取重复率: {duplicate_rate:.1f}%")
                    
                    if duplicate_rate >= popularity_threshold:
                        print(f"   🛑 热度爬取重复率达到阈值 ({popularity_threshold}%)，后续轮次将跳过热度爬取")
                        popularity_continue = False
                
                # 保存热度爬取原始数据
                popularity_filename = generate_safe_filename(video_title, oid, f"第{iteration_count}次热度排序爬取结果", "original")
                popularity_file = os.path.join(popularity_folder, f'{popularity_filename}.csv')
                save_comments_to_csv(popularity_comments, popularity_file, f"第{iteration_count}次热度排序爬取结果")
                all_popularity_comments.extend(popularity_comments)
                print(f"   ✅ 热度爬取完成: {len(popularity_comments)} 条评论")
                print(f"   💾 已保存: {os.path.basename(popularity_file)}")
                logger.info(f"热度爬取原始数据已保存: {popularity_file}")
            else:
                print(f"   ⚠️  热度爬取未获取到评论，停止热度爬取")
                popularity_continue = False
        else:
            print(f"🔥 热度排序爬取已跳过（重复率已达阈值）")
        
        # 时间排序爬取（仅在未达到阈值时执行）
        if time_continue:
            print(f"⏰ 时间排序爬取...")
            time_comments, time_reason = crawl_all_comments_with_reason(
                oid=oid, mode=0, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder
            )
            
            if time_comments:
                # 计算重复率
                current_rpids = set(comment.get('rpid', '') for comment in time_comments if comment.get('rpid'))
                time_rpid_history.append(current_rpids)
                
                if len(time_rpid_history) >= 2:
                    duplicate_rate = calculate_duplicate_rate(
                        time_rpid_history[-2], time_rpid_history[-1]
                    )
                    time_duplicate_rates.append(duplicate_rate)
                    print(f"   📊 时间爬取重复率: {duplicate_rate:.1f}%")
                    logger.info(f"第 {iteration_count} 轮时间爬取重复率: {duplicate_rate:.1f}%")
                    
                    if duplicate_rate >= time_threshold:
                        print(f"   🛑 时间爬取重复率达到阈值 ({time_threshold}%)，后续轮次将跳过时间爬取")
                        time_continue = False
                
                # 保存时间爬取原始数据
                time_filename = generate_safe_filename(video_title, oid, f"第{iteration_count}次时间排序爬取结果", "original")
                time_file = os.path.join(time_folder, f'{time_filename}.csv')
                save_comments_to_csv(time_comments, time_file, f"第{iteration_count}次时间排序爬取结果")
                all_time_comments.extend(time_comments)
                print(f"   ✅ 时间爬取完成: {len(time_comments)} 条评论")
                print(f"   💾 已保存: {os.path.basename(time_file)}")
                logger.info(f"时间爬取原始数据已保存: {time_file}")
            else:
                print(f"   ⚠️  时间爬取未获取到评论，停止时间爬取")
                time_continue = False
        else:
            print(f"⏰ 时间排序爬取已跳过（重复率已达阈值）")
        
        # 检查是否应该停止迭代
        if not popularity_continue and not time_continue:
            print(f"\n🛑 两种爬取方式的重复率都达到阈值，停止迭代")
            logger.info("重复率迭代结束：两种爬取方式的重复率都达到阈值")
            break
        
        # 轮次间隔
        time.sleep(2)
    
    # 执行迭代去重
    print(f"\n🔄 开始迭代去重处理...")
    deduped_popularity, deduped_time, merged_comments, duplicate_comments = perform_iteration_deduplication(
        all_popularity_comments, all_time_comments, logger
    )
    
    # 保存三份去重结果到原始数据文件夹
    popularity_filename = generate_safe_filename(video_title, oid, "按热度迭代去重结果", "final")
    time_filename = generate_safe_filename(video_title, oid, "按时间迭代去重结果", "final")
    final_filename = generate_safe_filename(video_title, oid, "合并去重结果", "final")
    
    popularity_file = os.path.join(iteration_folder, f'{popularity_filename}.csv')
    time_file = os.path.join(iteration_folder, f'{time_filename}.csv')
    final_file = os.path.join(iteration_folder, f'{final_filename}.csv')
    
    save_comments_to_csv(deduped_popularity, popularity_file, "按热度迭代去重结果")
    save_comments_to_csv(deduped_time, time_file, "按时间迭代去重结果")
    save_comments_to_csv(merged_comments, final_file, "合并去重结果")
    
    print(f"\n💾 按热度去重结果已保存: {os.path.basename(popularity_file)}")
    print(f"💾 按时间去重结果已保存: {os.path.basename(time_file)}")
    print(f"💾 合并去重结果已保存: {os.path.basename(final_file)}")
    logger.info(f"按热度去重结果已保存: {popularity_file}")
    logger.info(f"按时间去重结果已保存: {time_file}")
    logger.info(f"合并去重结果已保存: {final_file}")
    
    # 处理迭代模式数据，仅生成重复评论列表
    print("\n=== 开始生成重复评论列表 ===")
    # 生成重复评论列表
    duplicate_comments = []
    # 从原始数据中找出重复的评论
    all_rpids = set()
    for comment in all_popularity_comments + all_time_comments:
        rpid = comment.get('rpid', '')
        if rpid in all_rpids:
            duplicate_comments.append(comment)
        else:
            all_rpids.add(rpid)
    
    # 创建原始数据文件夹
    raw_data_folder = os.path.join(output_folder, "原始数据")
    os.makedirs(raw_data_folder, exist_ok=True)
    
    # 仅保存重复评论列表
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    duplicate_file = os.path.join(raw_data_folder, f"评论爬取_重复评论列表_{video_title}_{oid}_{timestamp}.csv")
    save_comments_to_csv(duplicate_comments, duplicate_file, "重复评论列表")
    print(f"💾 重复评论列表已保存: {os.path.basename(duplicate_file)}")
    logger.info(f"重复评论列表已保存: {duplicate_file}")
    
    # 对合并结果进行双重整理（与综合模式相同）
    print("\n=== 开始双重整理 ===")
    print("1. 按热度排序整理...")
    
    # 按热度排序整理（使用合并后的数据）
    _, popularity_organized_file, popularity_stats_file = process_and_organize_data(
        merged_comments, output_folder, oid, logger, video_title, sort_by_popularity=True, video_info=video_info
    )
    
    print("2. 按时间统计整理...")
    
    # 按时间统计整理（使用合并后的数据）- 不生成整理文件
    _, _, time_stats_file = process_and_organize_data(
        merged_comments, output_folder, oid, logger, video_title, sort_by_popularity=False, video_info=video_info
    )
    
    # 生成智能时间统计文件
    print("3. 生成时间统计分析...")
    bv_id = aid_to_bvid(int(oid))
    time_analysis_files = generate_restructured_time_statistics(
        merged_comments, output_folder, bv_id, logger, video_title, video_info
    )
    
    if time_analysis_files:
        print(f"   ✅ 已生成 {len(time_analysis_files)} 个时间统计文件")
        for file_path in time_analysis_files:
            print(f"      - {os.path.basename(file_path)}")
    else:
        print("   ⚠️  未生成时间统计文件（可能因为数据不足）")
    
    # 生成统计报告
    generate_iteration_statistics(
        all_popularity_comments, all_time_comments, merged_comments, 
        iteration_count, None, output_folder, oid, logger, 
        popularity_threshold=popularity_threshold, time_threshold=time_threshold,
        deduped_popularity=deduped_popularity, deduped_time=deduped_time,
        popularity_duplicate_rates=popularity_duplicate_rates, time_duplicate_rates=time_duplicate_rates,
        bv_id=bv_id, video_title=video_title
    )
    
    print(f"\n✅ 重复率迭代完成: {iteration_count} 轮迭代，最终获得 {len(merged_comments)} 条唯一评论")
    logger.info(f"重复率迭代完成: {iteration_count} 轮迭代，最终获得 {len(merged_comments)} 条唯一评论")
    
    # 生成文件夹结构文档
    try:
        # 生成BV号
        try:
            bv_id = aid_to_bvid(int(oid))
        except:
            bv_id = None
        structure_md_path = generate_folder_structure_md(output_folder, oid, video_title, logger, bv_id)
        print(f"📄 文件夹结构文档: {os.path.basename(structure_md_path)}")
    except Exception as e:
        logger.error(f"生成文件夹结构文档失败: {e}")
    
    return True

def calculate_duplicate_rate(prev_rpids, current_rpids):
    """
    计算两次爬取的重复率
    
    Args:
        prev_rpids: 上一次爬取的rpid集合
        current_rpids: 当前爬取的rpid集合
    
    Returns:
        float: 重复率百分比
    """
    if not current_rpids:
        return 0.0
    
    intersection = prev_rpids.intersection(current_rpids)
    duplicate_rate = (len(intersection) / len(current_rpids)) * 100
    
    return duplicate_rate

def perform_iteration_deduplication(popularity_comments, time_comments, logger):
    """
    执行迭代去重算法：按时间顺序保留最新数据，先对同类型爬取去重，再合并去重
    
    Args:
        popularity_comments: 所有热度爬取的评论
        time_comments: 所有时间爬取的评论
        logger: 日志记录器
    
    Returns:
        tuple: (热度去重结果, 时间去重结果, 合并去重结果)
    """
    logger.info("开始迭代去重处理")
    
    # 第一步：对同类型爬取进行去重（保留最新的）
    def deduplicate_by_rpid(comments, comment_type):
        """统一的去重函数，基于rpid和爬取时间去重，与综合模式保持一致"""
        rpid_to_comment = {}
        duplicates = []
        
        def extract_crawl_time_from_filename(comment):
            """从评论数据的来源文件名中提取爬取时间"""
            # 尝试从评论数据中获取文件来源信息
            # 如果没有直接的文件名信息，使用时间戳作为备选
            crawl_time_str = comment.get('爬取时间', '')
            if crawl_time_str:
                try:
                    # 解析时间格式：YYYY年MM月DD日_HH时MM分SS秒
                    from datetime import datetime
                    dt = datetime.strptime(crawl_time_str, '%Y年%m月%d日_%H时%M分%S秒')
                    return int(dt.timestamp())
                except:
                    pass
            
            # 备选方案：使用评论的时间戳
            return comment.get('时间戳', 0)
        
        for comment in comments:
            rpid = comment.get('rpid', '')
            if rpid:
                # 如果已存在该rpid，比较爬取时间，保留爬取时间更晚的
                if rpid in rpid_to_comment:
                    existing_crawl_time = extract_crawl_time_from_filename(rpid_to_comment[rpid])
                    current_crawl_time = extract_crawl_time_from_filename(comment)
                    
                    if current_crawl_time > existing_crawl_time:
                        # 将旧评论标记为重复
                        old_comment = rpid_to_comment[rpid].copy()
                        old_comment['重复来源'] = comment_type
                        old_comment['原始评论来源'] = comment_type
                        duplicates.append(old_comment)
                        # 更新为新评论（保留动态属性：点赞数、回复数、时间戳等）
                        rpid_to_comment[rpid] = comment
                    else:
                        # 当前评论是重复的（爬取时间更早或相等）
                        duplicate_comment = comment.copy()
                        duplicate_comment['重复来源'] = comment_type
                        duplicate_comment['原始评论来源'] = comment_type
                        duplicates.append(duplicate_comment)
                else:
                    rpid_to_comment[rpid] = comment
        
        deduped_comments = list(rpid_to_comment.values())
        logger.info(f"{comment_type}去重: {len(comments)} -> {len(deduped_comments)} 条评论，重复 {len(duplicates)} 条")
        return deduped_comments, duplicates
    
    # 对热度和时间爬取分别去重
    deduped_popularity, pop_duplicates = deduplicate_by_rpid(popularity_comments, "热度爬取")
    deduped_time, time_duplicates = deduplicate_by_rpid(time_comments, "时间爬取")
    
    # 第二步：合并两种爬取结果并去重
    all_comments = deduped_popularity + deduped_time
    final_comments, merge_duplicates = deduplicate_by_rpid(all_comments, "最终合并")
    
    # 合并所有重复评论
    all_duplicates = pop_duplicates + time_duplicates + merge_duplicates
    
    logger.info(f"迭代去重完成: 热度{len(deduped_popularity)}条，时间{len(deduped_time)}条，合并{len(final_comments)}条，总重复{len(all_duplicates)}条")
    return deduped_popularity, deduped_time, final_comments, all_duplicates

def generate_iteration_statistics(popularity_comments, time_comments, merged_comments, 
                                iteration_count, iteration_hours, output_folder, oid, logger,
                                deduped_popularity=None, deduped_time=None,
                                popularity_threshold=None, time_threshold=None,
                                popularity_duplicate_rates=None, time_duplicate_rates=None,
                                bv_id=None, video_title=None):
    """
    生成合并的迭代统计报告
    
    Args:
        popularity_comments: 热度爬取评论
        time_comments: 时间爬取评论
        merged_comments: 合并后评论
        iteration_count: 迭代轮数
        iteration_hours: 迭代时间（时间迭代模式）
        output_folder: 输出文件夹
        oid: 视频oid
        logger: 日志记录器
        deduped_popularity: 去重后的热度评论
        deduped_time: 去重后的时间评论
        popularity_threshold: 热度重复率阈值（重复率迭代模式）
        time_threshold: 时间重复率阈值（重复率迭代模式）
        popularity_duplicate_rates: 热度爬取每轮重复率列表（重复率迭代模式）
        time_duplicate_rates: 时间爬取每轮重复率列表（重复率迭代模式）
        bv_id: 视频BV号
        video_title: 视频标题
    """
    from datetime import datetime
    
    # 将统计报告保存到原始数据文件夹
    iteration_folder = os.path.join(output_folder, '原始数据')
    
    # 生成合并的迭代统计报告
    filename_suffix = f"{video_title}_{bv_id}"
    merged_stats_file = os.path.join(iteration_folder, f'迭代统计报告_{filename_suffix}.txt')
    
    with open(merged_stats_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("B站评论爬虫 - 迭代统计报告\n")
        f.write("=" * 60 + "\n\n")
        
        # 基本信息
        f.write("=== 基本信息 ===\n")
        f.write(f"视频BV号: {bv_id}\n")
        f.write(f"视频标题: {video_title}\n")
        f.write(f"统计时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        if iteration_hours:
            f.write(f"迭代模式: 时间迭代 ({iteration_hours} 小时)\n")
        else:
            f.write(f"迭代模式: 重复率迭代\n")
            if popularity_threshold:
                f.write(f"热度重复率阈值: {popularity_threshold}%\n")
            if time_threshold:
                f.write(f"时间重复率阈值: {time_threshold}%\n")
        
        f.write(f"迭代轮数: {iteration_count}\n\n")
        
        # 总体统计
        f.write("=== 总体统计 ===\n")
        all_raw_comments = popularity_comments + time_comments
        f.write(f"总原始爬取: {len(all_raw_comments)} 条评论\n")
        f.write(f"最终去重后: {len(merged_comments)} 条评论\n")
        total_duplicate_count = len(all_raw_comments) - len(merged_comments)
        total_duplicate_rate = (total_duplicate_count / len(all_raw_comments) * 100) if len(all_raw_comments) > 0 else 0
        f.write(f"总重复评论: {total_duplicate_count} 条\n")
        
        # 分类统计
        f.write("=== 分类统计 ===\n")
        
        # 热度爬取统计
        if deduped_popularity is not None:
            f.write("【热度爬取】\n")
            f.write(f"  原始爬取: {len(popularity_comments)} 条评论\n")
            f.write(f"  去重后: {len(deduped_popularity)} 条评论\n")
            pop_duplicate_count = len(popularity_comments) - len(deduped_popularity)
            pop_duplicate_rate = (pop_duplicate_count / len(popularity_comments) * 100) if len(popularity_comments) > 0 else 0
            f.write(f"  重复评论: {pop_duplicate_count} 条\n")

        # 时间爬取统计
        if deduped_time is not None:
            f.write("【时间爬取】\n")
            f.write(f"  原始爬取: {len(time_comments)} 条评论\n")
            f.write(f"  去重后: {len(deduped_time)} 条评论\n")
            time_duplicate_count = len(time_comments) - len(deduped_time)
            time_duplicate_rate = (time_duplicate_count / len(time_comments) * 100) if len(time_comments) > 0 else 0
            f.write(f"  重复评论: {time_duplicate_count} 条\n")
        
        # 重复率迭代详情（仅在重复率迭代模式下显示）
        if not iteration_hours and (popularity_duplicate_rates or time_duplicate_rates):
            f.write("=== 重复率迭代详情 ===\n")
            
            if popularity_duplicate_rates:
                f.write("【热度爬取每轮重复率】\n")
                for i, rate in enumerate(popularity_duplicate_rates, 1):
                    f.write(f"  第{i+1}轮与第{i}轮重复率: {rate:.1f}%\n")
                f.write("\n")
            
            if time_duplicate_rates:
                f.write("【时间爬取每轮重复率】\n")
                for i, rate in enumerate(time_duplicate_rates, 1):
                    f.write(f"  第{i+1}轮与第{i}轮重复率: {rate:.1f}%\n")
                f.write("\n")

    print(f"📊 迭代统计报告: {os.path.basename(merged_stats_file)}")
    logger.info(f"迭代统计报告已生成: {merged_stats_file}")

def generate_folder_structure_md(output_folder, oid, video_title=None, logger=None, bv_id=None):
    """
    生成输出文件夹结构的markdown文档
    
    Args:
        output_folder (str): 输出文件夹路径
        oid (str): 视频oid
        video_title (str, optional): 视频标题
        logger: 日志记录器
        bv_id (str, optional): 视频BV号
    
    Returns:
        str: 生成的markdown文件路径
    """
    import os
    from datetime import datetime
    
    def get_folder_tree(folder_path, prefix="", is_last=True, max_depth=5, current_depth=0):
        """
        递归生成文件夹树结构
        """
        if current_depth >= max_depth:
            return []
        
        items = []
        if not os.path.exists(folder_path):
            return items
        
        try:
            # 获取文件夹内容并排序
            entries = os.listdir(folder_path)
            entries.sort()
            
            # 分离文件夹和文件
            folders = []
            files = []
            
            for entry in entries:
                entry_path = os.path.join(folder_path, entry)
                if os.path.isdir(entry_path):
                    folders.append(entry)
                else:
                    files.append(entry)
            
            # 先处理文件夹
            all_entries = folders + files
            
            for i, entry in enumerate(all_entries):
                is_last_entry = (i == len(all_entries) - 1)
                entry_path = os.path.join(folder_path, entry)
                
                # 确定前缀符号
                if is_last_entry:
                    current_prefix = prefix + "└── "
                    next_prefix = prefix + "    "
                else:
                    current_prefix = prefix + "├── "
                    next_prefix = prefix + "│   "
                
                # 添加当前项
                if os.path.isdir(entry_path):
                    items.append(f"{current_prefix}{entry}/")
                    # 特殊处理logs文件夹，不递归扫描
                    if entry.lower() == "logs":
                        items.append(f"{next_prefix}└── （运行日志，省略）")
                    else:
                        # 递归处理子文件夹
                        sub_items = get_folder_tree(entry_path, next_prefix, is_last_entry, max_depth, current_depth + 1)
                        items.extend(sub_items)
                else:
                    # 文件大小信息
                    try:
                        file_size = os.path.getsize(entry_path)
                        if file_size > 1024 * 1024:  # MB
                            size_str = f" ({file_size / (1024 * 1024):.1f} MB)"
                        elif file_size > 1024:  # KB
                            size_str = f" ({file_size / 1024:.1f} KB)"
                        else:
                            size_str = f" ({file_size} B)"
                    except:
                        size_str = ""
                    
                    items.append(f"{current_prefix}{entry}{size_str}")
            
        except PermissionError:
            items.append(f"{prefix}└── [权限不足，无法访问]")
        except Exception as e:
            items.append(f"{prefix}└── [错误: {str(e)}]")
        
        return items
    
    # 生成markdown内容
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    folder_name = os.path.basename(output_folder)
    
    md_content = f"""# B站评论爬虫输出文件夹结构

## 基本信息

- **生成时间**: {timestamp}
- **视频OID**: {oid}
- **视频BV号**: {bv_id or '未获取'}
- **视频标题**: {video_title or '未获取'}
- **输出文件夹**: {folder_name}
- **完整路径**: {output_folder}

## 文件夹结构树

```
{folder_name}/
"""
    
    # 生成文件夹树
    tree_items = get_folder_tree(output_folder)
    for item in tree_items:
        md_content += item + "\n"
    
    md_content += "```\n\n## 文件说明\n\n### 主要文件类型\n\n"
    
    # 添加文件说明
    md_content += """- **CSV文件**: 评论数据文件
  - `*_按热度排序.csv`: 按热度排序的评论数据
  - `*_主楼评论.csv`: 仅包含主楼评论的数据
  - `*_合并去重结果.csv`: 合并去重后的完整数据
  - `*_重复评论列表.csv`: 检测到的重复评论

- **TXT文件**: 统计报告文件
  - `*_statistics.txt`: 基础统计报告
  - `按*统计_*.txt`: 各种时间粒度的统计文件

- **LOG文件**: 日志记录文件
  - `*_main.log`: 主程序运行日志
  - `*_page_*.log`: 分页爬取详细日志

### 文件夹说明

- **logs/**: 存放所有日志文件
- **原始数据/**: 存放原始爬取数据和中间处理结果
- **按时间统计/**: 存放各种时间粒度的统计文件

### 文件命名规则

文件名格式通常为: `[类型]_[视频标题]_[BV号]_[时间戳].[扩展名]`

- 类型: 如\"评论爬取\"、\"按日统计\"等
- 视频标题: 清理后的安全文件名
- BV号: 视频的BV号标识
- 时间戳: 生成时间(HHMMSS_YYYYMMDD格式)

## 使用说明

1. **查看评论数据**: 打开CSV文件，推荐使用Excel或其他表格软件
2. **查看统计报告**: 打开TXT文件，包含详细的数据分析
3. **检查运行日志**: 查看logs文件夹中的日志文件，了解爬取过程
4. **时间统计分析**: 查看\"按时间统计\"文件夹中的各种时间维度统计

---

*此文档由B站评论爬虫自动生成*
"""
    
    # 保存markdown文件
    md_filename = generate_safe_filename(video_title, oid, "文件夹结构", "other")
    md_file_path = os.path.join(output_folder, f"{md_filename}.md")
    
    try:
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        if logger:
            logger.info(f"文件夹结构文档已生成: {md_file_path}")
        
        return md_file_path
        
    except Exception as e:
        error_msg = f"生成文件夹结构文档失败: {e}"
        if logger:
            logger.error(error_msg)
        print(f"❌ {error_msg}")
        return None


# 主程序
if __name__ == "__main__":
    try:
        # 加载配置文件
        print("🔧 正在加载配置...")
        config = load_config()
        print("✅ 配置加载完成")
        
        # 检查命令行参数
        if len(sys.argv) > 1:
            # 测试模式：使用命令行参数
            if len(sys.argv) >= 6:
                default_oid = sys.argv[1]
                default_mode = int(sys.argv[2])
                default_ps = int(sys.argv[3])
                default_delay_ms = int(sys.argv[4])
                test_mode_flag = sys.argv[5].lower() == 'true'
                
                print(f"🧪 测试模式启动")
                print(f"参数: oid={default_oid}, mode={default_mode}, ps={default_ps}, delay={default_delay_ms}ms, test_mode={test_mode_flag}")
                
                # 获取视频信息
                print("\n🔍 正在获取视频信息...")
                video_info = None
                video_title = None
                try:
                    bv_id = aid_to_bvid(int(default_oid))
                    if bv_id:
                        video_info = get_video_info(bv_id)
                        if video_info and 'title' in video_info:
                            video_title = video_info['title']
                            print(f"📺 视频标题: {video_title}")
                        else:
                            # 回退到快速获取标题
                            video_title = get_video_title_quick(bv_id)
                            if video_title:
                                print(f"📺 视频标题: {video_title}")
                            else:
                                print("❌ 无法获取视频标题，程序终止")
                                print("程序退出")
                                sys.exit(1)
                    else:
                        print("❌ 无法获取BV号，程序终止")
                        print("程序退出")
                        sys.exit(1)
                except Exception as e:
                    print(f"❌ 获取视频信息失败: {e}")
                    print("程序退出")
                    sys.exit(1)
                
                # 开始爬取
                crawl_all_comments(default_oid, default_mode, default_ps, default_delay_ms, test_mode_flag, video_title, video_info)
            else:
                print("❌ 测试模式参数不足！")
                print("用法: python script.py <oid> <mode> <ps> <delay_ms> <test_mode>")
                sys.exit(1)
        else:
            # 正常模式：获取用户输入
            user_input = get_user_input()
            
            if user_input[0] is None:
                print("程序退出")
                sys.exit(1)
            
            # 解包用户输入
            oid, mode, ps, delay_ms, max_pages, test_sort_mode, iteration_config, video_title, video_info = user_input
            
            # 根据模式确定mode_type
            if mode == 'iteration':
                if iteration_config and iteration_config.get('type') == 'time':
                    mode_type = "iteration_time"
                elif iteration_config and iteration_config.get('type') == 'duplicate_rate':
                    mode_type = "iteration_rate"
                else:
                    mode_type = "iteration_time"  # 默认为时间限定
            elif mode == 'comprehensive':
                mode_type = "comprehensive"
            elif mode == 'test':
                # 测试模式根据排序方式确定mode_type
                if test_sort_mode == 0:  # 时间排序
                    mode_type = "test_time"
                else:  # 热度排序
                    mode_type = "test_popularity"
            else:
                mode_type = None
            
            # 创建输出文件夹和日志
            output_folder = create_output_folder(oid, video_title, mode_type)
            logger, main_log_file = setup_logging(oid, output_folder)
            
            # 根据模式选择不同的爬取方式
            if mode == 'iteration':
                # 迭代模式
                print(f"\n📁 输出文件夹: {output_folder}")
                print(f"📝 主日志文件: {main_log_file}")
                print(f"\n🔄 开始迭代模式爬取...")
                
                # 执行迭代模式爬取
                result = crawl_iteration_mode_comments(
                    oid=oid,
                    ps=ps,
                    delay_ms=delay_ms,
                    iteration_config=iteration_config,
                    logger=logger,
                    output_folder=output_folder,
                    video_title=video_title,
                    video_info=video_info
                )
                
                if result:
                    print("✅ 迭代模式爬取完成")
                    logger.info("迭代模式爬取完成")
                else:
                    print("❌ 迭代模式爬取失败")
                    logger.error("迭代模式爬取失败")
                    sys.exit(1)
                    
            elif mode == 'comprehensive':
        # 综合模式
                print(f"\n📁 输出文件夹: {output_folder}")
                print(f"📝 主日志文件: {main_log_file}")
                
                # 执行综合模式爬取
                result = crawl_comprehensive_mode_comments(
                    oid, ps, delay_ms, test_mode=False, logger=logger, output_folder=output_folder
                )
                
                if result:
                    popularity_comments, time_comments, merged_comments, duplicate_comments, popularity_end_reason = result
                    print(f"\n📊 热度爬取结束原因: {popularity_end_reason}")
                else:
                    print("❌ 综合模式爬取失败")
                    logger.error("综合模式爬取失败")
                    sys.exit(1)
                
                # 处理综合模式数据，生成4个原始数据文档
                raw_data_folder, doc_paths = process_comprehensive_mode_data(
                    oid, popularity_comments, time_comments, merged_comments, duplicate_comments, output_folder, logger, video_title
                )
                
                # 对合并结果进行双重整理
                print("\n=== 开始双重整理 ===")
                print("1. 按热度排序整理...")
                
                # 按热度排序整理（使用合并后的数据）
                _, popularity_organized_file, popularity_stats_file = process_and_organize_data(
                    merged_comments, output_folder, oid, logger, video_title, sort_by_popularity=True, video_info=video_info, mode="comprehensive"
                )
                
                print("2. 按时间统计整理...")
                
                # 按时间统计整理（使用合并后的数据）- 不生成整理文件
                _, _, time_stats_file = process_and_organize_data(
                    merged_comments, output_folder, oid, logger, video_title, sort_by_popularity=False, video_info=video_info, mode="comprehensive"
                )
                
                # 生成智能时间统计文件
                print("3. 生成时间统计分析...")
                bv_id = aid_to_bvid(int(oid))
                time_analysis_files = generate_restructured_time_statistics(
                    merged_comments, output_folder, bv_id, logger, video_title, video_info
                )
                
                if time_analysis_files:
                    print(f"   ✅ 已生成 {len(time_analysis_files)} 个时间统计文件")
                    for file_path in time_analysis_files:
                        print(f"      - {os.path.basename(file_path)}")
                else:
                    print("   ⚠️  未生成时间统计文件（可能因为数据不足）")
                
                # 输出最终结果
                print("\n=== 综合模式爬取完成 ===")
                print(f"📁 输出文件夹: {output_folder}")
                print(f"📁 原始数据文件夹: {raw_data_folder}")
                print("\n📄 原始数据文档:")
                for i, doc_path in enumerate(doc_paths, 1):
                    print(f"  {i}. {os.path.basename(doc_path)}")
                print("\n📄 整理后文档:")
                if popularity_organized_file:
                    print(f"  - 热度排序整理: {os.path.basename(popularity_organized_file)}")
                if popularity_stats_file:
                    print(f"  - 热度排序统计: {os.path.basename(popularity_stats_file)}")
                if time_stats_file:
                    print(f"  - 时间排序统计: {os.path.basename(time_stats_file)}")
                
                if time_analysis_files:
                    print("\n📊 时间统计分析文件:")
                    for file_path in time_analysis_files:
                        print(f"  - {os.path.basename(file_path)}")
                
                logger.info("综合模式爬取和整理完成")
                
                # 生成文件夹结构文档
                print("\n📋 生成文件夹结构文档...")
                # 生成BV号
                try:
                    bv_id = aid_to_bvid(int(oid))
                except:
                    bv_id = None
                structure_md_path = generate_folder_structure_md(output_folder, oid, video_title, logger, bv_id)
                if structure_md_path:
                    print(f"📄 文件夹结构文档: {os.path.basename(structure_md_path)}")
                
                # 输出爬取结果总结
                print("\n" + "="*50)
                print("🎯 爬取结果总结")
                print("="*50)
                
                # 热度爬取结果
                popularity_success = len(popularity_comments) > 0
                print(f"🔥 热度排序爬取: {'✅ 成功' if popularity_success else '❌ 失败'} ({len(popularity_comments)} 条评论)")
                print(f"   结束原因: {popularity_end_reason}")
                
                # 时间爬取结果
                time_crawl_performed = len(time_comments) > 0
                if time_crawl_performed:
                    time_success = len(time_comments) > 0
                    print(f"⏰ 时间排序爬取: {'✅ 成功' if time_success else '❌ 失败'} ({len(time_comments)} 条评论)")
                else:
                    print(f"⏰ 时间排序爬取: ⏭️ 跳过 (热度爬取已获取完整数据)")
                
                # 合并结果
                print(f"🔗 合并去重结果: ✅ 完成 ({len(merged_comments)} 条唯一评论, {len(duplicate_comments)} 条重复评论)")
                
                # 完整性评估
                if popularity_end_reason == "评论已全部爬取完毕":
                    print(f"📋 数据完整性: ✅ 完全爬取 (已获取该视频的所有评论)")
                elif time_crawl_performed and len(time_comments) > 0:
                    print(f"📋 数据完整性: ✅ 双重爬取完成 (热度+时间排序补充)")
                else:
                    print(f"📋 数据完整性: ⚠️ 部分爬取 (可能存在未获取的评论)")
                
                print("="*50)
            elif mode == 'test':
                # 测试模式 - 获取视频标题
                print("\n🔍 正在获取视频信息...")
                try:
                    # 从oid(aid)转换为BV号来获取视频标题
                    bv_id = aid_to_bvid(int(oid))
                    video_title = get_video_title_quick(bv_id) if bv_id else None
                    if not video_title:
                        print("❌ 无法获取视频标题，程序终止")
                        print("程序退出")
                        sys.exit(1)
                    else:
                        print(f"📺 视频标题: {video_title}")
                except Exception as e:
                    print(f"❌ 获取视频标题失败: {e}")
                    print("程序退出")
                    sys.exit(1)
                
                print(f"\n📁 输出文件夹: {output_folder}")
                print(f"📝 主日志文件: {main_log_file}")
                print(f"\n🧪 开始测试模式爬取...")
                
                # 执行测试模式爬取
                comments, end_reason = crawl_test_mode_comments(
                    oid=oid,
                    sort_mode=test_sort_mode,
                    ps=ps,
                    delay_ms=delay_ms,
                    max_pages=max_pages,
                    logger=logger,
                    output_folder=output_folder
                )
                
                # 处理和整理数据
                if comments:
                    print(f"\n📊 开始整理 {len(comments)} 条评论...")
                    
                    # 生成原始数据CSV文档（与整理后文件同级）
                    sort_name = "热度排序" if test_sort_mode == 1 else "时间排序"
                    raw_filename = generate_safe_filename(video_title, oid, f"测试模式_{sort_name}", "original")
                    raw_csv_file = os.path.join(output_folder, f"{raw_filename}.csv")
                    
                    # 调用综合模式使用的函数生成原始数据CSV
                    save_comments_to_csv(comments, raw_csv_file, f"测试模式_{sort_name}")
                    print(f"✅ 原始数据已保存: {os.path.basename(raw_csv_file)}")
                    
                    # 整理数据
                    sort_by_popularity = (test_sort_mode == 1)
                    mode_param = "test_popularity" if test_sort_mode == 1 else "test_time"
                    _, organized_file, stats_file = process_and_organize_data(
                        comments, output_folder, oid, logger, video_title, sort_by_popularity=sort_by_popularity, video_info=video_info, mode=mode_param
                    )
                    
                    print(f"✅ 整理完成")
                    if organized_file:
                        print(f"   - 整理文件: {os.path.basename(organized_file)}")
                    if stats_file:
                        print(f"   - 统计文件: {os.path.basename(stats_file)}")
                    
                    # 生成文件夹结构文档
                    try:
                        # 生成BV号
                        try:
                            bv_id = aid_to_bvid(int(oid))
                        except:
                            bv_id = None
                        structure_md_path = generate_folder_structure_md(output_folder, oid, video_title, logger, bv_id)
                        if structure_md_path:
                            print(f"   - 文件夹结构文档: {os.path.basename(structure_md_path)}")
                    except Exception as e:
                        logger.error(f"生成文件夹结构文档失败: {e}")
                
                # 输出爬取结果总结
                print("\n" + "="*50)
                print("🎯 测试模式爬取结果")
                print("="*50)
                
                sort_name = "热度排序" if test_sort_mode == 1 else "时间排序"
                success = len(comments) > 0
                print(f"🧪 测试模式 - {sort_name}: {'✅ 成功' if success else '❌ 失败'} ({len(comments)} 条评论)")
                print(f"📄 爬取页数: {max_pages} 页")
                print(f"⏱️  结束原因: {end_reason}")
                
                # 完整性评估
                if end_reason == "已达到指定页数限制":
                    print(f"📋 数据完整性: ✅ 按设定完成 (已爬取指定的 {max_pages} 页)")
                elif end_reason == "评论已全部爬取完毕":
                    print(f"📋 数据完整性: ✅ 完全爬取 (已获取该视频的所有评论)")
                else:
                    print(f"📋 数据完整性: ⚠️ 部分爬取 (可能存在未获取的评论)")
                
                print("="*50)
            else:
                print("❌ 不支持的模式选择")
                print("系统仅支持以下三种模式：")
                print("- 综合模式：智能组合热度和时间爬取")
                print("- 测试模式：单独测试基础爬取功能")
                print("- 迭代模式：交替执行热度和时间爬取")
                sys.exit(1)
        
    except CookieBannedException:
        # Cookie被封禁的特殊处理
        try:
            # 尝试获取输出文件夹路径和日志记录器
            if 'output_folder' in locals():
                output_folder_path = output_folder
            else:
                # 如果还没有创建输出文件夹，尝试构建路径
                if 'oid' in locals() and 'video_title' in locals() and 'mode_type' in locals():
                    output_folder_path = create_output_folder(oid, video_title, mode_type)
                else:
                    output_folder_path = None
            
            logger_instance = logger if 'logger' in locals() else None
            
            # 调用Cookie封禁处理函数
            handle_cookie_banned_error(output_folder_path, logger_instance)
        except Exception as cleanup_error:
            print(f"\n❌ 处理Cookie封禁错误时出现问题: {cleanup_error}")
            print("🚫 Cookie已被暂时封禁，请更换Cookie或等待一段时间后重试")
        
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断程序")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        sys.exit(1)


