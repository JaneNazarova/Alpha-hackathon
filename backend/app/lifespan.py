from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import select

from backend.database import Base, SessionLocal, engine
from backend.models import Company  # noqa: F401 - registers ORM metadata
from backend.services.company_data import seed_demo_companies
from backend.services.ml_personalization import load_company_dataset


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    dataset = load_company_dataset()
    with SessionLocal() as db:
        if dataset is None and not db.scalar(select(Company.id).limit(1)):
            seed_demo_companies(db)
    yield
