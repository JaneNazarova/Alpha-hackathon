from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models import Company, FeedScore, NewsArticle
from backend.services.news import classify


ROLE_WEIGHTS = {"ceo": {"macroeconomics": .12, "corporate_events": .12}, "cfo": {"monetary_policy": .12, "currency": .12}}


def company_profile(company: Company, role: str = "ceo") -> dict:
    fields = ["industry", "region", "revenue", "has_loans", "has_leasing", "has_guarantees", "has_foreign_trade"]
    known = [field for field in fields if getattr(company, field) is not None]
    return {"company_id": company.id, "industry": company.industry, "okved_code": company.okved_code,
        "region": company.region, "city": company.city, "revenue": company.revenue,
        "has_loans": company.has_loans, "has_leasing": company.has_leasing,
        "has_guarantees": company.has_guarantees, "has_foreign_trade": company.has_foreign_trade,
        "trade_countries": company.trade_countries or [], "group_id": company.group_id,
        "user_role": role, "profile_completeness": round(len(known) / len(fields), 2),
        "known_fields": known, "missing_fields": [field for field in fields if field not in known]}


def score_article(company: Company, article: NewsArticle, role: str):
    text = f"{article.title} {article.summary} {article.content}".lower()
    category, factors = classify(text)
    score, reasons, matched = 0.0, [], []
    if company.industry and company.industry.lower() in text:
        score += .35; reasons.append(f"Тема связана с отраслью компании: {company.industry}"); matched.append("industry")
    finance_terms = {"monetary_policy": ("has_loans", company.has_loans, ["ставк", "кредит", "финансир"]),
                     "currency": ("has_foreign_trade", company.has_foreign_trade, ["валют", "рубл", "курс", "экспорт", "импорт"]),
                     "commodities": ("has_leasing", company.has_leasing, ["сырь", "нефт", "газ", "золот"])}
    for cat, (field, value, terms) in finance_terms.items():
        if cat in factors and value is True:
            score += .25; reasons.append("Событие может влиять на указанный финансовый признак компании"); matched.extend([field, cat]); break
    if company.region and company.region.lower() in text:
        score += .15; reasons.append(f"Упомянут регион компании: {company.region}"); matched.append("region")
    now = datetime.now(timezone.utc)
    published = article.published_at
    if published and published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    if published and (now - published).days <= 14:
        score += .10; reasons.append("Недавняя публикация"); matched.append("freshness")
    score += ROLE_WEIGHTS.get(role, {}).get(category, .05)
    if category in ROLE_WEIGHTS.get(role, {}):
        reasons.append("Тема соответствует приоритетам роли " + role.upper()); matched.append("user_role")
    if not reasons:
        reasons.append("Новость доступна в общей ленте; данных для подтверждения специфической связи недостаточно")
    return min(1.0, round(score, 3)), reasons, list(dict.fromkeys(matched))


def refresh_scores(db: Session, company: Company):
    for article in db.scalars(select(NewsArticle)).all():
        score, reasons, factors = score_article(company, article, "ceo")
        row = db.scalar(select(FeedScore).where(FeedScore.company_id == company.id, FeedScore.article_id == article.id))
        if row is None:
            row = FeedScore(company_id=company.id, article_id=article.id)
        row.relevance_score, row.relevance_reasons, row.matched_factors = score, reasons, factors
        db.add(row)
    db.commit()
