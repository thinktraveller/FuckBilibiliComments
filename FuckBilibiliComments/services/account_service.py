# -*- coding: utf-8 -*-
"""
账号服务层

提供账号的 CRUD、有效性检测等操作，封装对 config.json 的读写。
GUI 和 CLI 均通过此模块操作账号配置，禁止直接读写 config.json。

注意：
    - 所有写操作使用"读 -> 内存改 -> 原子写"策略（先写 .tmp，再 os.replace）
    - 脱敏展示：get_accounts_masked() 返回 Cookie 已脱敏的账号列表
"""

import json
import os
import re
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

# config.json 路径：相对于工作目录（项目根目录）
_CONFIG_PATH = "config.json"


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _load_raw() -> dict:
    """读取并返回 config.json 的原始字典；文件不存在时返回空结构。"""
    if not os.path.exists(_CONFIG_PATH):
        return {"accounts": [], "selected_account_index": 0}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容旧格式
        if "cookie" in data and "accounts" not in data:
            old_cookie = data.get("cookie", "")
            old_ua = data.get("user_agent", "")
            data = {
                "accounts": [{"name": "默认账号", "cookie": old_cookie, "user_agent": old_ua}] if old_cookie else [],
                "selected_account_index": 0,
            }
        data.setdefault("accounts", [])
        data.setdefault("selected_account_index", 0)
        return data
    except (json.JSONDecodeError, IOError):
        return {"accounts": [], "selected_account_index": 0}


def _save_raw(data: dict) -> None:
    """原子写入 config.json（先写 .tmp，再 os.replace）。"""
    tmp = _CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, _CONFIG_PATH)


def _mask_cookie(cookie: str) -> str:
    """将 Cookie 字符串脱敏，仅保留 SESSDATA 前 8 后 4 字符，其余字段省略。"""
    match = re.search(r"SESSDATA=([^;]+)", cookie)
    if match:
        val = match.group(1)
        if len(val) > 12:
            masked_val = val[:8] + "..." + val[-4:]
        else:
            masked_val = val[:4] + "..."
        return f"SESSDATA={masked_val}"
    return "（未包含 SESSDATA）"


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def get_accounts() -> list:
    """
    返回完整账号列表（含完整 Cookie，内部使用）。

    Returns:
        list[dict]: 每项包含 name / cookie / user_agent
    """
    return _load_raw().get("accounts", [])


def get_accounts_masked() -> list:
    """
    返回脱敏后的账号列表（用于 GUI 展示）。

    Returns:
        list[dict]: 每项包含 name / cookie_masked / user_agent / index
    """
    accounts = get_accounts()
    result = []
    for i, acc in enumerate(accounts):
        result.append({
            "index": i,
            "name": acc.get("name", ""),
            "cookie_masked": _mask_cookie(acc.get("cookie", "")),
            "user_agent": acc.get("user_agent", ""),
        })
    return result


def get_selected_index() -> int:
    """返回当前选中的账号索引。"""
    return _load_raw().get("selected_account_index", 0)


def get_selected_account() -> Optional[dict]:
    """
    返回当前选中账号的完整配置。

    Returns:
        dict | None: 包含 cookie / user_agent；无账号时返回 None
    """
    data = _load_raw()
    accounts = data.get("accounts", [])
    idx = data.get("selected_account_index", 0)
    if not accounts:
        return None
    idx = max(0, min(idx, len(accounts) - 1))
    return accounts[idx]


def add_account(name: str, cookie: str, user_agent: str) -> dict:
    """
    新增一个账号。

    Args:
        name:       账号名称，不允许与已有账号重名
        cookie:     完整 Cookie 字符串
        user_agent: User-Agent 字符串

    Returns:
        dict: 新建的账号配置

    Raises:
        ValueError: 账号名已存在或参数非法
    """
    if not name.strip():
        raise ValueError("账号名称不能为空")
    if not cookie.strip():
        raise ValueError("Cookie 不能为空")

    data = _load_raw()
    existing_names = [a["name"] for a in data["accounts"]]
    if name in existing_names:
        raise ValueError(f"账号名称 '{name}' 已存在")

    account = {"name": name, "cookie": cookie.strip(), "user_agent": user_agent.strip()}
    data["accounts"].append(account)
    _save_raw(data)
    return account


