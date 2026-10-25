"""Cached diagnostics and benchmark reports for the ML personalization pipeline."""
import json
from functools import lru_cache
from pathlib import Path

from backend.config import get_settings
from backend.services.ml_personalization import load_company_dataset
from ml.data_access import iter_csv
from ml.eda import analyze
from ml.evaluation import evaluate
from ml.validate_dataset import validate


def _source_signature(paths: tuple[str, ...]) -> tuple[tuple[str, int | None, int | None], ...]:
    signature = []
    for raw_path in paths:
        path = Path(raw_path)
        try:
            stat = path.stat()
            signature.append((raw_path, stat.st_mtime_ns, stat.st_size))
        except OSError:
            signature.append((raw_path, None, None))
    return tuple(signature)


def get_ml_quality_report() -> dict:
    settings = get_settings()
    paths = (settings.companies_csv_path, settings.payments_csv_path, settings.person_links_csv_path)
    signature = _source_signature(paths)
    return _build_ml_quality_report(paths, signature)


@lru_cache(maxsize=1)
def _build_ml_quality_report(
    paths: tuple[str, ...],
    signature: tuple[tuple[str, int | None, int | None], ...],
) -> dict:
    del signature  # Included in the cache key so edits to a CSV invalidate the report.
    companies_path, payments_path, links_path = (Path(value) for value in paths)
    dataset = load_company_dataset()
    if dataset is None:
        raise FileNotFoundError("Companies CSV is unavailable")

    eda_report = analyze(
        iter_csv(companies_path),
        iter_csv(payments_path) if payments_path.is_file() else None,
        iter_csv(links_path) if links_path.is_file() else None,
    )
    validation_report = validate(dataset)

    evaluation_path = Path(__file__).resolve().parents[2] / "ml" / "fixtures" / "evaluation.json"
    evaluation_dataset = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation_report = evaluate(evaluation_dataset)
    return {
        "algorithm_version": evaluation_report["algorithm_version"],
        "weights": evaluation_report["weights"],
        "sources": dict(dataset.sources),
        "eda": eda_report,
        "validation": validation_report,
        "evaluation": evaluation_report,
    }
