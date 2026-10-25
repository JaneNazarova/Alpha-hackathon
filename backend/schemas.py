from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class CompanyOut(BaseModel):
    company_id: str
    industry: str | None = None
    okved_code: str | None = None
    region: str | None = None
    city: str | None = None
    revenue: float | None = None
    has_loans: bool | None = None
    has_leasing: bool | None = None
    has_guarantees: bool | None = None
    has_foreign_trade: bool | None = None
    has_deposits: bool | None = None
    has_factoring: bool | None = None
    trade_countries: list[str] = []
    industry_tags: list[str] = []
    role_priorities: list[str] = []
    group_id: str | None = None
    company_age: str | None = None
    business_stage: str | None = None
    workers_fns: str | None = None
    workers_spark: str | None = None
    counterparty_ids: list[str] | None = None
    linked_company_ids: list[str] | None = None
    group_company_ids: list[str] = []
    payments: dict[str, Any] | None = None
    is_large_business: bool | None = None
    invalid_fields: list[str] = []
    field_sources: dict[str, dict[str, Any]] = {}
    relation_sources: dict[str, str | None] = {}
    uncertainties: list[str] = []
    schema_version: str | None = None
    user_role: str = "ceo"
    profile_completeness: float = 0
    known_fields: list[str] = []
    missing_fields: list[str] = []


class NewsOut(BaseModel):
    id: str
    title: str
    content: str = ""
    summary: str = ""
    source_name: str
    source_url: str
    published_at: datetime | None = None
    fetched_at: datetime
    category: str | None = None
    processing_status: str
    relevance_score: float | None = None
    relevance_reasons: list[str] = []
    matched_factors: list[str] = []
    categories: list[str] = []
    facts: list[dict[str, Any]] = []
    participants: list[str] = []
    industry_tags: list[str] = []
    geographies: list[str] = []
    mechanisms: list[str] = []
    indicators: list[dict[str, Any]] = []
    temporal_context: dict[str, Any] = {}
    uncertainties: list[str] = []
    factor_values: dict[str, float] = {}
    factor_contributions: dict[str, float] = {}
    factor_weights: dict[str, float] = {}
    evidence: list[dict[str, Any]] = []
    algorithm_version: str | None = None
    business_match: bool | None = None
    event_id: str | None = None
    duplicate_article_ids: list[str] = []
    additional_sources: list[dict[str, Any]] = []


class InsightCreate(BaseModel):
    company_id: str
    article_id: str
    user_role: str = "ceo"


class QuestionCreate(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class InsightOut(BaseModel):
    insight_id: str
    company_id: str
    article_id: str
    what_happened: str
    why_it_matters: str
    risks: list[dict]
    opportunities: list[dict]
    next_steps: list[str]
    bank_position: dict
    ai_conclusion: str
    sources: list[dict]
    company_factors: list[str]
    uncertainties: list[str]
    validation_status: str
    trace_id: str
    created_at: datetime
    model_name: str | None = None