def update_account(index: int, name: str, cookie: str, user_agent: str) -> dict:
    """
    更新指定索引的账号配置。

    Args:
        index:      账号索引（0-based）
        name:       新账号名
        cookie:     新 Cookie
        user_agent: 新 User-Agent

    Returns:
        dict: 更新后的账号配置

    Raises:
        IndexError: 索引越界
        ValueError: 名称与其他账号重复
    """
    data = _load_raw()
    accounts = data["accounts"]

    if index < 0 or index >= len(accounts):
        raise IndexError(f"账号索引 {index} 超出范围（共 {len(accounts)} 个账号）")

    # 检查名称冲突（允许同名更新自身）
    for i, acc in enumerate(accounts):
        if acc["name"] == name and i != index:
            raise ValueError(f"账号名称 '{name}' 已被其他账号使用")

    accounts[index] = {"name": name, "cookie": cookie.strip(), "user_agent": user_agent.strip()}
    _save_raw(data)
    return accounts[index]


def delete_account(index: int) -> None:
    """
    删除指定索引的账号。

    Args:
        index: 账号索引（0-based）

    Raises:
        IndexError: 索引越界
    """
    data = _load_raw()
    accounts = data["accounts"]

    if index < 0 or index >= len(accounts):
        raise IndexError(f"账号索引 {index} 超出范围")

    accounts.pop(index)

    # 修正 selected_account_index
    sel = data.get("selected_account_index", 0)
    if sel >= len(accounts):
        data["selected_account_index"] = max(0, len(accounts) - 1)

    _save_raw(data)


def set_selected(index: int) -> None:
    """
    设置当前选中账号。

    Args:
        index: 账号索引（0-based）

    Raises:
        IndexError: 索引越界
    """
    data = _load_raw()
    if index < 0 or index >= len(data["accounts"]):
        raise IndexError(f"账号索引 {index} 超出范围")
    data["selected_account_index"] = index
    _save_raw(data)


def validate_account(cookie: str, user_agent: str) -> dict:
    """
    验证 Cookie 是否有效，调用 B 站个人信息接口。

    Args:
        cookie:     Cookie 字符串
        user_agent: User-Agent 字符串

    Returns:
        dict: {
            "valid": bool,
            "uid": str | None,
            "uname": str | None,
            "message": str
        }
    """
    if requests is None:
        return {"valid": False, "uid": None, "uname": None, "message": "requests 未安装"}

    url = "https://api.bilibili.com/x/web-interface/nav"
    headers = {
        "Cookie": cookie,
        "User-Agent": user_agent,
        "Referer": "https://www.bilibili.com",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            user_data = data.get("data", {})
            return {
                "valid": True,
                "uid": str(user_data.get("mid", "")),
                "uname": user_data.get("uname", ""),
                "message": f"登录有效，UID={user_data.get('mid')}，昵称={user_data.get('uname')}",
            }
        else:
            return {
                "valid": False,
                "uid": None,
                "uname": None,
                "message": f"Cookie 无效：{data.get('message', '未知错误')}（code={data.get('code')}）",
            }
    except requests.Timeout:
        return {"valid": False, "uid": None, "uname": None, "message": "请求超时，请检查网络"}
    except Exception as e:
        return {"valid": False, "uid": None, "uname": None, "message": f"请求失败：{e}"}


def switch_to_next_account() -> Optional[dict]:
    """
    切换到下一个账号（封禁时自动调用）。

    Returns:
        dict | None: 新账号的 {cookie, user_agent}；无可用账号时返回 None
    """
    data = _load_raw()
    accounts = data.get("accounts", [])
    if len(accounts) <= 1:
        return None

    current = data.get("selected_account_index", 0)
    next_idx = (current + 1) % len(accounts)
    data["selected_account_index"] = next_idx
    _save_raw(data)

    acc = accounts[next_idx]
    return {"cookie": acc["cookie"], "user_agent": acc["user_agent"]}
