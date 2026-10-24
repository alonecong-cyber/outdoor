"""配置：只读环境变量（backend/.env），代码里绝不硬编码密钥。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 运行时
    db_path: Path = BACKEND_DIR / "var" / "outdoordeal.db"
    scheduler_enabled: bool = False
    notifications_enabled: bool = False
    offer_freshness_hours: int = 24
    deal_recheck_hours: int = 6
    collection_keywords: list[str] = ["始祖鸟", "北面", "Patagonia"]
    collect_interval_minutes: int = 60
    ingest_deals_interval_minutes: int = 60
    ingest_deals_max_details: int = 8
    collection_specs: list[dict] = []

    # 京东联盟（宙斯开放平台）
    jd_union_app_key: str = ""
    jd_union_secret_key: str = ""

    # 淘宝联盟（淘宝客）
    taobao_app_key: str = ""
    taobao_app_secret: str = ""
    taobao_pid: str = ""

    # AvantLink
    avantlink_affiliate_id: str = ""
    avantlink_website_id: str = ""
    avantlink_api_key: str = ""

    # 通知
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_ssl: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    wecom_webhook: str = ""

    # 汇率缺省值（正式运行由每日任务刷新）
    usd_cny_rate: float = 7.1

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
