"""凑单：0-1 背包 DP。

满 N 减 M 差一点时，从候选凑单品里找"总金额刚好超过门槛、多花最少"的组合，
按金额（分）做 DP。dp[j] = 达到"至少 j 分"所需的最少花费，j 封顶在门槛 T。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_THRESHOLD_CENTS = 5_000_000  # 5 万元门槛：DP 数组保护上限


@dataclass(frozen=True)
class FillerItem:
    id: str
    name: str
    price_cents: int


def best_filler(
    threshold_cents: int,
    items: list[FillerItem],
) -> list[FillerItem] | None:
    """返回"合计 ≥ threshold 且多花最少"的凑单组合；items 为空或门槛 ≤0 返回 []。

    返回 None 表示给不出合法组合（所有候选加起来也够不到门槛）。
    """
    if threshold_cents <= 0:
        return []
    if not items:
        return None
    if threshold_cents > MAX_THRESHOLD_CENTS:
        raise ValueError(f"门槛 {threshold_cents} 分超过 DP 上限 {MAX_THRESHOLD_CENTS}")

    t = threshold_cents
    inf = float("inf")
    # dp[j] = (最少花费, 选中物品的位掩码)；j 被 clamp 到 t
    dp: list[tuple[float, int]] = [(inf, 0)] * (t + 1)
    dp[0] = (0.0, 0)

    for i, item in enumerate(items):
        bit = 1 << i
        price = item.price_cents
        if price <= 0:
            continue
        for j in range(t, -1, -1):
            cost, mask = dp[j]
            if cost == inf or mask & bit:
                continue
            nj = min(t, j + price)
            ncost = cost + price
            if ncost < dp[nj][0]:
                dp[nj] = (ncost, mask | bit)

    cost, mask = dp[t]
    if cost == inf:
        return None
    return [items[i] for i in range(len(items)) if mask >> i & 1]
