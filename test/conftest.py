from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.application import create_app
from backend.api.dependencies import get_ml_dataset
from backend.database import Base, get_db
from backend.models import Company, NewsArticle


@pytest.fixture
def database(tmp_path, monkeypatch):
    """Create a fresh database and point application startup at it."""
    from backend.app import lifespan as lifespan_module

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.sqlite3'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    monkeypatch.setattr(lifespan_module, "engine", engine)
    monkeypatch.setattr(lifespan_module, "SessionLocal", session_factory)
    monkeypatch.setattr(lifespan_module, "load_company_dataset", lambda: None)

    with session_factory() as db:
        db.add_all([
            Company(id="SYNTHETIC_U_001", industry="Производство", okved_code="25.11",
                    region="Москва", city="Москва", revenue=850_000_000,
                    group_id="GROUP_A", has_loans=True, has_leasing=True,
                    has_foreign_trade=True, trade_countries=["Китай"]),
            Company(id="SYNTHETIC_U_002", industry="Розничная торговля", region="Санкт-Петербург",
                    revenue=None, has_loans=False, has_leasing=None,
                    has_foreign_trade=False, trade_countries=[]),
        ])
        db.add_all([
            NewsArticle(id="news-rate", title="ЦБ повысил ключевую ставку",
                        content="Ставка влияет на кредиты компаний.", summary="Решение по ставке",
                        source_name="Тестовый источник", url="https://example.test/rate",
                        published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc),
                        category="monetary_policy", processing_status="processed",
                        content_hash="hash-rate", facts=["ключевая ставка"]),
            NewsArticle(id="news-currency", title="Курс рубля и экспорт",
                        content="Изменился курс валюты.", summary="Курс валюты",
                        source_name="Тестовый источник", url="https://example.test/currency",
                        published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc),
                        category="currency", processing_status="processed",
                        content_hash="hash-currency", facts=["курс рубля"]),
        ])
        db.commit()

    yield session_factory
    engine.dispose()


@pytest.fixture
def client(database):
    session_factory = database
    app = create_app()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ml_dataset] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
