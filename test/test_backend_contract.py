# Проверяет совместимость ML с моделями и схемами бэкенда.
from datetime import datetime, timezone

import pytest

from backend.models import Company, NewsArticle
from backend.schemas import CompanyOut, NewsOut
from ml.integration import article_record, profile_from_company
from ml.ranking import rank_news


@pytest.fixture
def company_profile():
    company = Company(id="compatibility-only", industry="Производство", okved_code="25.11",
                      has_loans=True, metadata_json={"CL_PRODUCT_DEP_MARK": "1"})
    return profile_from_company(company, "cfo")


@pytest.fixture
def ranked_article(company_profile):
    article = NewsArticle(id="compatibility-news", title="ЦБ повысил ключевую ставку",
                          content="Кредитное финансирование изменилось.", summary="Решение по ставке",
                          url="https://example.invalid/compatibility", source_name="Synthetic",
                          published_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
                          fetched_at=datetime(2026, 10, 24, tzinfo=timezone.utc))
    return rank_news(company_profile, [article_record(article)], now="2026-10-24T12:00:00Z")[0]


def test_company_response_preserves_loan_flag(company_profile):
    assert CompanyOut.model_validate(company_profile).has_loans is True


def test_news_response_preserves_article_id(ranked_article):
    assert NewsOut.model_validate(ranked_article).id == "compatibility-news"


def test_news_response_preserves_relevance_score(ranked_article):
    assert NewsOut.model_validate(ranked_article).relevance_score > .3


def test_news_response_preserves_loan_relevance_factor(ranked_article):
    assert "has_loans" in NewsOut.model_validate(ranked_article).matched_factors
