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
from .api import get_bilibili_comments
from .errors import CookieBannedException, handle_cookie_banned_error
from .io_utils import create_output_folder, generate_safe_filename, save_comments_to_csv, setup_logging
from .processing import calculate_duplicate_rate, merge_and_deduplicate_comments, perform_iteration_deduplication, process_and_organize_data, process_comments_page
from .reports import generate_folder_structure_md
from .stats import generate_restructured_time_statistics
from .video import get_video_info_from_api

def crawl_comprehensive_mode_comments(oid, bv_id, ps=20, delay_ms=1000, test_mode=False, logger=None, output_folder=None, request_headers=None):
    """
    综合模式评论爬取 - 执行固定流程：1次热度爬取 → 1次时间爬取
    使用统一爬取模块，通过mode参数区分时间爬取和热度爬取
    
    Args:
        oid (str): 视频oid，仅用于API请求
        bv_id (str): 视频BV号，用于日志和文件命名
        ps (int): 每页评论数量
        delay_ms (int): 请求延时（毫秒）
        test_mode (bool): 测试模式，只爬取一页
        logger: 日志记录器
        output_folder (str): 输出文件夹路径
        request_headers (dict): 请求头，通过mode参数区分爬取类型
    
    Returns:
        tuple: (热度爬取结果, 时间爬取结果, 合并去重结果, 重复评论列表, 热度爬取结束原因)
    """
    if logger:
        logger.info("开始综合模式爬取")
        logger.info("第一阶段：按热度排序爬取")
    
    print("\n=== 综合模式爬取（固定流程）===")
    print("📋 爬取策略：")
    print("   1️⃣ 执行1次热度排序爬取")
    print("   2️⃣ 执行1次时间排序爬取")
    print("   3️⃣ 合并数据并去除重复评论")
    print("   4️⃣ 按热度整理最终结果并生成统计")
    print()
    
    # 第一阶段：按热度排序爬取
    print("🔥 第一阶段：按热度排序爬取")
    try:
        popularity_comments, popularity_end_reason = crawl_all_comments_with_reason(
            oid=oid,
            bv_id=bv_id,
            mode=1,  # 热度排序（按点赞数排序）
            ps=ps, 
            delay_ms=delay_ms, 
            test_mode=test_mode,
            logger=logger,
            output_folder=output_folder,
            request_headers=request_headers
        )
    except CookieBannedException:
        # 重新抛出CookieBannedException，让上层处理
        raise
    
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
        try:
            time_comments, time_end_reason = crawl_all_comments_with_reason(
                oid=oid,
                bv_id=bv_id,
                mode=0,  # 时间排序（按时间排序）
                ps=ps, 
                delay_ms=delay_ms, 
                test_mode=test_mode,
                logger=logger,
                output_folder=output_folder,
                request_headers=request_headers
            )
        except CookieBannedException:
            # 重新抛出CookieBannedException，让上层处理
            raise
        
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
        print(f"   [INFO] 去重率：{len(duplicate_comments)/(len(popularity_comments)+len(time_comments))*100:.1f}%")
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

