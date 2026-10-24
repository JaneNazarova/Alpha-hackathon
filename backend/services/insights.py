from uuid import uuid4
from importlib import import_module
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models import Company, FeedScore, Insight, InsightQuestion, NewsArticle
from backend.services.personalization import company_profile, score_article


def _external(name, *args):
    """Use team modules when present, keeping the API usable before they are integrated."""
    try:
        module_name, function_name = name.rsplit(".", 1)
        fn = getattr(import_module(module_name), function_name)
        return fn(*args)
    except (ImportError, AttributeError, TypeError):
        return None


def create_insight(db: Session, company: Company, article: NewsArticle, role: str):
    existing = db.scalar(select(Insight).where(Insight.company_id == company.id,
        Insight.article_id == article.id, Insight.user_role == role).order_by(Insight.created_at.desc()))
    if existing:
        return existing
    profile = company_profile(company, role)
    ranked = db.scalar(select(FeedScore).where(FeedScore.company_id == company.id, FeedScore.article_id == article.id))
    ranked = ranked or FeedScore(company_id=company.id, article_id=article.id,
        relevance_score=score_article(company, article, role)[0], relevance_reasons=score_article(company, article, role)[1],
        matched_factors=score_article(company, article, role)[2])
    generated = _external("ai.agent.generate_insight", profile, {"id": article.id, "title": article.title, "content": article.content}, None)
    trace_id = str(uuid4())
    if isinstance(generated, dict):
        payload = generated
        payload.setdefault("what_happened", article.summary or article.title)
        payload.setdefault("why_it_matters", "")
        payload.setdefault("risks", [])
        payload.setdefault("opportunities", [])
        payload.setdefault("next_steps", [])
        payload.setdefault("bank_position", {"text": None, "source_ids": []})
        payload.setdefault("ai_conclusion", "")
        payload.setdefault("sources", [{"id": article.id, "type": "news", "title": article.title, "url": article.url}])
        payload.setdefault("company_factors", ranked.matched_factors or [])
        payload.setdefault("uncertainties", [])
        status = generated.get("validation_status", "generated")
        model = generated.get("model_name")
    else:
        payload = {"what_happened": article.summary or article.title,
            "why_it_matters": "Автоматическая оценка релевантности: " + "; ".join(ranked.relevance_reasons or []),
            "risks": [], "opportunities": [], "next_steps": ["Проверить первоисточник и влияние на планы компании"],
            "bank_position": {"text": None, "source_ids": []},
            "ai_conclusion": "Подробная интерпретация будет доступна после подключения AI-модуля. Данный ответ не содержит неподтверждённого мнения банка.",
            "sources": [{"id": article.id, "type": "news", "title": article.title, "url": article.url}],
            "company_factors": ranked.matched_factors or [],
            "uncertainties": ["AI-модуль и документы аналитики банка пока не подключены."], "trace_id": trace_id}
        status, model = "fallback", None
    payload.setdefault("trace_id", trace_id)
    payload.setdefault("bank_position", {"text": None, "source_ids": []})
    insight = Insight(id=str(uuid4()), company_id=company.id, article_id=article.id, user_role=role,
        payload=payload, model_name=model, validation_status=status,
        trace={"trace_id": trace_id, "steps": ["company_profile", "news_details", "relevance_factors", "insight_generation"],
               "sources": payload.get("sources", []), "matched_factors": ranked.matched_factors or [],
               "validation_status": status})
    db.add(insight); db.commit(); db.refresh(insight)
    return insight


def answer_question(db: Session, insight: Insight, question: str):
    answer = _external("ai.agent.answer_question", insight.payload, question)
    if not isinstance(answer, str):
        answer = ("В сохранённом анализе указано: " + str(insight.payload.get("why_it_matters", "")) +
                  " Основание: исходная новость и перечисленные признаки компании. "
                  "Подтверждённой аналитики банка в этом анализе нет.")
    row = InsightQuestion(insight_id=insight.id, question=question, answer=answer)
    db.add(row); db.commit(); db.refresh(row)
    return row
