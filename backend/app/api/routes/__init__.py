"""路由聚合。"""

from fastapi import APIRouter

from app.api.routes import alerts, catalog, deals, health, pricing, watch


def build_api_router() -> APIRouter:
    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(catalog.router)
    api.include_router(pricing.router)
    api.include_router(alerts.router)
    api.include_router(deals.router)
    api.include_router(watch.router)
    return api
