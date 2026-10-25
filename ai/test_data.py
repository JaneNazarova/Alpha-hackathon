PROFILES = {
    "A_loans_oil": {
        "industry": "Производство нефтепродуктов", "okved_code": "19.20",
        "industry_tags": ["oil_refining"], "region": "Самарская область", "city": None,
        "revenue": 120_000_000_000, "is_large_business": True,
        "has_loans": True, "has_leasing": False, "has_deposits": True,
        "missing_fields": ["company_age", "market_share"],
        "uncertainties": ["Market share is unknown."],
        "role_priorities": ["revenue", "credit_load"],
    },
    "B_no_loans_retail": {
        "industry": "Торговля розничная продуктами питания", "okved_code": "47.11",
        "industry_tags": ["retail"], "region": "Москва", "city": "Москва",
        "revenue": 18_000_000_000, "is_large_business": True,
        "has_loans": False, "has_leasing": False, "has_deposits": True,
        "missing_fields": ["company_age", "market_share"],
        "uncertainties": ["Market share is unknown."],
        "role_priorities": ["revenue", "consumer_demand"],
    },
    "C_small_no_products": {
        "industry": "Производство мебели", "okved_code": "31.01",
        "industry_tags": ["manufacturing"], "region": "Нижегородская область", "city": "Нижний Новгород",
        "revenue": 3_000_000_000, "is_large_business": False,
        "has_loans": False, "has_leasing": False, "has_deposits": False,
        "missing_fields": ["company_age", "market_share", "trade_countries"],
        "uncertainties": ["Market share is unknown."],
        "role_priorities": ["revenue", "cost_control"],
    },
}

NEWS = {
    "news_rate": "Банк России 11 сентября 2026 года сохранил ключевую ставку на уровне 14,0% годовых.",
    "news_macro": "Росстат: номинальные зарплаты в июне выросли на 9,6% в годовом выражении, безработица составила 2,2%.",
}

BANK_FRAGMENTS = {
    "news_rate": [
        {"source_material": "ALFA-Macro_Insights-Policy_Rate_11Sep.pdf, 11.09.2026",
         "text": "Ставка сохранена на уровне 14,0%; банк ожидает её сохранения до конца 2026 года."},
        {"source_material": "ALFA-Macro_Insights-Policy_Rate_11Sep.pdf, 11.09.2026",
         "text": "Базовая инфляция без туризма с июня по июль выросла с 5,7% до 7,6%."},
    ],
}