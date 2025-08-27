#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV文件去重工具

该脚本从FuckBilibiliComments.py中提取的去重算法，用于处理两个CSV文件的去重操作。
功能包括：
1. 合并去重：生成两个文件合并后去重的结果
2. 重复数据：生成在去重过程中发现的重复数据
3. 文件A独有：生成存在于文件A但不存在于文件B的数据
4. 文件B独有：生成存在于文件B但不存在于文件A的数据

使用方法：
python csv_deduplicator.py <文件A路径> <文件B路径> [输出目录]

基于FuckBilibiliComments.py提取
Python版本要求：Python 3.7+
"""

# 依赖检测和自动安装
import sys
import subprocess
import importlib

def check_and_install_dependencies():
    """
    检测并自动安装必要的依赖包
    """
    required_packages = {
        'pandas': 'pandas>=1.3.0',
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

# 导入所需模块
import pandas as pd
import os
from datetime import datetime
import logging


def setup_logger(output_dir):
    """设置日志记录器"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(output_dir, f'csv_deduplicator_{timestamp}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def extract_crawl_time_from_comment(comment):
    """
    从评论数据中提取爬取时间
    
    Args:
        comment (dict): 评论数据字典
    
    Returns:
        int: 时间戳
    """
    crawl_time_str = comment.get('爬取时间', '')
    if crawl_time_str:
        try:
            # 解析时间格式：YYYY年MM月DD日_HH时MM分SS秒
            dt = datetime.strptime(crawl_time_str, '%Y年%m月%d日_%H时%M分%S秒')
            return int(dt.timestamp())
        except:
            pass
    
    # 备选方案：使用评论的时间戳
    return comment.get('时间戳', 0)


def deduplicate_by_rpid(comments, comment_type, logger):
    """
    基于rpid和爬取时间进行去重
    
    Args:
        comments (list): 评论列表
        comment_type (str): 评论类型标识
        logger: 日志记录器
    
    Returns:
        tuple: (去重后的评论列表, 重复评论列表)
    """
    rpid_to_comment = {}
    duplicates = []
    
    for comment in comments:
        rpid = comment.get('rpid', '')
        if rpid:
            # 如果已存在该rpid，比较爬取时间，保留爬取时间更晚的
            if rpid in rpid_to_comment:
                existing_crawl_time = extract_crawl_time_from_comment(rpid_to_comment[rpid])
                current_crawl_time = extract_crawl_time_from_comment(comment)
                
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
    if logger:
        logger.info(f"{comment_type}去重: {len(comments)} -> {len(deduped_comments)} 条评论，重复 {len(duplicates)} 条")
    
    return deduped_comments, duplicates


def find_unique_data(comments_a, comments_b, label_a, label_b, logger):
    """
    找出两个评论列表中的独有数据
    
    Args:
        comments_a (list): 评论列表A
        comments_b (list): 评论列表B
        label_a (str): 列表A的标签
        label_b (str): 列表B的标签
        logger: 日志记录器
    
    Returns:
        tuple: (A独有的评论, B独有的评论)
    """
    # 构建rpid集合
    rpids_a = {comment.get('rpid', '') for comment in comments_a if comment.get('rpid', '')}
    rpids_b = {comment.get('rpid', '') for comment in comments_b if comment.get('rpid', '')}
    
    # 找出独有的rpid
    unique_rpids_a = rpids_a - rpids_b
    unique_rpids_b = rpids_b - rpids_a
    
    # 提取独有的评论
    unique_comments_a = [comment for comment in comments_a 
                        if comment.get('rpid', '') in unique_rpids_a]
    unique_comments_b = [comment for comment in comments_b 
                        if comment.get('rpid', '') in unique_rpids_b]
    
    if logger:
        logger.info(f"{label_a}独有评论: {len(unique_comments_a)} 条")
        logger.info(f"{label_b}独有评论: {len(unique_comments_b)} 条")
    
    return unique_comments_a, unique_comments_b


def validate_csv_file(file_path):
    """
    验证CSV文件是否包含必要的字段且无空值
    
    Args:
        file_path (str): CSV文件路径
    
    Returns:
        tuple: (是否有效, 错误信息)
    """
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        
        # 检查是否存在rpid列
        if 'rpid' not in df.columns:
            return False, "文件缺少'rpid'列"
        
        # 检查是否存在爬取时间列
        if '爬取时间' not in df.columns:
            return False, "文件缺少'爬取时间'列"
        
        # 检查rpid列是否有空值
        rpid_null_count = df['rpid'].isnull().sum()
        rpid_empty_count = (df['rpid'].astype(str).str.strip() == '').sum()
        if rpid_null_count > 0 or rpid_empty_count > 0:
            return False, f"rpid列存在 {rpid_null_count + rpid_empty_count} 个空值或空字符串"
        
        # 检查爬取时间列是否有空值
        crawl_time_null_count = df['爬取时间'].isnull().sum()
        crawl_time_empty_count = (df['爬取时间'].astype(str).str.strip() == '').sum()
        if crawl_time_null_count > 0 or crawl_time_empty_count > 0:
            return False, f"爬取时间列存在 {crawl_time_null_count + crawl_time_empty_count} 个空值或空字符串"
        
        return True, "文件验证通过"
    
    except Exception as e:
        return False, f"文件读取失败: {str(e)}"


