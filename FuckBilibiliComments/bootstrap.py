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


# 启动期依赖检测，仅由薄入口 FuckBilibiliComments.py 调用。

def check_and_install_dependencies():
    """
    检测并自动安装必要的依赖包
    """
    required_packages = {
        'requests': 'requests>=2.25.1',
        'pandas': 'pandas>=1.3.0',
        'PIL': 'Pillow>=8.0.0',
        'matplotlib': 'matplotlib>=3.3.0',
    }
    
    missing_packages = []
    
    print("[INFO] 检测依赖包...")
    
    for package_name, package_spec in required_packages.items():
        try:
            importlib.import_module(package_name)
            print(f"[OK] {package_name} 已安装")
        except ImportError:
            print(f"[ERROR] {package_name} 未安装")
            missing_packages.append(package_spec)
    
    if missing_packages:
        print(f"\n[INFO] 发现 {len(missing_packages)} 个缺失的依赖包，开始自动安装...")
        
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
        
        print("\n[OK] 所有依赖包安装完成！")
    else:
        print("\n[OK] 所有依赖包已满足要求")
