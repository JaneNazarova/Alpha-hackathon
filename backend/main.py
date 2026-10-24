import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import Base, engine, get_db
from backend.models import Company, FeedScore, Insight, InsightQuestion, NewsArticle
from backend.schemas import CompanyOut, InsightCreate, InsightOut, NewsOut, QuestionCreate
from backend.services.company_data import import_company_csv, seed_demo_companies
from backend.services.insights import answer_question, create_insight
from backend.services.news import fetch_rss
from backend.services.personalization import company_profile, score_article

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("alpha_backend")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        csv_path = __import__("pathlib").Path(settings.companies_csv_path)
        if not db.scalar(select(Company.id).limit(1)):
            if csv_path.exists():
                import_company_csv(db, csv_path)
            else:
                seed_demo_companies(db)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", description="Персонализированная новостная аналитика для бизнеса", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])


@app.middleware("http")
async def request_trace(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled server error trace_id=%s path=%s", trace_id, request.url.path)
        response = JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "Внутренняя ошибка сервера", "trace_id": trace_id}})
    response.headers["X-Trace-Id"] = trace_id
    return response


def _company(db: Session, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, detail={"code": "company_not_found", "message": "Компания не найдена"})
    return company


def _article(db: Session, article_id: str) -> NewsArticle:
    article = db.get(NewsArticle, article_id)
    if not article:
        raise HTTPException(404, detail={"code": "news_not_found", "message": "Новость не найдена"})
    return article


def _insight_out(insight: Insight):
    return {"insight_id": insight.id, "company_id": insight.company_id, "article_id": insight.article_id,
        **insight.payload, "validation_status": insight.validation_status,
        "trace_id": insight.trace.get("trace_id", insight.payload.get("trace_id")),
        "created_at": insight.created_at, "model_name": insight.model_name}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
        return {"status": "ok", "database": "ok"}
    except Exception:
        raise HTTPException(503, detail={"code": "database_unavailable", "message": "Хранилище временно недоступно"})


@app.get("/api/companies", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db), q: str | None = None, limit: int = Query(100, ge=1, le=500)):
    stmt = select(Company).order_by(Company.id).limit(limit)
    if q:
        stmt = select(Company).where(Company.id.ilike(f"%{q}%")).order_by(Company.id).limit(limit)
    return [company_profile(c) for c in db.scalars(stmt).all()]


@app.get("/api/companies/{company_id}", response_model=CompanyOut)
def get_company(company_id: str, role: str = Query("ceo", pattern="^(ceo|cfo)$"), db: Session = Depends(get_db)):
    return company_profile(_company(db, company_id), role)


@app.get("/api/feed", response_model=list[NewsOut])
def get_feed(company_id: str = Query(...), role: str = Query("ceo", pattern="^(ceo|cfo)$"),
             limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    company = _company(db, company_id)
    rows = []
    for article in db.scalars(select(NewsArticle)).all():
        score, reasons, factors = score_article(company, article, role)
        rows.append((score, article, reasons, factors))
    rows.sort(key=lambda item: (item[0], item[1].published_at or item[1].fetched_at), reverse=True)
    return [{"id": article.id, "title": article.title, "content": article.content, "summary": article.summary,
             "source_name": article.source_name, "source_url": article.url, "published_at": article.published_at,
             "fetched_at": article.fetched_at, "category": article.category, "processing_status": article.processing_status,
             "relevance_score": score, "relevance_reasons": reasons, "matched_factors": factors}
            for score, article, reasons, factors in rows[:limit]]


@app.get("/api/news/{article_id}", response_model=NewsOut)
def get_news(article_id: str, company_id: str | None = None, role: str = "ceo", db: Session = Depends(get_db)):
    article = _article(db, article_id)
    result = {"id": article.id, "title": article.title, "content": article.content, "summary": article.summary,
        "source_name": article.source_name, "source_url": article.url, "published_at": article.published_at,
        "fetched_at": article.fetched_at, "category": article.category, "processing_status": article.processing_status}
    if company_id:
        score, reasons, factors = score_article(_company(db, company_id), article, role)
        result.update(relevance_score=score, relevance_reasons=reasons, matched_factors=factors)
    return result


@app.post("/api/news/refresh")
async def refresh_news(db: Session = Depends(get_db), x_refresh_token: str | None = Header(default=None)):
    if settings.news_refresh_token and x_refresh_token != settings.news_refresh_token:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Недостаточно прав"})
    result = await fetch_rss(db)
    logger.info("RSS refresh inserted=%s skipped=%s failed_sources=%s", result["inserted"], result["skipped"], len(result["failures"]))
    if result["failures"] and result["inserted"] == 0 and result["skipped"] == 0:
        return JSONResponse(status_code=503, content={"error": {"code": "sources_unavailable", "message": "Источники новостей временно недоступны; сохранённые материалы доступны."}, **result})
    return result


@app.post("/api/insights", response_model=InsightOut)
def post_insight(payload: InsightCreate, db: Session = Depends(get_db)):
    company, article = _company(db, payload.company_id), _article(db, payload.article_id)
    if payload.user_role not in {"ceo", "cfo"}:
        raise HTTPException(400, detail={"code": "invalid_role", "message": "Допустимые роли: ceo, cfo"})
    return _insight_out(create_insight(db, company, article, payload.user_role))


@app.get("/api/insights/{insight_id}", response_model=InsightOut)
def get_insight(insight_id: str, db: Session = Depends(get_db)):
    insight = db.get(Insight, insight_id)
    if not insight:
        raise HTTPException(404, detail={"code": "insight_not_found", "message": "Анализ не найден"})
    return _insight_out(insight)


@app.post("/api/insights/{insight_id}/questions")
def post_question(insight_id: str, payload: QuestionCreate, db: Session = Depends(get_db)):
    insight = db.get(Insight, insight_id)
    if not insight:
        raise HTTPException(404, detail={"code": "insight_not_found", "message": "Анализ не найден"})
    row = answer_question(db, insight, payload.question)
    return {"question_id": row.id, "insight_id": insight_id, "question": row.question, "answer": row.answer, "created_at": row.created_at}


@app.get("/api/insights/{insight_id}/trace")
def get_trace(insight_id: str, db: Session = Depends(get_db)):
    insight = db.get(Insight, insight_id)
    if not insight:
        raise HTTPException(404, detail={"code": "insight_not_found", "message": "Анализ не найден"})
    return insight.trace


@app.get("/api/insights/{insight_id}/questions")
def list_questions(insight_id: str, db: Session = Depends(get_db)):
    if not db.get(Insight, insight_id):
        raise HTTPException(404, detail={"code": "insight_not_found", "message": "Анализ не найден"})
    return [{"question_id": row.id, "question": row.question, "answer": row.answer, "created_at": row.created_at}
            for row in db.scalars(select(InsightQuestion).where(InsightQuestion.insight_id == insight_id).order_by(InsightQuestion.created_at)).all()]
