from datetime import datetime
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
    trade_countries: list[str] = []
    group_id: str | None = None
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
