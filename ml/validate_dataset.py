# Проверяет профили всех компаний и явно переданные новости.
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ml.contracts import CompanyProfile, RankedNews
from ml.config import ALGORITHM_VERSION
from ml.dataset import CompanyDataset
from ml.ranking import rank_news


def validate(dataset, news=None, now=None):
    if news is not None and (not isinstance(news, list) or not news):
        raise ValueError("news must be a nonempty list of article mappings")
    start = perf_counter()
    successes, errors = 0, []
    completeness = 0.
    invalid, missing = Counter(), Counter()
    examples = {}
    for company_id in dataset.companies:
        if company_id in dataset.duplicate_ids:
            errors.append({"company_id": company_id, "code": "ambiguous_duplicate_id"})
            continue
        try:
            profile = dataset.profile(company_id)
            CompanyProfile.model_validate(profile)
        except (ValueError, KeyError) as exc:
            errors.append({"company_id": company_id, "code": type(exc).__name__})
            continue
        successes += 1
        completeness += profile["profile_completeness"]
        invalid.update(profile["invalid_fields"])
        missing.update(profile["missing_fields"])
        for sector in profile["industry_tags"] if news is not None else ():
            if sector not in examples or (profile["is_large_business"] and not examples[sector]["is_large_business"]):
                examples[sector] = profile
    comparisons = []
    for sector in ("manufacturing", "retail", "agriculture") if news is not None else ():
        selected = examples.get(sector)
        if not selected:
            continue
        company_id = selected["company_id"]
        for role in ("ceo", "cfo"):
            profile = dataset.profile(company_id, role)
            ranked = rank_news(profile, news, now=now)
            for row in ranked:
                RankedNews.model_validate(row)
            comparisons.append({"sector": sector, "company_id": company_id, "role": role,
                "is_large_business": profile["is_large_business"],
                "top5": [{"article_id": r["id"], "score": r["relevance_score"]} for r in ranked[:5]]})
    total = len(dataset.companies)
    return {"algorithm_version": ALGORITHM_VERSION, "input_company_rows": dataset.row_count, "unique_ids": total,
        "valid_profiles": successes, "profile_success_rate": successes/total if total else 0.,
        "ambiguous_ids": sorted(dataset.duplicate_ids), "errors": errors,
        "ambiguous_records": {key: {"rows": value["rows"], "conflicting_columns": sorted(value["conflicting_columns"])}
                              for key, value in dataset.duplicate_details.items()},
        "payment_rows": dataset.payment_rows, "person_link_rows": dataset.link_rows,
        "mean_completeness": completeness/successes if successes else 0.,
        "invalid_field_counts": dict(invalid),
        "missing_field_counts": dict(missing), "validation_seconds": round(perf_counter()-start, 3),
        "comparisons": comparisons,
        "news_evaluation": {"status": "provided_news_ranked" if news is not None else "not_run",
                            "article_count": len(news) if news is not None else 0,
                            "reference_time": now,
                            "reason": "No relevance labels supplied; only rankings checked." if news is not None
                            else "No news corpus supplied; no sample articles substituted."},
        "limitations": ["Profile validation does not measure news relevance.",
                        "No relevance metric on organizer profiles without independently labeled real news.",
                        "Ambiguous duplicate IDs are rejected, not silently merged or assigned arbitrary attributes.",
                        "Source tables are read only; supplied payments have unknown period/currency coverage."]}


def main():
    parser = argparse.ArgumentParser(description='Validate organizer profiles; optionally rank explicitly supplied news.')
    parser.add_argument("--companies", required=True)
    parser.add_argument("--payments")
    parser.add_argument("--person-links")
    parser.add_argument("--articles", help="Optional JSON file containing a nonempty list of news articles")
    parser.add_argument("--reference-time", help="Optional ISO-8601 reference time for reproducible news ranking")
    parser.add_argument("--output", required=True, help="Where to save the validation result")
    args = parser.parse_args()
    if args.reference_time and not args.articles:
        parser.error("--reference-time requires --articles")
    start = perf_counter()
    dataset = CompanyDataset.from_csv(args.companies, args.payments, args.person_links)
    index_seconds = perf_counter()-start
    news = json.loads(Path(args.articles).read_text(encoding="utf-8")) if args.articles else None
    reference_time = (args.reference_time or datetime.now(timezone.utc).isoformat()) if news is not None else None
    result = validate(dataset, news, reference_time)
    result["index_seconds"] = round(index_seconds, 3)
    result["input_files"] = dict(dataset.sources)
    if args.articles:
        result["input_files"]["articles"] = args.articles
    result["input_sha256"] = {}
    for key, path in dataset.sources.items():
        if path:
            with Path(path).open("rb") as source:
                result["input_sha256"][key] = hashlib.file_digest(source, "sha256").hexdigest()
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("unique_ids", "valid_profiles", "ambiguous_ids", "index_seconds", "validation_seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
