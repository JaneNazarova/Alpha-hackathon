# Индексирует таблицы для быстрого получения профилей компаний.
from collections import defaultdict

from ml.company_profile import _company_links, _empty_payment_stats, _payment_data, build_company_profile
from ml.data_access import clean, iter_csv


class CompanyDataset:

    def __init__(self, companies, payments=None, person_links=None, *, sources=None):
        self.sources = sources or {}
        self.companies, self.duplicate_ids = {}, set()
        self.duplicate_details = {}
        self.groups = defaultdict(list)
        self.row_count = 0
        for row in companies:
            self.row_count += 1
            company_id = clean(row.get("SYNTHETIC_U"))
            if company_id is None:
                raise ValueError("Company record has no SYNTHETIC_U")
            if company_id in self.companies:
                self.duplicate_ids.add(company_id)
                detail = self.duplicate_details.setdefault(company_id, {"rows": 1, "conflicting_columns": set()})
                detail["rows"] += 1
                detail["conflicting_columns"].update(k for k in row if row.get(k) != self.companies[company_id].get(k))
            else:
                self.companies[company_id] = row
        for company_id, row in self.companies.items():
            group = clean(row.get("GROUP_ID"))
            if group and company_id not in self.duplicate_ids:
                self.groups[group].append(row)
        self.payments_supplied = payments is not None
        self.payment_stats, self.counterparties, self.payment_rows, self.self_payment_rows = _payment_data(payments, self.companies)
        self.links_supplied = person_links is not None
        self.linked_companies, self.link_rows = _company_links(person_links)

    @classmethod
    def from_csv(cls, companies_path, payments_path=None, person_links_path=None):
        return cls(iter_csv(companies_path), iter_csv(payments_path) if payments_path else None,
                   iter_csv(person_links_path) if person_links_path else None,
                   sources={"companies": str(companies_path), "payments": str(payments_path) if payments_path else None,
                            "person_links": str(person_links_path) if person_links_path else None})

    def profile(self, company_id, user_role="ceo"):
        company_id = str(company_id)
        if company_id in self.duplicate_ids:
            raise ValueError(f"Ambiguous SYNTHETIC_U: {company_id}; duplicated source records require clarification")
        if company_id not in self.companies:
            raise KeyError(f"Unknown company ID: {company_id}")
        row = self.companies[company_id]
        group = clean(row.get("GROUP_ID"))
        profile = build_company_profile(company_id, user_role, companies=self.groups[group] if group else [row])
        for origin in profile["field_sources"].values():
            if origin["source"] == "injected_records":
                origin["source"] = self.sources.get("companies") or "indexed_records"
        if self.payments_supplied:
            stat = self.payment_stats.get(company_id, _empty_payment_stats())
            profile["payments"] = {**stat, "invalid_or_missing_cells": dict(stat["invalid_or_missing_cells"])}
            profile["counterparty_ids"] = sorted(self.counterparties.get(company_id, ()))
            profile["uncertainties"].remove("Payments table not supplied.")
        if self.links_supplied:
            profile["linked_company_ids"] = sorted(self.linked_companies.get(company_id, ()))
            profile["uncertainties"].remove("Person/company links table not supplied.")
        profile["relation_sources"] = {k: self.sources.get(k) for k in ("payments", "person_links")}
        profile["uncertainties"].append("Group membership excludes ambiguous duplicate IDs; payment totals cover only supplied records.")
        return profile
