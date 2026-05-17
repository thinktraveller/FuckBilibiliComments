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


# 本模块汇总所有 cookie 相关读写与调用：
#   - DEFAULT_HEADERS: 兜底请求头（Cookie 字段须保持为空）
#   - load_config / save_config / add_new_account: 配置文件读写
#   - select_account: 多账户选择
#   - get_request_headers: 由配置构造实际请求头
#   - try_switch_to_next_cookie: 封禁时自动切换
#
# 注意：本模块已手动改造（cookie-editor 解析 + UA 菜单），不要再用
# _refactor_explicit.py 重新生成，否则改动会被覆盖。

# 浏览器默认 User-Agent 预设
UA_FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

# B 站接口所需的核心 cookie 字段；导入时其它字段会被丢弃
REQUIRED_COOKIE_KEYS = (
    'SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5',
    'buvid3', 'buvid4', 'buvid_fp', 'buvid_fp_plain', 'b_nut',
    '_uuid', 'sid', 'b_lsid', 'bili_ticket', 'bili_ticket_expires',
    'fingerprint', 'rpdid',
)


def parse_cookie_editor_export(text):
    """解析 cookie-editor 导出的 `key=value;key=value` 字符串。

    Args:
        text (str): 用户粘贴的整段 cookie 字符串
    Returns:
        dict[str, str]: 字段名到值的映射
    """
    result = {}
    for chunk in text.split(';'):
        chunk = chunk.strip()
        if not chunk or '=' not in chunk:
            continue
        k, _, v = chunk.partition('=')
        k = k.strip()
        v = v.strip()
        if k:
            result[k] = v
    return result


def build_cookie_string(parsed):
    """按 REQUIRED_COOKIE_KEYS 过滤并重组 cookie 字符串。

    Args:
        parsed (dict): parse_cookie_editor_export 的返回值
    Returns:
        str: "k=v; k=v" 形式的 cookie 字符串
    """
    pairs = [f"{k}={parsed[k]}" for k in REQUIRED_COOKIE_KEYS if k in parsed]
    return '; '.join(pairs)


def prompt_user_agent():
    """User-Agent 选择菜单，默认 Firefox。"""
    print("\n请选择 User-Agent：")
    print(f"  1. Firefox（默认）")
    print(f"     {UA_FIREFOX}")
    print(f"  2. Chrome")
    print(f"     {UA_CHROME}")
    print(f"  3. 自定义")
    choice = input("请输入选项 [1/2/3，直接回车=1]: ").strip() or '1'
    if choice == '2':
        return UA_CHROME
    if choice == '3':
        custom = input("请粘贴自定义 User-Agent: ").strip()
        if not custom:
            print("⚠️ 自定义内容为空，回退到 Firefox 默认值")
            return UA_FIREFOX
        return custom
    return UA_FIREFOX

def try_switch_to_next_cookie(logger=None):
    """
    尝试切换到下一个可用的cookie
    
    Args:
        logger: 日志记录器
    
    Returns:
        dict: 新的cookie配置，如果没有可用的cookie则返回None
    """
    try:
        # 加载当前配置
        config = load_config()
        accounts = config.get('accounts', [])
        current_index = config.get('selected_account_index', 0)
        
        if len(accounts) <= 1:
            if logger:
                logger.warning("只有一个账号配置，无法切换cookie")
            return None
        
        # 尝试切换到下一个账号
        next_index = (current_index + 1) % len(accounts)
        next_account = accounts[next_index]
        
        # 更新配置
        config['selected_account_index'] = next_index
        save_config(config)
        
        print(f"\n🔄 自动切换到下一个账号: {next_account['name']}")
        if logger:
            logger.info(f"Cookie切换成功，从账号 {accounts[current_index]['name']} 切换到 {next_account['name']}")
        
        return {
            'cookie': next_account['cookie'],
            'user_agent': next_account['user_agent']
        }
    except Exception as e:
        if logger:
            logger.error(f"切换cookie时发生错误: {e}")
        return None

