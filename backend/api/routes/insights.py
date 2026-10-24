from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_article_or_404, get_company_or_404, get_insight_or_404
from backend.database import get_db
from backend.models import InsightQuestion
from backend.schemas import InsightCreate, InsightOut, QuestionCreate
from backend.services.insights import answer_question, create_insight

router = APIRouter(prefix="/api/insights", tags=["insights"])


def _to_response(insight):
    return {"insight_id": insight.id, "company_id": insight.company_id,
            "article_id": insight.article_id, **insight.payload,
            "validation_status": insight.validation_status,
            "trace_id": insight.trace.get("trace_id", insight.payload.get("trace_id")),
            "created_at": insight.created_at, "model_name": insight.model_name}


@router.post("", response_model=InsightOut)
def post_insight(payload: InsightCreate, db: Session = Depends(get_db)):
    if payload.user_role not in {"ceo", "cfo"}:
        raise HTTPException(400, detail={"code": "invalid_role", "message": "Допустимые роли: ceo, cfo"})
    company = get_company_or_404(db, payload.company_id)
    article = get_article_or_404(db, payload.article_id)
    return _to_response(create_insight(db, company, article, payload.user_role))


@router.get("/{insight_id}", response_model=InsightOut)
def get_insight(insight_id: str, db: Session = Depends(get_db)):
    return _to_response(get_insight_or_404(db, insight_id))


@router.post("/{insight_id}/questions")
def post_question(insight_id: str, payload: QuestionCreate, db: Session = Depends(get_db)):
    row = answer_question(db, get_insight_or_404(db, insight_id), payload.question)
    return {"question_id": row.id, "insight_id": insight_id, "question": row.question,
            "answer": row.answer, "created_at": row.created_at}


@router.get("/{insight_id}/trace")
def get_trace(insight_id: str, db: Session = Depends(get_db)):
    return get_insight_or_404(db, insight_id).trace


@router.get("/{insight_id}/questions")
def list_questions(insight_id: str, db: Session = Depends(get_db)):
    get_insight_or_404(db, insight_id)
    questions = db.scalars(select(InsightQuestion)
                           .where(InsightQuestion.insight_id == insight_id)
                           .order_by(InsightQuestion.created_at)).all()
    return [{"question_id": row.id, "question": row.question,
             "answer": row.answer, "created_at": row.created_at} for row in questions]
