"""OutdoorDeal 后端入口：FastAPI 应用 + 可选调度器。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routes import build_api_router, health
from app.config import get_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(getattr(app.state, "db_engine", None))
    scheduler = None
    if get_settings().scheduler_enabled and not getattr(app.state, "disable_scheduler", False):
        from app.scheduler import build_scheduler

        settings = get_settings()
        scheduler = build_scheduler(
            collect_interval_minutes=settings.collect_interval_minutes,
            ingest_deals_interval_minutes=settings.ingest_deals_interval_minutes,
        )
    app.state.scheduler = scheduler
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title="OutdoorDeal", version=__version__, lifespan=lifespan)
    app.include_router(health.router)  # 根路径 /health
    app.include_router(build_api_router())  # /api 前缀路由
    return app


app = create_app()


def main() -> None:
    """开发服务器入口：uv run python -m app.main"""
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
