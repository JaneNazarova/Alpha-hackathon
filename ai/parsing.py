from pydantic import ValidationError

from ai.schemas import LLMInsight


def parse_insight(raw: str):
    """Возвращает (LLMInsight, None) или (None, текст ошибки)."""
    if not raw or not raw.strip():
        return None, "Пустой ответ модели: скорее всего, не хватило max_tokens на рассуждения"

    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return LLMInsight.model_validate_json(text), None
    except ValidationError as e:
        return None, str(e)