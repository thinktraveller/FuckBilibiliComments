# FuckBilibiliComments 项目依赖说明

## Python 版本要求

**最低要求：Python 3.7+**

### 版本兼容性说明

- **Python 3.7+**: 完全支持
- **Python 3.6 及以下**: 不支持

### 为什么需要 Python 3.7+？

1. **f-string 格式化**: 代码中大量使用了 f-string 语法（Python 3.6+ 特性）
2. **类型注解**: 使用了现代 Python 的类型提示功能
3. **字典保序**: 依赖 Python 3.7+ 中字典保持插入顺序的特性
4. **pandas 兼容性**: pandas>=1.3.0 需要 Python 3.7+

## 依赖包说明

### 第三方依赖

| 包名 | 版本要求 | 用途 | 脚本 |
|------|----------|------|------|
| requests | >=2.25.1 | HTTP请求，获取B站API数据 | FuckBilibiliComments.py |
| pandas | >=1.3.0 | CSV文件处理和数据去重 | FuckBilibiliComments.py, 评论CSV去重工具.py, 楼中楼拖尾文件生成器.py |
| Pillow | >=8.0.0 | 图像生成和处理 | FuckBilibiliComments.py, 楼中楼拖尾文件生成器.py |
| matplotlib | >=3.3.0 | 生成评论趋势图表 | FuckBilibiliComments.py, 评论时间精细统计工具.py |

### 标准库依赖

以下模块为 Python 标准库，无需额外安装：

- `json` - JSON数据处理
- `csv` - CSV文件读写
- `datetime` - 日期时间处理
- `time` - 时间相关功能
- `hashlib` - 哈希计算
- `re` - 正则表达式
- `sys` - 系统相关功能
- `logging` - 日志记录
- `os` - 操作系统接口
- `collections` - 集合数据类型
- `shutil` - 高级文件操作
- `subprocess` - 子进程管理
- `importlib` - 动态导入模块

## 自动依赖管理

### 功能特性

所有脚本都内置了自动依赖检测和安装功能：

1. **启动时检测**: 脚本启动时自动检测所需依赖
2. **自动安装**: 发现缺失依赖时自动使用 pip 安装
3. **版本验证**: 检查 Python 版本是否满足要求
4. **友好提示**: 提供清晰的安装进度和错误信息

### 安装流程

```
🔍 检测依赖包...
✅ requests 已安装

✅ 所有依赖包已满足要求
```

或者：

```
🔍 检测依赖包...
❌ requests 未安装

📦 发现 1 个缺失的依赖包，开始自动安装...
正在安装 requests>=2.25.1...
✅ requests>=2.25.1 安装成功

🎉 所有依赖包安装完成！
```

## 手动安装依赖

如果自动安装失败，可以手动安装：

```bash
# 安装所有依赖
pip install -r requirements.txt

# 或者单独安装
pip install requests>=2.25.1
pip install pandas>=1.3.0
pip install Pillow>=8.0.0
pip install matplotlib>=3.3.0
```

## 常见问题

### Q: 为什么选择这些版本要求？

A: 
- `requests>=2.25.1`: 该版本修复了重要的安全漏洞，提供更好的 SSL/TLS 支持
- `pandas>=1.3.0`: 提供更好的 CSV 处理性能和内存优化

### Q: 可以使用更低版本的依赖吗？

A: 不建议。虽然某些功能可能在较低版本中工作，但可能存在兼容性问题或安全风险。

### Q: 如何检查当前 Python 版本？

A: 
```bash
python --version
# 或
python -c "import sys; print(sys.version)"
```

### Q: 如何升级 Python？

A: 
- **Windows**: 从 [python.org](https://www.python.org/downloads/) 下载最新版本
- **macOS**: 使用 Homebrew: `brew install python`
- **Linux**: 使用包管理器，如 `sudo apt install python3.9`

### Q: csv_deduplicator.py 运行时出现 NumPy 版本兼容性错误？

A: 这是 NumPy 2.x 与 pandas 生态的兼容性问题：

**错误现象**：
```
A module that was compiled using NumPy 1.x cannot be run in NumPy 2.2.6 as it may crash.
```

**解决方案**：
1. **降级 NumPy**（推荐）：
   ```bash
   pip install "numpy<2.0.0"
   ```

2. **重新安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

3. **完全重装 pandas 生态**：
   ```bash
   pip uninstall pandas numpy
   pip install "numpy<2.0.0" pandas
   ```

**原因**：pandas 及其依赖模块基于 NumPy 1.x 编译，与 NumPy 2.x 存在二进制不兼容问题。

## 开发环境建议

推荐使用虚拟环境来管理依赖：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```