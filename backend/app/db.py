"""数据库：SQLite 起步，SQLModel + SQLAlchemy engine。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def _ensure_dir(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def get_engine(db_path: Path | None = None):
    """创建 engine。SQLite 需要允许跨线程访问（FastAPI 多 worker 检查用）。"""
    if db_path is None:
        db_path = get_settings().db_path
    _ensure_dir(db_path)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def init_db(engine=None) -> None:
    """建表（幂等）。模型必须在调用前导入完成。"""
    from app import models  # noqa: F401  确保表定义已注册

    if engine is None:
        engine = get_engine()
    SQLModel.metadata.create_all(engine)
    # SQLite create_all 不会为已存在的表添加列；仅做可回滚的增量扩展。
    additions = {
        "listing": {
            "source": "TEXT NOT NULL DEFAULT 'manual'",
            "merchant": "TEXT NOT NULL DEFAULT ''",
            "stock_verified": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "pricesnapshot": {
            "stock_verified": "BOOLEAN NOT NULL DEFAULT 0",
            "paid_now_cents": "INTEGER",
            "rebate_cents": "INTEGER NOT NULL DEFAULT 0",
            "effective_cents": "INTEGER",
        },
        "deal": {
            "last_checked_at": "DATETIME",
            "expires_at": "DATETIME",
            "expired": "BOOLEAN NOT NULL DEFAULT 0",
        },
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table}")')}
            for column, definition in columns.items():
                if column not in existing:
                    conn.exec_driver_sql(
                        f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'
                    )


def get_session(engine=None) -> Iterator[Session]:
    if engine is None:
        engine = get_engine()
    with Session(engine) as session:
        yield session
