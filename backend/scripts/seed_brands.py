"""DDG 定向品牌补种：搜 site:smzdm.com <品牌>，抓详情入库。"""

import re
import time
import urllib.parse
import urllib.request

from sqlmodel import Session

from app.collectors.base import fetch_with_backoff
from app.collectors.smzdm import SMZDM_HOST, SmzdmFeedCollector, parse_deal_page
from app.db import get_engine, init_db
from app.deals import ingest_deals

QUERIES = [
    "site:smzdm.com patagonia 好价",
    "site:smzdm.com 凯乐石 冲锋衣",
    "site:smzdm.com kailas 徒步鞋",
    "site:smzdm.com marmot 土拨鼠",
    "site:smzdm.com 土拨鼠 冲锋衣",
    "site:smzdm.com 哥伦比亚 冲锋衣",
    "site:smzdm.com 始祖鸟 beta",
    "site:smzdm.com 软壳 男",
]


def ddg_ids(query: str, proxy: str) -> set[int]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh)"})
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    resp = urllib.request.build_opener(handler).open(req, timeout=20)
    html = resp.read().decode("utf-8", "ignore")
    ids = set()
    for enc in re.findall(r'uddg=([^&"<]+)', html):
        real = urllib.parse.unquote(enc)
        m = re.match(r"https?://(?:www\.)?smzdm\.com/p/(\d+)/", real)
        if m:
            ids.add(int(m.group(1)))
    return ids


init_db()
proxy = "http://127.0.0.1:7890"
all_ids: set[int] = set()
for q in QUERIES:
    try:
        got = ddg_ids(q, proxy)
        print(f"{q!r} -> {sorted(got, reverse=True)}")
        all_ids |= got
    except Exception as exc:  # noqa: BLE001
        print(f"{q!r} -> ERROR {exc!r}")
    time.sleep(3)

all_ids = sorted(all_ids, reverse=True)
print(f"合并去重 {len(all_ids)} 篇，抓详情…")
drafts = []
with SmzdmFeedCollector() as c:
    for i in all_ids:
        url = f"https://www.smzdm.com/p/{i}/"
        try:
            c.rate_limiter.wait(SMZDM_HOST)
            resp = fetch_with_backoff(lambda u=url: c.client.get(u), sleep=c.sleep)
            resp.raise_for_status()
            drafts.append(parse_deal_page(resp.text, url))
        except Exception as exc:  # noqa: BLE001
            print(f"  {url} 失败: {exc!r}")
print(f"详情 {len(drafts)} 篇")
with Session(get_engine()) as session:
    print(ingest_deals(session, drafts))
