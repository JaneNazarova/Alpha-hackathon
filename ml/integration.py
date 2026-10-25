# Преобразует объекты бэкенда в данные для ML-модуля.
from ml.company_profile import FIELDS, build_company_profile


def company_record(company):
    raw = dict(getattr(company, "metadata_json", None) or {})
    raw["SYNTHETIC_U"] = str(company.id)
    for field, column in FIELDS.items():
        value = getattr(company, field, None)
        if column not in raw and value is not None:
            raw[column] = value
    if "FTS_COUNTRY_NAME" not in raw:
        raw["trade_countries"] = list(getattr(company, "trade_countries", None) or [])
    return raw


def article_record(article):
    fields = ("id", "title", "content", "summary", "source_name", "published_at", "fetched_at")
    row = {f: getattr(article, f, None) for f in fields}
    for field in ("published_at", "fetched_at"):
        if row[field] is not None:
            row[field] = row[field].isoformat()
    row["source_url"] = getattr(article, "url", "")
    return row


def profile_from_company(company, role="ceo", *, peers=(), payments=None, person_links=None):
    records = [company_record(company)] + [company_record(c) for c in peers if c.id != company.id]
    return build_company_profile(str(company.id), role, companies=records, payments=payments, person_links=person_links)
