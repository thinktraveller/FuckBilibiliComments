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
from .cookie import DEFAULT_HEADERS
from .errors import CookieBannedException
from .io_utils import create_page_logger

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

def get_bilibili_comments(oid, bv_id, mode=1, ps=20, next_offset='', is_first_page=True, page_num=1, logger=None, output_folder=None, request_headers=None):
    """
    统一的B站视频评论爬取核心模块
    所有爬取操作（时间/热度）使用同一核心模块，通过mode参数区分时间爬取和热度爬取
    
    Args:
        oid: 视频的oid（稿件avid），仅用于API请求
        bv_id: 视频的BV号，用于日志和文件命名
        mode (int): 排序模式，根据B站API文档：0=按时间排序，1=按点赞数排序（热度），2=按回复数排序
        next_offset (str): 分页偏移量，用于获取下一页评论
        is_first_page (bool): 是否为第一页
        page_num (int): 页码
        logger: 主日志记录器
        output_folder: 输出文件夹路径，用于创建页面日志
        request_headers (dict): 请求头，通过mode参数区分爬取类型
    
    Returns:
        dict: 评论数据
    """
    # 创建页面专用日志记录器
    page_logger = None
    page_log_file = None
    if output_folder:
        print(f"🔍 调试：正在为第 {page_num} 页创建页面日志记录器...")
        page_logger, page_log_file = create_page_logger(output_folder, bv_id, page_num)
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
    
    # 使用传入的请求头，如果没有则使用默认请求头
    if request_headers is None:
        request_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
    
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
    
    # 使用默认请求头（楼中楼回复不需要特殊的cookie配置）
    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    
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
        import time as time_module
        time_module.sleep(0.5)
    
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
