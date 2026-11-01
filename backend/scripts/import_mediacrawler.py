# ruff: noqa: E501
"""导入 MediaCrawler 采集的小红书笔记 / B站视频，按型号匹配到榜单产品，写入 cn_reviews.json（xhs_notes / bili_videos）。

小红书需要登录态与请求签名、api.bilibili.com 的 robots.txt 为 Disallow: /，本项目都不直接请求。推荐使用开源工具 MediaCrawler
（https://github.com/NanmiCoder/MediaCrawler，仅限学习研究、非商业用途，请遵守其许可证与平台规则）：

    # 在你自己的电脑上（需要扫码登录小红书）
    git clone https://github.com/NanmiCoder/MediaCrawler && cd MediaCrawler
    uv sync && uv run playwright install chromium
    # config/base_config.py: PLATFORM="xhs", KEYWORDS="始祖鸟 Beta AR,凯乐石 MONT-X", SAVE_DATA_OPTION="json"
    uv run main.py --platform xhs --lt qrcode --type search
    uv run main.py --platform bili --lt qrcode --type search   # B站同理

    # 回到本仓库
    cd backend && uv run python scripts/import_mediacrawler.py ../MediaCrawler/data/xhs/json/ ../MediaCrawler/data/bilibili/json/

支持 .json（数组）与 .jsonl 文件，或包含它们的目录（只读取 *contents* / *notes* 文件）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.rankings.brands import brand_by_slug, detect_brand  # noqa: E402
from app.rankings.sources.cn import (  # noqa: E402
    model_tokens,
    parse_mediacrawler_bili,
    parse_mediacrawler_xhs,
)

RANK_DIR = ROOT / "backend" / "app" / "rankings"


def load_notes(paths: list[Path]) -> list[dict]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files += [
                f
                for f in sorted(p.rglob("*"))
                if f.suffix in (".json", ".jsonl") and ("content" in f.name or "note" in f.name)
            ]
        else:
            files.append(p)
    notes: dict[str, dict] = {}
    for f in files:
        text = f.read_text(encoding="utf-8").strip()
        rows = (
            json.loads(text)
            if text.startswith("[")
            else [json.loads(line) for line in text.splitlines() if line.strip()]
        )
        for r in rows:
            key = isinstance(r, dict) and (r.get("note_id") or r.get("video_id") or r.get("bvid"))
            if key:
                notes[str(key)] = r
    return list(notes.values())


def match_terms(item: dict) -> tuple[list[str], list[str]]:
    """产品 → (型号 token, 品牌词)。"""
    b = brand_by_slug(item["brand"])
    _, model = detect_brand(item["name"])
    words = [b.name_cn, b.name, *b.aliases] if b else []
    return model_tokens(model or item["name"]), words


def match_notes(
    items: list[dict], rows: list[dict], limit: int = 5
) -> dict[str, dict[str, list[dict]]]:
    """返回 {item_id: {"xhs_notes": [...], "bili_videos": [...]}}。"""
    notes = [r for r in rows if r.get("note_id")]
    videos = [r for r in rows if not r.get("note_id")]
    out: dict[str, dict[str, list[dict]]] = {}
    for it in items:
        toks, words = match_terms(it)
        found = {
            "xhs_notes": parse_mediacrawler_xhs(notes, toks, words, it["category"]),
            "bili_videos": parse_mediacrawler_bili(videos, toks, words, it["category"]),
        }
        rec = {k: [h.to_dict() for h in v[:limit]] for k, v in found.items() if v}
        if rec:
            out[it["id"]] = rec
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="+", type=Path, help="MediaCrawler 导出的 json/jsonl 文件或目录")
    args = ap.parse_args()
    notes = load_notes(args.paths)
    items = json.loads((RANK_DIR / "catalog.json").read_text())
    cn_path = RANK_DIR / "cn_catalog.json"
    if cn_path.exists():
        items += json.loads(cn_path.read_text())
    matched = match_notes(items, notes)
    out_path = RANK_DIR / "cn_reviews.json"
    out = json.loads(out_path.read_text()) if out_path.exists() else {}
    for iid, rec in matched.items():
        out.setdefault(iid, {}).update(rec)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print(f"读取 {len(notes)} 条笔记/视频，匹配到 {len(matched)} 个产品 → {out_path}")


if __name__ == "__main__":
    main()
