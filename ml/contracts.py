# Описывает и проверяет форматы данных ML-модуля.
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanyProfile(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    schema_version: Literal["1.0"]
    company_id: str = Field(min_length=1)
    user_role: Literal["ceo", "cfo"]
    industry: str | None
    okved_code: str | None
    region: str | None
    city: str | None
    revenue: float | None = Field(ge=0)
    group_id: str | None
    company_age: str | None
    has_loans: bool | None
    has_leasing: bool | None
    has_guarantees: bool | None
    has_deposits: bool | None
    has_factoring: bool | None
    has_foreign_trade: bool | None
    trade_countries: list[str]
    industry_tags: list[str]
    counterparty_ids: list[str] | None
    linked_company_ids: list[str] | None
    group_company_ids: list[str]
    payments: dict[str, Any] | None
    is_large_business: bool | None
    profile_completeness: float = Field(ge=0, le=1)
    known_fields: list[str]
    missing_fields: list[str]
    invalid_fields: list[str]
    field_sources: dict[str, dict[str, str]]
    uncertainties: list[str]


class NewsInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = ""
    summary: str = ""
    source_url: str = ""
    published_at: str | None = None


class NewsFeatures(NewsInput):
    schema_version: Literal["1.0"]
    article_id: str
    category: str
    categories: list[str]
    facts: list[dict[str, Any]]
    participants: list[str]
    industry_tags: list[str]
    geographies: list[str]
    mechanisms: list[str]
    indicators: list[dict[str, str]]
    temporal_context: dict[str, Any]
    processing_status: Literal["processed"]
    content_hash: str
    uncertainties: list[str]


class RankedNews(NewsFeatures):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    company_id: str
    relevance_score: float = Field(ge=0, le=1)
    relevance_reasons: list[str]
    matched_factors: list[str]
    factor_values: dict[str, float]
    factor_contributions: dict[str, float]
    evidence: list[dict[str, Any]]
    algorithm_version: str
    business_match: bool


if __name__ == "__main__":
    from pydantic.json_schema import models_json_schema
    _, schema = models_json_schema([(m, "validation") for m in (CompanyProfile, NewsInput, NewsFeatures, RankedNews)], title="ML contracts v1")
    print(json.dumps(schema, ensure_ascii=False, indent=2))
