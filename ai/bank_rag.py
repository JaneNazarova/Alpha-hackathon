import re

from ai.test_data import BANK_FRAGMENTS

STEM_LEN = 5
STOP = {"банк", "россии", "года", "году"}  # слова, которые есть почти во всех материалах


def _stems(text: str) -> set[str]:
    words = re.findall(r"[а-яa-z0-9]+", text.casefold().replace("ё", "е"))
    return {w[:STEM_LEN] for w in words if len(w) >= 4 and w not in STOP}


def build_corpus() -> list[dict]:
    """Все фрагменты материалов банка. Сейчас тестовые, позже сюда попадут куски из трёх PDF."""
    corpus = []
    for news_id, items in BANK_FRAGMENTS.items():
        for i, item in enumerate(items):
            corpus.append({"id": f"{news_id}:{i}", **item})
    return corpus


def search_bank(query: str, corpus: list[dict], k: int = 3, min_score: int = 2) -> list[dict]:
    """Фрагменты, у которых есть хотя бы min_score общих основ слов с запросом."""
    query_stems = _stems(query)
    scored = []
    for item in corpus:
        score = len(query_stems & _stems(item["text"]))
        if score >= min_score:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return [{"text": it["text"], "source_material": it["source_material"]} for _, it in scored[:k]]