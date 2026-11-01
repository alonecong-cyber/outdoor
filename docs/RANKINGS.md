# 权威榜单数据说明

## 数据来源

| 来源 | 类型 | 提供的数据 |
| --- | --- | --- |
| [OutdoorGearLab](https://www.outdoorgearlab.com) | 实验室并排实测 | 榜单排名、总分（满分 100）、分项评分、美标价、Bottom Line、优缺点、规格表、实测图 |
| [Switchback Travel](https://www.switchbacktravel.com) | 编辑长期实测榜单 | 奖项（Best Overall / Best Budget …）、排名、美标价、What we like / don't、白底产品图 |
| 国内口碑 | 检索直达 | 什么值得买 / 小红书 / B站 / 8264 / 京东 / 淘宝的搜索链接 |

国内平台（什么值得买、小红书、B站等）需要登录或有风控，按 AGENTS.md 约束不做爬取，只生成检索链接；
国内实时到手价继续由现有的联盟 API / 线报采集器负责。

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

产物：

- `backend/app/rankings/catalog.json`：API 直接加载
- `frontend/public/rankings/<id>.webp`：本地产品图（720px webp），前端按 本地图 → 原站图 → 占位图 回退

## 口径

- **价位梯队**：按本品类美标价三等分（入门 / 进阶 / 旗舰），袜子和帐篷不再共用同一套人民币阈值。
- **人民币折算**：美标价 × 7.1。
- **海淘落地估算**：复用 `app/pricing/overseas.py`，含品类典型转运费和 20% 行邮税（≤50 元免征），不含折扣/返现。
- **评分**：只展示 OGL 的真实实测分；仅出现在 Switchback 的产品显示"编辑推荐"，不编造分数。
- **合并**：同品类内按品牌 + 型号模糊匹配合并两站数据（型号中的数字必须一致，避免 Beta AR / Beta SL 混淆）。
- 无法识别品牌的白牌商品（亚马逊杂牌等）不收录；新增品牌在 `brands.py` 里加一行即可。
