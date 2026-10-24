import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles 

from backend.api.router import api_router
from backend.app.lifespan import lifespan
from backend.app.middleware import register_middleware
from backend.config import get_settings

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


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

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    @app.get("/", include_in_schema=False)
    def frontend():
        return FileResponse(FRONTEND_DIR / "index.html")
        
    return app