def load_config():
    """
    加载配置文件，支持多账号配置和用户选择
    
    Returns:
        dict: 包含选中账号的cookie和user_agent的配置字典
    """
    config_file = 'config.json'
    
    # 尝试读取配置文件
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"❌ 配置文件 {config_file} 不存在，将创建默认配置文件")
        config = {
            "accounts": [],
            "selected_account_index": 0,
            "description": {
                "accounts": "账号配置列表，每个账号包含名称、cookie和user_agent",
                "selected_account_index": "当前选中的账号索引（从0开始）",
                "cookie": "通过 Cookie-Editor 扩展导出后过滤得到的 cookie 字符串",
                "user_agent": "浏览器 User-Agent，默认 Firefox；添加账号时可选 Chrome 或自定义"
            }
        }
        save_config(config)
    except json.JSONDecodeError:
        print(f"❌ 配置文件 {config_file} 格式错误，将重新创建")
        config = {
            "accounts": [],
            "selected_account_index": 0,
            "description": {
                "accounts": "账号配置列表，每个账号包含名称、cookie和user_agent",
                "selected_account_index": "当前选中的账号索引（从0开始）",
                "cookie": "通过 Cookie-Editor 扩展导出后过滤得到的 cookie 字符串",
                "user_agent": "浏览器 User-Agent，默认 Firefox；添加账号时可选 Chrome 或自定义"
            }
        }
        save_config(config)
    
    # 兼容旧版本配置格式
    if 'cookie' in config and 'accounts' not in config:
        print("🔄 检测到旧版本配置格式，正在转换为新格式...")
        old_cookie = config.get('cookie', '')
        old_user_agent = config.get('user_agent', UA_FIREFOX)
        
        config = {
            "accounts": [
                {
                    "name": "默认账号",
                    "cookie": old_cookie,
                    "user_agent": old_user_agent
                }
            ] if old_cookie else [],
            "selected_account_index": 0,
            "description": {
                "accounts": "账号配置列表，每个账号包含名称、cookie和user_agent",
                "selected_account_index": "当前选中的账号索引（从0开始）",
                "cookie": "通过 Cookie-Editor 扩展导出后过滤得到的 cookie 字符串",
                "user_agent": "浏览器 User-Agent，默认 Firefox；添加账号时可选 Chrome 或自定义"
            }
        }
        save_config(config)
        print("✅ 配置格式转换完成")
    
    # 确保accounts字段存在
    if 'accounts' not in config:
        config['accounts'] = []
    if 'selected_account_index' not in config:
        config['selected_account_index'] = 0
    
    # 显示账号选择界面
    selected_account = select_account(config)
    
    return selected_account

def select_account(config):
    """
    账号选择和管理界面
    
    Args:
        config (dict): 完整的配置字典
    
    Returns:
        dict: 包含选中账号的cookie和user_agent的配置字典
    """
    accounts = config.get('accounts', [])
    
    if not accounts:
        print("\n=== 首次使用，需要添加账号配置 ===")
        account = add_new_account()
        if account:
            config['accounts'].append(account)
            config['selected_account_index'] = 0
            save_config(config)
            return {
                'cookie': account['cookie'],
                'user_agent': account['user_agent']
            }
        else:
            print("[WARNING] 未配置任何账号，可能影响爬取效果")
            return {
                'cookie': '',
                'user_agent': UA_FIREFOX
            }
    
    print("\n=== 账号选择 ===")
    print("当前可用账号：")
    for i, account in enumerate(accounts):
        status = "[当前选中]" if i == config.get('selected_account_index', 0) else ""
        cookie_preview = account['cookie'][:50] + "..." if len(account['cookie']) > 50 else account['cookie']
        print(f"  {i+1}. {account['name']} {status}")
        print(f"     Cookie预览: {cookie_preview}")
    
    print(f"\n选择操作：")
    print(f"  直接回车: 使用当前选中的账号 ({accounts[config.get('selected_account_index', 0)]['name']})")
    print(f"  输入数字 1-{len(accounts)}: 选择对应账号")
    print(f"  输入 'add' 或 'a': 添加新账号")
    
    while True:
        choice = input("请选择 (回车/数字/add): ").strip().lower()
        
        if not choice:  # 直接回车，使用当前选中的账号
            selected_index = config.get('selected_account_index', 0)
            if 0 <= selected_index < len(accounts):
                selected_account = accounts[selected_index]
                print(f"✅ 使用账号: {selected_account['name']}")
                return {
                    'cookie': selected_account['cookie'],
                    'user_agent': selected_account['user_agent']
                }
            else:
                print("❌ 当前选中的账号索引无效，使用第一个账号")
                config['selected_account_index'] = 0
                save_config(config)
                selected_account = accounts[0]
                return {
                    'cookie': selected_account['cookie'],
                    'user_agent': selected_account['user_agent']
                }
        
        elif choice in ['add', 'a']:  # 添加新账号
            account = add_new_account()
            if account:
                config['accounts'].append(account)
                config['selected_account_index'] = len(config['accounts']) - 1
                save_config(config)
                print(f"✅ 已添加并选择新账号: {account['name']}")
                return {
                    'cookie': account['cookie'],
                    'user_agent': account['user_agent']
                }
            else:
                print("❌ 添加账号失败，请重新选择")
                continue
        
        elif choice.isdigit():  # 选择指定账号
            index = int(choice) - 1
            if 0 <= index < len(accounts):
                config['selected_account_index'] = index
                save_config(config)
                selected_account = accounts[index]
                print(f"✅ 已选择账号: {selected_account['name']}")
                return {
                    'cookie': selected_account['cookie'],
                    'user_agent': selected_account['user_agent']
                }
            else:
                print(f"❌ 无效的选择，请输入 1-{len(accounts)} 之间的数字")
                continue
        
        else:
            print("❌ 无效的输入，请重新选择")
            continue

