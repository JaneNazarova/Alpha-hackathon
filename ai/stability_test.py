"""Проверка устойчивости: два независимых запуска агента без кэша на одних данных."""
import re

from ai.agent import run_agent
from ai.test_data import PROFILES, NEWS

RUNS = 2
PROFILE = "A_loans_oil"
NEWS_ID = "news_rate"

# Фразы, которые правило 15 запрещает в what_happened, если их нет в новости.
FORBIDDEN_IN_EVENT = ["по оценке", "ожида", "по итогам", "не меняя", "не изменив",
                      "предыдущ", "ранее", "без изменений", "стоимость денег", "в экономике"]


def _numbers(items):
    """Все числа из списка строк: ставки, проценты, годы. Сравниваем по ним, а не по словам."""
    return sorted({n for text in items for n in re.findall(r"\d+(?:[.,]\d+)?", text)})


def main():
    results = []
    for i in range(RUNS):
        r = run_agent(PROFILES[PROFILE], company_id=PROFILE, news_id=NEWS_ID,
                      news_text=NEWS[NEWS_ID], use_cache=False)
        results.append({
            "what_happened": r.what_happened,
            "bank_position": [b.text for b in r.bank_position],
        })
        print(f"\nЗапуск {i + 1}:")
        print("  what_happened:", r.what_happened)
        print("  bank_position:", results[-1]["bank_position"])

    same_event_text = results[0]["what_happened"] == results[1]["what_happened"]
    same_event_facts = _numbers([results[0]["what_happened"]]) == _numbers([results[1]["what_happened"]])
    same_bank_text = results[0]["bank_position"] == results[1]["bank_position"]
    same_bank_facts = _numbers(results[0]["bank_position"]) == _numbers(results[1]["bank_position"])

    print("\nСравнение по тексту:")
    print("  what_happened совпадает:", same_event_text)
    print("  bank_position совпадает:", same_bank_text)

    print("\nСравнение по фактам (числа):")
    print("  числа в what_happened совпадают:", same_event_facts)
    print("  числа в bank_position совпадают:", same_bank_facts)

    print("\nПравило 15 (запрещённые фразы в what_happened):")
    for i, res in enumerate(results, 1):
        found = [p for p in FORBIDDEN_IN_EVENT if p in res["what_happened"].casefold()]
        print(f"  Запуск {i}: {'нарушений нет' if not found else 'найдено: ' + ', '.join(found)}")


if __name__ == "__main__":
    main()