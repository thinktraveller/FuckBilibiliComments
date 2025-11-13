#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
楼中楼拖尾文件生成器

基于CSV文件中的rpid和parent字段，构建楼中楼评论的层级关系树，
并生成Markdown格式的拖尾文件和可视化图片。

功能特性：
1. 自动删除评论文本中的换行符，确保文本连续
2. 生成层级结构可视化图片
3. 使用不同颜色区分不同层级
4. 只对CSV文件中回复数超过5条的主楼评论进行处理
"""

import os
from datetime import datetime
from collections import defaultdict
import re
import sys
import subprocess
import importlib

def check_and_install_dependencies():
    """
    检测并自动安装必要的依赖包
    """
    required_packages = {
        'pandas': 'pandas>=1.3.0',
        'PIL': 'Pillow>=8.0.0',
    }
    
    missing_packages = []
    
    print("🔍 检测依赖包...")
    
    for package_name, package_spec in required_packages.items():
        try:
            importlib.import_module(package_name)
            print(f"✅ {package_name} 已安装")
        except ImportError:
            print(f"❌ {package_name} 未安装")
            missing_packages.append(package_spec)
    
    if missing_packages:
        print(f"\n📦 发现 {len(missing_packages)} 个缺失的依赖包，开始自动安装...")
        
        for package in missing_packages:
            try:
                print(f"正在安装 {package}...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"✅ {package} 安装成功")
            except subprocess.CalledProcessError as e:
                print(f"❌ {package} 安装失败: {e}")
                print("请手动安装依赖包：")
                print(f"pip install {package}")
                sys.exit(1)
        
        print("\n🎉 所有依赖包安装完成！")
    else:
        print("\n✅ 所有依赖包已满足要求")

# 检查Python版本
if sys.version_info < (3, 7):
    print("❌ 错误：此脚本需要Python 3.7或更高版本")
    print(f"当前Python版本：{sys.version}")
    print("请升级Python版本后重试")
    sys.exit(1)

# 自动检测和安装依赖
check_and_install_dependencies()

# 导入第三方库
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


class CommentTreeBuilder:
    """评论树构建器"""
    
    def __init__(self):
        self.comments = {}
        self.children = defaultdict(list)
        self.root_comments = []
        # 层级颜色配置
        self.level_colors = [
            '#2E86AB',  # 主楼 - 深蓝色
            '#A23B72',  # 一级回复 - 紫红色
            '#F18F01',  # 二级回复 - 橙色
            '#C73E1D',  # 三级回复 - 红色
            '#6A994E',  # 四级回复 - 绿色
            '#577590',  # 五级及以上 - 灰蓝色
        ]
    
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
            
            if not rpid:
                print(f"警告：第 {index + 1} 行缺少rpid，跳过")
                continue
            
            # 存储评论信息
            self.comments[rpid] = {
                'rpid': rpid,
                'parent': parent_rpid,
                'uname': uname,
                'message': message,
                'row_data': row
            }
            
            # 构建父子关系
            if parent_rpid and parent_rpid != '0':
                self.children[parent_rpid].append(rpid)
            else:
                self.root_comments.append(rpid)
        
        print(f"构建评论树完成: 主楼评论 {len(self.root_comments)} 条")
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
    
    def calculate_image_size(self, rpid, level=0, font=None):
        """计算生成图片所需的尺寸，更精确的计算方法"""
        if rpid not in self.comments:
            return 0, 0
        
        comment = self.comments[rpid]
        uname = comment['uname']
        message = comment['message']
        
        # 计算层级缩进
        indent = level * 30
        
        # 计算用户名宽度和高度
        username_text = f"【{uname}】"
        username_height = 25 if font else 20
        
        # 计算评论内容的行数和宽度
        content_height = 0
        max_content_width = 0
        
        if message:
            # 根据层级调整每行字符数
            max_chars_per_line = 60 - level * 5
            max_chars_per_line = max(20, max_chars_per_line)  # 最少20个字符
            
            # 计算实际需要的行数
            lines = []
            current_line = ""
            
            for char in message:
                if len(current_line) >= max_chars_per_line:
                    lines.append(current_line)
                    current_line = char
                else:
                    current_line += char
            
            if current_line:
                lines.append(current_line)
            
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
        
        # 获取层级颜色
        color = self.get_level_color(level)
        
        # 绘制层级缩进线
        indent = level * 30
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
            # 将长文本分行显示
            max_chars_per_line = 60 - level * 5  # 根据层级调整每行字符数
            lines = []
            current_line = ""
            
            for char in message:
                if len(current_line) >= max_chars_per_line:
                    lines.append(current_line)
                    current_line = char
                else:
                    current_line += char
            
            if current_line:
                lines.append(current_line)
            
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
    
    def generate_comment_image(self, rpid, output_dir, max_retries=3):
        """为单个评论树生成图片，带边缘检测和自动调整"""
        if rpid not in self.comments:
            return None
        
        root_comment = self.comments[rpid]
        root_uname = root_comment['uname']
        
        # 尝试加载字体
        font = None
        try:
            font = ImageFont.truetype("msyh.ttc", 14)  # 微软雅黑
        except:
            try:
                font = ImageFont.truetype("simhei.ttf", 14)  # 黑体
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
        
        # 使用字体信息计算更准确的图片尺寸
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
        
        # 生成文件名（清理用户名中的特殊字符）
        safe_username = re.sub(r'[<>:"/\\|?*]', '_', root_uname)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_username}_{rpid}_{timestamp}.png"
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
    
    def generate_integrated_markdown(self, output_dir, df):
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
        
        # 生成整合的Markdown文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"楼中楼拖尾整合文件_{timestamp}.md"
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


def get_user_input():
    """获取用户输入"""
    print("=" * 60)
    print("楼中楼拖尾文件生成器 - 交互式模式")
    print("=" * 60)
    print()
    
    while True:
        csv_file = input("请输入CSV文件路径: ").strip()
        
        # 处理引号包围的路径
        if csv_file.startswith('"') and csv_file.endswith('"'):
            csv_file = csv_file[1:-1]
        elif csv_file.startswith("'") and csv_file.endswith("'"):
            csv_file = csv_file[1:-1]
        
        if not csv_file:
            print("错误: 请输入有效的文件路径")
            continue
        
        if not os.path.exists(csv_file):
            print(f"错误: 文件不存在: {csv_file}")
            print("请检查文件路径是否正确")
            continue
        
        if not csv_file.lower().endswith('.csv'):
            print("警告: 输入的文件不是CSV格式，是否继续？(y/n): ", end="")
            if input().lower() != 'y':
                continue
        
        return csv_file

def main():
    """主函数"""
    try:
        # 获取用户输入
        csv_file = get_user_input()
        
        # 设置输出目录为脚本同级目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = script_dir
        
        print()
        print(f"开始处理CSV文件: {csv_file}")
        print(f"输出目录: {output_dir}")
        print("-" * 50)
        
        # 创建评论树构建器
        builder = CommentTreeBuilder()
        
        # 加载CSV文件
        df = builder.load_csv(csv_file)
        if df is None:
            return
        
        # 构建评论树
        if not builder.build_tree(df):
            return
        
        # 生成整合的Markdown文件
        generated_file = builder.generate_integrated_markdown(output_dir, df)
        
        # 生成图片文件
        print("\n开始生成评论层级结构图片...")
        images_dir = os.path.join(output_dir, "楼中楼图片")
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
            print(f"创建图片输出目录: {images_dir}")
        
        generated_images = []
        qualified_roots = []
        
        # 筛选符合条件的主楼评论
        for root_rpid in builder.root_comments:
            comment = builder.comments[root_rpid]
            row_data = comment['row_data']
            
            # 从CSV文件的回复数栏获取回复数量
            reply_count_from_csv = 0
            if '回复数' in df.columns and pd.notna(row_data['回复数']):
                reply_count_from_csv = int(row_data['回复数'])
            
            # 只对CSV中回复数超过5的评论生成图片
            if reply_count_from_csv > 5:
                qualified_roots.append(root_rpid)
        
        # 生成图片
        for i, rpid in enumerate(qualified_roots, 1):
            print(f"正在生成第 {i}/{len(qualified_roots)} 张图片...")
            image_path = builder.generate_comment_image(rpid, images_dir)
            if image_path:
                generated_images.append(image_path)
        
        print("-" * 50)
        if generated_file:
            print(f"处理完成! 生成整合拖尾文件: {os.path.basename(generated_file)}")
            print(f"文件位置: {generated_file}")
        else:
            print("处理完成，但没有生成文件")
        
        print(f"\n成功生成 {len(generated_images)} 张评论层级结构图片")
        print(f"图片保存目录: {images_dir}")
        print("\n提示: 只有CSV中回复数超过5条的评论才会被包含在拖尾文件中")
        
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"\n发生错误: {e}")


if __name__ == "__main__":
    main()