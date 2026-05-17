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

def extract_id_from_url(url):
    """
    从B站URL中提取BV号或AV号，严格验证BV号格式
    
    Args:
        url (str): B站视频URL
        
    Returns:
        tuple: (id_type, id_value) 其中id_type为'bv'或'av'，id_value为对应的ID值，如果没有找到合法ID则返回(None, None)
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
    
    # 查找AV号
    av_pattern = r'av(\d+)'
    av_match = re.search(av_pattern, url.lower())
    if av_match:
        return 'av', av_match.group(1)
    
    return None, None

def get_video_info_from_api(video_id, id_type='bv', timeout=10):
    """
    通过B站官方API获取视频信息，包括oid(aid)、标题、发布时间等
    
    Args:
        video_id (str): 视频的BV号或AV号
        id_type (str): ID类型，'bv'或'av'
        timeout (int): 请求超时时间，默认10秒
        
    Returns:
        dict: 包含视频信息的字典，包括aid(oid)、标题、时长、作者等信息，获取失败返回None
    """
    # B站视频信息API接口
    url = "https://api.bilibili.com/x/web-interface/view"
    
    # 根据ID类型设置请求参数
    if id_type == 'bv':
        params = {"bvid": video_id}
    elif id_type == 'av':
        params = {"aid": video_id}
    else:
        print(f"不支持的ID类型: {id_type}")
        return None
    
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
                "aid": video_data.get("aid", ""),  # 这就是oid
                "title": video_data.get("title", ""),
                "desc": video_data.get("desc", ""),
                "duration": video_data.get("duration", 0),  # 视频时长（秒）
                "pubdate": video_data.get("pubdate", 0),  # 发布时间戳
                "owner": {
                    "mid": video_data.get("owner", {}).get("mid", ""),  # 作者UID
                    "name": video_data.get("owner", {}).get("name", ""),  # 作者名称
                    "face": video_data.get("owner", {}).get("face", "")
                },
                "stat": {
                    "view": video_data.get("stat", {}).get("view", 0),  # 播放量
                    "danmaku": video_data.get("stat", {}).get("danmaku", 0),
                    "reply": video_data.get("stat", {}).get("reply", 0),  # 评论数
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

def parse_video_input(user_input):
    """
    解析用户输入的B站URL，提取视频ID并获取视频信息
    
    Args:
        user_input (str): 用户输入的B站URL
        
    Returns:
        tuple: (oid, video_info) - oid和完整的视频信息，如果解析失败返回(None, None)
    """
    if not user_input or not isinstance(user_input, str):
        return None, None
    
    user_input = user_input.strip()
    
    # 从URL提取视频ID
    id_type, id_value = extract_id_from_url(user_input)
    
    if id_type and id_value:
        # 通过官方API获取视频信息
        video_info = get_video_info_from_api(id_value, id_type)
        if video_info and video_info.get('aid'):
            return str(video_info['aid']), video_info
    
    # 如果没有找到合法的视频ID或API调用失败，返回None
    return None, None

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

def validate_bv(bv_id):
    """
    验证BV号格式是否正确
    
    Args:
        bv_id (str): 输入的BV号
    
    Returns:
        bool: 格式是否正确
    """
    # BV号应该以BV开头，后跟10位字符
    return bv_id.startswith('BV') and len(bv_id) == 12
