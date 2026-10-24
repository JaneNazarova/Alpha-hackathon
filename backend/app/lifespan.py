from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import select

from backend.config import get_settings
from backend.database import Base, SessionLocal, engine
from backend.models import Company  # noqa: F401 - registers ORM metadata
from backend.services.company_data import import_company_csv, seed_demo_companies


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    with SessionLocal() as db:
        if not db.scalar(select(Company.id).limit(1)):
            csv_path = Path(settings.companies_csv_path)
            if csv_path.exists():
                import_company_csv(db, csv_path)
            else:
                seed_demo_companies(db)
    yield
