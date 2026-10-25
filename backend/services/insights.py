from uuid import uuid4
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models import Company, FeedScore, Insight, InsightQuestion, NewsArticle
from backend.services.personalization import score_article
from ml.integration import profile_from_company

logger = logging.getLogger("alpha_backend.insights")


def _agent_result(profile: dict, article: NewsArticle):
    from ai.agent import INTERPRET_MODEL, run_agent

    article_text = f"{article.title}\n{article.content or article.summary}"
    result = run_agent(profile, str(profile["company_id"]), article.id, article_text)
    result_data = result.model_dump(mode="json")
    bank_items = result_data.get("bank_position", [])
    consequences = result_data.get("consequences", [])
    sources = [{"id": article.id, "type": "news", "title": article.title, "url": article.url}]
    sources.extend({"id": f"bank:{item['source_material']}", "type": "bank_analytics",
                    "title": item["source_material"], "url": None}
                   for item in bank_items if item.get("source_material"))
    payload = {
        "what_happened": result_data.get("what_happened", article.title),
        "why_it_matters": result_data.get("why_important", ""),
        "risks": [{"description": row.get("description", ""), "confidence": row.get("confidence"),
                   "evidence_ids": [article.id]} for row in consequences if row.get("type") == "risk"],
        "opportunities": [{"description": row.get("description", ""), "confidence": row.get("confidence"),
                           "evidence_ids": [article.id]} for row in consequences if row.get("type") == "opportunity"],
        "next_steps": result_data.get("next_actions", []),
        "bank_position": {"text": "\n".join(item.get("text", "") for item in bank_items) or None,
                          "source_ids": list(dict.fromkeys(f"bank:{item['source_material']}" for item in bank_items
                                                           if item.get("source_material")))},
        "ai_conclusion": "\n".join(result_data.get("ai_conclusions", [])),
        "sources": sources,
        "company_factors": result_data.get("company_factors", []),
        "uncertainties": result_data.get("data_limitations", []) + result_data.get("assumptions", []),
        "trace_id": str(uuid4()),
    }
    trace = {"trace_id": payload["trace_id"],
             "steps": result_data.get("agent_trace", []), "sources": sources,
             "matched_factors": payload["company_factors"], "validation_status": "passed",
             "agent_result": result_data, "article_text": article_text}
    return payload, trace, INTERPRET_MODEL


def create_insight(db: Session, company: Company, article: NewsArticle, role: str,
                   *, profile_data: dict | None = None, relevance: dict | None = None):
    existing = db.scalar(select(Insight).where(Insight.company_id == company.id,
        Insight.article_id == article.id, Insight.user_role == role).order_by(Insight.created_at.desc()))
    if existing and existing.validation_status == "passed":
        return existing
    profile = profile_data or profile_from_company(company, role)
    ranked = db.scalar(select(FeedScore).where(FeedScore.company_id == company.id, FeedScore.article_id == article.id))
    ranked = ranked or FeedScore(company_id=company.id, article_id=article.id,
        relevance_score=score_article(company, article, role)[0], relevance_reasons=score_article(company, article, role)[1],
        matched_factors=score_article(company, article, role)[2])
    relevance = relevance or {"relevance_reasons": ranked.relevance_reasons or [],
                              "matched_factors": ranked.matched_factors or []}
    status, model = "unavailable", None
    try:
        payload, trace, model = _agent_result(profile, article)
        payload.setdefault("what_happened", article.summary or article.title)
        payload.setdefault("why_it_matters", "")
        payload.setdefault("risks", [])
        payload.setdefault("opportunities", [])
        payload.setdefault("next_steps", [])
        payload.setdefault("bank_position", {"text": None, "source_ids": []})
        payload.setdefault("ai_conclusion", "")
        payload.setdefault("sources", [{"id": article.id, "type": "news", "title": article.title, "url": article.url}])
        payload.setdefault("company_factors", relevance.get("matched_factors", []))
        payload.setdefault("uncertainties", [])
        payload.setdefault("trace_id", trace.get("trace_id", str(uuid4())))
        trace.setdefault("trace_id", payload["trace_id"])
        trace.setdefault("sources", payload["sources"])
        trace.setdefault("matched_factors", relevance.get("matched_factors", []))
        trace["ml_ranking"] = {key: relevance.get(key) for key in (
            "relevance_score", "relevance_reasons", "matched_factors", "factor_values",
            "factor_contributions", "algorithm_version", "business_match") if key in relevance}
        status = "passed"
    except Exception as exc:
        from ai.llm_client import LLMConfigurationError

        if isinstance(exc, LLMConfigurationError):
            logger.warning("AI provider is not configured company_id=%s article_id=%s", company.id, article.id)
            user_uncertainty = (
                "AI-провайдер не настроен. Добавьте LLM_API_KEY и LLM_BASE_URL в .env "
                "и перезапустите приложение."
            )
            conclusion = "Подключите AI-провайдера, чтобы получить автоматический разбор новости."
        else:
            logger.exception("Agent analysis failed company_id=%s article_id=%s", company.id, article.id)
            user_uncertainty = "AI-анализ не завершён. Попробуйте позже."
            conclusion = "AI-анализ временно недоступен. Этот ответ не является аналитикой Альфа-Банка."
        trace_id = str(uuid4())
        payload = {"what_happened": article.summary or article.title,
            "why_it_matters": "Оценка ML: " + "; ".join(relevance.get("relevance_reasons", [])),
            "risks": [], "opportunities": [],
            "next_steps": ["Проверить первоисточник и влияние на планы компании"],
            "bank_position": {"text": None, "source_ids": []},
            "ai_conclusion": conclusion,
            "sources": [{"id": article.id, "type": "news", "title": article.title, "url": article.url}],
            "company_factors": relevance.get("matched_factors", []),
            "uncertainties": [user_uncertainty],
            "trace_id": trace_id}
        trace = {"trace_id": trace_id, "steps": [{"step": "agent", "ok": False,
                 "output_summary": type(exc).__name__}], "sources": payload["sources"],
                 "matched_factors": payload["company_factors"], "validation_status": status}
    insight = existing or Insight(id=str(uuid4()), company_id=company.id, article_id=article.id, user_role=role)
    insight.payload = payload
    insight.model_name = model
    insight.validation_status = status
    insight.trace = trace
    db.add(insight); db.commit(); db.refresh(insight)
    return insight


def answer_question(db: Session, insight: Insight, question: str):
    answer = None
    agent_result = insight.trace.get("agent_result")
    if agent_result:
        try:
            from ai.ask import ask
            from ai.schemas import Insight as AgentInsight

            article = db.get(NewsArticle, insight.article_id)
            news_text = insight.trace.get("article_text") or (article.title + "\n" + (article.content or ""))
            result = ask(AgentInsight.model_validate(agent_result), news_text, question)
            if result.get("ok"):
                answer = result["answer"]
        except Exception:
            answer = None
    if answer is None:
        answer = ("В сохранённом анализе указано: " + str(insight.payload.get("why_it_matters", "")) +
                  " Основание: исходная новость и перечисленные признаки компании. "
                  "Подтверждённой аналитики банка в этом анализе нет.")
    row = InsightQuestion(insight_id=insight.id, question=question, answer=answer)
    db.add(row); db.commit(); db.refresh(row)
    return row
