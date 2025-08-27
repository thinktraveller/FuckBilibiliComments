#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时间整理模块独立脚本

该脚本基于主脚本中的时间统计模块，专门用于对评论数据进行精细时间统计。
接受主脚本生成的CSV文件和TXT文件，让用户选择特定时间段进行再次统计。

功能：
1. 读取包含评论发布时间的CSV文件
2. 从TXT文件中提取视频发布时间
3. 让用户选择时间段进行精细统计
4. 生成小时、分钟级别的统计报告和折线图

作者：基于FuckBilibiliComments.py提取
版本：1.0
"""

import os
import sys
import csv
import re
from datetime import datetime, timedelta
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

def read_csv_file(csv_path):
    """
    读取CSV文件并验证是否包含评论发布时间栏
    
    Args:
        csv_path (str): CSV文件路径
    
    Returns:
        tuple: (comments_data, has_time_column)
    """
    if not os.path.exists(csv_path):
        print(f"❌ CSV文件不存在: {csv_path}")
        return None, False
    
    try:
        comments_data = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            # 检查是否存在时间相关的列
            time_columns = ['发布时间', '评论发布时间', '时间', '发表时间']
            time_column = None
            
            for col in time_columns:
                if col in fieldnames:
                    time_column = col
                    break
            
            if not time_column:
                print("❌ CSV文件中未找到评论发布时间栏")
                print(f"可用列名: {list(fieldnames)}")
                return None, False
            
            print(f"✅ 找到时间列: {time_column}")
            
            # 读取所有数据
            for row in reader:
                if row.get(time_column) and row[time_column] != '未知时间':
                    # 转换时间格式为时间戳
                    try:
                        time_str = row[time_column]
                        time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        row['时间戳'] = int(time_obj.timestamp())
                        row['发布时间'] = time_str
                        comments_data.append(row)
                    except ValueError as e:
                        print(f"⚠️  时间格式转换失败: {time_str}, 错误: {e}")
                        continue
            
            print(f"✅ 成功读取 {len(comments_data)} 条有效评论数据")
            return comments_data, True
            
    except Exception as e:
        print(f"❌ 读取CSV文件时出错: {e}")
        return None, False

def extract_video_publish_time(txt_path):
    """
    从TXT文件中提取视频发布时间
    
    Args:
        txt_path (str): TXT文件路径
    
    Returns:
        tuple: (publish_timestamp, publish_datetime_str)
    """
    if not os.path.exists(txt_path):
        print(f"❌ TXT文件不存在: {txt_path}")
        return None, None
    
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找视频发布时间参数
        patterns = [
            r'视频发布时间[：:]\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            r'发布时间[：:]\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            r'pubdate[：:]\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                time_str = match.group(1)
                try:
                    time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    timestamp = int(time_obj.timestamp())
                    print(f"✅ 找到视频发布时间: {time_str}")
                    return timestamp, time_str
                except ValueError as e:
                    print(f"⚠️  时间格式解析失败: {time_str}, 错误: {e}")
                    continue
        
        print("❌ 在TXT文件中未找到视频发布时间参数")
        print("请确保TXT文件中包含以下格式之一的视频发布时间:")
        print("- 视频发布时间：YYYY-MM-DD HH:MM:SS")
        print("- 发布时间：YYYY-MM-DD HH:MM:SS")
        return None, None
        
    except Exception as e:
        print(f"❌ 读取TXT文件时出错: {e}")
        return None, None

def check_time_precision(comments_data, publish_timestamp):
    """
    检查评论时间与视频发布时间，判断是否需要精细统计
    
    Args:
        comments_data (list): 评论数据
        publish_timestamp (int): 视频发布时间戳
    
    Returns:
        tuple: (need_fine_analysis, latest_comment_time)
    """
    if not comments_data:
        return False, None
    
    # 获取最新评论时间
    latest_timestamp = max(comment['时间戳'] for comment in comments_data)
    latest_datetime = datetime.fromtimestamp(latest_timestamp)
    publish_datetime = datetime.fromtimestamp(publish_timestamp)
    
    print(f"\n📅 时间信息:")
    print(f"视频发布时间: {publish_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"最新评论时间: {latest_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查是否在同一日内
    if publish_datetime.date() == latest_datetime.date():
        print("\n⚠️  按时间整理的精度已经达到最大值")
        print("视频发布时间与最新评论时间在同一日内，无需进行精细统计")
        return False, latest_datetime.strftime('%Y-%m-%d %H:%M:%S')
    
    print("\n✅ 可以进行精细时间统计")
    return True, latest_datetime.strftime('%Y-%m-%d %H:%M:%S')

def get_user_time_range(publish_datetime, latest_comment_datetime):
    """
    获取用户指定的时间段
    
    Args:
        publish_datetime (datetime): 视频发布时间
        latest_comment_datetime (datetime): 最新评论时间
    
    Returns:
        tuple: (start_datetime, end_datetime, use_video_publish_time)
    """
    print("\n📋 请指定需要再次统计的时间段:")
    
    # 询问起始时间是否与视频发布时间一致
    while True:
        use_publish_time = input("再次统计的时间段的起始时间和视频发布时间是否一致？(y/n): ").strip().lower()
        if use_publish_time in ['y', 'yes', '是', 'Y']:
            start_datetime = publish_datetime
            print(f"✅ 起始时间设为视频发布时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            break
        elif use_publish_time in ['n', 'no', '否', 'N']:
            start_datetime = get_custom_datetime("起始", publish_datetime, latest_comment_datetime, is_start=True)
            break
        else:
            print("请输入 y 或 n")
    
    # 获取结束时间
    end_datetime = get_custom_datetime("结束", publish_datetime, latest_comment_datetime, is_start=False)
    
    return start_datetime, end_datetime, use_publish_time in ['y', 'yes', '是', 'Y']

def get_custom_datetime(time_type, publish_datetime, latest_comment_datetime, is_start=True):
    """
    获取用户自定义的日期时间
    
    Args:
        time_type (str): 时间类型（起始/结束）
        publish_datetime (datetime): 视频发布时间
        latest_comment_datetime (datetime): 最新评论时间
        is_start (bool): 是否为起始时间
    
    Returns:
        datetime: 用户指定的时间
    """
    while True:
        try:
            print(f"\n请输入{time_type}时间:")
            
            # 根据时间跨度决定需要输入的信息
            need_year = publish_datetime.year != latest_comment_datetime.year
            need_month = need_year or publish_datetime.month != latest_comment_datetime.month
            
            if need_year:
                year = int(input(f"{time_type}时间的年份: "))
            else:
                year = publish_datetime.year
                print(f"年份自动设为: {year}")
            
            if need_month:
                month = int(input(f"{time_type}时间的月份: "))
            else:
                month = publish_datetime.month
                print(f"月份自动设为: {month}")
            
            day = int(input(f"{time_type}时间的日期: "))
            
            # 验证日期合法性
            try:
                target_datetime = datetime(year, month, day)
            except ValueError as e:
                print(f"❌ 日期不合法: {e}")
                continue
            
            # 验证时间范围
            if is_start:
                if target_datetime.date() < publish_datetime.date():
                    print(f"❌ 起始时间不能早于视频发布时间 ({publish_datetime.strftime('%Y-%m-%d')})")
                    continue
            else:
                if target_datetime.date() > latest_comment_datetime.date():
                    print(f"❌ 结束时间不能晚于最新评论时间 ({latest_comment_datetime.strftime('%Y-%m-%d')})")
                    continue
            
            print(f"✅ {time_type}时间设为: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            return target_datetime
            
        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            print(f"❌ 输入错误: {e}")

def filter_comments_by_time_range(comments_data, start_datetime, end_datetime):
    """
    根据时间范围过滤评论数据
    
    Args:
        comments_data (list): 评论数据
        start_datetime (datetime): 起始时间
        end_datetime (datetime): 结束时间
    
    Returns:
        list: 过滤后的评论数据
    """
    start_timestamp = int(start_datetime.timestamp())
    end_timestamp = int((end_datetime + timedelta(days=1)).timestamp())  # 包含结束日期的整天
    
    filtered_comments = []
    for comment in comments_data:
        comment_timestamp = comment['时间戳']
        if start_timestamp <= comment_timestamp < end_timestamp:
            filtered_comments.append(comment)
    
    print(f"\n✅ 在指定时间段内找到 {len(filtered_comments)} 条评论")
    return filtered_comments

def generate_fine_time_statistics(comments_data, start_datetime, end_datetime, use_video_publish_time):
    """
    生成精细时间统计（小时、分钟级别）
    
    Args:
        comments_data (list): 评论数据
        start_datetime (datetime): 起始时间
        end_datetime (datetime): 结束时间
        use_video_publish_time (bool): 是否使用视频发布时间作为起始时间
    
    Returns:
        tuple: (hour_stats, minute_stats, time_points_hour, counts_hour, time_points_minute, counts_minute)
    """
    if not comments_data:
        return {}, {}, [], [], [], []
    
    start_timestamp = int(start_datetime.timestamp())
    end_timestamp = int((end_datetime + timedelta(days=1)).timestamp())
    
    # 按小时统计
    hour_stats = {}
    time_points_hour = []
    counts_hour = []
    
    # 计算需要统计的小时数
    total_hours = int((end_timestamp - start_timestamp) / 3600) + 1
    
    for i in range(total_hours):
        hour_start = start_timestamp + i * 3600
        hour_end = hour_start + 3600
        
        # 统计这个小时内的评论数量
        count = sum(1 for comment in comments_data 
                   if hour_start <= comment['时间戳'] < hour_end)
        
        # 生成显示用的时间段描述
        if use_video_publish_time:
            if i == 0:
                key = f"视频发布后0-1小时内新增的评论数量"
            else:
                key = f"视频发布后{i}-{i+1}小时内新增的评论数量"
        else:
            key = f"起始时间后{i}-{i+1}小时内新增的评论数量"
        
        hour_stats[key] = count
        time_points_hour.append(datetime.fromtimestamp(hour_start))
        counts_hour.append(count)
    
    # 按分钟统计
    minute_stats = {}
    time_points_minute = []
    counts_minute = []
    
    # 计算需要统计的分钟数
    total_minutes = int((end_timestamp - start_timestamp) / 60) + 1
    
    for i in range(total_minutes):
        minute_start = start_timestamp + i * 60
        minute_end = minute_start + 60
        
        # 统计这个分钟内的评论数量
        count = sum(1 for comment in comments_data 
                   if minute_start <= comment['时间戳'] < minute_end)
        
        # 生成显示用的时间段描述
        if use_video_publish_time:
            if i == 0:
                key = f"视频发布后0-1分钟内新增评论数量"
            else:
                key = f"视频发布后{i}-{i+1}分钟内新增评论数量"
        else:
            key = f"起始时间后{i}-{i+1}分钟内新增评论数量"
        
        minute_stats[key] = count
        time_points_minute.append(datetime.fromtimestamp(minute_start))
        counts_minute.append(count)
    
    return hour_stats, minute_stats, time_points_hour, counts_hour, time_points_minute, counts_minute

def save_fine_statistics_report(hour_stats, minute_stats, output_folder, start_datetime, end_datetime, use_video_publish_time, csv_filename):
    """
    保存精细统计报告
    
    Args:
        hour_stats (dict): 小时统计数据
        minute_stats (dict): 分钟统计数据
        output_folder (str): 输出文件夹
        start_datetime (datetime): 起始时间
        end_datetime (datetime): 结束时间
        use_video_publish_time (bool): 是否使用视频发布时间
        csv_filename (str): 原CSV文件名
    
    Returns:
        tuple: (hour_report_path, minute_report_path)
    """
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    base_name = os.path.splitext(os.path.basename(csv_filename))[0]
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存小时统计报告
    hour_filename = f"{base_name}_精细统计_按小时_{timestamp_str}.txt"
    hour_filepath = os.path.join(output_folder, hour_filename)
    
    with open(hour_filepath, 'w', encoding='utf-8') as f:
        f.write("=== 精细时间统计报告 - 按小时统计 ===\n\n")
        f.write(f"原始数据文件: {csv_filename}\n")
        f.write(f"统计时间段: {start_datetime.strftime('%Y-%m-%d')} 至 {end_datetime.strftime('%Y-%m-%d')}\n")
        
        if use_video_publish_time:
            f.write(f"再次统计的起始时间：和视频发布时间一致\n")
        else:
            f.write(f"再次统计的起始时间：{start_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        f.write(f"再次统计的结束时间：{end_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 统计汇总
        total_comments = sum(hour_stats.values())
        total_hours = len(hour_stats)
        avg_comments = total_comments / total_hours if total_hours > 0 else 0
        
        if hour_stats:
            max_count = max(hour_stats.values())
            min_count = min(hour_stats.values())
            max_period = [k for k, v in hour_stats.items() if v == max_count][0]
            min_period = [k for k, v in hour_stats.items() if v == min_count][0]
        else:
            max_count = min_count = 0
            max_period = min_period = "无数据"
        
        f.write("=== 统计汇总 ===\n")
        f.write(f"- 统计粒度: 小时\n")
        f.write(f"- 累计统计时间段数量: {total_hours}\n")
        f.write(f"- 总评论数: {total_comments}\n")
        f.write(f"- 平均每小时: {avg_comments:.2f} 条评论\n")
        f.write(f"- 最高峰: {max_count} 条评论，出现在 {max_period}\n")
        f.write(f"- 最低谷: {min_count} 条评论，出现在 {min_period}\n\n")
        
        # 详细统计数据
        f.write("=== 详细统计 ===\n")
        for key, count in hour_stats.items():
            f.write(f"{key}：{count}\n")
    
    # 保存分钟统计报告
    minute_filename = f"{base_name}_精细统计_按分钟_{timestamp_str}.txt"
    minute_filepath = os.path.join(output_folder, minute_filename)
    
    with open(minute_filepath, 'w', encoding='utf-8') as f:
        f.write("=== 精细时间统计报告 - 按分钟统计 ===\n\n")
        f.write(f"原始数据文件: {csv_filename}\n")
        f.write(f"统计时间段: {start_datetime.strftime('%Y-%m-%d')} 至 {end_datetime.strftime('%Y-%m-%d')}\n")
        
        if use_video_publish_time:
            f.write(f"再次统计的起始时间：和视频发布时间一致\n")
        else:
            f.write(f"再次统计的起始时间：{start_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        f.write(f"再次统计的结束时间：{end_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 统计汇总
        total_comments = sum(minute_stats.values())
        total_minutes = len(minute_stats)
        avg_comments = total_comments / total_minutes if total_minutes > 0 else 0
        
        if minute_stats:
            max_count = max(minute_stats.values())
            min_count = min(minute_stats.values())
            max_period = [k for k, v in minute_stats.items() if v == max_count][0]
            min_period = [k for k, v in minute_stats.items() if v == min_count][0]
        else:
            max_count = min_count = 0
            max_period = min_period = "无数据"
        
        f.write("=== 统计汇总 ===\n")
        f.write(f"- 统计粒度: 分钟\n")
        f.write(f"- 累计统计时间段数量: {total_minutes}\n")
        f.write(f"- 总评论数: {total_comments}\n")
        f.write(f"- 平均每分钟: {avg_comments:.2f} 条评论\n")
        f.write(f"- 最高峰: {max_count} 条评论，出现在 {max_period}\n")
        f.write(f"- 最低谷: {min_count} 条评论，出现在 {min_period}\n\n")
        
        # 详细统计数据
        f.write("=== 详细统计 ===\n")
        for key, count in minute_stats.items():
            f.write(f"{key}：{count}\n")
    
    print(f"\n✅ 统计报告已保存:")
    print(f"📄 小时统计: {hour_filepath}")
    print(f"📄 分钟统计: {minute_filepath}")
    
    return hour_filepath, minute_filepath

def generate_trend_charts(time_points_hour, counts_hour, time_points_minute, counts_minute, 
                         output_folder, start_datetime, end_datetime, use_video_publish_time, csv_filename, publish_datetime_str):
    """
    生成趋势折线图
    
    Args:
        time_points_hour (list): 小时时间点
        counts_hour (list): 小时评论数量
        time_points_minute (list): 分钟时间点
        counts_minute (list): 分钟评论数量
        output_folder (str): 输出文件夹
        start_datetime (datetime): 起始时间
        end_datetime (datetime): 结束时间
        use_video_publish_time (bool): 是否使用视频发布时间
        csv_filename (str): 原CSV文件名
    
    Returns:
        tuple: (hour_chart_path, minute_chart_path)
    """
    try:
        # 设置中文字体
        try:
            font_prop = FontProperties(fname='C:\\Windows\\Fonts\\simhei.ttf')
            plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            plt.rcParams['axes.unicode_minus'] = False
        
        base_name = os.path.splitext(os.path.basename(csv_filename))[0]
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 生成小时趋势图
        if time_points_hour and counts_hour:
            plt.figure(figsize=(12, 6))
            plt.plot(time_points_hour, counts_hour, marker='o', linewidth=2, markersize=4)
            
            # 设置标题
            if use_video_publish_time:
                title = f'评论数量变化趋势 - 按小时统计\n视频发布时间：{publish_datetime_str}\n再次统计的起始时间：和视频发布时间一致\n再次统计的结束时间：{end_datetime.strftime("%Y-%m-%d %H:%M:%S")}'
            else:
                title = f'评论数量变化趋势 - 按小时统计\n视频发布时间：{publish_datetime_str}\n再次统计的起始时间：{start_datetime.strftime("%Y-%m-%d %H:%M:%S")}\n再次统计的结束时间：{end_datetime.strftime("%Y-%m-%d %H:%M:%S")}'
            
            plt.title(title, fontsize=14, fontweight='bold')
            plt.xlabel('时间（小时）', fontsize=12)
            plt.ylabel('评论数量', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:00'))
            plt.tight_layout()
            
            hour_chart_filename = f"{base_name}_精细统计_按小时趋势图_{timestamp_str}.png"
            hour_chart_filepath = os.path.join(output_folder, hour_chart_filename)
            plt.savefig(hour_chart_filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"📈 小时趋势图已生成: {hour_chart_filepath}")
        else:
            hour_chart_filepath = None
        
        # 生成分钟趋势图
        if time_points_minute and counts_minute:
            plt.figure(figsize=(12, 6))
            plt.plot(time_points_minute, counts_minute, marker='o', linewidth=2, markersize=2)
            
            # 设置标题
            if use_video_publish_time:
                title = f'评论数量变化趋势 - 按分钟统计\n视频发布时间：{publish_datetime_str}\n再次统计的起始时间：和视频发布时间一致\n再次统计的结束时间：{end_datetime.strftime("%Y-%m-%d %H:%M:%S")}'
            else:
                title = f'评论数量变化趋势 - 按分钟统计\n视频发布时间：{publish_datetime_str}\n再次统计的起始时间：{start_datetime.strftime("%Y-%m-%d %H:%M:%S")}\n再次统计的结束时间：{end_datetime.strftime("%Y-%m-%d %H:%M:%S")}'
            
            plt.title(title, fontsize=14, fontweight='bold')
            plt.xlabel('时间（分钟）', fontsize=12)
            plt.ylabel('评论数量', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.tight_layout()
            
            minute_chart_filename = f"{base_name}_精细统计_按分钟趋势图_{timestamp_str}.png"
            minute_chart_filepath = os.path.join(output_folder, minute_chart_filename)
            plt.savefig(minute_chart_filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"📈 分钟趋势图已生成: {minute_chart_filepath}")
        else:
            minute_chart_filepath = None
        
        return hour_chart_filepath, minute_chart_filepath
        
    except ImportError:
        print("⚠️  matplotlib未安装，无法生成趋势图")
        return None, None
    except Exception as e:
        print(f"⚠️  生成趋势图时出错: {e}")
        return None, None

def main():
    """
    主函数
    """
    print("=== 时间整理模块独立脚本 ===")
    print("该脚本用于对评论数据进行精细时间统计")
    print("")
    
    # 1. 获取CSV文件路径
    while True:
        csv_path = input("请输入包含评论发布时间的CSV文件路径: ").strip().strip('"')
        if os.path.exists(csv_path):
            break
        else:
            print(f"❌ 文件不存在: {csv_path}")
    
    # 2. 读取CSV文件
    comments_data, has_time_column = read_csv_file(csv_path)
    if not comments_data or not has_time_column:
        print("❌ CSV文件读取失败或缺少时间列，程序终止")
        return
    
    # 3. 获取TXT文件路径
    while True:
        txt_path = input("请输入包含视频发布时间的TXT文件路径: ").strip().strip('"')
        if os.path.exists(txt_path):
            break
        else:
            print(f"❌ 文件不存在: {txt_path}")
    
    # 4. 提取视频发布时间
    publish_timestamp, publish_time_str = extract_video_publish_time(txt_path)
    if not publish_timestamp:
        print("❌ 缺少视频发布时间，程序终止")
        return
    
    publish_datetime = datetime.fromtimestamp(publish_timestamp)
    
    # 5. 检查时间精度
    need_fine_analysis, latest_comment_time = check_time_precision(comments_data, publish_timestamp)
    if not need_fine_analysis:
        print("程序终止")
        return
    
    latest_comment_datetime = datetime.strptime(latest_comment_time, '%Y-%m-%d %H:%M:%S')
    
    # 6. 获取用户指定的时间段
    start_datetime, end_datetime, use_video_publish_time = get_user_time_range(publish_datetime, latest_comment_datetime)
    
    # 7. 过滤评论数据
    filtered_comments = filter_comments_by_time_range(comments_data, start_datetime, end_datetime)
    if not filtered_comments:
        print("❌ 指定时间段内没有评论数据")
        return
    
    # 8. 生成精细时间统计
    print("\n📊 开始生成精细时间统计...")
    hour_stats, minute_stats, time_points_hour, counts_hour, time_points_minute, counts_minute = generate_fine_time_statistics(
        filtered_comments, start_datetime, end_datetime, use_video_publish_time
    )
    
    # 9. 创建输出文件夹
    output_folder = os.path.join(os.path.dirname(csv_path), "精细时间统计结果")
    
    # 10. 保存统计报告
    hour_report_path, minute_report_path = save_fine_statistics_report(
        hour_stats, minute_stats, output_folder, start_datetime, end_datetime, 
        use_video_publish_time, os.path.basename(csv_path)
    )
    
    # 11. 生成趋势图
    hour_chart_path, minute_chart_path = generate_trend_charts(
        time_points_hour, counts_hour, time_points_minute, counts_minute,
        output_folder, start_datetime, end_datetime, use_video_publish_time, os.path.basename(csv_path), publish_time_str
    )
    
    print("\n🎉 精细时间统计完成！")
    print(f"📁 输出文件夹: {output_folder}")
    print("\n生成的文件:")
    print(f"📄 {os.path.basename(hour_report_path)}")
    print(f"📄 {os.path.basename(minute_report_path)}")
    if hour_chart_path:
        print(f"📈 {os.path.basename(hour_chart_path)}")
    if minute_chart_path:
        print(f"📈 {os.path.basename(minute_chart_path)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n按回车键退出...")