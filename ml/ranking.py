# Ранжирует новости для компании и объясняет оценки.
import math
from datetime import datetime, timezone

from ml.config import ALGORITHM_VERSION, GEOGRAPHY, ROLE_TOPICS, WEIGHTS
from ml.deduplication import group_news
from ml.news_processing import mentions, parse_datetime, process_news


def rank_news(company_profile, articles, *, now=None, weights=None, deduplicate=True):
    profile = company_profile
    if not profile.get("company_id") or profile.get("user_role", "ceo") not in ROLE_TOPICS:
        raise ValueError("Profile needs company_id and ceo/cfo role")
    selected = dict(WEIGHTS if weights is None else weights)
    if set(selected) != set(WEIGHTS) or any(not isinstance(w, (float, int)) or not math.isfinite(w) or w < 0 for w in selected.values()) or not math.isclose(sum(selected.values()), 1.):
        raise ValueError("Weights must cover all seven factors, be finite/nonnegative and sum to one")
    now = parse_datetime(now) if now is not None else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("Invalid reference time")
    processed = group_news(articles) if deduplicate else [process_news(a) for a in articles]
    results = []
    for article in processed:
        factors = dict.fromkeys(WEIGHTS, 0.)
        evidence, reasons, matched = [], [], []
        topics = set(article["categories"])
        text = (article["title"] + " " + article["content"]).casefold()
        def add(factor, value, field, reason):
            factors[factor] = max(factors[factor], value)
            matched.append(field)
            reasons.append(reason)
            evidence.append({"factor": factor, "company_field": field,
                             "company_value": profile.get(field), "article_id": article["id"],
                             "source_type": "news" if factor == "freshness" else "company_profile",
                             "mechanism": article["mechanisms"], "reason": reason})
        common = set(profile.get("industry_tags") or []) & set(article["industry_tags"])
        if common:
            add("industry", 1., "industry_tags", "Тема соответствует отрасли по ОКВЭД/виду деятельности: " + ", ".join(sorted(common)))
        elif profile.get("industry") and mentions(text, str(profile["industry"]).casefold()):
            add("industry", 1., "industry", "В тексте упомянут вид деятельности компании")
        products = (("has_loans", {"monetary_policy"}, "Кредитный продукт: потенциальная связь со стоимостью финансирования"),
                    ("has_leasing", {"monetary_policy"}, "Лизинговый продукт: проверить условия финансирования"),
                    ("has_deposits", {"monetary_policy"}, "Депозитный продукт: возможная связь с процентными условиями"),
                    ("has_factoring", {"monetary_policy", "logistics_trade"}, "Факторинг: проверить оборотное финансирование и расчеты"),
                    ("has_guarantees", {"tax_regulation", "corporate_events"}, "Банковская гарантия: проверить требования и обязательства"),
                    ("has_foreign_trade", {"currency", "logistics_trade"}, "Признак ФТС: проверить актуальность ВЭД и валютных контрактов"))
        for field, relevant, reason in products:
            if profile.get(field) is True and topics & relevant:
                add("finance", 1., field, reason)
        canonical_geo = {name.casefold(): name for name in GEOGRAPHY}
        for field in ("region", "city"):
            place = profile.get(field)
            place_key = canonical_geo.get(str(place).casefold(), place)
            terms = GEOGRAPHY.get(place_key, (str(place).casefold(),)) if place else ()
            if any(mentions(text, t) for t in terms):
                add("geography", 1., field, f"Упомянута география компании: {place}")
        for country in profile.get("trade_countries") or []:
            country_key = canonical_geo.get(country.casefold(), country)
            if any(mentions(text, t) for t in GEOGRAPHY.get(country_key, (country.casefold(),))):
                add("geography", 1., "trade_countries", f"Упомянута страна из данных ФТС: {country}")
        participants = set(article["participants"])
        for field in ("counterparty_ids", "group_company_ids", "linked_company_ids"):
            common_ids = participants & set(profile.get(field) or [])
            if common_ids:
                add("relations", 1., field, "Упомянута подтвержденная связь из таблиц: " + ", ".join(sorted(common_ids)))
        if str(profile["company_id"]) in participants:
            add("relations", 1., "company_id", "В новости явно указан синтетический ID компании")
        if any(factors[k] for k in ("industry", "finance", "geography", "relations")) and topics:
            add("event", 1., "company_id", "Найден экономический механизм и связь с доступным признаком компании")
        date = parse_datetime(article.get("published_at"))
        age = (now - date).total_seconds() / 86400 if date else None
        if age is not None and age >= 0:
            add("freshness", math.exp(-age / 14), "published_at", "Актуальность с учетом даты публикации (полупериод около 10 дней)")
        priority = topics & ROLE_TOPICS[profile.get("user_role", "ceo")]
        if priority:
            add("role", 1., "user_role", "Тема входит в приоритеты роли " + profile.get("user_role", "ceo").upper())
        contributions = {k: round(selected[k] * factors[k], 6) for k in selected}
        results.append({**article, "company_id": profile["company_id"],
                        "relevance_score": round(sum(contributions.values()), 6),
                        "relevance_reasons": list(dict.fromkeys(reasons)) or ["Подтвержденная связь с бизнесом не найдена"],
                        "matched_factors": list(dict.fromkeys(matched)), "factor_values": factors,
                        "factor_contributions": contributions, "evidence": evidence,
                        "algorithm_version": ALGORITHM_VERSION,
                        "business_match": any(factors[k] > 0 for k in ("industry", "finance", "geography", "relations"))})
    return sorted(results, key=lambda r: (-r["relevance_score"], r["article_id"]))