def load_csv_file(file_path, logger):
    """
    加载CSV文件
    
    Args:
        file_path (str): CSV文件路径
        logger: 日志记录器
    
    Returns:
        list: 评论数据列表
    """
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        comments = df.to_dict('records')
        logger.info(f"成功加载文件 {file_path}，共 {len(comments)} 条记录")
        return comments
    except Exception as e:
        logger.error(f"加载文件 {file_path} 失败: {str(e)}")
        return []


def save_csv_file(comments, file_path, logger):
    """
    保存评论数据到CSV文件
    
    Args:
        comments (list): 评论数据列表
        file_path (str): 输出文件路径
        logger: 日志记录器
    """
    try:
        if comments:
            df = pd.DataFrame(comments)
            # 使用UTF-8-BOM编码，确保Excel能正确显示中文
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"成功保存 {len(comments)} 条记录到 {file_path}")
        else:
            # 创建空文件
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write('')
            logger.info(f"创建空文件 {file_path}")
    except Exception as e:
        logger.error(f"保存文件 {file_path} 失败: {str(e)}")


def process_csv_deduplication(file_a_path, file_b_path, output_dir, logger):
    """
    处理CSV文件去重
    
    Args:
        file_a_path (str): 文件A路径
        file_b_path (str): 文件B路径
        output_dir (str): 输出目录
        logger: 日志记录器
    """
    # 加载CSV文件
    logger.info("开始加载CSV文件...")
    comments_a = load_csv_file(file_a_path, logger)
    comments_b = load_csv_file(file_b_path, logger)
    
    if not comments_a and not comments_b:
        logger.error("两个文件都无法加载，退出处理")
        return
    
    # 获取文件名（不含扩展名）用于标识
    file_a_name = os.path.splitext(os.path.basename(file_a_path))[0]
    file_b_name = os.path.splitext(os.path.basename(file_b_path))[0]
    
    # 第一步：对每个文件内部去重
    logger.info("开始对文件内部进行去重...")
    deduped_a, duplicates_a = deduplicate_by_rpid(comments_a, f"文件A({file_a_name})", logger)
    deduped_b, duplicates_b = deduplicate_by_rpid(comments_b, f"文件B({file_b_name})", logger)
    
    # 第二步：找出独有数据
    logger.info("开始查找独有数据...")
    unique_a, unique_b = find_unique_data(deduped_a, deduped_b, 
                                         f"文件A({file_a_name})", 
                                         f"文件B({file_b_name})", logger)
    
    # 第三步：合并并去重
    logger.info("开始合并去重...")
    all_comments = deduped_a + deduped_b
    merged_comments, merge_duplicates = deduplicate_by_rpid(all_comments, "合并去重", logger)
    
    # 合并所有重复数据
    all_duplicates = duplicates_a + duplicates_b + merge_duplicates
    
    # 生成输出文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存结果文件
    logger.info("开始保存结果文件...")
    
    # 1. 合并去重文件
    merged_file = os.path.join(output_dir, f'合并去重结果_{timestamp}.csv')
    save_csv_file(merged_comments, merged_file, logger)
    
    # 2. 重复数据文件
    duplicates_file = os.path.join(output_dir, f'重复数据_{timestamp}.csv')
    save_csv_file(all_duplicates, duplicates_file, logger)
    
    # 3. 文件A独有数据
    unique_a_file = os.path.join(output_dir, f'独有数据_隶属于文件A：{file_a_name}_{timestamp}.csv')
    save_csv_file(unique_a, unique_a_file, logger)
    
    # 4. 文件B独有数据
    unique_b_file = os.path.join(output_dir, f'独有数据_隶属于文件B：{file_b_name}_{timestamp}.csv')
    save_csv_file(unique_b, unique_b_file, logger)
    
    # 生成统计报告
    generate_statistics_report(comments_a, comments_b, deduped_a, deduped_b, 
                              merged_comments, all_duplicates, unique_a, unique_b,
                              file_a_name, file_b_name, output_dir, timestamp, logger)


