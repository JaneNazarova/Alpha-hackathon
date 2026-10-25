import json
from pathlib import Path

from pydantic import ValidationError

from ai.llm_client import chat
from ai.prompts import build_messages
from ai.schemas import LLMInsight
from ai.test_data import PROFILES, NEWS, BANK_FRAGMENTS
from ai.validation import validate_insight, print_issues
from ai.parsing import parse_insight

MODEL = "z-ai/glm-5.3-flash"
RESULTS = Path("results")


def parse_insight(raw: str):
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


def run_one(profile_name, news_id):
    messages = build_messages(
        PROFILES[profile_name], news_id, NEWS[news_id], BANK_FRAGMENTS.get(news_id)
    )
    note = f"{news_id}/{profile_name}"

    res = chat(MODEL, messages, max_tokens=6000, note=note)
    insight, err = parse_insight(res["content"])
    if insight is None:
        print(f"  Ответ не прошёл схему, повтор с большим лимитом. Ошибка: {err[:200]}")
        res = chat(MODEL, messages, max_tokens=10000, use_cache=False, note=note + " retry")
        insight, err = parse_insight(res["content"])

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{news_id}__{profile_name}.json"
    out.write_text(json.dumps(
        {"finish_reason": res["finish_reason"], "usage": res["usage"],
         "parsed": insight.model_dump() if insight else None, "error": err,
         "raw": res["content"]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return insight, res, err


def main():
    for news_id in NEWS:
        for profile_name in PROFILES:
            print(f"\n=== {news_id} | {profile_name} ===")
            try:
                insight, res, err = run_one(profile_name, news_id)
            except Exception as e:
                print("Ошибка запроса:", e)
                continue

            u = res["usage"]
            print("finish_reason:", res["finish_reason"],
                  "| токены вход/выход:", u.get("prompt_tokens"), "/", u.get("completion_tokens"))
            if insight is None:
                print("Не прошёл схему:", err[:300])
                continue

            print("Что произошло:", insight.what_happened)
            print("Почему важно:", insight.why_important)
            print("Риски:", [c.description for c in insight.consequences if c.type == "risk"])
            print("Возможности:", [c.description for c in insight.consequences if c.type == "opportunity"])
            print("Позиция банка:", [b.text for b in insight.bank_position])
            print("Ограничения данных:", insight.data_limitations)

            issues = validate_insight(
                insight,
                news_id=news_id,
                news_text=NEWS[news_id],
                bank_fragments=BANK_FRAGMENTS.get(news_id),
                missing_fields=PROFILES[profile_name].get("missing_fields"),
            )
            print_issues(issues)


if __name__ == "__main__":
    main()
    