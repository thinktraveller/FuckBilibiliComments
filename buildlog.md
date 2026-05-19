# 构建日志

## [2026-05-19] M5 阶段：帮助教程 Tab + 空状态优化

### 执行的任务

1. **创建 `gui/resources/help/` 目录**，新增 7 个 HTML 帮助文档：
   - `01_quick_start.html`：快速上手（4 步走：安装扩展 → 导出 Cookie → 添加账号 → 开始爬取）
   - `02_cookie_chrome.html`：Chrome/Edge Cookie 获取（Cookie-Editor 方式 + F12 手动方式）
   - `03_cookie_firefox.html`：Firefox Cookie 获取（步骤与 Chrome 类似，附存储检查器方式）
   - `04_user_agent.html`：User-Agent 获取（F12 Network 标签抓取 + 常见 UA 示例）
   - `05_crawl_modes.html`：四种爬取模式详解（综合/热度/时间/迭代）+ 对比速查表
   - `06_common_errors.html`：6 类常见错误及解决方法（Cookie 失效、限流、视频不存在等）
   - `07_privacy.html`：隐私说明（本地存储、Cookie 脱敏机制）+ 免责声明
2. **新建 `gui/tabs/help_tab.py`**：帮助教程 Tab 完整实现，包含：
   - 左侧 `QTreeWidget` 目录树，列出 7 个章节，选中即切换右侧内容
   - 右侧 `QTextBrowser` 直接渲染 HTML（无需外部 Markdown 库）
   - 通过 `_load_html()` 读取 `gui/resources/help/` 下的 HTML 文件，文件缺失时显示友好错误页
   - 默认加载第一章节，切换章节时自动滚动到顶部
3. **更新 `gui/main_window.py`**：
   - 导入 `HelpTab`
   - 将 Tab 5（帮助教程）从占位符替换为真实 `HelpTab()` 实例
4. **优化 `gui/tabs/history_tab.py` 空状态**：
   - 在表格区域下方增加 `QLabel` 空状态提示
   - 修改 `_fill_table` 方法，调用 `_update_empty_state()` 控制表格与空标签的可见性
   - 有搜索/筛选条件时显示"未找到匹配的记录"，无过滤条件时显示"暂无记录"

### 关键变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `gui/resources/help/01_quick_start.html` | 新增 | 快速上手帮助文档 |
| `gui/resources/help/02_cookie_chrome.html` | 新增 | Chrome/Edge Cookie 获取文档 |
| `gui/resources/help/03_cookie_firefox.html` | 新增 | Firefox Cookie 获取文档 |
| `gui/resources/help/04_user_agent.html` | 新增 | User-Agent 获取文档 |
| `gui/resources/help/05_crawl_modes.html` | 新增 | 爬取模式说明文档 |
| `gui/resources/help/06_common_errors.html` | 新增 | 常见错误文档 |
| `gui/resources/help/07_privacy.html` | 新增 | 隐私与免责文档 |
| `gui/tabs/help_tab.py` | 新增 | 帮助教程 Tab 完整实现 |
| `gui/main_window.py` | 修改 | 注册 HelpTab，替换占位符 |
| `gui/tabs/history_tab.py` | 修改 | 增加空状态提示（暂无记录 / 未找到匹配的记录） |

### 遇到的问题及解决方案

- `QTextBrowser` 不原生支持 Markdown，因此将帮助文档直接编写为 HTML 格式，无需引入任何外部依赖，兼容性更好。
- 空状态标签与表格采用同一 `QVBoxLayout` 内通过 `setVisible` 互斥切换的方式实现，逻辑简单清晰，避免了 `QStackedWidget` 的额外复杂度。

### 下一步计划（M6）

- PyInstaller onedir 打包配置（.spec 文件）
- 锁定 requirements-lock.txt 版本
- 在干净 Windows 环境中进行烟雾测试

---

## [2026-05-19] M4 阶段：历史记录 Tab

### 执行的任务

1. **新建 `gui/tabs/history_tab.py`**：历史记录 Tab 完整实现，包含：
   - 工具栏：关键词搜索框（BV 号/标题）、状态下拉筛选（全部/成功/失败/已中止/运行中）、类型下拉筛选（全部/爬取/去重/统计）、手动刷新按钮
   - 左侧 `QTableWidget` 列表：时间 / BV号 / 标题（拉伸列）/ 类型 / 模式 / 评论数 / 状态 共 7 列；状态列按颜色区分（绿/红/橙/蓝）；双击行直接打开输出文件夹
   - 右侧 `_DetailPanel` 详情面板：展示选中记录的标题、BV号、UP主、类型、模式、状态（带颜色）、开始/结束时间、评论数、输出目录、错误信息；状态联动启用"打开输出文件夹"（仅当目录存在）和"删除记录"按钮
   - 内存过滤：搜索/筛选变更时在已加载记录中实时过滤，无需重新读文件
   - `refresh()` 公开接口：供外部调用触发重新读取 history.json
