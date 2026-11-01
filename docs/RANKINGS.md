# 权威榜单数据说明

## 数据来源

| 来源 | 类型 | 提供的数据 |
| --- | --- | --- |
| [OutdoorGearLab](https://www.outdoorgearlab.com) | 实验室并排实测 | 榜单排名、总分（满分 100）、分项评分、美标价、Bottom Line、优缺点、规格表、实测图 |
| [Switchback Travel](https://www.switchbacktravel.com) | 编辑长期实测榜单 | 奖项（Best Overall / Best Budget …）、排名、美标价、What we like / don't、白底产品图 |
| [什么值得买](https://www.smzdm.com) | 国内好价 + 原创测评 | 好价爆料（价格/商城/日期）→ 国内好价区间；原创测评文章；国货口碑款 |
| B站 / 小红书 | 用户自行采集后导入 | MediaCrawler 导出的视频 / 笔记（播放、点赞、链接） |
| 国内口碑 | 检索直达 | 什么值得买 / 小红书 / B站 / 8264 / 京东 / 淘宝的搜索链接 |

## 国内数据方案

调研结论（按 AGENTS.md：优先 API、遵守 robots、同站 ≥10 秒/请求、不绕过登录/验证码/风控）：

| 平台 | 可行方式 | 本项目做法 |
| --- | --- | --- |
| 什么值得买 | `api.smzdm.com/v1/list?keyword=…` 免登录公开接口，无 robots 限制（search.smzdm.com 网页有 JS 挑战，不碰） | `scripts/enrich_cn.py` 直接请求：一次混合检索按频道拆成"好价/原创"，10 秒/请求，结果缓存在 `data/raw_cache/cn/` |
| B站 | 搜索接口可免登录访问，但 `api.bilibili.com/robots.txt` 为 `Disallow: /` | **不直接请求**；用 MediaCrawler 采集后导入 |
| 小红书 | 需登录态 + `x-s` 请求签名 | **不做逆向**；用 MediaCrawler 扫码登录采集后导入 |
| 翻译 | 奖项（459 条）、分项名、优缺点（2959 条）为**人工翻译**（`badges_zh.json` / `glossary_zh.py` / `pros_cons_zh.json`）；评价摘录用机器翻译：Google gtx 公共接口优先（遇 429 等 10 分钟，不换 UA/IP 绕过），不可用时用本地 Qwen2.5-0.5B-Instruct 兜底 | Argos Translate、opus-mt-en-zh 试过，户外术语质量差未采用；机翻结果经 `GLOSSARY` 术语校正；前端悬停可看英文原文 |

开源工具：[MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)（Playwright 扫码登录，支持小红书 / 抖音 / B站 / 微博等，
**许可证仅限学习研究、禁止商业用途**），在你自己的电脑上登录采集，导出 JSON 后：

```bash
cd backend
uv run python scripts/import_mediacrawler.py ../MediaCrawler/data/xhs/json/ ../MediaCrawler/data/bilibili/json/
```

按「品牌词 + 型号关键 token + 品类词」匹配到榜单产品，写入 `cn_reviews.json` 的 `xhs_notes` / `bili_videos`，前端"国内口碑"自动展示。

匹配规则（`app/rankings/sources/cn.py`）：

- 标题须含品牌（中/英/别名任一）且含全部型号 token；短 token（AR、6）要求词边界；
- 型号后紧跟其它版本后缀（查 Beta 却是 Beta AR / SV / LT）视为另一款；
- 好价须命中品类词（冲锋衣不收 Beta AR 裤的价格）；裤类内容必须明确提到"裤"；
- 好价汇总剔除离群价（中位数 0.4~2.5 倍之外，多为配件/定金/错标）。

国内实时到手价继续由现有的联盟 API / 线报采集器负责；这里的"国内好价"是什么值得买近期爆料区间，仅供参考。

## 品类（21 个）

硬壳冲锋衣、轻量防水夹克、软壳、抓绒、排汗打底/秋衣、羽绒服、棉服、徒步裤、防水裤、户外袜、
徒步鞋（通勤+徒步）、徒步靴、越野跑鞋、接近鞋、帐篷、登山杖、重装背包、日行包、睡袋、睡垫、头灯。

品类与来源 URL 在 `backend/app/rankings/catalog_config.py` 配置，品牌中英文与产地在 `backend/app/rankings/brands.py`。

## 构建 / 更新

```bash
cd backend
uv run python scripts/build_rankings.py            # 用 data/raw_cache 缓存，缺页才抓（同站 ≥10s/请求）
uv run python scripts/build_rankings.py --refresh  # 强制重抓所有榜单页（测评站一般半年一更）
```

国内数据（什么值得买 + 翻译 + 国货口碑款，全量约 2 小时，之后走缓存只需几秒）：

```bash
uv run python scripts/enrich_cn.py                    # 国货精选 → 海外款国内好价/原创 → 翻译
uv run python scripts/enrich_cn.py --only translate   # 只补翻译
uv run python scripts/enrich_cn.py --only picks       # 只重建国货口碑款（种子在 app/rankings/cn_picks.py）
```

产物：

- `backend/app/rankings/catalog.json`：API 直接加载
- `backend/app/rankings/cn_catalog.json`：国货口碑款（迪卡侬、凯乐石、牧高笛、挪客、骆驼、伯希和…），好价不足 2 条或无图自动剔除
- `backend/app/rankings/cn_reviews.json`：每款的国内好价汇总、好价/原创列表（+ 导入的 B站/小红书）
- `backend/app/rankings/translations_zh.json`：优缺点 / 奖项 / 评价的中文译文（`data.py` 加载时合并，原文悬停可见）
- `frontend/public/rankings/<id>.webp`：本地产品图（720px webp），前端按 本地图 → 原站图 → 占位图 回退

## 口径

- **价位梯队**：按本品类美标价三等分（入门 / 进阶 / 旗舰），袜子和帐篷不再共用同一套人民币阈值。
- **人民币折算**：美标价 × 7.1。
- **海淘落地估算**：复用 `app/pricing/overseas.py`，含品类典型转运费和 20% 行邮税（≤50 元免征），不含折扣/返现。
- **评分**：只展示 OGL 的真实实测分；仅出现在 Switchback 的产品显示"编辑推荐"，国货口碑款显示"国内口碑"，不编造分数。
- **国货价位梯队**：用国内好价中位数，对照同品类海外款（海淘落地价）的梯队分界归入入门 / 进阶 / 旗舰。
- **合并**：同品类内按品牌 + 型号模糊匹配合并两站数据（型号中的数字必须一致，避免 Beta AR / Beta SL 混淆）。
- 无法识别品牌的白牌商品（亚马逊杂牌等）不收录；新增品牌在 `brands.py` 里加一行即可。