def generate_statistics_report(comments_a, comments_b, deduped_a, deduped_b,
                              merged_comments, all_duplicates, unique_a, unique_b,
                              file_a_name, file_b_name, output_dir, timestamp, logger):
    """
    生成统计报告
    """
    report_file = os.path.join(output_dir, f'去重统计报告_{timestamp}.txt')
    
    try:
        # 使用UTF-8-BOM编码，确保在Windows记事本等程序中正确显示中文
        with open(report_file, 'w', encoding='utf-8-sig') as f:
            f.write("CSV文件去重统计报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"处理时间: {datetime.now().strftime('%Y年%m月%d日 %H时%M分%S秒')}\n")
            f.write(f"文件A: {file_a_name}\n")
            f.write(f"文件B: {file_b_name}\n\n")
            
            f.write("原始数据统计:\n")
            f.write(f"  文件A原始记录数: {len(comments_a)}\n")
            f.write(f"  文件B原始记录数: {len(comments_b)}\n")
            f.write(f"  总原始记录数: {len(comments_a) + len(comments_b)}\n\n")
            
            f.write("去重后统计:\n")
            f.write(f"  文件A去重后: {len(deduped_a)}\n")
            f.write(f"  文件B去重后: {len(deduped_b)}\n")
            f.write(f"  合并去重后: {len(merged_comments)}\n")
            f.write(f"  总重复记录数: {len(all_duplicates)}\n\n")
            
            f.write("独有数据统计:\n")
            f.write(f"文件A独有: {len(unique_a)}\n")
            f.write(f"文件B独有: {len(unique_b)}\n\n")
            
            # 计算重复率
            if len(comments_a) + len(comments_b) > 0:
                duplicate_rate = len(all_duplicates) / (len(comments_a) + len(comments_b)) * 100
                f.write(f"总重复率: {duplicate_rate:.2f}%\n")
            
            # 计算交集率
            if len(deduped_a) > 0 and len(deduped_b) > 0:
                intersection = len(deduped_a) + len(deduped_b) - len(merged_comments)
                intersection_rate_a = intersection / len(deduped_a) * 100
                intersection_rate_b = intersection / len(deduped_b) * 100
                f.write(f"文件A与文件B的交集率: {intersection_rate_a:.2f}% (基于文件A)\n")
                f.write(f"文件A与文件B的交集率: {intersection_rate_b:.2f}% (基于文件B)\n")
        
        logger.info(f"统计报告已保存到 {report_file}")
    except Exception as e:
        logger.error(f"生成统计报告失败: {str(e)}")


def main():
    """主函数"""
    print("CSV文件去重工具")
    print("=" * 30)
    
    # 交互式输入文件A路径
    while True:
        file_a = input("请输入文件A的路径: ").strip()
        if not file_a:
            print("文件A路径不能为空，请重新输入")
            continue
        
        # 处理引号
        file_a = file_a.strip('"\'')
        
        if not os.path.exists(file_a):
            print(f"错误：文件 {file_a} 不存在，请重新输入")
            continue
        
        if not file_a.lower().endswith('.csv'):
            print("警告：文件A不是CSV格式，是否继续？(y/n): ", end="")
            if input().lower() != 'y':
                continue
        
        # 验证CSV文件的字段完整性
        is_valid, error_msg = validate_csv_file(file_a)
        if not is_valid:
            print(f"错误：文件A {error_msg}，请重新输入文件")
            continue
        
        print("文件A验证通过")
        break
    
    # 交互式输入文件B路径
    while True:
        file_b = input("请输入文件B的路径: ").strip()
        if not file_b:
            print("文件B路径不能为空，请重新输入")
            continue
        
        # 处理引号
        file_b = file_b.strip('"\'')
        
        if not os.path.exists(file_b):
            print(f"错误：文件 {file_b} 不存在，请重新输入")
            continue
        
        if not file_b.lower().endswith('.csv'):
            print("警告：文件B不是CSV格式，是否继续？(y/n): ", end="")
            if input().lower() != 'y':
                continue
        
        # 验证CSV文件的字段完整性
        is_valid, error_msg = validate_csv_file(file_b)
        if not is_valid:
            print(f"错误：文件B {error_msg}，请重新输入文件")
            continue
        
        print("文件B验证通过")
        break
    
    # 交互式输入输出目录
    output_input = input("请输入输出目录路径（留空则在脚本同目录下创建文件夹）: ").strip()
    
    if output_input:
        # 处理引号
        output_dir = output_input.strip('"\'')
        output_dir = os.path.abspath(output_dir)
    else:
        # 默认在脚本同目录下创建输出文件夹
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(script_dir, f'csv_deduplication_output_{timestamp}')
    
    # 创建输出目录
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"输出目录: {output_dir}")
    except Exception as e:
        print(f"创建输出目录失败: {str(e)}")
        sys.exit(1)
    
    # 设置日志
    logger = setup_logger(output_dir)
    
    logger.info("CSV文件去重工具启动")
    logger.info(f"文件A: {file_a}")
    logger.info(f"文件B: {file_b}")
    logger.info(f"输出目录: {output_dir}")
    
    print("\n开始处理...")
    
    try:
        # 执行去重处理
        process_csv_deduplication(file_a, file_b, output_dir, logger)
        logger.info("CSV文件去重处理完成")
        print("\n处理完成！请查看输出目录中的结果文件。")
    except Exception as e:
        logger.error(f"处理过程中发生错误: {str(e)}")
        print(f"\n处理失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()