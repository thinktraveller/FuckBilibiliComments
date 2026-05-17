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

class CommentTreeBuilder:
    """评论树构建器"""
    
    def __init__(self):
        self.comments = {}
        self.children = defaultdict(list)
        self.root_comments = []
        self.user_color_map = {}
        # 层级颜色配置
        self.level_colors = [
            '#2E86AB',  # 主楼 - 深蓝色
            '#A23B72',  # 一级回复 - 紫红色
            '#F18F01',  # 二级回复 - 橙色
            '#C73E1D',  # 三级回复 - 红色
            '#6A994E',  # 四级回复 - 绿色
            '#577590',  # 五级及以上 - 灰蓝色
        ]
        self.max_depth = 0
        self.indent_step = 30
        self.base_chars = 60
        self.reduce_per_level = 5
    
    def clean_text(self, text):
        """清理文本：删除换行符和多余空格"""
        if not text or pd.isna(text):
            return ""
        # 删除所有换行符和回车符
        cleaned = re.sub(r'[\r\n]+', ' ', str(text))
        # 删除多余的空格
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()
    
    def load_csv(self, csv_file):
        """加载CSV文件"""
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
            print(f"成功加载CSV文件: {csv_file}")
            print(f"总评论数: {len(df)}")
            return df
        except Exception as e:
            print(f"加载CSV文件失败: {e}")
            return None
    
    def build_tree(self, df):
        """构建评论树"""
        # 检查必要的列是否存在
        required_columns = ['rpid', 'parent', '用户名称', '评论内容']
        for col in required_columns:
            if col not in df.columns:
                print(f"CSV文件缺少必要的列: {col}")
                return False
        
        print(f"开始构建评论树，总评论数: {len(df)}")
        
        # 将评论数据存储到字典中
        for index, row in df.iterrows():
            rpid = str(row['rpid']) if pd.notna(row['rpid']) else None
            parent_rpid = str(row['parent']) if pd.notna(row['parent']) and row['parent'] != 0 else None
            uname = self.clean_text(row['用户名称']) if pd.notna(row['用户名称']) else "未知用户"
            message = self.clean_text(row['评论内容']) if pd.notna(row['评论内容']) else ""
            uid_key = str(row['用户ID']) if ('用户ID' in df.columns and pd.notna(row['用户ID'])) else uname
            
            if not rpid:
                print(f"警告：第 {index + 1} 行缺少rpid，跳过")
                continue
            
            # 存储评论信息
            self.comments[rpid] = {
                'rpid': rpid,
                'parent': parent_rpid,
                'uname': uname,
                'message': message,
                'uid': uid_key,
                'row_data': row
            }
            
            # 构建父子关系
            if parent_rpid and parent_rpid != '0':
                self.children[parent_rpid].append(rpid)
            else:
                self.root_comments.append(rpid)
        
        print(f"构建评论树完成: 主楼评论 {len(self.root_comments)} 条")
        self.max_depth = 0
        for r in self.root_comments:
            d = self._depth_of(r)
            if d > self.max_depth:
                self.max_depth = d
        return True
    
    def count_replies(self, rpid):
        """递归计算某个评论下的所有回复数量"""
        count = len(self.children[rpid])
        for child_rpid in self.children[rpid]:
            count += self.count_replies(child_rpid)
        return count
    
    def get_level_color(self, level):
        """获取层级对应的颜色"""
        if level < len(self.level_colors):
            return self.level_colors[level]
        else:
            return self.level_colors[-1]  # 使用最后一个颜色作为默认

    def get_user_color(self, uid):
        if not uid:
            return '#333333'
        if uid in self.user_color_map:
            return self.user_color_map[uid]
        h = hashlib.md5(str(uid).encode('utf-8')).hexdigest()
        hue = int(h[0:2], 16) / 255.0
        sat = 0.7 + 0.2 * (int(h[2:4], 16) / 255.0)
        val = 0.35 + 0.25 * (int(h[4:6], 16) / 255.0)
        def to_hex_from_hsv(hh, ss, vv):
            r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
            r = int(r * 255)
            g = int(g * 255)
            b = int(b * 255)
            return '#{0:02X}{1:02X}{2:02X}'.format(r, g, b), (r, g, b)
        hex_color, rgb = to_hex_from_hsv(hue, sat, val)
        def contrast_with_white(rgb):
            r, g, b = [x / 255.0 for x in rgb]
            def srgb_to_linear(c):
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            rl, gl, bl = srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)
            L = 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
            white_L = 1.0
            return (white_L + 0.05) / (L + 0.05)
        ratio = contrast_with_white(rgb)
        attempts = 0
        while ratio < 3.0 and attempts < 4:
            val = max(0.25, val - 0.05)
            hex_color, rgb = to_hex_from_hsv(hue, sat, val)
            ratio = contrast_with_white(rgb)
            attempts += 1
        self.user_color_map[uid] = hex_color
        return hex_color

    def _depth_of(self, rpid):
        if rpid not in self.children or len(self.children[rpid]) == 0:
            return 0
        m = 0
        for c in self.children[rpid]:
            d = self._depth_of(c)
            if d > m:
                m = d
        return 1 + m

    def compute_layout(self, font):
        char_width = 12 if font else 10
        deepest_required = 20
        max_d = max(self.max_depth, 0)
        if max_d <= 0:
            self.indent_step = 30
            self.reduce_per_level = 5
            self.base_chars = max(deepest_required, 60)
            return
        content_min_width = 600
        usable = content_min_width - 40
        step = max(18, min(40, int((usable - (deepest_required * char_width)) / max_d)))
        self.indent_step = step
        self.reduce_per_level = 5
        self.base_chars = deepest_required + self.reduce_per_level * max_d

    def _chars_for_level(self, level):
        return max(20, self.base_chars - self.reduce_per_level * level)

    def wrap_text(self, text, max_chars):
        if not text:
            return []
        tokens = re.split(r"(\s+)", text)
        lines = []
        cur = ""
        for t in tokens:
            if not t:
                continue
            if len(t) > max_chars:
                while len(t) > 0:
                    chunk = t[:max_chars]
                    t = t[max_chars:]
                    if len(cur) == 0:
                        lines.append(chunk)
                    else:
                        if len(cur) + len(chunk) <= max_chars:
                            cur += chunk
                            lines.append(cur)
                            cur = ""
                        else:
                            lines.append(cur)
                            cur = chunk
                continue
            if len(cur) + len(t) <= max_chars:
                cur += t
            else:
                if cur:
                    lines.append(cur)
                cur = t
        if cur:
            lines.append(cur)
        if not lines:
            s = text
            while s:
                lines.append(s[:max_chars])
                s = s[max_chars:]
        return lines
    
    def calculate_image_size(self, rpid, level=0, font=None):
        """计算生成图片所需的尺寸，更精确的计算方法"""
        if rpid not in self.comments:
            return 0, 0
        
        comment = self.comments[rpid]
        uname = comment['uname']
        message = comment['message']
        
        indent = level * self.indent_step
        
        # 计算用户名宽度和高度
        username_text = f"【{uname}】"
        username_height = 25 if font else 20
        
        # 计算评论内容的行数和宽度
        content_height = 0
        max_content_width = 0
        
        if message:
            max_chars_per_line = self._chars_for_level(level)
            
            lines = self.wrap_text(message, max_chars_per_line)
            
            # 计算内容高度
            line_height = 22 if font else 18
            content_height = len(lines) * line_height
            
            # 计算内容宽度（估算每个字符宽度）
            char_width = 12 if font else 10
            for line in lines:
                line_width = len(line) * char_width + indent + 10  # 加上缩进和边距
                max_content_width = max(max_content_width, line_width)
        
        # 计算用户名宽度
        char_width = 12 if font else 10
        username_width = len(username_text) * char_width + indent
        
        # 当前评论的总高度
        current_height = username_height + content_height + 10  # 10是评论间距
        
        # 当前评论的最大宽度
        current_width = max(username_width, max_content_width)
        
        # 递归计算子评论的尺寸
        children_height = 0
        max_child_width = 0
        
        for child_rpid in self.children[rpid]:
            child_width, child_height = self.calculate_image_size(child_rpid, level + 1, font)
            children_height += child_height
            max_child_width = max(max_child_width, child_width)
        
        # 总尺寸
        total_height = current_height + children_height
        total_width = max(current_width, max_child_width)
        
        # 如果是根节点，添加标题和分隔线的空间
        if level == 0:
            title_height = 50  # 标题和分隔线的高度
            total_height += title_height
            
            # 确保最小宽度
            total_width = max(total_width, 600)
            
            # 添加边距
            total_width += 40  # 左右边距
            total_height += 40  # 上下边距
        
        return total_width, total_height
    
    def draw_comment_tree(self, draw, rpid, x, y, level=0, font=None):
        """在图片上绘制评论树"""
        if rpid not in self.comments:
            return y
        
        comment = self.comments[rpid]
        uname = comment['uname']
        message = comment['message']
        uid = comment.get('uid', uname)
        color = self.get_user_color(uid)
        
        indent = level * self.indent_step
        if level > 0:
            # 绘制连接线
            draw.line([(x + indent - 15, y + 10), (x + indent, y + 10)], fill=color, width=2)
        
        # 绘制用户名（加粗效果）
        username_text = f"【{uname}】"
        try:
            if font:
                draw.text((x + indent, y), username_text, fill=color, font=font)
                y += 25
            else:
                draw.text((x + indent, y), username_text, fill=color)
                y += 20
        except:
            draw.text((x + indent, y), username_text, fill=color)
            y += 20
        
        # 绘制评论内容（自动换行）
        if message:
            max_chars_per_line = self._chars_for_level(level)
            lines = self.wrap_text(message, max_chars_per_line)
            
            # 绘制每一行
            for line in lines:
                try:
                    if font:
                        draw.text((x + indent + 10, y), line, fill='#333333', font=font)
                        y += 22
                    else:
                        draw.text((x + indent + 10, y), line, fill='#333333')
                        y += 18
                except:
                    draw.text((x + indent + 10, y), line, fill='#333333')
                    y += 18
        
        y += 10  # 评论间距
        
        # 递归绘制子评论
        for child_rpid in self.children[rpid]:
            y = self.draw_comment_tree(draw, child_rpid, x, y, level + 1, font)
        
        return y
    
    def check_image_edges(self, img, edge_width=5):
        """检测图片边缘是否存在非白色像素点"""
        width, height = img.size
        pixels = img.load()
        
        # 检查上边缘
        for y in range(min(edge_width, height)):
            for x in range(width):
                if pixels[x, y] != (255, 255, 255):  # 非白色像素
                    return True, 'top'
        
        # 检查下边缘
        for y in range(max(0, height - edge_width), height):
            for x in range(width):
                if pixels[x, y] != (255, 255, 255):
                    return True, 'bottom'
        
        # 检查左边缘
        for x in range(min(edge_width, width)):
            for y in range(height):
                if pixels[x, y] != (255, 255, 255):
                    return True, 'left'
        
        # 检查右边缘
        for x in range(max(0, width - edge_width), width):
            for y in range(height):
                if pixels[x, y] != (255, 255, 255):
                    return True, 'right'
        
        return False, None
    
    def generate_comment_image(self, rpid, output_dir, video_title, bv_id, max_retries=3):
        """为单个评论树生成图片，带边缘检测和自动调整"""
        if rpid not in self.comments:
            return None
        
        root_comment = self.comments[rpid]
        root_uname = root_comment['uname']
        
        # 尝试加载字体
        font = None
        try:
            # 尝试使用系统字体
            font = ImageFont.truetype("msyh.ttc", 14)  # 微软雅黑
        except:
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                font = ImageFont.load_default()
        
        self.compute_layout(font)
        width, height = self.calculate_image_size(rpid, 0, font)
        height = max(height, 200)  # 最小高度
        
        # 多次尝试生成合适尺寸的图片
        for attempt in range(max_retries):
            # 创建图片
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # 绘制标题
            title = f"楼中楼评论结构 - {root_uname}"
            try:
                if font:
                    draw.text((10, 10), title, fill='#000000', font=font)
                else:
                    draw.text((10, 10), title, fill='#000000')
            except:
                draw.text((10, 10), title, fill='#000000')
            
            # 绘制分隔线
            draw.line([(10, 35), (width - 10, 35)], fill='#CCCCCC', width=1)
            
            # 绘制评论树
            final_y = self.draw_comment_tree(draw, rpid, 10, 50, 0, font)
            
            # 检测边缘是否有内容溢出
            has_edge_content, edge_position = self.check_image_edges(img)
            
            if not has_edge_content:
                # 没有边缘溢出，图片生成成功
                break
            else:
                # 有边缘溢出，需要调整尺寸
                print(f"检测到内容溢出到 {edge_position} 边缘，正在调整图片尺寸... (尝试 {attempt + 1}/{max_retries})")
                
                if edge_position in ['top', 'bottom'] or edge_position == 'bottom':
                    # 垂直方向溢出，增加高度
                    height = int(height * 1.3)  # 增加30%高度
                elif edge_position in ['left', 'right']:
                    # 水平方向溢出，增加宽度
                    width = int(width * 1.2)  # 增加20%宽度
                
                # 如果是最后一次尝试，强制增加更多空间
                if attempt == max_retries - 1:
                    width = int(width * 1.5)
                    height = int(height * 1.5)
                    print(f"最后一次尝试，大幅增加图片尺寸至 {width}x{height}")
        
        else:
            # 所有尝试都失败了，使用最后一次的结果
            print(f"警告: 经过 {max_retries} 次尝试仍有内容溢出，使用当前尺寸保存")
        
        # 生成文件名（按要求的命名格式）
        safe_username = re.sub(r'[<>:"/\\|?*]', '_', root_uname)
        safe_video_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
        timestamp = datetime.now().strftime("%H%M%S_%Y%m%d")
        filename = f"楼中楼拖尾图片_{safe_username}_{safe_video_title}_{bv_id}_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        
        # 保存图片
        try:
            img.save(filepath, 'PNG')
            print(f"生成图片: {filename} (尺寸: {width}x{height})")
            return filepath
        except Exception as e:
            print(f"保存图片失败 {filename}: {e}")
            return None
    
    def generate_tree_text(self, rpid, level=0, prefix="", is_last=True):
        """递归生成树状文本"""
        if rpid not in self.comments:
            return ""
        
        comment = self.comments[rpid]
        uname = comment['uname']
        message = comment['message']
        
        # 限制消息长度，避免过长
        if len(message) > 100:
            message = message[:100] + "..."
        
        result = ""
        
        # 生成当前节点的文本
        if level == 0:
            # 根节点（主楼评论）
            result = f"{uname}：{message}\n"
        else:
            # 子节点（楼中楼回复）
            tree_symbol = "└── " if is_last else "├── "
            result = f"{prefix}{tree_symbol}{uname}：{message}\n"
        
        # 递归处理子评论
        children = self.children[rpid]
        for i, child_rpid in enumerate(children):
            is_last_child = (i == len(children) - 1)
            
            if level == 0:
                # 从根节点开始的子节点
                child_prefix = ""
                next_prefix = "│   " if not is_last_child else "    "
            else:
                # 更深层的子节点
                child_prefix = prefix
                next_prefix = prefix + ("    " if is_last else "│   ")
            
            result += self.generate_tree_text(child_rpid, level + 1, next_prefix, is_last_child)
        
        return result
    
    def generate_integrated_markdown(self, output_dir, df, video_title, bv_id):
        """生成整合的Markdown拖尾文件"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print(f"开始检查 {len(self.root_comments)} 个主楼评论...")
        
        # 收集所有符合条件的评论
        qualified_comments = []
        
        for root_rpid in self.root_comments:
            comment = self.comments[root_rpid]
            row_data = comment['row_data']
            
            # 从CSV文件的回复数栏获取回复数量
            reply_count_from_csv = 0
            if '回复数' in df.columns and pd.notna(row_data['回复数']):
                reply_count_from_csv = int(row_data['回复数'])
            
            print(f"主楼 {root_rpid}: CSV中记录的回复数 {reply_count_from_csv}")
            
            # 只对CSV中回复数超过5的评论生成拖尾文件
            if reply_count_from_csv > 5:
                qualified_comments.append({
                    'rpid': root_rpid,
                    'uname': comment['uname'],
                    'reply_count': reply_count_from_csv,
                    'tree_text': self.generate_tree_text(root_rpid)
                })
        
        if not qualified_comments:
            print("没有找到符合条件的评论（CSV中回复数超过5条）")
            return None
        
        # 生成整合的Markdown文件（按要求的命名格式）
        safe_video_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
        timestamp = datetime.now().strftime("%H%M%S_%Y%m%d")
        filename = f"楼中楼拖尾整合_{safe_video_title}_{bv_id}_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)
        
        # 构建整合的Markdown内容
        markdown_content = f"""# 楼中楼评论拖尾整合文件

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**符合条件的评论数量**: {len(qualified_comments)} 条  
**筛选条件**: CSV中回复数超过5条的评论  

---

"""
        
        # 添加每个评论的详细内容
        for i, comment in enumerate(qualified_comments, 1):
            markdown_content += f"""## {i}. {comment['uname']}

**楼中楼回复数量**: {comment['reply_count']} 条

### 评论层级结构

```
{comment['tree_text']}
```

---

"""
        
        markdown_content += "*此文件由楼中楼拖尾文件生成器自动生成*\n"
        
        # 写入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"生成整合拖尾文件: {filename}")
            print(f"包含 {len(qualified_comments)} 个符合条件的评论")
            return filepath
        except Exception as e:
            print(f"写入文件失败 {filename}: {e}")
            return None
