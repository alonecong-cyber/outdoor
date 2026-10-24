"""采集器基础设施：统一 RawListing 产出、指数退避、限速。

原则（AGENTS.md 约束）：解析顺序 API → JSON-LD → CSS；失败退避重试；
禁止绕过登录、验证码和风控——遇到风控就降级为人工，不做对抗。
"""

from __future__ import annotations

import os
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable

import httpx

from app.models import RawListing


def make_http_client(**kwargs) -> httpx.Client:
    """构造 httpx.Client，容忍 no_proxy 里的带括号 IPv6 字面量。

    httpx 0.28 解析 no_proxy 含 "[::1]" 之类条目时抛 InvalidURL
    （本机 Clash 等代理工具的常见写法）。构造失败时清理这类条目重试；
    只影响本地 IPv6 直连的豁免，代理本身不受影响。
    """
    try:
        return httpx.Client(**kwargs)
    except httpx.InvalidURL:
        for var in ("no_proxy", "NO_PROXY"):
            val = os.environ.get(var)
            if val and "[" in val:
                os.environ[var] = ",".join(p for p in val.split(",") if "[" not in p)
        return httpx.Client(**kwargs)


class CollectorError(Exception):
    """采集失败（重试耗尽 / 解析失败），应记录并降级，不允许静默吞掉。"""


class CredentialsMissing(CollectorError):
    """联盟 API 密钥未配置。采集器只读环境变量，不硬编码。"""


def fetch_with_backoff(
    fetch,
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    sleep=time.sleep,
    jitter: float = 0.5,
) -> object:
    """指数退避 + 抖动的抓取包装。fetch() 抛异常则重试，耗尽抛 CollectorError。"""
    delay = base_delay
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fetch()
        except Exception as e:  # noqa: BLE001 - 网络层异常种类多，统一退避
            last_exc = e
            if attempt >= max_retries:
                break
            actual = delay * (1 + random.uniform(0, jitter))
            sleep(actual)
            delay = min(delay * 2, max_delay)
    raise CollectorError(f"重试 {max_retries} 次后仍失败: {last_exc}") from last_exc


class BaseCollector(ABC):
    """采集器接口：collect() 返回统一 RawListing 列表。"""

    channel_slug: str = ""

    @abstractmethod
    def collect(self) -> Iterable[RawListing]: ...
