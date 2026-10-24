"""OutdoorDeal 后端入口：FastAPI 应用 + 可选调度器。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routes import build_api_router
from app.config import get_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = None
    if get_settings().scheduler_enabled:
        from app.scheduler import build_scheduler

        scheduler = build_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title="OutdoorDeal", version=__version__, lifespan=lifespan)
    app.include_router(build_api_router())
    return app


app = create_app()


def main() -> None:
    """开发服务器入口：uv run python -m app.main"""
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