def crawl_test_mode_comments(oid, bv_id, sort_mode, ps=20, delay_ms=1000, max_pages=5, logger=None, output_folder=None):
    """
    测试模式爬取评论 - 仅测试模式使用预设页数作为停止条件
    迭代模式和综合模式不设预设停止条件
    
    Args:
        oid (str): 视频oid，仅用于API请求
        bv_id (str): 视频BV号，用于日志和文件命名
        sort_mode (int): 排序模式 (0=时间排序, 1=热度排序)
        ps (int): 每页评论数量
        delay_ms (int): 请求延时（毫秒）
        max_pages (int): 最大爬取页数（仅测试模式使用此停止条件）
        logger: 日志记录器
        output_folder (str): 输出文件夹路径
    
    Returns:
        tuple: (评论列表, 结束原因)
    """
    import time as time_module
    
    if logger:
        logger.info(f"开始测试模式爬取，oid={oid}, sort_mode={sort_mode}, max_pages={max_pages}")
    
    sort_name = "热度排序" if sort_mode == 1 else "时间排序"
    print(f"🧪 测试模式爬取设置（仅测试模式使用预设页数限制）：")
    print(f"   📊 排序方式：{sort_name}")
    print(f"   📄 最大页数：{max_pages}（预设停止条件）")
    print(f"   📝 每页数量：{ps}")
    print(f"   ⏱️  请求延时：{delay_ms}ms")
    
    comments = []
    current_page = 1
    next_offset = ''
    
    while current_page <= max_pages:
        print(f"\n📄 正在爬取第 {current_page}/{max_pages} 页...")
        
        # 获取评论数据（页面日志记录器将在get_bilibili_comments函数内部创建）
        comments_data = get_bilibili_comments(oid, bv_id, sort_mode, ps, next_offset, current_page == 1, current_page, logger, output_folder)
        
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
            print(f"[WARNING] 第 {current_page} 页无评论数据，停止爬取")
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
            time_module.sleep(delay_ms / 1000.0)
    
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

