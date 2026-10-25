# Строит профиль компании и рассчитывает её платежи и связи.
import os
import re
from collections import defaultdict

from ml.config import GEOGRAPHY, ROLE_TOPICS, SCHEMA_VERSION, SECTORS
from ml.data_access import boolean, clean, number, read_csv

FIELDS = {
    "industry": "MAINOKVED_NAME", "okved_code": "MAINOKVED_CODE", "region": "REGION",
    "city": "CITY", "revenue": "REVENUE_COMPANY", "group_id": "GROUP_ID",
    "company_age": "COMPANY_AGE_YEARS_GRADATION", "business_stage": "ECO_MARK_LABEL",
    "workers_fns": "AMOUNT_WORKERS_FNS_GRADATION", "workers_spark": "AMOUNT_WORKERS_SPARK_GRADATION",
    "has_loans": "CL_PRODUCT_LOA_MARK", "has_leasing": "CL_PRODUCT_LEA_MARK",
    "has_guarantees": "CL_PRODUCT_GAR_MARK", "has_deposits": "CL_PRODUCT_DEP_MARK",
    "has_factoring": "FACTORING_MARK", "has_foreign_trade": "FTS_FLAG",
}


def _empty_payment_stats():
    return {"incoming_amount": 0., "outgoing_amount": 0., "incoming_count": 0., "outgoing_count": 0.,
            "invalid_or_missing_cells": {}}


def _payment_data(rows, company_ids):
    stats, counterparties, pool = {}, defaultdict(set), {cid: cid for cid in company_ids}
    row_count = self_payments = 0
    for row in rows or ():
        row_count += 1
        payer, payee = clean(row.get("PAYER")), clean(row.get("BENEFICIARY"))
        payer, payee = pool.setdefault(payer, payer), pool.setdefault(payee, payee)
        self_payments += payer is not None and payer == payee
        values = (("amount", number(row.get("PAY_AMT"))), ("count", number(row.get("PAY_CNT"))))
        for cid, other, direction in ((payer, payee, "outgoing"), (payee, payer, "incoming")):
            if cid not in company_ids:
                continue
            if cid not in stats:
                stats[cid] = _empty_payment_stats()
            if other and other != cid:
                counterparties[cid].add(other)
            for suffix, value in values:
                key = f"{direction}_{suffix}"
                if value is None or value < 0 or (suffix == "count" and not value.is_integer()):
                    bad = stats[cid]["invalid_or_missing_cells"]
                    bad[key] = bad.get(key, 0) + 1
                    stats[cid][key] = None
                elif stats[cid][key] is not None:
                    stats[cid][key] += value
    return stats, counterparties, row_count, self_payments


def _company_links(rows, target=None):
    people, links, row_count = defaultdict(set), defaultdict(set), 0
    for row in rows or ():
        row_count += 1
        person, company_id = clean(row.get("SYNTHETIC_F")), clean(row.get("SYNTHETIC_U"))
        if person and company_id:
            people[person].add(company_id)
    for company_ids in people.values():
        for company_id in company_ids:
            if target is None or company_id == target:
                links[company_id].update(company_ids - {company_id})
    return links, row_count


def build_company_profile(company_id, user_role="ceo", *, companies=None, payments=None,
                          person_links=None, csv_path=None):
    if user_role not in ROLE_TOPICS:
        raise ValueError("user_role must be ceo or cfo")
    source = "injected_records"
    if companies is None:
        source = str(csv_path or os.getenv("COMPANIES_CSV_PATH", "data/companies.csv"))
        companies = read_csv(source)
    if isinstance(companies, dict):
        companies = list(companies.values())
    else:
        companies = list(companies)
    def record_id(row):
        return clean(row.get("SYNTHETIC_U", row.get("company_id", row.get("id"))))
    matches = [row for row in companies if record_id(row) == str(company_id)]
    if not matches:
        raise KeyError(f"Unknown company ID: {company_id}")
    if len(matches) > 1:
        raise ValueError(f"Duplicate company ID: {company_id}; resolve duplicates before profiling")
    row = matches[0]
    profile = {"schema_version": SCHEMA_VERSION, "company_id": str(company_id), "user_role": user_role}
    origins, invalid = {}, []
    for field, column in FIELDS.items():
        raw = row.get(column, row.get(field))
        value = boolean(raw) if field.startswith("has_") else number(raw) if field == "revenue" else clean(raw)
        if field == "revenue" and value is not None and value < 0:
            value = None
        if clean(raw) is not None and value is None:
            invalid.append(field)
        profile[field] = value
        origins[field] = {"source": source, "column": column if column in row else field}
    countries = row.get("FTS_COUNTRY_NAME", row.get("trade_countries"))
    countries = ([str(c).strip() for c in countries if clean(c)] if isinstance(countries, list)
                 else [c.strip() for c in re.split(r"[,;|]", clean(countries) or "") if c.strip()])
    canonical = {name.casefold(): name for name in GEOGRAPHY}
    profile["trade_countries"] = list(dict.fromkeys(canonical.get(c.casefold(), c) for c in countries))
    origins["trade_countries"] = {"source": source, "column": "FTS_COUNTRY_NAME"}
    code = (profile["okved_code"] or "").split(".")[0].zfill(2)
    industry = (profile["industry"] or "").casefold()
    sectors = [key for key, spec in SECTORS.items() if code in spec["okved"]]
    profile["industry_tags"] = (sectors if profile["okved_code"] else
        [key for key, spec in SECTORS.items() if any(t in industry for t in spec["terms"])])
    revenue = profile["revenue"]
    profile["is_large_business"] = None if revenue is None else revenue > 15_000_000_000
    origins["is_large_business"] = {"source": "derived", "rule": "revenue > 15 billion RUB (case p.4)"}
    profile["role_priorities"] = sorted(ROLE_TOPICS[user_role])
    group = profile["group_id"]
    profile["group_company_ids"] = sorted({record_id(r) for r in companies
        if group and clean(r.get("GROUP_ID", r.get("group_id"))) == group and record_id(r) != str(company_id)
        and record_id(r)})
    profile["counterparty_ids"] = None
    profile["payments"] = None
    if payments is not None:
        stats, counterparties, _, _ = _payment_data(payments, {str(company_id)})
        profile["payments"] = stats.get(str(company_id), _empty_payment_stats())
        profile["counterparty_ids"] = sorted(counterparties.get(str(company_id), ()))
    profile["linked_company_ids"] = None
    if person_links is not None:
        links, _ = _company_links(person_links, str(company_id))
        profile["linked_company_ids"] = sorted(links.get(str(company_id), ()))
    known = [f for f in FIELDS if profile[f] is not None]
    profile.update(known_fields=known, missing_fields=[f for f in FIELDS if f not in known],
                   profile_completeness=round(len(known) / len(FIELDS), 4), field_sources=origins,
                   invalid_fields=invalid)
    profile["uncertainties"] = ["Products do not establish debt load; FTS_FLAG is not proof of current trade.",
                                "Market share and payment concentration are unknown without market/period coverage."]
    if payments is None:
        profile["uncertainties"].append("Payments table not supplied.")
    if person_links is None:
        profile["uncertainties"].append("Person/company links table not supplied.")
    return profile
