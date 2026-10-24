"""路由聚合。"""

from fastapi import APIRouter

from app.api.routes import alerts, catalog, health, pricing


def build_api_router() -> APIRouter:
    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(catalog.router)
    api.include_router(pricing.router)
    api.include_router(alerts.router)
    return api
