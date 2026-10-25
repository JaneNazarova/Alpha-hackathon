import re

from ai.schemas import LLMInsight

# Доля слов утверждения, которая должна встречаться в источнике.
# Модель перефразирует, поэтому точное совпадение не требуется.
COVERAGE_THRESHOLD = 0.6
# Выше этого порога вывод AI почти дословно повторяет материал банка.
VERBATIM_THRESHOLD = 0.9


def _tokens(text: str) -> set[str]:
    """Слова от 3 символов и числа с запятой или точкой (14,0 остаётся одним токеном)."""
    words = re.findall(r"[а-яa-z0-9]+(?:[.,][0-9]+)?", text.casefold().replace("ё", "е"))
    return {w for w in words if len(w) >= 3 or any(ch.isdigit() for ch in w)}


def _coverage(claim: str, source: str) -> float:
    """Какая доля слов утверждения встречается в источнике. От 0 до 1."""
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return 0.0
    source_tokens = _tokens(source)
    return len(claim_tokens & source_tokens) / len(claim_tokens)


def _best_coverage(claim: str, sources: list[str]) -> float:
    if not sources:
        return 0.0
    return max(_coverage(claim, s) for s in sources)


def validate_insight(
    insight: LLMInsight,
    news_id: str,
    news_text: str,
    bank_fragments: list[dict] | None = None,
    missing_fields: list[str] | None = None,
) -> list[str]:
    """Возвращает список нарушений. Пустой список означает, что ответ прошёл проверку."""
    issues: list[str] = []
    bank_fragments = bank_fragments or []
    fragment_texts = [f["text"] for f in bank_fragments]
    known_sources = {f["source_material"] for f in bank_fragments}

    # 1. Факты: должны ссылаться на текущую новость и быть в её тексте.
    for i, fact in enumerate(insight.facts):
        if fact.source != news_id:
            issues.append(f"facts[{i}]: source '{fact.source}' не совпадает с id новости '{news_id}'")
        if _coverage(fact.text, news_text) < COVERAGE_THRESHOLD:
            issues.append(f"facts[{i}]: факт не найден в тексте новости: «{fact.text[:80]}»")

    # 2. Позиция банка: только из материалов, с известным источником.
    if insight.bank_position and not bank_fragments:
        issues.append("bank_position заполнен, но материалы банка не переданы")

    for i, bp in enumerate(insight.bank_position):
        if bank_fragments:
            if bp.source_material not in known_sources:
                issues.append(f"bank_position[{i}]: неизвестный источник '{bp.source_material}'")
            if _best_coverage(bp.text, fragment_texts) < COVERAGE_THRESHOLD:
                issues.append(f"bank_position[{i}]: утверждения нет в материалах банка: «{bp.text[:80]}»")

    # 3. Выводы AI не должны выдаваться за позицию банка.
    for i, concl in enumerate(insight.ai_conclusions):
        if fragment_texts and _best_coverage(concl, fragment_texts) >= VERBATIM_THRESHOLD:
            issues.append(
                f"ai_conclusions[{i}]: почти дословно повторяет материал банка, "
                f"проверьте, не должен ли он быть в bank_position: «{concl[:80]}»"
            )

    # 4. Пропуски в профиле должны отражаться в ограничениях.
    if missing_fields and not insight.data_limitations:
        issues.append("в профиле есть missing_fields, но data_limitations пустой")

    return issues


def print_issues(issues: list[str]) -> None:
    if not issues:
        print("Проверка: нарушений нет")
        return
    print(f"Проверка: найдено нарушений: {len(issues)}")
    for item in issues:
        print("  -", item)