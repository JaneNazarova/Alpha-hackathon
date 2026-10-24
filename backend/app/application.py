import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.app.lifespan import lifespan
from backend.app.middleware import register_middleware
from backend.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(title=settings.app_name, version="1.0.0",
                  description="Персонализированная новостная аналитика для бизнеса",
                  lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins,
                       allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["*"])
    register_middleware(app)
    app.include_router(api_router)
    return app
