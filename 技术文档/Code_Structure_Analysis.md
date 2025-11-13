# FuckBilibiliComments.py 代码结构分析

## 整体结构概述

该脚本是一个Bilibili视频评论爬虫工具，支持多种爬取模式，包括综合模式、测试模式和迭代模式。主要功能包括：
- 获取视频信息和标题
- 配置加载和请求头生成
- 评论数据爬取（热度排序、时间排序）
- 数据去重、整理和统计分析
- 生成各种报告和文件夹结构文档
- 支持日志记录和错误处理

程序采用模块化设计，分为工具函数、配置管理、爬取核心、数据处理和主程序逻辑。

## 主要模块和功能

### 1. ID转换和输入解析
- `bvid_to_aid(bvid)`: BV号转AID
- `aid_to_bvid(aid)`: AID转BV号
- `extract_id_from_url(url)`: 从URL提取ID
- `parse_video_input(user_input)`: 解析用户输入的视频标识

### 2. 视频信息获取
- `get_video_info(bvid)`: 获取视频详细信息
- `get_video_title_quick(bvid)`: 快速获取视频标题

### 3. 配置和头信息
- `load_config()`: 加载配置
- `save_config(config)`: 保存配置
- `get_request_headers(config)`: 生成请求头

### 4. 文件和日志管理
- `generate_safe_filename(...)`: 生成安全文件名
- `create_output_folder(oid, video_title)`: 创建输出文件夹
- `setup_logging(oid, output_folder)`: 设置日志
- `create_page_logger(...)`: 创建分页日志

### 5. 用户输入和验证
- `validate_oid(oid)`: 验证OID
- `get_user_input()`: 获取用户输入

### 6. API请求和签名
- `get_response(url, data, method)`: 发送请求
- `generate_w_rid(params)`: 生成w_rid签名

### 7. 评论爬取核心
- `get_bilibili_comments(...)`: 获取单页评论
- `process_comments_page(replies, ...)`: 处理评论页
- `get_all_sub_replies(...)`: 获取子回复
- `get_additional_sub_replies(...)`: 获取额外子回复
- `process_single_comment(reply, ...)`: 处理单个评论
- `process_reply_relationships(comments)`: 处理回复关系

### 8. 数据处理和统计
- `process_and_organize_data(...)`: 处理和整理数据
- `sort_comments_by_popularity(comments)`: 按热度排序
- `generate_time_statistics_by_date(...)`: 生成日期统计
- `generate_restructured_time_statistics(...)`: 生成重构时间统计
- `save_restructured_time_statistics(...)`: 保存统计
- `generate_time_trend_chart(...)`: 生成趋势图
- `generate_smart_time_statistics(...)`: 生成智能统计
- `generate_statistics(comments, filename)`: 生成统计报告
- `merge_and_deduplicate_comments(...)`: 合并去重
- `deduplicate_by_rpid(comments)`: 按RPID去重

### 9. 爬取模式
- `crawl_comprehensive_mode_comments(...)`: 综合模式
- `crawl_test_mode_comments(...)`: 测试模式
- `crawl_iteration_mode_comments(...)`: 迭代模式
- `crawl_time_iteration(...)`: 时间迭代
- `crawl_duplicate_rate_iteration(...)`: 重复率迭代
- `perform_iteration_deduplication(...)`: 迭代去重
- `generate_iteration_statistics(...)`: 生成迭代统计
- `write_stats_report(...)`: 写统计报告

### 10. 其他
- `generate_folder_structure_md(...)`: 生成文件夹结构MD
- `get_folder_tree(...)`: 生成文件夹树

## 程序流程
1. 加载配置
2. 获取用户输入或命令行参数
3. 创建输出文件夹和日志
4. 根据模式执行爬取
5. 处理数据、生成报告
6. 输出总结和文件夹结构文档

此分析基于函数定义搜索结果，覆盖脚本主要功能。