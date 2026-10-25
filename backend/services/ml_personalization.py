"""Application adapter for the team's indexed ML dataset and ranking pipeline."""
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import Company, NewsArticle
from ml.dataset import CompanyDataset
from ml.integration import article_record
from ml.ranking import rank_news


def load_company_dataset() -> CompanyDataset | None:
    settings = get_settings()
    paths = (settings.companies_csv_path, settings.payments_csv_path, settings.person_links_csv_path)
    signature = []
    for raw_path in paths:
        try:
            stat = Path(raw_path).stat()
            signature.append((raw_path, stat.st_mtime_ns, stat.st_size))
        except OSError:
            signature.append((raw_path, None, None))
    return _load_company_dataset(paths, tuple(signature))


@lru_cache(maxsize=1)
def _load_company_dataset(paths: tuple[str, ...], signature: tuple[tuple[str, int | None, int | None], ...]) -> CompanyDataset | None:
    del signature  # File metadata is part of the cache key and invalidates the index after a CSV update.
    companies, payments, person_links = (Path(value) for value in paths)
    if not companies.is_file():
        return None
    return CompanyDataset.from_csv(
        companies,
        payments if payments.is_file() else None,
        person_links if person_links.is_file() else None,
    )


def profile_for_company(dataset: CompanyDataset, company_id: str, role: str = "ceo") -> dict:
    return dataset.profile(str(company_id), role)


def profiles_for_companies(dataset: CompanyDataset, *, query: str | None = None, limit: int = 100) -> list[dict]:
    query_text = query.casefold().strip() if query else None
    profiles = []
    for company_id in sorted(dataset.companies):
        if company_id in dataset.duplicate_ids:
            continue
        row = dataset.companies[company_id]
        if query_text and not any(
            query_text in str(row.get(field) or "").casefold()
            for field in ("SYNTHETIC_U", "MAINOKVED_NAME", "MAINOKVED_CODE", "REGION", "CITY")
        ):
            continue
        profiles.append(dataset.profile(company_id))
        if len(profiles) >= limit:
            break
    return profiles


def rank_articles(dataset: CompanyDataset, company_id: str, role: str,
                  articles: list[NewsArticle], weights: dict[str, float] | None = None) -> list[dict]:
    profile = dataset.profile(str(company_id), role)
    records = [article_record(article) for article in articles]
    return rank_news(profile, records, weights=weights)


def materialize_company(db: Session, dataset: CompanyDataset, company_id: str, role: str = "ceo") -> Company:
    """Persist only the selected anonymized company needed by Insight foreign keys."""
    profile = dataset.profile(str(company_id), role)
    company = db.get(Company, str(company_id))
    if company is None:
        company = Company(id=str(company_id))
    company.industry = profile.get("industry")
    company.okved_code = profile.get("okved_code")
    company.region = profile.get("region")
    company.city = profile.get("city")
    company.revenue = profile.get("revenue")
    company.group_id = profile.get("group_id")
    company.has_loans = profile.get("has_loans")
    company.has_leasing = profile.get("has_leasing")
    company.has_guarantees = profile.get("has_guarantees")
    company.has_foreign_trade = profile.get("has_foreign_trade")
    company.trade_countries = profile.get("trade_countries") or []
    company.metadata_json = dict(dataset.companies[str(company_id)])
    db.add(company)
    db.flush()
    return company