2. **更新 `gui/main_window.py`**：
   - 导入 `HistoryTab` 并将 Tab 3 从占位符替换为 `self._history_tab = HistoryTab()`
   - 新增 `_on_tab_changed(index)` 槽：切换到历史记录 Tab（索引 2）时自动调用 `_history_tab.refresh()`，确保每次切换都显示最新数据

### 关键变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `gui/tabs/history_tab.py` | 新增 | 历史记录 Tab 完整实现（约 370 行） |
| `gui/main_window.py` | 修改 | 注册 HistoryTab；添加 Tab 切换自动刷新逻辑 |

### 接口对齐确认

- `history_service.get_all(limit=1000)` 返回按时间倒序排列的记录列表，与 Tab 展示需求一致
- `history_service.delete_task(task_id)` 返回 `bool`，Tab 根据返回值决定是否刷新并给出错误提示
- 记录字段 `stats.comments`、`output_dir`、`start_time`（ISO 8601 字符串）均已正确解析

### 遇到的问题及解决方案

- 删除按钮的回调通过 `set_delete_callback()` 由父 Tab 注入 `_DetailPanel`，避免 `_DetailPanel` 直接持有父类引用，保持解耦。
- 历史记录 Tab 刷新时机：未在 `CrawlTab` 内添加额外信号，而是利用 Tab 切换事件（`currentChanged`）触发刷新，避免修改已稳定的爬取 Tab。

### 下一步计划（M5）

- 实现「帮助教程」Tab：左侧目录树 + 右侧 QTextBrowser 渲染 Markdown 文档
- Cookie 脱敏审计、日志安全审计
- 错误提示统一、空状态/异常状态 UI 优化

---

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

## [2026-05-19] M3 阶段：CSV 去重 Tab

### 执行的任务

1. **新建 `gui/tabs/dedup_tab.py`**：CSV 去重 Tab 完整实现，包含：
   - 输入区：红色警告横幅（强调需使用含 rpid 列的 CSV）、文件 A / 文件 B 选择
   - 输出目录区：默认自动推断为文件 A 同目录下的 `dedup_output` 子目录
   - 控制区：开始去重 / 中止 / 打开输出文件夹三个按钮
   - 进度区：进度条 + 六格统计摘要（文件A/文件B/合并结果/重复评论/A独有/B独有）
   - 日志区：黑色背景 Consolas 日志窗口，运行时锁定输入控件
   - 后台 Worker：`_DedupWorker(QObject)` 在 QThread 中调用 `dedup_service.run_dedup()`
2. **更新 `gui/main_window.py`**：将 Tab 2 从占位替换为 `DedupTab()`，时间统计 Tab 删除，Tab 顺序调整为：评论爬取 / CSV去重 / 历史记录（占位）/ 账号管理 / 帮助教程（占位）
3. **修复日志过滤关键词匹配**（`gui/tabs/crawl_tab.py`）：
   - `"csv中记录的回复数"` → `"中记录的回复数"`（修复大小写不一致问题）
   - `"生成图片：/:"` 两条 → `"楼中楼拖尾图片"`（修复含空格变体未匹配问题）
   - `"[INFO]评论趋势图已生成"` → `"评论趋势图已生成"`（修复 `[INFO]` 后空格问题）
   - 过滤逻辑改为大小写不敏感（`line.lower()` / `kw.lower()`）

### 关键变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `gui/tabs/dedup_tab.py` | 新增 | CSV 去重 Tab 完整实现（约 230 行） |
| `gui/tabs/stats_tab.py` | 删除 | 时间统计 Tab 暂不需要，移除 |
| `gui/main_window.py` | 修改 | 注册 DedupTab；移除 StatsTab；Tab 序号更新 |
| `gui/tabs/crawl_tab.py` | 修改 | 日志过滤关键词修复（大小写 + 空格变体） |

### 遇到的问题及解决方案

- 日志过滤三类消息仍然刷屏：原因是关键词大小写与实际日志不一致（`csv` vs `CSV`）、冒号后空格（`生成图片: ` vs `生成图片：`）、`[INFO]` 后有空格；改用更短的唯一子串并统一转小写匹配解决。
- tip 标签与文件 B 行 grid 行号冲突（均写在第 2 行）导致文字重叠；将 tip 移至第 3 行修复。

### 下一步计划（M4）

- 实现「历史记录」Tab：展示 history.json 中的爬取记录，支持按视频/时间筛选，点击可打开输出文件夹

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
