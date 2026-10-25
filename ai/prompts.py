import json

from ai.schemas import LLMInsight

# Смысловые поля профиля, которые уходят в модель.
# Служебные поля (schema_version, field_sources, invalid_fields и т.п.) не передаём:
# они раздувают контекст и увеличивают расход токенов.
PROFILE_FIELDS = [
    "industry", "okved_code", "industry_tags", "region", "city", "revenue",
    "is_large_business", "company_age", "business_stage", "workers_fns",
    "workers_spark", "has_loans", "has_leasing", "has_guarantees",
    "has_deposits", "has_factoring", "has_foreign_trade", "trade_countries",
    "group_company_ids", "counterparty_ids", "payments", "linked_company_ids",
    "role_priorities", "missing_fields", "uncertainties",
]

SCHEMA_JSON = json.dumps(LLMInsight.model_json_schema(), ensure_ascii=False, indent=2)

SYSTEM_PROMPT = """Ты аналитик, который готовит персонализированную интерпретацию новости
для руководителя крупной компании (выручка выше 15 млрд руб.).

Правила:
1. Отвечай ТОЛЬКО одним JSON-объектом по схеме ниже. Без пояснений вне JSON и без Markdown-обёртки.
2. Заполняй ВСЕ поля схемы. Если данных нет, оставляй пустой список или пустую строку и опиши нехватку в data_limitations.
3. Факты (facts) — только то, что прямо написано в тексте новости. Каждый факт сопровождай полем source с идентификатором новости.
4. Предположения (assumptions) отделяй от фактов.
5. Признаки компании используй только из блока «Профиль компании». Значение null означает, что данных нет. Не угадывай его и не подставляй значения по отрасли.
6. Поля из missing_fields считай неизвестными и не делай на них выводов.
7. Поле bank_position заполняй ТОЛЬКО утверждениями, которые есть в блоке «Материалы Альфа-Банка». Если такого утверждения нет, оставь список пустым. Никогда не приписывай банку выводы, которых нет в материалах.
8. Выводы, сделанные тобой, записывай в ai_conclusions, а не в bank_position.
9. Для каждого риска и возможности укажи confidence: high, medium или low, в зависимости от того, насколько сильно это подтверждается данными.
10. В why_important объясни связь события с конкретной компанией, опираясь на её признаки. Не ограничивайся пересказом новости.
11. В next_actions пиши конкретные действия или вопросы для дополнительного анализа, а не общие рекомендации.
12. Ответ компактный: в каждом списке не больше 3 пунктов, каждый пункт — одно предложение.
13. В facts перечисли все факты из новости (события, даты, числа, участники). Если новость содержит числа или даты, facts не может быть пустым.
14. Предположения, прогнозы и выводы никогда не записывай в facts. Они идут в assumptions или ai_conclusions.
15. В what_happened описывай только событие из новости. Не добавляй оценок банка, сравнений с прошлыми решениями и не используй формулировки «по оценке», «ожидает», если их нет в тексте новости.
16. Порог крупного бизнеса (выручка выше 15 млрд руб.) учитывай, но не делай на нём вывод без связи с конкретной новостью.

Схема ответа (JSON Schema):
""" + SCHEMA_JSON


def build_profile_block(profile: dict) -> str:
    """Оставляет только смысловые поля профиля. Отсутствующие значения остаются null."""
    trimmed = {field: profile.get(field) for field in PROFILE_FIELDS}
    return json.dumps(trimmed, ensure_ascii=False, indent=2)


def build_bank_block(bank_fragments: list[dict] | None) -> str:
    """Фрагменты материалов банка с указанием источника. Если их нет, блок пустой."""
    if not bank_fragments:
        return "Материалы Альфа-Банка не переданы. Поле bank_position оставь пустым."
    lines = []
    for item in bank_fragments:
        lines.append(f"- [{item['source_material']}] {item['text']}")
    return "\n".join(lines)


def build_user_prompt(
    profile: dict,
    news_id: str,
    news_text: str,
    bank_fragments: list[dict] | None = None,
) -> str:
    return (
        f"## Профиль компании\n"
        f"{build_profile_block(profile)}\n\n"
        f"## Новость (id: {news_id})\n"
        f"{news_text}\n\n"
        f"## Материалы Альфа-Банка\n"
        f"{build_bank_block(bank_fragments)}\n\n"
        f"Верни JSON по схеме. В каждом fact.source укажи id новости: {news_id}."
    )


def build_messages(
    profile: dict,
    news_id: str,
    news_text: str,
    bank_fragments: list[dict] | None = None,
) -> list[dict]:
    """Список сообщений в формате OpenAI-совместимого chat API."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(profile, news_id, news_text, bank_fragments)},
    ]