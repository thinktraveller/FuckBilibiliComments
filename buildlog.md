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

## [2026-05-19] M2 阶段：评论爬取 Tab

### 执行的任务

1. **读取实际接口**：仔细核对 `crawl_service.py`、`callbacks.py`、`account_service.py`、`history_service.py` 的真实签名，发现与计划书描述存在若干差异（见下方问题记录）。
2. **创建 `gui/tabs/crawl_tab.py`**：完整实现评论爬取 Tab，包含：
   - 视频输入区（BV 号/链接输入 + 异步解析 + 视频信息卡片/错误提示）
   - 爬取参数区（4 种模式单选、迭代附加参数、楼中楼/充电视频复选、间隔输入框）
   - 控制区（开始/停止按钮、账号状态显示栏）
   - 进度与日志区（进度条、已爬/唯一/耗时/速率 4 个统计标签、5000 行上限日志窗口）
   - 后台 QThread Worker（ResolveWorker + CrawlWorker，TaskCallbacks 通过 Signal 桥接）
   - 历史记录联动（开始时 add_task running，结束时 update_task）
   - 完成对话框（成功/停止/失败三种状态 + "打开输出文件夹"按钮）
3. **修改 `gui/main_window.py`**：将 Tab 1 从占位替换为 `CrawlTab()`；账号切换时联动刷新爬取 Tab 的账号显示。

### 关键变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `gui/tabs/crawl_tab.py` | 新增 | 评论爬取 Tab 完整实现（约 450 行） |
| `gui/main_window.py` | 修改 | 注册 CrawlTab；账号切换联动 |

### 遇到的问题及解决方案

- `resolve_video()` 实际只接受一个参数（`bv_or_url`），不接受 `cookie/ua`；已按实际签名调用。
- `crawl_service` 中无 `hot` / `time` 模式，而是用 `mode="test"` + `test_sort=0/1` 区分热度/时间排序；UI 提供 4 个选项，内部映射到正确参数。
- `TaskCallbacks` 是普通数据类（4 个可调用字段），不是 dataclass with threading.Event；中止逻辑通过在 `is_aborted` 字段中闭包 `threading.Event.is_set` 实现。
- `video_info` 中评论数字段路径为 `stat.reply`，发布时间为 UNIX 时间戳，UP 主为嵌套 dict；已逐一处理。

### 下一步计划（M3）

- 实现「时间统计」Tab：加载已有 CSV 文件，调用 `stats_service.run_stats()` 生成时间统计报告
- 实现「CSV 去重」Tab：选择多个 CSV 文件，调用 `dedup_service.run_dedup()` 合并去重

---

## [2026-05-18] M1 阶段：主窗口骨架 + 账号管理 Tab

### 执行的任务

1. **新建 `gui/` 包**：建立 `gui/__init__.py` 和 `gui/tabs/__init__.py`，确立 GUI 层包结构。
2. **实现 `gui/tabs/account_tab.py`**：
   - 左侧 `QListWidget` 展示账号列表，当前账号加粗高亮显示"[当前]"标记
   - 右侧编辑区：账号名称、Cookie（多行 QTextEdit）、UA 下拉（Firefox/Chrome/自定义）
   - Cookie 编辑模式留空表示保持原值，查看模式用 Label 显示脱敏版本
   - 新增 / 编辑 / 删除 / 设为当前账号四种操作，均委托 `account_service`
   - "测试账号有效性"使用 `QThread + QObject Worker` 模式，不阻塞主线程
   - 账号变更时通过 `current_account_changed` 信号通知主窗口
3. **实现 `gui/main_window.py`**：
   - `MainWindow(QMainWindow)`，默认 1200×800，最小 1000×700
   - `QTabWidget` 包含 6 个 Tab：评论爬取（占位）/ 时间统计（占位）/ CSV 去重（占位）/ 历史记录（占位）/ 账号管理（完整实现）/ 帮助教程（占位）
   - 底部状态栏：左侧"就绪"文字 + 右侧当前账号名（实时更新）
4. **实现 `gui/app.py`**：`run_gui()` 函数，设置高 DPI 策略、全局字体（Microsoft YaHei UI）、QApplication 元数据
5. **新建 `gui_main.py`（项目根目录）**：GUI 入口，自动切换 cwd 到项目根目录，检查 Python 版本和 PySide6 可用性

### 关键变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `gui/__init__.py` | 新增 | GUI 包初始化 |
| `gui/app.py` | 新增 | QApplication 创建与启动 |
| `gui/main_window.py` | 新增 | 主窗口，6 Tab 骨架 |
| `gui/tabs/__init__.py` | 新增 | tabs 子包初始化 |
| `gui/tabs/account_tab.py` | 新增 | 账号管理 Tab 完整实现 |
| `gui_main.py` | 新增 | GUI 启动入口（根目录） |

### 验证结果

- 所有 6 个新文件 Python 语法检查通过（`ast.parse`）
- `account_service` 导入及 `get_accounts_masked()` / `get_selected_account()` 调用正常
- GUI 层与业务层完全解耦：`account_tab.py` 仅通过 `services/account_service` 操作数据

### 遇到的问题及解决方案

- 无，M1 阶段顺利完成。

### 下一步计划（M2）

- 实现"评论爬取 Tab"：BV 号/链接输入、模式选择、参数配置、进度展示、日志输出
- 需要将 `crawl_service.run_crawl()` 接入 QThread Worker
- 涉及 `TaskCallbacks` 的 GUI 实现（信号 emit 版本）

---
