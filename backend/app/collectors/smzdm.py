"""smzdm 好价线报采集：sitemap 增量发现 → 详情页解析（robots 合规路径）。

依据实测（2026-10-24）：
- robots.txt 允许 /p/<id>/ 详情页，禁止列表组合 /p/*/p*/、/*?* 查询串、/baoliao/；
- /p/1 列表页已 JS 化不可直接抓；
- sitemap https://www.smzdm.com/sitemap/smzdm_youhui.xml（robots 公开声明）每日
  生成，含 50000 条 /p/<id>/，最新线报 ID 递增——记录 max_seen_id 即可增量发现；
- 详情页服务端渲染：og:title = "标题 价格元_渠道优惠促销_报价_多少钱-什么值得买"，
  正文含发布时间（北京时间）与 og:image。

频率纪律：同 host 请求间隔 ≥10s（HostRateLimiter），单轮详情页数量有上限。
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.collectors.base import fetch_with_backoff, make_http_client
from app.collectors.web_product import USER_AGENT, HostRateLimiter
from app.models import DealDraft

SMZDM_HOST = "www.smzdm.com"
SITEMAP_URL = f"https://{SMZDM_HOST}/sitemap/smzdm_youhui.xml"
CATEGORY_BASE = f"https://{SMZDM_HOST}/fenlei/{{slug}}/"
# 户外定向品类页（robots 允许 /fenlei/；全站 sitemap 是全品类，户外会被稀释）
CATEGORY_SLUGS = [
    "chongfengyi",
    "chongfengku",
    "dengshanxie",
    "tubuxie",
    "yueyepaoxie",
    # 2026-10 扩品类（官方 /fenlei/ 目录核对过的有效 slug）：铺宽搜索语料
    "huwaifushi",  # 户外服饰（品类大入口）
    "yurongyiku",  # 户外羽绒衣裤
    "zhuarongyiku",  # 抓绒衣裤
    "suganyiku",  # 速干衣裤
    "pifuyi",  # 皮肤衣
    "huwaimianfu",  # 户外棉服
    "yundongjiake",  # 运动夹克
    "yundongyurongfu",  # 运动羽绒服
    "paobuxie",  # 跑鞋
    "huaxuefu",  # 滑雪服
]
MAX_DETAILS_PER_RUN = 20

SMZDM_TZ = timezone(timedelta(hours=8))  # 发布时间是北京时间，统一转 naive UTC

DEAL_URL_RE = re.compile(r"^https://www\.smzdm\.com/p/(\d+)/$")
LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>")
# 品类页线报卡片链接；正文 JSON 里也出现同款 URL，parse 时去重
CATEGORY_LINK_RE = re.compile(r'href="(https://www\.smzdm\.com/p/(\d+)/)"')
OG_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)"')
OG_IMAGE_RE = re.compile(r'<meta property="og:image" content="([^"]*)"')
OG_DESC_RE = re.compile(r'<meta property="og:description" content="([^"]*)"')
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
PUB_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
TAG_RE = re.compile(r"[\s　]+")

# 价格尾巴：标题段末尾的 "100元" / "9.9 元"，元后可带 "（需用券）" / "返200积分(后)" 尾注
PRICE_TAIL_RE = re.compile(
    r"^(.*?)[\s　]*(\d+(?:\.\d+)?)\s*元"
    r"(?:\s*(?:[（(][^（）()]*[)）]|返\d+积分(?:后)?|补贴))?$"
)
# 渠道段："京东优惠促销"
MALL_SEG_RE = re.compile(r"(.{2,14}?)优惠促销")

# 渠道词典（长词优先）：fallback 扫描整个 og:title
MALL_WORDS = [
    "亚马逊海外购", "京东国际", "京东自营", "京东", "天猫超市", "天猫", "淘宝直播",
    "淘宝", "拼多多", "抖音商城", "亚马逊", "海外购", "唯品会", "苏宁", "考拉",
    "得物", "美团", "闲鱼", "飞猪", "官网", "微信小程序",
]

# 详情页「结构化」区：购买渠道 + 特征（自营 / 商品好评率NN% / 旗舰店…）
STRUCT_BOX_RE = re.compile(
    r'<div class="structuration-box">.*?<span>([^<]{2,12})</span>'
    r"((?:\s*<span class=\"featrue\">[^<]*</span>)*)",
    re.S,
)
FEATRUE_RE = re.compile(r'<span class="featrue">([^<]*)</span>')


def parse_sitemap(xml_text: str) -> list[tuple[str, int]]:
    """sitemap → [(url, 文章ID)]，只收 /p/<id>/ 详情页。"""
    out: list[tuple[str, int]] = []
    for loc in LOC_RE.findall(xml_text):
        m = DEAL_URL_RE.match(loc.strip())
        if m:
            out.append((loc.strip(), int(m.group(1))))
    return out


def parse_category_page(html: str) -> list[tuple[str, int]]:
    """品类页 → [(url, 文章ID)]，按出现顺序去重。"""
    out: list[tuple[str, int]] = []
    seen: set[int] = set()
    for url, sid in CATEGORY_LINK_RE.findall(html):
        i = int(sid)
        if i not in seen:
            seen.add(i)
            out.append((url, i))
    return out


# 列表卡片锚点：每张折扣卡必有商品图；指南/资讯卡没有 → 天然过滤
CARD_IMG_RE = re.compile(
    r'<a href="(https://www\.smzdm\.com/p/(\d+)/)"[^>]*>\s*'
    r'<img class="product-img" src="([^"]+)"'
)
CARD_TITLE_RE = re.compile(
    r'class="[^"]*title-normal-box[^"]*"[^>]*>(.*?)</a>', re.S
)
CARD_SUBTITLE_RE = re.compile(
    r'class="[^"]*sub-title-box[^"]*"[^>]*>(.*?)</a>', re.S
)
CARD_CONTENT_RE = re.compile(
    r'class="[^"]*content-normal-box[^"]*"[^>]*>(.*?)(?:</div>|</span>)', re.S
)
CARD_TAG_RE = re.compile(r'<a class="tags-item[^>]*>(?:<!---->)?\s*([^<]{2,24}?)\s*</a>')
DIRECTLINK_RE = re.compile(r'directlink="([^"]+)"')

# directlink 商家域名 → 渠道名（长词优先，逐一子串匹配）
MALL_HOSTS: list[tuple[str, str]] = [
    ("jd.com", "京东"),
    ("tmall.com", "天猫"),
    ("taobao.com", "淘宝"),
    ("pinduoduo.com", "拼多多"),
    ("yangkeduo.com", "拼多多"),
    ("suning.com", "苏宁"),
    ("vip.com", "唯品会"),
    ("dewu.com", "得物"),
    ("douyin.com", "抖音商城"),
    ("amazon.", "亚马逊"),
    ("kaola.com", "考拉"),
    ("mi.com", "小米有品"),
    ("fliggy.com", "飞猪"),
]


def _mall_from_url(url: str) -> str:
    host = url.split("//", 1)[-1].lower()
    for fragment, mall in MALL_HOSTS:
        if fragment in host:
            return mall
    return ""


def parse_category_cards(html: str) -> list[DealDraft]:
    """品类列表页 → 摘要 DealDraft 列表（不发详情请求）。

    卡片边界用 product-img 锚点切分：directlink 在锚点前 ~600 字符内，
    标题/价格副标/简介/标签在锚点之后。没有价格副标的卡（指南/资讯）跳过。
    """
    anchors = list(CARD_IMG_RE.finditer(html))
    drafts: list[DealDraft] = []
    seen: set[int] = set()
    for idx, m in enumerate(anchors):
        deal_id = int(m.group(2))
        if deal_id in seen:
            continue
        seen.add(deal_id)
        block_start = m.start()
        # directlink 归属当前卡：取锚点前最近的一个（≤600 字符）
        window = html[max(0, block_start - 600) : block_start]
        links = DIRECTLINK_RE.findall(window)
        directlink = links[-1].strip() if links else ""
        block_end = anchors[idx + 1].start() if idx + 1 < len(anchors) else len(html)
        block = html[m.end() : block_end]

        title_m = CARD_TITLE_RE.search(block)
        title = _strip_tags(title_m.group(1)) if title_m else ""
        if not title:
            continue
        price_cents = 0
        sub_m = CARD_SUBTITLE_RE.search(block)
        if not sub_m:
            continue  # 无价格副标：指南/资讯卡，不进线报流
        subtitle = _strip_tags(sub_m.group(1))
        pm = PRICE_TAIL_RE.match(subtitle)
        if not pm:
            continue  # 副标不是价格形态（如“免费领取”类），宁缺毋滥
        price_cents = int(
            (Decimal(pm.group(2)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        content_m = CARD_CONTENT_RE.search(block)
        summary = _strip_tags(content_m.group(1))[:200] if content_m else ""
        tags = [t.strip() for t in CARD_TAG_RE.findall(block) if t.strip()]
        image = m.group(3).strip()
        if image.startswith("//"):
            image = "https:" + image

        drafts.append(
            DealDraft(
                source="smzdm",
                source_id=str(deal_id),
                url=f"https://www.smzdm.com/p/{deal_id}/",
                title=title,
                summary=summary,
                price_cents=price_cents,
                currency="CNY",
                channel=_mall_from_url(directlink),
                image=image,
                tags=tags,
            )
        )
    return drafts


def parse_og_title(og: str) -> tuple[str, int, str]:
    """og:title → (标题, 价格分, 渠道)。

    实测格式："蒂佳婷 蓝色药丸补水面膜 5片 100元_京东优惠促销_报价_多少钱-什么值得买"
    价格缺失（免费送/信息型线报）时价格记 0。
    """
    s = og.strip()
    for suffix in ("-什么值得买", "什么值得买"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    parts = [p.strip() for p in s.split("_") if p.strip()]
    head = parts[0] if parts else s
    title, price_cents = head, 0
    m = PRICE_TAIL_RE.match(head)
    if m:
        title = m.group(1).strip()
        price_cents = int(
            (Decimal(m.group(2)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

    channel = ""
    if len(parts) > 1:
        m2 = MALL_SEG_RE.match(parts[1])
        if m2:
            channel = m2.group(1).strip()
    if not channel:
        for word in MALL_WORDS:
            if word in s:
                channel = word
                break
    return title, price_cents, channel


def _strip_tags(fragment: str) -> str:
    return TAG_RE.sub(" ", re.sub(r"<[^>]+>", " ", fragment)).strip()


def parse_deal_page(html: str, url: str) -> DealDraft:
    """详情页 HTML → DealDraft。og:title 优先，h1 兜底。"""
    deal_id = ""
    m = DEAL_URL_RE.match(url.strip())
    if m:
        deal_id = m.group(1)

    og = OG_TITLE_RE.search(html)
    if og:
        title, price_cents, channel = parse_og_title(og.group(1))
    else:
        h1 = H1_RE.search(html)
        title, price_cents, channel = (_strip_tags(h1.group(1)) if h1 else url), 0, ""
        for word in MALL_WORDS:
            if word in html:
                channel = word
                break

    image = ""
    og_img = OG_IMAGE_RE.search(html)
    if og_img:
        image = og_img.group(1).strip()
        if image.startswith("//"):
            image = "https:" + image

    summary = ""
    og_desc = OG_DESC_RE.search(html)
    if og_desc:
        summary = _strip_tags(og_desc.group(1)).strip()

    published_at = None
    t = PUB_TIME_RE.search(html)
    if t:
        published_at = (
            datetime.strptime(t.group(1), "%Y-%m-%d %H:%M")
            .replace(tzinfo=SMZDM_TZ)
            .astimezone(UTC)
            .replace(tzinfo=None)
        )

    # 结构化区：渠道与特征（自营 / 好评率）比 og:title 推断更准，优先采用
    tags: list[str] = []
    sb = STRUCT_BOX_RE.search(html)
    if sb:
        mall = sb.group(1).strip()
        feats = [f.strip() for f in FEATRUE_RE.findall(sb.group(2)) if f.strip()]
        if mall:
            channel = f"{mall}自营" if "自营" in feats else mall
        tags = [f for f in feats if f != "自营"]

    return DealDraft(
        source="smzdm",
        source_id=deal_id or url,
        url=url,
        title=title or url,
        summary=summary,
        price_cents=price_cents,
        currency="CNY",
        channel=channel,
        image=image,
        tags=tags,
        published_at=published_at,
    )


class SmzdmFeedCollector:
    """好价线报流采集器。collect(since_id) 只抓比 since_id 新的详情页。"""

    channel_slug = "smzdm"

    def __init__(
        self,
        *,
        client=None,
        rate_limiter: HostRateLimiter | None = None,
        sleep=time.sleep,
        max_details_per_run: int = MAX_DETAILS_PER_RUN,
        sitemap_url: str = SITEMAP_URL,
    ):
        self.client = client or make_http_client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
            follow_redirects=True,
            timeout=30.0,
        )
        self.rate_limiter = rate_limiter or HostRateLimiter()
        self.sleep = sleep
        self.max_details_per_run = max_details_per_run
        self.sitemap_url = sitemap_url
        self._owns_client = client is None

    def fetch_sitemap(self) -> list[tuple[str, int]]:
        self.rate_limiter.wait(SMZDM_HOST)
        resp = fetch_with_backoff(lambda: self.client.get(self.sitemap_url), sleep=self.sleep)
        resp.raise_for_status()
        return parse_sitemap(resp.text)

    def fetch_page(self, url: str) -> str:
        """抓单个详情页（限速），返回 HTML。"""
        self.rate_limiter.wait(SMZDM_HOST)
        resp = fetch_with_backoff(lambda: self.client.get(url), sleep=self.sleep)
        resp.raise_for_status()
        return resp.text

    def collect(self, since_id: int = 0, *, limit: int | None = None) -> list[DealDraft]:
        """sitemap 模式（全品类兜底）：发现比 since_id 新的线报并抓详情页。"""
        entries = self.fetch_sitemap()
        fresh = [(u, i) for u, i in entries if i > since_id]
        fresh.sort(key=lambda x: -x[1])  # 最新优先
        cap = limit if limit is not None else self.max_details_per_run
        drafts: list[DealDraft] = []
        for url, _deal_id in fresh[:cap]:
            try:
                self.rate_limiter.wait(SMZDM_HOST)
                resp = fetch_with_backoff(lambda u=url: self.client.get(u), sleep=self.sleep)
                resp.raise_for_status()
                drafts.append(parse_deal_page(resp.text, url))
            except Exception:  # noqa: BLE001 - 线报流容错：单条失败继续
                continue
        return drafts

    def collect_categories(
        self,
        slugs: list[str] | None = None,
        *,
        exclude_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> list[DealDraft]:
        """品类页模式（户外定向）：逐品类发现线报 ID，跳过已知 ID 再抓详情页。"""
        exclude = {str(x) for x in (exclude_ids or set())}
        cap = limit if limit is not None else self.max_details_per_run
        drafts: list[DealDraft] = []
        queued: set[str] = set()
        for slug in slugs or CATEGORY_SLUGS:
            if len(drafts) >= cap:
                break
            try:
                self.rate_limiter.wait(SMZDM_HOST)
                page_url = CATEGORY_BASE.format(slug=slug)
                resp = fetch_with_backoff(
                    lambda u=page_url: self.client.get(u), sleep=self.sleep
                )
                resp.raise_for_status()
            except Exception:  # noqa: BLE001 - 品类页失败跳过该品类
                continue
            for url, _sid in parse_category_page(resp.text):
                sid = str(_sid)
                if sid in exclude or sid in queued:
                    continue
                if len(drafts) >= cap:
                    break
                queued.add(sid)
                try:
                    self.rate_limiter.wait(SMZDM_HOST)
                    resp = fetch_with_backoff(
                        lambda u=url: self.client.get(u), sleep=self.sleep
                    )
                    resp.raise_for_status()
                    drafts.append(parse_deal_page(resp.text, url))
                except Exception:  # noqa: BLE001 - 线报流容错：单条失败继续
                    continue
        return drafts

    def collect_category_summaries(
        self,
        slugs: list[str] | None = None,
        *,
        pages: int = 1,
        exclude_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> list[DealDraft]:
        """品类列表摘要模式：每页 1 个请求覆盖 ~30 条线报，用于铺搜索语料。

        摘要缺渠道/详情由后续周期的详情复核补全（save_deal 按 source_id 幂等更新）。
        """
        exclude = {str(x) for x in (exclude_ids or set())}
        cap = limit if limit is not None else len(slugs or CATEGORY_SLUGS) * pages * 30
        drafts: list[DealDraft] = []
        for slug in slugs or CATEGORY_SLUGS:
            for page in range(1, max(1, pages) + 1):
                if len(drafts) >= cap:
                    return drafts
                page_url = CATEGORY_BASE.format(slug=slug)
                if page > 1:
                    page_url = f"{page_url}p{page}/"
                try:
                    self.rate_limiter.wait(SMZDM_HOST)
                    resp = fetch_with_backoff(
                        lambda u=page_url: self.client.get(u), sleep=self.sleep
                    )
                    resp.raise_for_status()
                except Exception:  # noqa: BLE001 - 单页失败跳过
                    continue
                for draft in parse_category_cards(resp.text):
                    if draft.source_id in exclude:
                        continue
                    exclude.add(draft.source_id)
                    drafts.append(draft)
                    if len(drafts) >= cap:
                        return drafts
        return drafts

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> SmzdmFeedCollector:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
