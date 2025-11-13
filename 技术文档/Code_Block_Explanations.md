# FuckBilibiliComments.py 代码逐块解释

## 块1: 导入语句 (行1-13)

```python
import requests
import json
import csv
from datetime import datetime
import time
import hashlib
import re
import sys
import logging
import os
from collections import Counter
import shutil
```

**解释**:
- 这些是脚本所需的Python库导入。
- `requests`: 用于HTTP请求，爬取B站API。
- `json` 和 `csv`: 处理JSON数据和CSV文件。
- `datetime` 和 `time`: 处理时间相关操作。
- `hashlib`: 可能用于生成哈希。
- `re`: 正则表达式，用于字符串匹配。
- `sys`: 系统相关操作。
- `logging`: 日志记录。
- `os`: 文件和目录操作。
- `Counter`: 计数器，用于统计。
- `shutil`: 文件操作，如复制。

## 块2: BV号转换常量 (行16-26)

```python
# BV号转换相关常量定义
XOR_CODE = 23442827791579
MASK_CODE = 2251799813685247
MAX_AID = 2251799813685248
MIN_AID = 1
BASE = 58
BV_LEN = 12

# Base58编码表
ALPHABET = 'FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf'

# 创建反向查找字典
REVERSE_DICT = {char: idx for idx, char in enumerate(ALPHABET)}
```

**解释**:
- 定义了BV号和AV号转换所需的常量。
- `XOR_CODE` 和 `MASK_CODE`: 用于加密/解密转换。
- `ALPHABET`: Base58编码字符集。
- `REVERSE_DICT`: 用于解码的查找表。

## 块3: bvid_to_aid 函数 (行28-59)

```python
def bvid_to_aid(bvid):
    # 函数体...
```

**解释**:
- 将BV号转换为AV号（oid）。
- 检查BV格式，进行位置交换，Base58解码，应用掩码和XOR操作。

## 块4: aid_to_bvid 函数 (行61-92)

```python
def aid_to_bvid(aid):
    # 函数体...
```

**解释**:
- 将AV号转换为BV号。
- 反向操作：应用XOR和掩码，Base58编码，位置交换。

## 块5: extract_id_from_url 函数 (行94-133)

```python
def extract_id_from_url(url):
    # 函数体...
```

**解释**:
- 从URL中提取并验证BV号。
- 查找'BV'，检查后续10位字符是否有效。

## 块6: parse_video_input 函数 (行135-161)

```python
def parse_video_input(user_input):
    # 函数体...
```

**解释**:
- 解析用户输入URL，提取BV号并转换为oid。

## 块7: get_video_info 函数 (行163-200)

```python
def get_video_info(bvid, timeout=10):
    # 函数体...
```

**解释**:
- 使用B站API获取视频信息。
- 发送GET请求，处理响应。

# 块8: get_video_info 函数剩余部分 (行201-240)

```python
    try:
        # 发送请求
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # 解析JSON响应
        data = response.json()
        
        # 检查API返回状态
        if data.get("code") == 0:
            video_data = data.get("data", {})
            
            # 提取关键信息
            video_info = {
                "bvid": video_data.get("bvid", ""),
                "aid": video_data.get("aid", ""),
                "title": video_data.get("title", ""),
                "desc": video_data.get("desc", ""),
                "duration": video_data.get("duration", 0),
                "pubdate": video_data.get("pubdate", 0),
                "owner": {
                    "mid": video_data.get("owner", {}).get("mid", ""),
                    "name": video_data.get("owner", {}).get("name", ""),
                    "face": video_data.get("owner", {}).get("face", "")
                },
                "stat": {
                    "view": video_data.get("stat", {}).get("view", 0),
                    "danmaku": video_data.get("stat", {}).get("danmaku", 0),
                    "reply": video_data.get("stat", {}).get("reply", 0),
                    "favorite": video_data.get("stat", {}).get("favorite", 0),
                    "coin": video_data.get("stat", {}).get("coin", 0),
                    "share": video_data.get("stat", {}).get("share", 0),
                    "like": video_data.get("stat", {}).get("like", 0)
                },
                "pic": video_data.get("pic", ""),
                "tname": video_data.get("tname", "")
            }
            
            return video_info
            
        else:
            error_msg = data.get("message", "未知错误")
            print(f"API返回错误: {data.get('code')} - {error_msg}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        return None
    except Exception as e:
        print(f"获取视频信息时发生未知错误: {e}")
        return None
```

**解释**:
- 处理API响应，提取视频信息如标题、描述、统计数据等。
- 包括错误处理。

# 块9: get_video_title_quick 函数 (行242-250)

```python
def get_video_title_quick(bvid):
    """
    快速获取视频标题
    
    Args:
        bvid (str): 视频的BV号
        
    Returns:
        str: 视频标题，获取失败返回None
    """
    video_info = get_video_info(bvid)
    if video_info:
        return video_info.get("title")
    return None
```

**解释**:
- 快速获取视频标题的包装函数。

# 块10: load_config 函数 (行252-320)

```python
def load_config():
    # 函数体...
```

**解释**:
- 加载或创建配置文件，处理cookie和user_agent。
- 如果cookie为空，提示用户输入。

# 块11: save_config 函数 (行322-332)

```python
def save_config(config):
    # 函数体...
```

**解释**:
- 保存配置到JSON文件。

# 块12: get_request_headers 函数 (行334-358)

```python
def get_request_headers(config):
    # 函数体...
```

**解释**:
- 根据配置生成HTTP请求头。

# 块13: generate_safe_filename 函数 (行360-400, 继续到401-500)

```python
def generate_safe_filename(video_title, oid, suffix="", file_type="original"):
    # 函数体...
```

**解释**:
- 生成安全的文件名，根据类型如original, final等。
- 处理标题清理、BV转换、时间戳。

(文档将继续更新以覆盖更多代码块。)