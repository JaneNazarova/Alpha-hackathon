import csv
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models import Company


def _bool(value):
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "да", "y"}


def _float(value):
    try:
        return float(str(value).replace(" ", "").replace(",", ".")) if value not in (None, "") else None
    except ValueError:
        return None


def import_company_csv(db: Session, path: Path) -> int:
    """Import organizer CSV while preserving synthetic IDs and unknown values."""
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
        delimiter = ";" if ";" in first_line else ","
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            normalized = {str(k).strip().upper(): v for k, v in row.items() if k}
            company_id = normalized.get("SYNTHETIC_U")
            if not company_id:
                continue
            record = db.get(Company, company_id) or Company(id=company_id)
            record.industry = normalized.get("MAINOKVED_NAME") or record.industry
            record.okved_code = normalized.get("MAINOKVED_CODE") or record.okved_code
            record.region = normalized.get("REGION") or record.region
            record.city = normalized.get("CITY") or record.city
            record.revenue = _float(normalized.get("REVENUE_COMPANY"))
            record.group_id = normalized.get("GROUP_ID") or None
            record.has_loans = _bool(normalized.get("CL_PRODUCT_LOA_MARK"))
            record.has_leasing = _bool(normalized.get("CL_PRODUCT_LEA_MARK"))
            record.has_guarantees = _bool(normalized.get("CL_PRODUCT_GAR_MARK"))
            record.has_foreign_trade = _bool(normalized.get("FTS_FLAG"))
            country = normalized.get("FTS_COUNTRY_NAME")
            record.trade_countries = [country] if country else []
            record.metadata_json = normalized
            db.add(record)
            count += 1
    db.commit()
    return count


def seed_demo_companies(db: Session):
    if db.scalar(select(Company.id).limit(1)):
        return
    db.add_all([
        Company(id="SYNTHETIC_U_001", industry="Производство", okved_code="25.11", region="Москва", city="Москва", revenue=850_000_000, group_id="GROUP_A", has_loans=True, has_leasing=True, has_guarantees=None, has_foreign_trade=True, trade_countries=["Китай"]),
        Company(id="SYNTHETIC_U_002", industry="Розничная торговля", okved_code="47.19", region="Санкт-Петербург", city="Санкт-Петербург", revenue=120_000_000, group_id=None, has_loans=False, has_leasing=None, has_guarantees=True, has_foreign_trade=False, trade_countries=[]),
        Company(id="SYNTHETIC_U_003", industry="Сельское хозяйство", okved_code="01.11", region="Краснодарский край", city="Краснодар", revenue=None, group_id="GROUP_C", has_loans=None, has_leasing=True, has_guarantees=None, has_foreign_trade=True, trade_countries=["Турция"]),
    ])
    db.commit()
