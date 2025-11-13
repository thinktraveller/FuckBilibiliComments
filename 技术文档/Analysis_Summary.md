# FuckBilibiliComments.py 综合分析文档

此文档整合了所有分析内容，包括整体结构、代码逐块解释、程序决策树、输出文件目录结构和函数间引用关系图。

## 1. 整体结构和主要功能

脚本是一个Bilibili视频评论爬取工具，支持多种模式（测试、综合、迭代），处理评论数据，包括去重、排序、统计和日志记录。主要功能：
- BV/AV转换
- 视频信息获取
- 配置加载
- 评论爬取（主楼+楼中楼）
- 数据处理（去重、排序、统计）
- 输出CSV和Markdown报告

## 2. 代码逐块解释

（从Code_Block_Explanations.md复制的关键部分，简要概述）
- 导入模块和常量定义：基础设置。
- 转换函数：bvid_to_aid, aid_to_bvid。
- 输入解析和视频信息获取。
- 配置和日志设置。
- 核心爬取：get_bilibili_comments, process_comments_page。
- 模式处理：crawl_*_mode_comments。
- 数据处理：process_and_organize_data, generate_*。
- 主程序：模式分支和异常处理。

## 3. 程序决策树

（从Program_Decision_Tree.md复制）
- 启动 -> 加载配置 -> 检查模式 -> 分支到迭代/综合/测试 -> 处理数据 -> 生成报告。

## 4. 输出文件目录结构

（从Output_File_Structure.md复制）
- 输出根文件夹 -> logs, 原始数据, 热度排序, 时间排序, 合并去重, 迭代数据, 智能时间统计, 文件夹结构.md。

## 5. 函数间引用关系图

（从Function_Call_Graph.md复制）
- __main__ -> crawl_* -> process_* -> generate_*。
- 核心调用链：crawl_all_comments -> get_bilibili_comments -> process_comments_page。

详细内容请参考各自独立文件。