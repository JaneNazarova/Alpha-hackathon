from fastapi import APIRouter

from backend.api.routes import companies, health, insights, news

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(companies.router)
api_router.include_router(news.router)
api_router.include_router(insights.router)
