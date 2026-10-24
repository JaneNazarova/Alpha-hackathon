import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_article_or_404, get_company_or_404
from backend.config import get_settings
from backend.database import get_db
from backend.models import NewsArticle
from backend.schemas import NewsOut
from backend.services.news import fetch_rss
from backend.services.personalization import score_article

logger = logging.getLogger("alpha_backend.news")
settings = get_settings()
router = APIRouter(tags=["news"])


def _news_payload(article: NewsArticle, score=None, reasons=None, factors=None):
    return {"id": article.id, "title": article.title, "content": article.content,
            "summary": article.summary, "source_name": article.source_name,
            "source_url": article.url, "published_at": article.published_at,
            "fetched_at": article.fetched_at, "category": article.category,
            "processing_status": article.processing_status, "relevance_score": score,
            "relevance_reasons": reasons or [], "matched_factors": factors or []}


@router.get("/api/feed", response_model=list[NewsOut])
def get_feed(company_id: str = Query(...), role: str = Query("ceo", pattern="^(ceo|cfo)$"),
             limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    company = get_company_or_404(db, company_id)
    rows = []
    for article in db.scalars(select(NewsArticle)).all():
        score, reasons, factors = score_article(company, article, role)
        rows.append((score, article, reasons, factors))
    rows.sort(key=lambda item: (item[0], item[1].published_at or item[1].fetched_at), reverse=True)
    return [_news_payload(article, score, reasons, factors)
            for score, article, reasons, factors in rows[:limit]]


@router.get("/api/news/{article_id}", response_model=NewsOut)
def get_news(article_id: str, company_id: str | None = None, role: str = "ceo",
             db: Session = Depends(get_db)):
    article = get_article_or_404(db, article_id)
    if company_id:
        score, reasons, factors = score_article(get_company_or_404(db, company_id), article, role)
        return _news_payload(article, score, reasons, factors)
    return _news_payload(article)


@router.post("/api/news/refresh")
async def refresh_news(db: Session = Depends(get_db), x_refresh_token: str | None = Header(default=None)):
    if settings.news_refresh_token and x_refresh_token != settings.news_refresh_token:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Недостаточно прав"})
    result = await fetch_rss(db)
    logger.info("RSS refresh inserted=%s skipped=%s failed_sources=%s",
                result["inserted"], result["skipped"], len(result["failures"]))
    if result["failures"] and result["inserted"] == 0 and result["skipped"] == 0:
        return JSONResponse(status_code=503, content={"error": {
            "code": "sources_unavailable",
            "message": "Источники новостей временно недоступны; сохранённые материалы доступны."}, **result})
    return result
