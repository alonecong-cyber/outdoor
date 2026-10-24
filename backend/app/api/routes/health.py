"""健康检查：GET /health（验收标准之一）。"""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.api.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__)
