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
from .video import get_video_info

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
            print("[WARNING] 按时间统计需要视频发布时间信息，跳过统计")
            
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
    valid_comments = []
    for comment in all_comments:
        try:
            timestamp = int(comment.get('时间戳', 0))
            if timestamp > 0:
                comment['时间戳'] = timestamp  # 确保时间戳是整数
                valid_comments.append(comment)
        except (ValueError, TypeError):
            continue
    
    if not valid_comments:
        return []
    
    # 过滤掉发布时间之前的评论
    new_comments = [comment for comment in valid_comments if comment['时间戳'] >= publish_timestamp]
    if not new_comments:
        print("[WARNING] 没有找到视频发布后的评论")
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
                       if start_time <= int(comment.get('时间戳', 0)) < end_time)
            
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
                       if start_time <= int(comment.get('时间戳', 0)) < end_time)
            
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
            timestamp = int(comment.get('时间戳', 0))
            if timestamp > 0:
                comment_dt = datetime.fromtimestamp(timestamp)
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
            timestamp = int(comment.get('时间戳', 0))
            if timestamp > 0:
                comment_dt = datetime.fromtimestamp(timestamp)
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
            timestamp = int(comment.get('时间戳', 0))
            if timestamp > 0:
                comment_dt = datetime.fromtimestamp(timestamp)
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
            print(f"[WARNING] 字体设置失败: {font_error}. 使用默认字体。")
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
        
        print(f"[INFO] 评论趋势图已生成: {chart_filepath}")
        return chart_filepath
        
    except ImportError:
        print("[WARNING] matplotlib未安装，无法生成趋势图")
        return None
    except Exception as e:
        print(f"[WARNING] 生成趋势图时出错: {e}")
        return None

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
    # 统计主楼评论数和楼中楼评论数
    main_floor_count = sum(1 for comment in all_comments if comment.get('评论类型') == '主楼评论')
    sub_floor_count = sum(1 for comment in all_comments if comment.get('评论类型') == '楼中楼回复')
    
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
            
        # 添加视频详细信息（通过API获取）
        if video_info:
            # 视频时长
            if video_info.get('duration'):
                duration_seconds = video_info['duration']
                duration_minutes = duration_seconds // 60
                duration_seconds_remainder = duration_seconds % 60
                f.write(f"视频时长: {duration_minutes}分{duration_seconds_remainder}秒\n")
            
            # 作者信息
            if video_info.get('owner'):
                owner = video_info['owner']
                author_name = owner.get('name', '未知')
                author_uid = owner.get('mid', '未知')
                f.write(f"作者: {author_name}\n")
                f.write(f"作者UID: {author_uid}\n")
            
            # 播放量
            if video_info.get('stat'):
                stat = video_info['stat']
                view_count = stat.get('view', 0)
                reply_count = stat.get('reply', 0)
                f.write(f"播放量: {view_count:,} 次\n")
                f.write(f"评论数: {reply_count:,} 条\n")
        
        f.write(f"本次爬取评论数: {total_comments} 条\n")
        
        # 计算爬取率和爬取失败评论数
        if video_info and video_info.get('stat') and video_info['stat'].get('reply') and isinstance(video_info['stat'].get('reply'), int) and video_info['stat'].get('reply') > 0:
            api_total_comments = video_info['stat']['reply']
            crawl_rate = (total_comments / api_total_comments) * 100
            failed_comments = api_total_comments - total_comments
            f.write(f"爬取率: {crawl_rate:.2f}%\n")
            f.write(f"爬取失败评论数: {failed_comments} 条\n")
        else:
            f.write(f"爬取率: 无法计算（缺少视频评论总数信息）\n")
            f.write(f"爬取失败评论数: 无法计算（缺少视频评论总数信息）\n")
        
        f.write(f"主楼评论数: {main_floor_count} 条\n")
        f.write(f"楼中楼评论数: {sub_floor_count} 条\n\n")
        
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
