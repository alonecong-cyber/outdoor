"""通用小工具：时间与 JSON 字段辅助。

时间统一用 naive UTC 存库（SQLite 不带时区），展示层再转时区。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime


def utc_now() -> datetime:
    """当前 UTC 时间（naive，供 SQLite 存储）。"""
    return datetime.now(UTC).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def load_json(raw: str | None, default: object) -> object:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def dump_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
