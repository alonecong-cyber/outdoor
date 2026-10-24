"""FastAPI 依赖：DB session。"""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session

from app.db import get_engine


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
