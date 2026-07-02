"""自选股监控 —— 定时分析 + 信号变化推送。

存储: data/watchlist.json
每个用户独立的监控列表，定时跑 TradingGraph.analyze()，
建议变化时推送通知。
"""
from __future__ import annotations
import asyncio
import json
import os
import time
from typing import Any

_WATCHLIST_FILE = None  # 延迟初始化


def _get_path(plugin_dir: str) -> str:
    global _WATCHLIST_FILE
    if not _WATCHLIST_FILE:
        data_dir = os.path.join(plugin_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        _WATCHLIST_FILE = os.path.join(data_dir, "watchlist.json")
    return _WATCHLIST_FILE


def _load(plugin_dir: str) -> dict:
    path = _get_path(plugin_dir)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}}


def _save(plugin_dir: str, data: dict):
    with open(_get_path(plugin_dir), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---- 公开接口 ----

def add_stock(plugin_dir: str, user_id: str, code: str) -> bool:
    """添加自选股，返回 True 表示新增成功。"""
    data = _load(plugin_dir)
    user = data["users"].setdefault(user_id, {"stocks": [], "history": {}})
    if code not in user["stocks"]:
        user["stocks"].append(code)
        _save(plugin_dir, data)
        return True
    return False


def remove_stock(plugin_dir: str, user_id: str, code: str) -> bool:
    """删除自选股。"""
    data = _load(plugin_dir)
    user = data["users"].get(user_id)
    if not user or code not in user["stocks"]:
        return False
    user["stocks"].remove(code)
    _save(plugin_dir, data)
    return True


def list_stocks(plugin_dir: str, user_id: str) -> list[str]:
    """列出用户的自选股。"""
    data = _load(plugin_dir)
    return data["users"].get(user_id, {}).get("stocks", [])


def get_last_verdict(plugin_dir: str, user_id: str, code: str) -> str:
    """获取上次分析结论。"""
    data = _load(plugin_dir)
    return (
        data.get("users", {})
        .get(user_id, {})
        .get("history", {})
        .get(code, {})
        .get("verdict", "")
    )


def update_history(plugin_dir: str, user_id: str, code: str, verdict: str):
    """更新分析历史。"""
    data = _load(plugin_dir)
    h = (
        data.setdefault("users", {})
        .setdefault(user_id, {})
        .setdefault("history", {})
        .setdefault(code, {})
    )
    h["verdict"] = verdict
    h["ts"] = time.time()
    _save(plugin_dir, data)


def get_all_watch_entries(plugin_dir: str) -> list[dict]:
    """获取所有监控条目 [{user_id, code, last_verdict}]"""
    data = _load(plugin_dir)
    entries = []
    for uid, uconf in data.get("users", {}).items():
        for code in uconf.get("stocks", []):
            entries.append({
                "user_id": uid,
                "code": code,
                "last_verdict": uconf.get("history", {}).get(code, {}).get("verdict", ""),
            })
    return entries
