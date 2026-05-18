# 构建日志

## [2026-05-18] M0 阶段：核心模块解耦

### 执行的任务

1. **读取并分析构建计划书**：确认 6 个里程碑（M0-M5）+ 打包（M6）的整体架构，识别风险点。
2. **新增 `callbacks.py`**：定义 `TaskCallbacks` 数据类（log / progress / prompt / is_aborted 四件套）；实现 `make_cli_callbacks()`（CLI 默认实现）和 `make_noop_callbacks()`（测试用）。
3. **建立 `services/` 目录**：新增以下 6 个服务模块：
   - `__init__.py`：包说明
   - `account_service.py`：账号 CRUD、Cookie 脱敏、有效性检测（调 B 站 nav 接口）
   - `history_service.py`：历史记录读写（原子写入 history.json）
   - `task_manager.py`：内存任务注册、进度更新、中止标志、状态变更通知
   - `dedup_service.py`：双文件 CSV 合并去重完整流程
   - `stats_service.py`：调用 `stats.generate_restructured_time_statistics` 的时间统计流程
   - `crawl_service.py`：综合/测试/迭代三种爬取模式的流程编排，含 `resolve_video` 和 `CrawlParams`
4. **改造 `tools/` 薄壳**：
   - `评论CSV去重工具.py` → 10 行导入 + 交互式调用 `dedup_service.run_dedup()`
   - `评论时间精细统计工具.py` → 10 行导入 + 交互式调用 `stats_service.run_stats()`
   - 原版本备份为 `*_original.py`

### 关键变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `FuckBilibiliComments/callbacks.py` | 新增 | TaskCallbacks 接口与 CLI 默认实现 |
| `FuckBilibiliComments/services/__init__.py` | 新增 | 服务层包初始化 |
| `FuckBilibiliComments/services/account_service.py` | 新增 | 账号管理服务 |
| `FuckBilibiliComments/services/history_service.py` | 新增 | 历史记录服务 |
| `FuckBilibiliComments/services/task_manager.py` | 新增 | 任务管理器 |
| `FuckBilibiliComments/services/dedup_service.py` | 新增 | CSV 去重服务 |
| `FuckBilibiliComments/services/stats_service.py` | 新增 | 时间统计服务 |
| `FuckBilibiliComments/services/crawl_service.py` | 新增 | 爬取流程服务 |
| `tools/评论CSV去重工具.py` | 改为薄壳 | 原版备份为 _original.py |
| `tools/评论时间精细统计工具.py` | 改为薄壳 | 原版备份为 _original.py |

### 验证结果

- `python -c "from FuckBilibiliComments.callbacks import make_cli_callbacks"` -> OK
- `python -c "from FuckBilibiliComments.services.crawl_service import run_crawl"` -> OK
- 所有 6 个服务模块一次性导入无报错
- `task_manager` 单元测试通过（register / progress / mark_done）
- `history_service` 单元测试通过（add / update / delete）
- `python -c "import FuckBilibiliComments"` 原有包初始化无破坏

### 遇到的问题及解决方案

- Windows 下 `copy` 命令不可用于 bash；改用 `cp` 完成备份。
- `tools/` 目录中原脚本在模块顶层调用了 `check_and_install_dependencies()`，会在 import 时触发副作用；薄壳版本完全重写，规避此问题。

### 下一步计划（M1）

- 搭建 `gui/` 目录、QApplication、主窗口（QTabWidget）
- 实现账号管理 Tab（CRUD + 有效性测试）
- 集成 task_manager / history_service 空壳联动
- 前提：用户需安装 PySide6（`pip install "PySide6>=6.6,<6.8"`）

---
