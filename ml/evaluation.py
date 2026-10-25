# Считает метрики ранжирования и сравнивает их с сортировкой по дате.
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from time import perf_counter

from ml.company_profile import build_company_profile
from ml.config import ALGORITHM_VERSION, WEIGHTS
from ml.deduplication import group_news
from ml.news_processing import process_news
from ml.ranking import rank_news


def metrics(ranked_ids, labels, k=5):
    if k < 1 or len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError("k must be positive and ranked ids unique")
    if any(not isinstance(v, int) or not 0 <= v <= 3 for v in labels.values()):
        raise ValueError("Labels must be integer grades in [0,3]")
    if any(i not in labels for i in ranked_ids):
        raise ValueError("Missing relevance labels")
    grades = [labels[i] for i in ranked_ids[:k]]
    hits = sum(g >= 2 for g in grades)
    relevant = sum(g >= 2 for g in labels.values())
    def dcg(items):
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(items))
    ideal = dcg(sorted(labels.values(), reverse=True)[:k])
    return {f"precision@{k}": hits / k, f"recall@{k}": hits / relevant if relevant else 0.,
            f"ndcg@{k}": dcg(grades) / ideal if ideal else 0.}


def evaluate(dataset):
    articles = dataset["articles"]
    now = dataset["reference_time"]
    rows, examples, durations = [], [], []
    profiles_ok, news_ok = 0, 0
    for article in articles:
        process_news(article)
        news_ok += 1
    baseline = sorted(articles, key=lambda a: (a.get("published_at") or "", a["id"]), reverse=True)
    for company in dataset["companies"]:
        company_id = company["SYNTHETIC_U"]
        profile = build_company_profile(company_id, dataset.get("user_role", "ceo"), companies=dataset["companies"])
        profiles_ok += 1
        labels = dataset["labels"][company_id]
        if set(labels) != {a["id"] for a in articles}:
            raise ValueError("Every company/news pair must be explicitly labeled")
        start = perf_counter()
        ranked = rank_news(profile, articles, now=now, deduplicate=False)
        durations.append((perf_counter() - start) * 1000)
        rows.append({"company_id": company_id, "personalized": metrics([a["id"] for a in ranked], labels),
                     "date_baseline": metrics([a["id"] for a in baseline], labels)})
        examples.append({"company_id": company_id, "top5": [{"id": a["id"],
            "score": a["relevance_score"], "grade": labels[a["id"]]}
            for a in ranked[:5]], "baseline_top5": [a["id"] for a in baseline[:5]]})
    aggregates = {method: {key: round(statistics.mean(r[method][key] for r in rows), 6)
                           for key in rows[0][method]} for method in ("personalized", "date_baseline")}
    grouped = group_news(articles)
    return {"algorithm_version": ALGORITHM_VERSION, "weights": WEIGHTS, "reference_time": now,
            "dataset_kind": dataset["kind"], "labeling": dataset["labeling"],
            "companies": len(rows), "articles": len(articles), "pairs": len(rows)*len(articles),
            "macro_metrics": aggregates, "per_company": rows, "comparisons": examples,
            "profile_success_rate": profiles_ok / len(dataset["companies"]),
            "processing_success_rate": news_ok / len(articles),
            "duplicate_fraction": 1 - len(grouped) / len(articles),
            "ranking_ms_mean": round(statistics.mean(durations), 3),
            "limitations": ["Synthetic author labels; no independent expert assessment or production quality claim.",
                            "Dataset is a smoke/regression benchmark, not a statistically independent test set.",
                            "Latency includes processing; hardware-dependent; event grouping is quadratic."]}


def main():
    parser = argparse.ArgumentParser(description='Offline graded retrieval metrics, chronological baseline and final reports.')
    parser.add_argument("--dataset", required=True, help="Explicit labeled dataset; no demo data is loaded automatically")
    parser.add_argument("--output", required=True, help="Where to save the evaluation report")
    args = parser.parse_args()
    raw = Path(args.dataset).read_bytes()
    result = evaluate(json.loads(raw))
    result["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["macro_metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
