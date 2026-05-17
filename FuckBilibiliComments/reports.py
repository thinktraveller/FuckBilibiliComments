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
from .io_utils import generate_safe_filename

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
                        items.append(f"{next_prefix}└── （运行日志，省略具体内容）")
                    # 特殊处理楼中楼拖尾图片文件夹，不递归扫描
                    elif entry == "楼中楼拖尾图片":
                        items.append(f"{next_prefix}└── （拖尾图片合集，省略具体内容）")
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

- **楼中楼拖尾文件**: 子评论层级结构可视化文件
  - `楼中楼拖尾图片_*.png`: 评论树状结构图片，展示楼中楼回复的层级关系
  - `楼中楼拖尾整合_*.md`: 整合的Markdown文件，包含所有符合条件评论的文本结构
  - **生成条件**: 仅对CSV中回复数超过5条的主楼评论生成拖尾文件
  - **功能说明**: 通过rpid和parent字段构建评论树，以图片和文本形式展示楼中楼回复的完整层级结构
  - **实现逻辑**: 使用CommentTreeBuilder类解析CSV数据，构建评论层级关系，生成带颜色层级的可视化图片
  - **文件命名**: 图片文件格式为`楼中楼拖尾图片_{视频标题}_{BV号}_{时间戳}_{评论ID}.png`
  - **文件命名**: MD文件格式为`楼中楼拖尾整合_{视频标题}_{BV号}_{时间戳}.md`

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
    md_filename = generate_safe_filename(video_title, bv_id, "文件夹结构", "other")
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
