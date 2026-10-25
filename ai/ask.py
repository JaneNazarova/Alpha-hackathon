import json
import re

from pydantic import BaseModel, Field, ValidationError

from ai.llm_client import chat
from ai.schemas import Insight

ASK_MODEL = "z-ai/glm-5.3-flash"
MAX_TOKENS = 4000

SYSTEM = """Ты отвечаешь на уточняющий вопрос руководителя по уже подготовленной аналитике.

Правила:
1. Используй ТОЛЬКО данные из блоков «Новость» и «Аналитика». Не добавляй новых фактов, цифр, дат и прогнозов.
2. Если ответа нет в данных, напиши «В имеющихся данных ответа нет» и укажи, чего не хватает.
3. Позицию Альфа-Банка приводи только из поля bank_position. Выводы модели помечай как «вывод модели».
4. Ответ короткий: до 5 предложений, без списков.
5. Верни ТОЛЬКО JSON без обёртки: {"answer": "...", "used_fields": ["..."], "insufficient_data": true или false}. Ставь insufficient_data = true только если по существу вопроса в данных нет ответа вообще. Если ответ есть, но с оговорками о неполноте данных, ставь false и пиши оговорки в answer.
"""


class AskAnswer(BaseModel):
    answer: str
    used_fields: list[str] = Field(default_factory=list)
    insufficient_data: bool = False


NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", ".")) for n in NUM_RE.findall(text)}


def _context(insight: Insight, news_text: str) -> str:
    data = insight.model_dump(exclude={"agent_trace", "sources"})
    return f"## Новость\n{news_text}\n\n## Аналитика\n{json.dumps(data, ensure_ascii=False, indent=2)}"


def ask(insight: Insight, news_text: str, question: str) -> dict:
    context = _context(insight, news_text)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"{context}\n\n## Вопрос\n{question}"},
    ]
    res = chat(ASK_MODEL, messages, max_tokens=MAX_TOKENS, note=f"ask/{insight.news_id}")

    raw = res["content"].strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not raw:
        return {"ok": False, "error": "Пустой ответ модели", "finish_reason": res["finish_reason"]}
    try:
        parsed = AskAnswer.model_validate_json(raw)
    except ValidationError as e:
        return {"ok": False, "error": str(e)[:300], "finish_reason": res["finish_reason"]}

    known = _numbers(context + question)
    unverified = sorted(_numbers(parsed.answer) - known)
    return {
        "ok": True,
        "answer": parsed.answer,
        "used_fields": parsed.used_fields,
        "insufficient_data": parsed.insufficient_data,
        "unverified_numbers": unverified,
        "finish_reason": res["finish_reason"],
    }


if __name__ == "__main__":
    from pathlib import Path

    from ai.test_data import NEWS

    insight = Insight.model_validate_json(
        Path("results/agent__news_rate__A_loans_oil.json").read_text(encoding="utf-8")
    )
    questions = [
        "Как ставка повлияет на наши кредиты?",        # ответ есть в данных
        "Каким будет курс доллара на конец 2026 года?"  # ответа в данных нет
    ]
    for q in questions:
        print(f"\nВопрос: {q}")
        print(ask(insight, NEWS["news_rate"], q))