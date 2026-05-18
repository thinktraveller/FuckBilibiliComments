# -*- coding: utf-8 -*-
"""
应用服务层（Services Layer）

该层介于 GUI/CLI 入口层与核心业务层之间，负责：
- 流程编排（组合多个核心业务调用）
- 回调注入（将 TaskCallbacks 传入业务函数）
- 状态管理（任务注册、历史记录读写）

各子模块：
    crawl_service.py    爬取流程编排
    stats_service.py    时间统计流程编排
    dedup_service.py    CSV 去重流程编排
    account_service.py  账号 CRUD 与有效性检测
    history_service.py  历史记录读写
    task_manager.py     任务注册与查询
"""