def process_comprehensive_mode_data(oid, bv_id, popularity_comments, time_comments, merged_comments, duplicate_comments, output_folder, logger=None, video_title=None):
    """
    处理综合模式数据，生成4个文档
    
    Args:
        oid (str): 视频oid，仅用于API请求
        bv_id (str): 视频BV号，用于文件命名
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
    doc1_filename = generate_safe_filename(video_title, bv_id, "热度排序爬取结果", "original")
    doc1_path = os.path.join(raw_data_folder, f'{doc1_filename}.csv')
    save_comments_to_csv(popularity_comments, doc1_path, '热度排序爬取结果')
    doc_paths.append(doc1_path)
    
    # 文档2：时间爬取结果
    doc2_filename = generate_safe_filename(video_title, bv_id, "时间排序爬取结果", "original")
    doc2_path = os.path.join(raw_data_folder, f'{doc2_filename}.csv')
    save_comments_to_csv(time_comments, doc2_path, '时间排序爬取结果')
    doc_paths.append(doc2_path)
    
    # 文档3：合并去重结果
    doc3_filename = generate_safe_filename(video_title, bv_id, "合并去重结果", "final")
    doc3_path = os.path.join(raw_data_folder, f'{doc3_filename}.csv')
    save_comments_to_csv(merged_comments, doc3_path, '合并去重结果')
    doc_paths.append(doc3_path)
    
    # 文档4：重复评论列表
    doc4_filename = generate_safe_filename(video_title, bv_id, "重复评论列表", "final")
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

def crawl_all_comments_with_reason(oid, bv_id, mode=1, ps=20, delay_ms=1000, test_mode=False, logger=None, output_folder=None, request_headers=None):
    """
    爬取所有评论并返回结束原因
    
    Args:
        oid: 视频的oid（稿件avid），仅用于API请求
        bv_id: 视频BV号，用于日志和文件命名
        mode (int): 排序模式，根据B站API文档：0=按时间排序，1=按点赞数排序（热度），2=按回复数排序
        ps (int): 每页评论数量
        delay_ms (int): 请求延时（毫秒）
        test_mode (bool): 是否为测试模式，测试模式只爬取一页
    
    Returns:
        tuple: (评论列表, 结束原因)
    """
    import time as time_module
    
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
        max_cookie_retries = 3  # 最大cookie切换重试次数
        cookie_retry_count = 0
        
        while cookie_retry_count <= max_cookie_retries:
            try:
                result = get_bilibili_comments(oid, bv_id, mode, ps, next_offset, is_first_page, page_count, logger, output_folder, request_headers)
                break  # 请求成功，跳出重试循环
            except CookieBannedException:
                cookie_retry_count += 1
                if cookie_retry_count <= max_cookie_retries:
                    print(f"\n[WARNING] 第{cookie_retry_count}次尝试切换cookie...")
                    if logger:
                        logger.warning(f"第{cookie_retry_count}次尝试切换cookie，当前页面：{page_count}")
                    
                    # 尝试切换cookie
                    new_config = handle_cookie_banned_error(output_folder, logger, auto_switch=True)
                    if new_config:
                        # 更新请求头中的cookie
                        if request_headers is None:
                            request_headers = {}
                        request_headers['Cookie'] = new_config['cookie']
                        request_headers['User-Agent'] = new_config['user_agent']
                        
                        print(f"✅ Cookie切换成功，继续第{page_count}页爬取...")
                        if logger:
                            logger.info(f"Cookie切换成功，继续第{page_count}页爬取")
                        
                        # 添加额外延时，避免频繁请求
                        time_module.sleep(2)
                        continue  # 重试当前页面
                    else:
                        # 没有更多可用的cookie，抛出异常
                        if logger:
                            logger.error(f"所有cookie都已被封禁，无法继续爬取")
                        raise CookieBannedException("所有可用的cookie都已被封禁")
                else:
                    # 超过最大重试次数，抛出异常
                    if logger:
                        logger.error(f"Cookie切换重试次数已达上限({max_cookie_retries}次)，停止爬取")
                    raise CookieBannedException(f"Cookie切换重试次数已达上限({max_cookie_retries}次)")
        
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
        
        print(f"[INFO] 累计处理 {total_comments} 条评论")
        
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
            time_module.sleep(delay_ms / 1000)
    
    print(f"\n🎉 评论爬取完成！")
    print(f"📊 总共爬取了 {page_count} 页，{total_comments} 条评论")
    print(f"🏁 结束原因：{end_reason}")
    
    return all_comments, end_reason

def crawl_all_comments(oid, bv_id, mode=3, ps=20, delay_ms=1000, test_mode=False, video_title=None, video_info=None, request_headers=None):
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
    output_folder = create_output_folder(bv_id, video_title, mode_type)
    print(f"📁 输出文件夹已创建: {output_folder}")
    
    # 设置日志
    logger, main_log_file = setup_logging(bv_id, output_folder)
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
        
        try:
            # 获取评论数据
            is_first_page = (page_count == 1)
            result = get_bilibili_comments(oid, bv_id, mode, ps, next_offset, is_first_page, page_count, logger, output_folder, request_headers)
            
            if not result:
                error_msg = "获取评论失败，停止爬取"
                print(f"❌ {error_msg}")
                logger.error(error_msg)
                break
        except CookieBannedException as e:
            # Cookie被封禁，抛出异常让上层处理
            raise e
        
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
        
        print(f"[INFO] 累计处理 {total_comments} 条评论")
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
                all_comments, output_folder, bv_id, logger, video_title, sort_by_popularity=True, video_info=video_info
            )
            
            # 如果是时间排序模式，生成按时间统计的文件
            time_stats_files = []
            if mode == 2:  # 时间排序模式
                print(f"\n⏰ 检测到时间排序模式，开始生成时间统计文件...")
                logger.info("开始生成按时间统计的文件")
                # 通过get_video_info_from_api获取BV号
                video_info_temp = get_video_info_from_api(str(oid), 'av')
                bv_id = video_info_temp.get('bvid') if video_info_temp else None
                time_stats_files = generate_restructured_time_statistics(all_comments, output_folder, bv_id, logger, video_title, video_info)
                
                if time_stats_files:
                    print(f"✅ 时间统计完成，生成了 {len(time_stats_files)} 个统计文件")
                    for file_path in time_stats_files:
                        print(f"📄 时间统计文件: {os.path.basename(file_path)}")
                    logger.info(f"时间统计文件生成完成，共 {len(time_stats_files)} 个文件")
                else:
                    print(f"[WARNING] 时间统计文件生成失败")
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
                video_info_temp = get_video_info_from_api(str(oid), 'av')
                bv_id = video_info_temp.get('bvid') if video_info_temp else None
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

def crawl_iteration_mode_comments(oid, bv_id, ps, delay_ms, iteration_config, logger, output_folder, video_title=None, video_info=None, request_headers=None):
    """
    迭代模式爬取评论
    
    Args:
        oid: 视频oid，仅用于API请求
        bv_id: 视频BV号，用于日志和文件命名
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
            
            return crawl_time_iteration(oid, ps, delay_ms, iteration_hours, logger, output_folder, video_title, video_info, request_headers)
            
        elif iteration_type == 'duplicate_rate':
            # 重复率迭代模式
            popularity_threshold = iteration_config['hot_rate_threshold']
            time_threshold = iteration_config['time_rate_threshold']
            print(f"📊 重复率迭代模式: 热度阈值={popularity_threshold}%, 时间阈值={time_threshold}%")
            logger.info(f"开始重复率迭代模式，热度阈值: {popularity_threshold}%, 时间阈值: {time_threshold}%")
            
            return crawl_duplicate_rate_iteration(oid, ps, delay_ms, popularity_threshold, time_threshold, logger, output_folder, video_title, video_info, request_headers)
            
        else:
            logger.error(f"未知的迭代类型: {iteration_type}")
            return False
            
    except Exception as e:
        logger.error(f"迭代模式爬取失败: {e}")
        return False

