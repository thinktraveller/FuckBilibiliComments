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
from .cli import get_user_input
from .cookie import get_request_headers, load_config
from .crawl import crawl_all_comments, crawl_comprehensive_mode_comments, crawl_iteration_mode_comments, crawl_test_mode_comments, process_comprehensive_mode_data
from .errors import CookieBannedException, handle_cookie_banned_error
from .io_utils import create_output_folder, generate_safe_filename, prompt_delete_logs, save_comments_to_csv, setup_logging
from .processing import process_and_organize_data
from .reports import generate_folder_structure_md
from .stats import generate_restructured_time_statistics
from .video import get_video_info, get_video_info_from_api, get_video_title_quick


def main():
    try:
        # 加载配置文件和全局请求头
        print("🔧 正在加载配置...")
        config = load_config()
        global_request_headers = get_request_headers(config)
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
                    video_info_temp = get_video_info_from_api(str(default_oid), 'av')
                    bv_id = video_info_temp.get('bvid') if video_info_temp else None
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
                try:
                    crawl_all_comments(default_oid, bv_id, default_mode, default_ps, default_delay_ms, test_mode_flag, video_title, video_info, global_request_headers)
                    prompt_delete_logs()
                except CookieBannedException as e:
                    print(f"\n❌ Cookie切换失败: {e}")
                    print("所有可用的cookie都已被封禁，程序终止")
                    handle_cookie_banned_error(None, None, auto_switch=False)
                    sys.exit(1)
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
            
            # 获取BV号
            if oid:
                video_info_temp = get_video_info_from_api(str(oid), 'av')
                bv_id = video_info_temp.get('bvid') if video_info_temp else None
            else:
                bv_id = None
            if not bv_id:
                print("❌ 无法获取BV号，程序终止")
                sys.exit(1)
            
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
            output_folder = create_output_folder(bv_id, video_title, mode_type)
            logger, main_log_file = setup_logging(bv_id, output_folder)
            
            # 根据模式选择不同的爬取方式
            if mode == 'iteration':
                # 迭代模式
                print(f"\n📁 输出文件夹: {output_folder}")
                print(f"📝 主日志文件: {main_log_file}")
                print(f"\n🔄 开始迭代模式爬取...")
                
                # 执行迭代模式爬取
                try:
                     result = crawl_iteration_mode_comments(
                         oid=oid,
                         bv_id=bv_id,
                         ps=ps,
                         delay_ms=delay_ms,
                         iteration_config=iteration_config,
                         logger=logger,
                         output_folder=output_folder,
                         video_title=video_title,
                         video_info=video_info,
                         request_headers=global_request_headers
                     )
                except CookieBannedException as e:
                    print(f"\n❌ Cookie切换失败: {e}")
                    print("所有可用的cookie都已被封禁，程序终止")
                    logger.error(f"Cookie切换失败: {e}")
                    handle_cookie_banned_error(logger, output_folder, auto_switch=False)
                    sys.exit(1)
                
                if result:
                    print("✅ 迭代模式爬取完成")
                    logger.info("迭代模式爬取完成")
                    prompt_delete_logs(output_folder)
                else:
                    print("❌ 迭代模式爬取失败")
                    logger.error("迭代模式爬取失败")
                    sys.exit(1)
                    
            elif mode == 'comprehensive':
        # 综合模式
                print(f"\n📁 输出文件夹: {output_folder}")
                print(f"📝 主日志文件: {main_log_file}")
                
                # 执行综合模式爬取
                try:
                     result = crawl_comprehensive_mode_comments(
                         oid, bv_id, ps, delay_ms, test_mode=False, logger=logger, output_folder=output_folder, request_headers=global_request_headers
                     )
                except CookieBannedException as e:
                    print(f"\n❌ Cookie切换失败: {e}")
                    print("所有可用的cookie都已被封禁，程序终止")
                    logger.error(f"Cookie切换失败: {e}")
                    handle_cookie_banned_error(logger, output_folder, auto_switch=False)
                    sys.exit(1)
                
                if result:
                    popularity_comments, time_comments, merged_comments, duplicate_comments, popularity_end_reason = result
                    print(f"\n📊 热度爬取结束原因: {popularity_end_reason}")
                else:
                    print("❌ 综合模式爬取失败")
                    logger.error("综合模式爬取失败")
                    sys.exit(1)
                
                # 处理综合模式数据，生成4个原始数据文档
                raw_data_folder, doc_paths = process_comprehensive_mode_data(
                    oid, bv_id, popularity_comments, time_comments, merged_comments, duplicate_comments, output_folder, logger, video_title
                )
                
                # 对合并结果进行双重整理
                print("\n=== 开始双重整理 ===")
                print("1. 按热度排序整理...")
                
                # 按热度排序整理（使用合并后的数据）- 生成统计文件
                _, popularity_organized_file, popularity_stats_file = process_and_organize_data(
                    merged_comments, output_folder, bv_id, logger, video_title, sort_by_popularity=True, video_info=video_info, mode="comprehensive", generate_stats=True
                )
                
                print("2. 按时间统计整理...")
                
                # 按时间统计整理（使用合并后的数据）- 不生成整理文件，也不生成统计文件（避免重复）
                _, _, time_stats_file = process_and_organize_data(
                    merged_comments, output_folder, bv_id, logger, video_title, sort_by_popularity=False, video_info=video_info, mode="comprehensive", generate_stats=False
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
                    video_info_temp = get_video_info_from_api(str(oid), 'av')
                    bv_id = video_info_temp.get('bvid') if video_info_temp else None
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
                    print(f"[INFO] 数据完整性: [WARNING] 部分爬取 (可能存在未获取的评论)")
                
                print("="*50)
                prompt_delete_logs(output_folder)
            elif mode == 'test':
                # 测试模式 - 获取视频标题
                print("\n🔍 正在获取视频信息...")
                try:
                    # 从oid(aid)转换为BV号来获取视频标题
                    video_info_temp = get_video_info_from_api(str(oid), 'av')
                    bv_id = video_info_temp.get('bvid') if video_info_temp else None
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
                    bv_id=bv_id,
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
                    raw_filename = generate_safe_filename(video_title, bv_id, f"测试模式_{sort_name}", "original")
                    raw_csv_file = os.path.join(output_folder, f"{raw_filename}.csv")
                    
                    # 调用综合模式使用的函数生成原始数据CSV
                    save_comments_to_csv(comments, raw_csv_file, f"测试模式_{sort_name}")
                    print(f"✅ 原始数据已保存: {os.path.basename(raw_csv_file)}")
                    
                    # 整理数据
                    sort_by_popularity = (test_sort_mode == 1)
                    mode_param = "test_popularity" if test_sort_mode == 1 else "test_time"
                    _, organized_file, stats_file = process_and_organize_data(
                        comments, output_folder, bv_id, logger, video_title, sort_by_popularity=sort_by_popularity, video_info=video_info, mode=mode_param
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
                            video_info_temp = get_video_info_from_api(str(oid), 'av')
                            bv_id = video_info_temp.get('bvid') if video_info_temp else None
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
                prompt_delete_logs(output_folder)
                
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
                    print(f"[INFO] 数据完整性: [WARNING] 部分爬取 (可能存在未获取的评论)")
                
                print("="*50)
            else:
                print("❌ 不支持的模式选择")
                print("系统仅支持以下三种模式：")
                print("- 综合模式：智能组合热度和时间爬取")
                print("- 测试模式：单独测试基础爬取功能")
                print("- 迭代模式：交替执行热度和时间爬取")
                sys.exit(1)
        
    except CookieBannedException as e:
        # Cookie切换失败的特殊处理
        print(f"\n❌ Cookie切换失败: {e}")
        print("所有可用的cookie都已被封禁，程序终止")
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
            
            # 调用Cookie封禁处理函数（不进行自动切换）
            handle_cookie_banned_error(logger_instance, output_folder_path, auto_switch=False)
        except Exception as cleanup_error:
            print(f"\n❌ 处理Cookie封禁错误时出现问题: {cleanup_error}")
            print("🚫 所有Cookie都已被封禁，请更换Cookie或等待一段时间后重试")
        
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n[WARNING] 用户中断程序")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        sys.exit(1)



