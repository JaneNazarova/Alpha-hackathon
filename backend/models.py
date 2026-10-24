from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    okved_code: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    group_id: Mapped[str | None] = mapped_column(String, nullable=True)
    has_loans: Mapped[bool | None] = mapped_column(nullable=True)
    has_leasing: Mapped[bool | None] = mapped_column(nullable=True)
    has_guarantees: Mapped[bool | None] = mapped_column(nullable=True)
    has_foreign_trade: Mapped[bool | None] = mapped_column(nullable=True)
    trade_countries: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class NewsArticle(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint("url", name="uq_news_url"), UniqueConstraint("content_hash", name="uq_news_hash"))
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    source_name: Mapped[str] = mapped_column(String, default="Unknown")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    processing_status: Mapped[str] = mapped_column(String, default="new")
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    facts: Mapped[list] = mapped_column(JSON, default=list)


class FeedScore(Base):
    __tablename__ = "feed_scores"
    __table_args__ = (UniqueConstraint("company_id", "article_id", name="uq_feed_company_article"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("news.id", ondelete="CASCADE"), index=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0)
    relevance_reasons: Mapped[list] = mapped_column(JSON, default=list)
    matched_factors: Mapped[list] = mapped_column(JSON, default=list)


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("news.id"), index=True)
    user_role: Mapped[str] = mapped_column(String, default="ceo")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    trace: Mapped[dict] = mapped_column(JSON, default=dict)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, default="fallback")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InsightQuestion(Base):
    __tablename__ = "insight_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    insight_id: Mapped[str] = mapped_column(ForeignKey("insights.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