def crawl_time_iteration(oid, ps, delay_ms, iteration_hours, logger, output_folder, video_title=None, video_info=None, request_headers=None):
    """
    迭代模式（时间限定）- 执行循环流程：1次热度爬取 → 1次时间爬取（循环执行）
    使用统一爬取模块，通过mode参数区分时间爬取和热度爬取
    终止条件：以最后一次完成爬取的时间为终止条件
    
    Args:
        oid: 视频oid
        ps: 每页评论数
        delay_ms: 请求延时
        iteration_hours: 迭代时间（小时）
        logger: 日志记录器
        output_folder: 输出文件夹
        video_title: 视频标题
        video_info: 视频信息
        request_headers: 请求头，通过mode参数区分爬取类型
    
    Returns:
        bool: 是否成功
    """
    import time as time_module
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
        try:
            popularity_comments, popularity_reason = crawl_all_comments_with_reason(
                oid=oid, bv_id=bv_id, mode=1, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder, request_headers=request_headers
            )
        except CookieBannedException:
            # 重新抛出CookieBannedException，让上层处理
            raise
        
        if popularity_comments:
            # 保存热度爬取原始数据
            popularity_filename = generate_safe_filename(video_title, bv_id, f"第{iteration_count}次热度排序爬取结果", "original")
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
        try:
            time_comments, time_reason = crawl_all_comments_with_reason(
                oid=oid, bv_id=bv_id, mode=0, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder, request_headers=request_headers
            )
        except CookieBannedException:
            # 重新抛出CookieBannedException，让上层处理
            raise
        
        if time_comments:
            # 保存时间爬取原始数据
            time_filename = generate_safe_filename(video_title, bv_id, f"第{iteration_count}次时间排序爬取结果", "original")
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
        time_module.sleep(2)
    
    # 执行迭代去重
    print(f"\n🔄 开始迭代去重处理...")
    deduped_popularity, deduped_time, merged_comments, duplicate_comments = perform_iteration_deduplication(
        all_popularity_comments, all_time_comments, logger
    )
    
    # 保存三份去重结果到原始数据文件夹
    popularity_filename = generate_safe_filename(video_title, bv_id, "按热度迭代去重结果", "final")
    time_filename = generate_safe_filename(video_title, bv_id, "按时间迭代去重结果", "final")
    final_filename = generate_safe_filename(video_title, bv_id, "合并去重结果", "final")
    
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
    duplicate_filename = generate_safe_filename(video_title, bv_id, "重复评论列表", "final")
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
    
    # 按热度排序整理（使用合并后的数据）- 生成统计文件
    _, popularity_organized_file, popularity_stats_file = process_and_organize_data(
        merged_comments, output_folder, bv_id, logger, video_title, sort_by_popularity=True, video_info=video_info, mode="iteration", generate_stats=True
    )
    
    print("2. 按时间统计整理...")
    
    # 按时间统计整理（使用合并后的数据）- 不生成整理文件，也不生成统计文件（避免重复）
    _, _, time_stats_file = process_and_organize_data(
        merged_comments, output_folder, bv_id, logger, video_title, sort_by_popularity=False, video_info=video_info, mode="iteration", generate_stats=False
    )
    
    # 生成智能时间统计文件
    print("3. 生成时间统计分析...")
    video_info_temp = get_video_info_from_api(str(oid), 'av')
    bv_id = video_info_temp.get('bvid') if video_info_temp else None
    time_analysis_files = generate_restructured_time_statistics(
        merged_comments, output_folder, bv_id, logger, video_title, video_info
    )
    
    if time_analysis_files:
        print(f"   ✅ 已生成 {len(time_analysis_files)} 个时间统计文件")
        for file_path in time_analysis_files:
            print(f"      - {os.path.basename(file_path)}")
    else:
        print("   [WARNING] 未生成时间统计文件（可能因为数据不足）")
    
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
            video_info_temp = get_video_info_from_api(str(oid), 'av')
            bv_id = video_info_temp.get('bvid') if video_info_temp else None
        except:
            bv_id = None
        structure_md_path = generate_folder_structure_md(output_folder, oid, video_title, logger, bv_id)
        print(f"📄 文件夹结构文档: {os.path.basename(structure_md_path)}")
    except Exception as e:
        logger.error(f"生成文件夹结构文档失败: {e}")
    
    return True

