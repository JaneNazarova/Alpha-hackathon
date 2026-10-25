"""Агент: план → инструменты → интерпретация → самопроверка → повтор при жёстких ошибках."""
from pathlib import Path

from ai.bank_rag import build_corpus, search_bank
from ai.llm_client import chat
from ai.parsing import parse_insight
from ai.prompts import build_messages
from ai.schemas import Insight, TraceStep
from ai.validation import validate_insight

CLASSIFY_MODEL = "google/gemma-4-26b-a4b-it"  # простая задача: один ярлык
INTERPRET_MODEL = "z-ai/glm-5.3-flash"        # интерпретация и самопроверка
MAX_REPAIRS = 2                                # не больше двух повторов после первой попытки
TOPICS = ["monetary_policy", "macro_stats", "industry", "company_news", "other"]
MACRO_TERMS = ("ставк", "инфляц", "ввп", "зарплат", "безработ", "курс", "кредит", "бюджет")
RESULTS = Path("results")


def _trace(trace, step, ok, tool=None, inp="", out=""):
    trace.append(TraceStep(step=step, tool=tool, input_summary=str(inp)[:200],
                           output_summary=str(out)[:200], ok=ok))


def _is_hard(issue: str) -> bool:
    """Жёсткие ошибки требуют переделки. Мягкие только логируются."""
    return issue.startswith("bank_position") or "source '" in issue


def make_plan(news_text: str) -> list[str]:
    """Правила планирования без вызова модели."""
    steps = ["load_profile", "classify_news"]
    if any(term in news_text.casefold() for term in MACRO_TERMS):
        steps.append("search_bank")
    return steps + ["interpret", "validate"]


def classify_news(news_text: str, trace: list) -> str:
    system = "Классифицируй новость. Ответь одним словом из списка: " + ", ".join(TOPICS)
    try:
        res = chat(CLASSIFY_MODEL,
                   [{"role": "system", "content": system}, {"role": "user", "content": news_text}],
                   max_tokens=300, note="classify")
        words = res["content"].strip().split()
        word = words[0].strip(".,:;").casefold() if words else ""
        topic = word if word in TOPICS else "other"
        _trace(trace, "classify_news", True, tool=CLASSIFY_MODEL, inp=news_text, out=topic)
        return topic
    except Exception as e:
        _trace(trace, "classify_news", False, tool=CLASSIFY_MODEL, inp=news_text, out=e)
        return "other"


def _repair_message(issues: list[str]) -> str:
    return ("Самопроверка нашла проблемы в ответе:\n"
            + "\n".join("- " + i for i in issues)
            + "\nИсправь их, не меняя смысл остальных полей, и верни полный JSON по схеме.")


def interpret(profile, news_id, news_text, fragments, trace, use_cache=True):
    """Возвращает (insight, мягкие замечания). Бросает исключение, если валидного ответа нет."""
    base = build_messages(profile, news_id, news_text, fragments)
    messages = base
    insight, last_raw, last_issues = None, "", []

    for attempt in range(MAX_REPAIRS + 1):
        res = chat(INTERPRET_MODEL, messages,
                   max_tokens=6000 if attempt == 0 else 10000,
                   use_cache=use_cache and attempt == 0,
                   note=f"{news_id}/agent_try{attempt}")
        last_raw = res["content"]
        parsed, err = parse_insight(last_raw)

        if parsed is None:
            issues = [f"Ответ не прошёл схему JSON: {err[:300]}"]
            _trace(trace, f"interpret_{attempt}", False, tool=INTERPRET_MODEL, out=err)
            hard, soft = issues, []
        else:
            insight = parsed
            issues = validate_insight(parsed, news_id, news_text, fragments,
                                      profile.get("missing_fields"))
            hard = [i for i in issues if _is_hard(i)]
            soft = [i for i in issues if not _is_hard(i)]
            _trace(trace, f"interpret_{attempt}", not hard, tool=INTERPRET_MODEL,
                   out=f"жёстких: {len(hard)}, мягких: {len(soft)}")
            if not hard:
                return insight, soft

        last_issues = issues
        assistant = [{"role": "assistant", "content": last_raw}] if last_raw.strip() else []
        messages = base + assistant + [{"role": "user", "content": _repair_message(hard)}]

    if insight is None:
        raise RuntimeError("Агент не получил валидный ответ после всех попыток")
    return insight, last_issues


def run_agent(profile: dict, company_id: str, news_id: str, news_text: str,
              corpus: list[dict] | None = None, use_cache: bool = True) -> Insight:
    corpus = corpus if corpus is not None else build_corpus()
    trace: list[TraceStep] = []

    plan = make_plan(news_text)
    _trace(trace, "plan", True, out=" → ".join(plan))
    _trace(trace, "load_profile", True, tool="profile", inp=company_id,
           out=f"missing_fields: {profile.get('missing_fields')}")

    topic = classify_news(news_text, trace) if "classify_news" in plan else "other"

    fragments = []
    if "search_bank" in plan:
        fragments = search_bank(news_text, corpus, k=3)
        found = len(fragments)
        _trace(trace, "search_bank", True, tool="bank_rag", inp=news_text,
               out=f"найдено фрагментов: {found}" + ("" if found else " (материалов банка по теме нет)"))
    else:
        _trace(trace, "search_bank", True, tool="bank_rag", out="пропущен по плану: нет макротерминов")

    insight, soft_issues = interpret(profile, news_id, news_text, fragments, trace,
                                     use_cache=use_cache)
    if soft_issues:
        _trace(trace, "soft_issues", True,
               out=f"мягких замечаний: {len(soft_issues)}; {soft_issues[0][:150]}")
    _trace(trace, "topic", True, out=topic)

    used_sources = sorted({bp.source_material for bp in insight.bank_position})
    return Insight(**insight.model_dump(), news_id=news_id, company_id=company_id,
                   sources=[news_id] + used_sources, agent_trace=trace)


if __name__ == "__main__":
    from ai.test_data import PROFILES, NEWS

    RESULTS.mkdir(exist_ok=True)
    for news_id, news_text in NEWS.items():
        for name, profile in PROFILES.items():
            print(f"\n=== {news_id} | {name} ===")
            result = run_agent(profile, company_id=name, news_id=news_id, news_text=news_text)
            print("Что произошло:", result.what_happened)
            print("Позиция банка:", [b.text for b in result.bank_position])
            print("Источники:", result.sources)
            print("Trace:")
            for step in result.agent_trace:
                print(f"  [{'ok' if step.ok else 'FAIL'}] {step.step}: {step.output_summary}")
            (RESULTS / f"agent__{news_id}__{name}.json").write_text(
                result.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")