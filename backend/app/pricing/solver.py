"""单品单渠道求解：枚举优惠子集，取最低到手价。

单渠道可用优惠通常 ≤12 个，2^12=4096 种子集；过滤互斥组合后按顺序计算。
"""

from __future__ import annotations

from itertools import combinations

from app.pricing.engine import AppliedResult, apply_promos
from app.pricing.rules import Promo

MAX_ENUM_PROMOS = 20  # 2^20 ≈ 100 万，再大就该上 CP-SAT 了


def _exclusive_ok(chosen: list[Promo]) -> bool:
    seen: set[str] = set()
    for p in chosen:
        if p.exclusive_group:
            if p.exclusive_group in seen:
                return False
            seen.add(p.exclusive_group)
    return True


def all_combinations(base_cents: int, promos: list[Promo]) -> list[AppliedResult]:
    """枚举全部合法子集（含空集 = 不用优惠）的计算结果，供展示与测试。"""
    if len(promos) > MAX_ENUM_PROMOS:
        raise ValueError(f"优惠数 {len(promos)} 超过枚举上限 {MAX_ENUM_PROMOS}，请改用 CP-SAT")
    results = [apply_promos(base_cents, [])]  # 空集：什么优惠都不用
    for r in range(1, len(promos) + 1):
        for combo in combinations(promos, r):
            if _exclusive_ok(list(combo)):
                results.append(apply_promos(base_cents, list(combo)))
    return results


def best_combination(base_cents: int, promos: list[Promo]) -> AppliedResult:
    """最低到手价（effective = 当下实付 − 返利），并列时取当下实付更低者。"""
    results = all_combinations(base_cents, promos)
    return min(results, key=lambda r: (r.effective_cents, r.paid_now_cents))