def crawl_duplicate_rate_iteration(oid, ps, delay_ms, popularity_threshold, time_threshold, logger, output_folder, video_title=None, video_info=None, request_headers=None):
    """
    迭代模式（重复率限定）- 执行循环流程：1次热度爬取 → 1次时间爬取（循环执行）
    使用统一爬取模块，通过mode参数区分时间爬取和热度爬取
    终止条件：每次爬取后与上次结果比较重复率，实际重复率超过设定值时终止
    特殊规则：热度爬取停止后仍需完成时间爬取（反之亦然）
    
    Args:
        oid: 视频oid
        ps: 每页评论数
        delay_ms: 请求延时
        popularity_threshold: 热度爬取重复率阈值
        time_threshold: 时间爬取重复率阈值
        logger: 日志记录器
        output_folder: 输出文件夹
        video_title: 视频标题
        video_info: 视频信息
        request_headers: 请求头，通过mode参数区分爬取类型
    
    Returns:
        bool: 是否成功
    """
    import time as time_module
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
            try:
                popularity_comments, popularity_reason = crawl_all_comments_with_reason(
                    oid=oid, bv_id=bv_id, mode=1, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder, request_headers=request_headers
                )
            except CookieBannedException:
                # 重新抛出CookieBannedException，让上层处理
                raise
            
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
                popularity_filename = generate_safe_filename(video_title, bv_id, f"第{iteration_count}次热度排序爬取结果", "original")
                popularity_file = os.path.join(popularity_folder, f'{popularity_filename}.csv')
                save_comments_to_csv(popularity_comments, popularity_file, f"第{iteration_count}次热度排序爬取结果")
                all_popularity_comments.extend(popularity_comments)
                print(f"   ✅ 热度爬取完成: {len(popularity_comments)} 条评论")
                print(f"   💾 已保存: {os.path.basename(popularity_file)}")
                logger.info(f"热度爬取原始数据已保存: {popularity_file}")
            else:
                print(f"   [WARNING] 热度爬取未获取到评论，停止热度爬取")
                popularity_continue = False
        else:
            print(f"🔥 热度排序爬取已跳过（重复率已达阈值）")
        
        # 时间排序爬取（仅在未达到阈值时执行）
        if time_continue:
            print(f"⏰ 时间排序爬取...")
            try:
                time_comments, time_reason = crawl_all_comments_with_reason(
                    oid=oid, bv_id=bv_id, mode=0, ps=ps, delay_ms=delay_ms, test_mode=False, logger=logger, output_folder=output_folder, request_headers=request_headers
                )
            except CookieBannedException:
                # 重新抛出CookieBannedException，让上层处理
                raise
            
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
                time_filename = generate_safe_filename(video_title, bv_id, f"第{iteration_count}次时间排序爬取结果", "original")
                time_file = os.path.join(time_folder, f'{time_filename}.csv')
                save_comments_to_csv(time_comments, time_file, f"第{iteration_count}次时间排序爬取结果")
                all_time_comments.extend(time_comments)
                print(f"   ✅ 时间爬取完成: {len(time_comments)} 条评论")
                print(f"   💾 已保存: {os.path.basename(time_file)}")
                logger.info(f"时间爬取原始数据已保存: {time_file}")
            else:
                print(f"   [WARNING] 时间爬取未获取到评论，停止时间爬取")
                time_continue = False
        else:
            print(f"⏰ 时间排序爬取已跳过（重复率已达阈值）")
        
        # 检查是否应该停止迭代
        if not popularity_continue and not time_continue:
            print(f"\n🛑 两种爬取方式的重复率都达到阈值，停止迭代")
            logger.info("重复率迭代结束：两种爬取方式的重复率都达到阈值")
            break
        
        # 轮次间隔
        time_module.sleep(2)
    
    # 执行迭代去重
    print(f"\n🔄 开始迭代去重处理...")
    deduped_popularity, deduped_time, merged_comments, duplicate_comments = perform_iteration_deduplication(
        all_popularity_comments, all_time_comments, logger
    )
    
    # 保存三份去重结果到原始数据文件夹
    popularity_filename = generate_safe_filename(video_title, bv_id, "按热度迭代去重结果", "final")
    time_filename = generate_safe_filename(video_title, bv_id, "按时间迭代去重结果", "final")
    final_filename = generate_safe_filename(video_title, bv_id, "合并去重结果", "final")
    
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
    
    # 按热度排序整理（使用合并后的数据）- 生成统计文件
    _, popularity_organized_file, popularity_stats_file = process_and_organize_data(
        merged_comments, output_folder, bv_id, logger, video_title, sort_by_popularity=True, video_info=video_info, generate_stats=True
    )
    
    print("2. 按时间统计整理...")
    
    # 按时间统计整理（使用合并后的数据）- 不生成整理文件，也不生成统计文件（避免重复）
    _, _, time_stats_file = process_and_organize_data(
        merged_comments, output_folder, bv_id, logger, video_title, sort_by_popularity=False, video_info=video_info, generate_stats=False
    )
    
    # 生成智能时间统计文件
    print("3. 生成时间统计分析...")
    video_info_temp = get_video_info_from_api(str(oid), 'av')
    bv_id = video_info_temp.get('bvid') if video_info_temp else None
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
            video_info_temp = get_video_info_from_api(str(oid), 'av')
            bv_id = video_info_temp.get('bvid') if video_info_temp else None
        except:
            bv_id = None
        structure_md_path = generate_folder_structure_md(output_folder, oid, video_title, logger, bv_id)
        print(f"📄 文件夹结构文档: {os.path.basename(structure_md_path)}")
    except Exception as e:
        logger.error(f"生成文件夹结构文档失败: {e}")
    
    return True

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