def add_new_account():
    """添加新账号配置（基于 cookie-editor 导出）。

    交互流程：
      1. 输入账号名（去重）
      2. 粘贴 cookie-editor 导出的 `key=value;key=value` 字符串，
         脚本自动提取 SESSDATA / bili_jct / DedeUserID 等核心字段
      3. 从 Firefox / Chrome / 自定义 三选一指定 User-Agent

    Returns:
        dict | None: 账号配置；用户取消时返回 None
    """
    print("\n=== 添加新账号 ===")
    print("请按以下步骤获取 Cookie：")
    print("  1. 在浏览器装上 Cookie-Editor 扩展（chrome/firefox 都有）")
    print("  2. 登录 https://www.bilibili.com")
    print("  3. 打开 Cookie-Editor → 选择 Export → Export as Header String")
    print("  4. 复制导出的整段 key=value;key=value 文本，下方粘贴")
    print()

    # 直接读取配置文件以检查账号名重复（避免递归调用 load_config）
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            current_config = json.load(f)
        existing_names = [a['name'] for a in current_config.get('accounts', [])]
    except Exception:
        existing_names = []

    # 输入账号名
    while True:
        name = input("请输入账号名称（如'主号'、'小号'）: ").strip()
        if not name:
            print("❌ 账号名称不能为空")
            continue
        if name in existing_names:
            print(f"❌ 账号名称 '{name}' 已存在")
            print(f"   现有账号: {', '.join(existing_names)}")
            continue
        break

    # 粘贴并解析 cookie
    while True:
        raw = input("请粘贴 Cookie-Editor 导出的字符串（直接回车取消）: ").strip()
        if not raw:
            if input("确定要取消添加账号吗？(y/N): ").strip().lower() == 'y':
                return None
            continue

        parsed = parse_cookie_editor_export(raw)
        if not parsed:
            print("❌ 无法解析：请确认粘贴的是 key=value;key=value 格式")
            continue

        found = [k for k in REQUIRED_COOKIE_KEYS if k in parsed]
        if 'SESSDATA' not in parsed:
            print("⚠️ 警告：未检测到 SESSDATA（登录态字段）")
            print("   未登录的 cookie 只能爬到前几页评论")
            if input("仍然继续？(y/N): ").strip().lower() != 'y':
                continue

        cookie = build_cookie_string(parsed)
        ignored_count = len(parsed) - len(found)
        print(f"✅ 识别到 {len(found)} 个核心字段: {', '.join(found)}")
        if ignored_count:
            print(f"   已过滤 {ignored_count} 个无关字段")
        break

    user_agent = prompt_user_agent()

    print(f"✅ 账号 '{name}' 配置完成")
    return {"name": name, "cookie": cookie, "user_agent": user_agent}

def save_config(config):
    """
    保存配置文件
    
    Args:
        config (dict): 配置字典
    """
    config_file = 'config.json'
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ 保存配置文件失败: {e}")

def get_request_headers(config):
    """
    根据配置生成请求头
    
    Args:
        config (dict): 配置字典，包含cookie和user_agent字段
    
    Returns:
        dict: 请求头字典
    """
    return {
        'Cookie': config.get('cookie', ''),
        'User-Agent': config.get('user_agent', UA_FIREFOX),
        'Referer': 'https://www.bilibili.com',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

DEFAULT_HEADERS = {
    'Cookie': '',
    'User-Agent': UA_FIREFOX,
    'Referer': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"'
}
