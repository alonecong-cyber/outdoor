"""Shopify 零售商采集：/collections/<handle>/products.json（evo.com 等站）。

- 这些站点 robots.txt 明确「公开商品页可爬」，products.json 是 Shopify 官方接口；
- 每个变体（颜色×尺码）一条 RawListing：price 为现价，compare_at_price 为原价；
- 零售商商品没有品牌原厂款号，style_number_hint 留空，
  由 ingestion 按「品牌+款式名 token 集合精确相等」并入已有款式，缺则转人工。
"""

from __future__ import annotations

from collections.abc import Iterable

import httpx

from app.collectors.base import make_http_client
from app.models import RawListing
from app.util import utc_now


def _cents(value) -> int:
    if value in (None, ""):
        return 0
    return int(round(float(value) * 100))


def _variant_image(variant: dict, product: dict) -> str:
    img = variant.get("featured_image") or {}
    src = img.get("src") or ""
    if not src:
        top = product.get("image") or {}
        src = top.get("src") or ""
    if not src:
        gallery = product.get("images") or []
        if gallery:
            src = gallery[0].get("src") or ""
    return str(src)


def parse_products_json(
    payload: dict, *, channel_slug: str, base_url: str
) -> list[RawListing]:
    """Shopify products.json 载荷 → 每个在售/有价变体一条 RawListing。"""
    out: list[RawListing] = []
    handle = ""
    for product in payload.get("products", []):
        handle = str(product.get("handle") or "")
        vendor = str(product.get("vendor") or "")
        title = str(product.get("title") or "").strip()
        product_url = f"{base_url.rstrip('/')}/products/{handle}"
        options = [str(o.get("name") or "").lower() for o in product.get("options", [])]
        for variant in product.get("variants", []):
            price_cents = _cents(variant.get("price"))
            if price_cents <= 0:
                continue
            # option1/option2 按 options 名称解释；默认 Shopify 约定 Color / Size。
            color = str(variant.get("option1") or "").strip()
            size = str(variant.get("option2") or "").strip()
            if len(options) >= 2 and "color" in options[1]:
                color, size = size, color
            out.append(
                RawListing(
                    source="shopify",
                    channel_slug=channel_slug,
                    external_id=str(variant.get("id") or f"{handle}:{color}:{size}"),
                    url=product_url,
                    title=title,
                    image=_variant_image(variant, product),
                    brand_hint=vendor,
                    style_number_hint="",
                    color_hint=color,
                    size_hint=size,
                    price_cents=price_cents,
                    list_price_cents=_cents(variant.get("compare_at_price")) or price_cents,
                    currency="USD",
                    in_stock=bool(variant.get("available")),
                    coupons=[],
                    collected_at=utc_now(),
                )
            )
    return out


class ShopifyCollector:
    """Shopify 商品接口采集器。targets 为 (channel_slug, products_json_url)。"""

    channel_slug = ""

    def __init__(self, targets: list[tuple[str, str]]) -> None:
        self.targets = targets

    def collect(
        self, client: httpx.Client | None = None, *, max_pages: int = 3
    ) -> Iterable[RawListing]:
        client = client or make_http_client(timeout=30, follow_redirects=True)
        for channel_slug, url in self.targets:
            base_url = url.split("/collections/")[0]
            separator = "&" if "?" in url else "?"
            for page in range(1, max_pages + 1):
                try:
                    resp = client.get(f"{url}{separator}limit=250&page={page}")
                    resp.raise_for_status()
                    payload = resp.json()
                except (httpx.HTTPError, ValueError):
                    break  # 单个 URL/页失败不拖垮整批
                raws = parse_products_json(payload, channel_slug=channel_slug, base_url=base_url)
                if not raws:
                    break
                yield from raws
                if len(payload.get("products", [])) < 250:
                    break


def discounted_deal_drafts(
    raws: Iterable[RawListing],
) -> list[tuple[object, list[RawListing]]]:
    """在售且有折扣的变体按商品聚合为 (DealDraft, 变体列表)。

    一个商品一条线报：price = 该商品在售变体最低现价，summary 标注原价与
    折扣幅度；source = 渠道 slug（evo_us / gearx_us…），source_id = 商品 handle。
    """
    from app.models import DealDraft

    by_product: dict[tuple[str, str, str], list[RawListing]] = {}
    for raw in raws:
        if raw.in_stock and 0 < raw.price_cents < raw.list_price_cents:
            by_product.setdefault((raw.channel_slug, raw.url, raw.title), []).append(raw)
    drafts: list[tuple[DealDraft, list[RawListing]]] = []
    now = utc_now()
    for (channel_slug, url, title), variants in by_product.items():
        best = min(variants, key=lambda r: r.price_cents)
        discount = round((1 - best.price_cents / best.list_price_cents) * 100)
        store = url.split("/")[2].removeprefix("www.") if "//" in url else channel_slug
        summary = (
            f"原价 ${best.list_price_cents / 100:.2f} → 现价 ${best.price_cents / 100:.2f}"
            f"（约 -{discount}%，{len(variants)} 个规格在售）"
        )
        drafts.append(
            (
                DealDraft(
                    source=channel_slug,
                    source_id=url.rsplit("/", 1)[-1],
                    url=url,
                    title=title,
                    summary=summary,
                    price_cents=best.price_cents,
                    currency="USD",
                    channel=store,
                    image=best.image,
                    tags=["美国零售", store],
                    published_at=now,
                    checked_at=now,
                ),
                variants,
            )
        )
    return drafts


def ingest_discount_deals(session, raws: Iterable[RawListing]) -> dict:
    """折扣线报落库：先款式名精确匹配挂变体，并不上再用标题哈希聚档。"""
    from app.deals import grow_variant, save_deal
    from app.ingestion import resolve_variant

    saved = created = matched = 0
    for draft, variants in discounted_deal_drafts(raws):
        deal, is_new = save_deal(session, draft, grow_catalog=False)  # type: ignore[arg-type]
        vid = None
        for raw in variants:
            vid = resolve_variant(session, raw, auto_only=True)
            if vid:
                break
        if vid is None:
            vid = grow_variant(session, draft.title)  # type: ignore[attr-defined]
        deal.matched_variant_id = vid  # type: ignore[attr-defined]
        session.add(deal)
        session.flush()
        saved += 1
        created += int(is_new)
        matched += int(vid is not None)
    session.commit()
    return {"saved": saved, "created": created, "matched": matched}
