from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models import Company, Insight, NewsArticle
from backend.services.ml_personalization import load_company_dataset


def get_company_or_404(db: Session, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, detail={"code": "company_not_found", "message": "Компания не найдена"})
    return company


def get_article_or_404(db: Session, article_id: str) -> NewsArticle:
    article = db.get(NewsArticle, article_id)
    if article is None:
        raise HTTPException(404, detail={"code": "news_not_found", "message": "Новость не найдена"})
    return article


def get_insight_or_404(db: Session, insight_id: str) -> Insight:
    insight = db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(404, detail={"code": "insight_not_found", "message": "Анализ не найден"})
    return insight


def get_ml_dataset():
    return load_company_dataset()
