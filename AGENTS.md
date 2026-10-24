# OutdoorDeal — 项目背景（每次新会话先读这段）

项目名：OutdoorDeal（户外服饰比价 + 最低到手价计算）

目标：同一件户外服饰（品牌+型号+颜色+尺码）在多个渠道的价格采集、价格历史、降价提醒，
并计算"叠加所有可用优惠后"的最低到手价：
- 国内：标价 − 直降 − 店铺券 − 满减分摊 − 平台券 − 支付立减 − 返利
  （规则应用顺序：直降/会员价 → 店铺券 → 店铺满减 → 跨店满减 → 平台券/红包 → 支付立减 → 返利）
- 海淘：(美元价 × (1−折扣) × (1−折扣码) + 美国运费) × 汇率 + 转运费 + 行邮税 − 返现×汇率
  （行邮税 20%，税额 ≤50 元免征；单次限值 2000 元，超限提示可能退运）

开发环境：Intel MacBook，macOS，**无 Docker**；Python 3.12（uv 管理），SQLite 起步，
后期可换 Postgres（Homebrew 安装）。

技术栈：FastAPI + SQLModel + Playwright(Python) + httpx + APScheduler + OR-Tools；
前端 Next.js（App Router）+ Tailwind + React Query。

代码规范：类型注解齐全，pydantic 模型做数据边界，pytest 测试，ruff 格式化；不要引入 Docker。

目录：
- `backend/app/collectors` — 采集器（jd_union / tbk / avantlink / web_product），统一产出 `RawListing`
- `backend/app/normalize` — SKU 归一化（款号正则 + 颜色/尺码词典，相似度兜底，<0.85 转人工）
- `backend/app/pricing` — 优惠规则引擎、单品枚举求解、凑单背包 DP、CP-SAT 多商品、海淘落地价
- `backend/app/history` — 价格快照（只在变化时写）、30/90 天统计、新低判定（历史 ≥14 天才报）
- `backend/app/alerts` — 到手价提醒评估（同类 24h 去重）、Telegram/邮件/企业微信通知
- `backend/app/api` — FastAPI 路由
- `data/fixtures` — 真实样例数据（接口返回 JSON、页面 HTML），测试以此为准
- `frontend` — Next.js 前端（M5）

数据口径：**价格一律存整数"分"**；返利/返现按实付计算、事后到账，与"当下实付"分开展示；
满减分摊按商品金额比例摊到每件。

重要约束：
1. 采集优先用联盟/官方 API；网页采集必须遵守 robots.txt，单站点 ≥10 秒/请求。
2. 禁止绕过登录、验证码和风控；解析顺序：API → JSON-LD → CSS；失败退避，失效降级为人工。
3. 不做：得物/闲鱼二手、全站爬取、多用户账号体系、自动下单/领券（第二阶段再说）。
4. 密钥一律放 `backend/.env`（已在 .gitignore），代码里只读环境变量。
5. 不要引入 Docker。

## 给 AI 协作者的规矩

- 一次只做一个模块；先说方案，确认后再写代码。
- 价格计算先写测试，每个用例附手算过程；测试即需求文档。
- 出 bug 先列可能原因和验证方法，不要上来就改代码。
- 验收：`cd backend && uv run pytest` 全绿；`uv run uvicorn app.main:app` 后 `GET /health` 返回 ok。
