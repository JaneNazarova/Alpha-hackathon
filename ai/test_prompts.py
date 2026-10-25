from ai.prompts import build_messages

profile = {
    "industry": "Производство нефтепродуктов",
    "okved_code": "19.20",
    "industry_tags": ["oil_refining"],
    "region": "Самарская область",
    "revenue": 120_000_000_000,
    "is_large_business": True,
    "has_loans": True,
    "has_leasing": False,
    "missing_fields": ["company_age"],
    "uncertainties": ["Market share is unknown."],
}

news = "Ключевая ставка ЦБ РФ сохранена на уровне 14,0%."

messages = build_messages(profile, "news_001", news)
print(messages[1]["content"])
print("Символов в запросе:", len(messages[0]["content"]) + len(messages[1]["content"]))