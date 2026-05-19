# -*- coding: utf-8 -*-
"""
GUI 偏好设置持久化

轻量键值存储，写入项目根目录的 gui_settings.json。
仅存储 GUI 层的用户偏好（如默认输出目录），不存储账号或 Cookie 等敏感信息。
"""

import json
import os

_SETTINGS_PATH = "gui_settings.json"


def _load() -> dict:
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(settings: dict) -> None:
    tmp = _SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _SETTINGS_PATH)


def get(key: str, default=None):
    """读取一个设置项。"""
    return _load().get(key, default)


def set(key: str, value) -> None:
    """写入一个设置项（原子写入）。"""
    s = _load()
    s[key] = value
    _save(s)
