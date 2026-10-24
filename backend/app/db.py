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


def get_session(engine=None) -> Iterator[Session]:
    if engine is None:
        engine = get_engine()
    with Session(engine) as session:
        yield session
