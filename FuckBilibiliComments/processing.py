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
from .api import get_all_sub_replies
from .io_utils import generate_safe_filename
from .stats import generate_statistics
from .tree import CommentTreeBuilder
from .video import get_video_info_from_api

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
        '用户ID': reply.get('member', {}).get('mid', ''),
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
        # 保留所有原始字段，包括rpid和parent
        processed_comment = comment.copy()
        
        # 确保基本字段存在
        processed_comment.update({
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
            '评论类型': comment.get('评论类型', ''),
            'rpid': comment.get('rpid', ''),
            'parent': comment.get('parent', 0)
        })
        
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
        # 调试：检查前几条评论的rpid和parent字段
        for i, comment in enumerate(processed_comments[:3]):
            logger.debug(f"调试评论 {i+1}: rpid={comment.get('rpid', 'MISSING')}, parent={comment.get('parent', 'MISSING')}")
    
    return processed_comments

def process_and_organize_data(all_comments, output_folder, bv_id, logger=None, video_title=None, sort_by_popularity=True, video_info=None, mode=None, generate_stats=True):
    """
    整理和统计评论数据
    
    Args:
        all_comments (list): 所有评论数据
        output_folder (str): 输出文件夹路径
        bv_id (str): 视频BV号，用于文件命名
        logger: 日志记录器
        sort_by_popularity (bool): 是否按热度排序整理数据
        video_info (dict): 视频信息
        mode (str): 运行模式，用于区分是否生成时间排序最终文件
        generate_stats (bool): 是否生成统计文件，默认为True
    
    Returns:
        tuple: (None, 整理数据文件路径或None, 统计文件路径或None)
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
        
        # 保存完整整理数据（包含楼中楼）- 不包含rpid和parent字段
        filename = generate_safe_filename(video_title, bv_id, "最终数据_按热度排序", "final")
        processed_filename = os.path.join(output_folder, f'{filename}.csv')
        with open(processed_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if processed_comments:
                # 不包含rpid、parent和回复对象字段
                fieldnames = ['主楼序号', '楼中楼序号', '用户名称', '用户ID', '评论内容', '回复评论对象', '点赞数', '回复数', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                # 过滤掉rpid、parent和回复对象字段
                filtered_comments = []
                for comment in processed_comments:
                    filtered_comment = {k: v for k, v in comment.items() if k not in ['rpid', 'parent', '回复对象']}
                    filtered_comments.append(filtered_comment)
                writer.writerows(filtered_comments)
        
        # 生成孪生文件（包含rpid和parent字段）
        twin_filename = generate_safe_filename(video_title, bv_id, "最终数据_按热度排序_含rpid和parent", "final")
        twin_processed_filename = os.path.join(output_folder, f'{twin_filename}.csv')
        with open(twin_processed_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if processed_comments:
                # 包含rpid和parent字段，但不包含回复对象字段
                fieldnames_with_rpid = ['主楼序号', '楼中楼序号', '用户名称', '用户ID', '评论内容', '回复评论对象', '点赞数', '回复数', 'rpid', 'parent', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames_with_rpid)
                writer.writeheader()
                # 过滤掉回复对象字段
                filtered_comments = []
                for comment in processed_comments:
                    filtered_comment = {k: v for k, v in comment.items() if k != '回复对象'}
                    filtered_comments.append(filtered_comment)
                writer.writerows(filtered_comments)
        
        # 调用拖尾模块处理孪生文件
        if processed_comments and os.path.exists(twin_processed_filename):
            try:
                if logger:
                    logger.info("开始调用楼中楼拖尾模块...")
                
                # 创建CommentTreeBuilder实例
                tree_builder = CommentTreeBuilder()
                
                # 加载CSV数据
                df = tree_builder.load_csv(twin_processed_filename)
                
                # 构建评论树
                if df is not None:
                    tree_builder.build_tree(df)
                
                # 生成时间戳
                current_time = datetime.now()
                time_str = current_time.strftime('%H%M%S')
                date_str = current_time.strftime('%Y%m%d')
                
                # 生成整合的Markdown文件
                md_filepath = tree_builder.generate_integrated_markdown(output_folder, df, video_title, bv_id)
                
                # 创建图片输出文件夹
                image_output_folder = os.path.join(output_folder, "楼中楼拖尾图片")
                os.makedirs(image_output_folder, exist_ok=True)
                
                # 为符合条件的评论生成图片
                for rpid in tree_builder.root_comments:
                    if rpid in tree_builder.comments:
                        comment = tree_builder.comments[rpid]
                        row_data = comment['row_data']
                        
                        # 从CSV文件的回复数栏获取回复数量
                        reply_count_from_csv = 0
                        if '回复数' in df.columns and pd.notna(row_data['回复数']):
                            reply_count_from_csv = int(row_data['回复数'])
                        
                        # 只对CSV中回复数超过5的评论生成图片
                        if reply_count_from_csv > 5:
                            # 生成图片
                            image_filepath = tree_builder.generate_comment_image(rpid, image_output_folder, video_title, bv_id)
                            if image_filepath and logger:
                                logger.info(f"生成楼中楼拖尾图片: {os.path.basename(image_filepath)}")
                
                if logger:
                    logger.info(f"楼中楼拖尾模块处理完成")
                    logger.info(f"Markdown文件已保存: {md_filepath}")
                    logger.info(f"图片文件已保存到: {image_output_folder}")
                
            except Exception as e:
                if logger:
                    logger.error(f"楼中楼拖尾模块处理失败: {str(e)}")
                print(f"❌ 楼中楼拖尾模块处理失败: {str(e)}")
            
            finally:
                # 删除临时的孪生文件
                try:
                    if os.path.exists(twin_processed_filename):
                        os.remove(twin_processed_filename)
                        if logger:
                            logger.info(f"已删除临时孪生文件: {twin_processed_filename}")
                except Exception as e:
                    if logger:
                        logger.warning(f"删除临时孪生文件失败: {str(e)}")
        
        # 保存只包含主楼评论的文件（无楼中楼）
        main_floor_name = generate_safe_filename(video_title, bv_id, "最终数据_按热度排序且无楼中楼", "final")
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
            logger.info(f"孪生文件（含rpid和parent）已保存: {twin_processed_filename}")
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
            
            # 保存完整整理数据（包含楼中楼）- 不包含rpid和parent字段
            filename = generate_safe_filename(video_title, bv_id, "最终数据_按时间排序", "final")
            processed_filename = os.path.join(output_folder, f'{filename}.csv')
            with open(processed_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                if processed_comments:
                    # 不包含rpid、parent和回复对象字段
                    fieldnames = ['主楼序号', '楼中楼序号', '用户名称', '用户ID', '评论内容', '回复评论对象', '点赞数', '回复数', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    # 过滤掉rpid、parent和回复对象字段
                    filtered_comments = []
                    for comment in processed_comments:
                        filtered_comment = {k: v for k, v in comment.items() if k not in ['rpid', 'parent', '回复对象']}
                        filtered_comments.append(filtered_comment)
                    writer.writerows(filtered_comments)
            
            # 生成孪生文件（包含rpid和parent字段）
            twin_filename = generate_safe_filename(video_title, bv_id, "最终数据_按时间排序_含rpid和parent", "final")
            twin_processed_filename = os.path.join(output_folder, f'{twin_filename}.csv')
            with open(twin_processed_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                if processed_comments:
                    # 包含rpid和parent字段，但不包含回复对象字段
                    fieldnames_with_rpid = ['主楼序号', '楼中楼序号', '用户名称', '用户ID', '评论内容', '回复评论对象', '点赞数', '回复数', 'rpid', 'parent', '发布时间', '时间戳', '用户等级', 'IP地区', '性别', '评论类型', '爬取时间']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames_with_rpid)
                    writer.writeheader()
                    # 过滤掉回复对象字段
                    filtered_comments = []
                    for comment in processed_comments:
                        filtered_comment = {k: v for k, v in comment.items() if k != '回复对象'}
                        filtered_comments.append(filtered_comment)
                    writer.writerows(filtered_comments)
            
            # 调用拖尾模块处理孪生文件
            if processed_comments and os.path.exists(twin_processed_filename):
                try:
                    if logger:
                        logger.info("开始调用楼中楼拖尾模块...")
                    
                    # 创建CommentTreeBuilder实例
                    tree_builder = CommentTreeBuilder()
                    
                    # 加载CSV数据
                    df = tree_builder.load_csv(twin_processed_filename)
                    
                    # 构建评论树
                    if df is not None:
                        tree_builder.build_tree(df)
                    
                    # 生成时间戳
                    current_time = datetime.now()
                    time_str = current_time.strftime('%H%M%S')
                    date_str = current_time.strftime('%Y%m%d')
                    
                    # 生成整合的Markdown文件
                    md_filepath = tree_builder.generate_integrated_markdown(output_folder, df, video_title, bv_id)
                    
                    # 创建图片输出文件夹
                    image_output_folder = os.path.join(output_folder, "楼中楼拖尾图片")
                    os.makedirs(image_output_folder, exist_ok=True)
                    
                    # 为符合条件的评论生成图片
                    for rpid in tree_builder.root_comments:
                        if rpid in tree_builder.comments:
                            comment = tree_builder.comments[rpid]
                            row_data = comment['row_data']
                            
                            # 从CSV文件的回复数栏获取回复数量
                            reply_count_from_csv = 0
                            if '回复数' in df.columns and pd.notna(row_data['回复数']):
                                reply_count_from_csv = int(row_data['回复数'])
                            
                            # 只对CSV中回复数超过5的评论生成图片
                            if reply_count_from_csv > 5:
                                # 生成图片
                                image_filepath = tree_builder.generate_comment_image(rpid, image_output_folder, video_title, bv_id)
                                if image_filepath and logger:
                                    logger.info(f"生成楼中楼拖尾图片: {os.path.basename(image_filepath)}")
                    
                    if logger:
                        logger.info(f"楼中楼拖尾模块处理完成")
                        logger.info(f"Markdown文件已保存: {md_filepath}")
                        logger.info(f"图片文件已保存到: {image_output_folder}")
                    
                except Exception as e:
                    if logger:
                        logger.error(f"楼中楼拖尾模块处理失败: {str(e)}")
                    print(f"❌ 楼中楼拖尾模块处理失败: {str(e)}")
                
                finally:
                    # 删除临时的孪生文件
                    try:
                        if os.path.exists(twin_processed_filename):
                            os.remove(twin_processed_filename)
                            if logger:
                                logger.info(f"已删除临时孪生文件: {twin_processed_filename}")
                    except Exception as e:
                        if logger:
                            logger.warning(f"删除临时孪生文件失败: {str(e)}")
            
            # 保存只包含主楼评论的文件（无楼中楼）
            main_floor_name = generate_safe_filename(video_title, bv_id, "最终数据_按时间排序且无楼中楼", "final")
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
    
    # 生成统计文件（添加"统计结果"前缀）- 仅在需要时生成
    stats_filename = None
    if generate_stats:
        stats_name = generate_safe_filename(video_title, bv_id, "统计结果", "stats")
        stats_filename = os.path.join(output_folder, f'{stats_name}.txt')
        # 从BV号获取oid用于API调用
        oid = None
        if bv_id:
            try:
                video_info_temp = get_video_info_from_api(bv_id, 'bv')
                if video_info_temp and video_info_temp.get('aid'):
                    oid = str(video_info_temp['aid'])
            except:
                pass
        generate_statistics(all_comments, stats_filename, logger, oid, video_title, bv_id, video_info)
        if logger:
            logger.info(f"统计文件已生成: {stats_filename}")
    else:
        if logger:
            logger.info("跳过统计文件生成（避免重复）")
    
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
