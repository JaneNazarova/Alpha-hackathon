import asyncio
from datetime import timezone

import httpx

from backend.models import Company, NewsArticle
from backend.services.company_data import import_company_csv
from backend.services.news import classify, clean_html, fetch_rss, parse_date
from backend.services.personalization import company_profile, score_article


def test_news_text_classification_and_date_normalization():
    assert clean_html("<p>ЦБ &amp; ставка</p>") == "ЦБ & ставка"
    category, factors = classify("ЦБ повысил ключевую ставку")
    assert category == "monetary_policy"
    assert "monetary_policy" in factors
    assert parse_date("not a date") is None
    parsed = parse_date("2026-10-24T10:00:00Z")
    assert parsed is not None and parsed.tzinfo == timezone.utc


def test_company_csv_import_handles_values_and_missing_fields(database, tmp_path):
    csv_file = tmp_path / "companies.csv"
    csv_file.write_text(
        "SYNTHETIC_U;MAINOKVED_CODE;MAINOKVED_NAME;REVENUE_COMPANY;REGION;CITY;CL_PRODUCT_LOA_MARK;FTS_FLAG;FTS_COUNTRY_NAME\n"
        "CSV_COMPANY_1;25.11;Производство;1 234,5;Москва;Москва;1;0;\n"
        "CSV_COMPANY_2;47.19;Торговля;;;;;;\n",
        encoding="utf-8",
    )

    with database() as db:
        assert import_company_csv(db, csv_file) == 2
        imported = db.get(Company, "CSV_COMPANY_1")
        assert imported.industry == "Производство"
        assert imported.revenue == 1234.5
        assert imported.has_loans is True
        assert imported.has_foreign_trade is False
        assert imported.trade_countries == []
        missing = db.get(Company, "CSV_COMPANY_2")
        assert missing.revenue is None
        assert missing.has_loans is None


def test_company_profile_preserves_unknowns_and_scoring_is_bounded(database):
    with database() as db:
        company = db.get(Company, "SYNTHETIC_U_002")
        profile = company_profile(company, "cfo")
        assert profile["revenue"] is None
        assert "revenue" in profile["missing_fields"]
        assert profile["user_role"] == "cfo"

        article = db.get(NewsArticle, "news-rate")
        score, reasons, factors = score_article(company, article, "cfo")
        assert 0 <= score <= 1
        assert reasons
        assert isinstance(factors, list)


def test_rss_fetch_saves_normalized_news_and_deduplicates(database, monkeypatch):
    feed = """<?xml version='1.0' encoding='utf-8'?>
    <rss version='2.0'><channel><title>Test</title><item>
      <title>  ЦБ повысил ставку  </title>
      <link>https://example.test/article-1</link>
      <description>&lt;p&gt;Банк объявил решение.&lt;/p&gt;</description>
      <pubDate>Sat, 24 Oct 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>""".encode("utf-8")

    class FakeResponse:
        content = feed

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url):
            return FakeResponse()

    monkeypatch.setattr("backend.services.news.httpx.AsyncClient", FakeAsyncClient)
    with database() as db:
        first = asyncio.run(fetch_rss(db))
        second = asyncio.run(fetch_rss(db))
        assert first["inserted"] == 1
        assert first["skipped"] == 1  # The duplicate across the two configured feeds.
        assert second["inserted"] == 0
        assert second["skipped"] == 2
        article = db.query(NewsArticle).filter_by(url="https://example.test/article-1").one()
        assert article.title == "ЦБ повысил ставку"
        assert article.content == "Банк объявил решение."
        assert article.category == "monetary_policy"
        assert article.processing_status == "processed"


def test_rss_fetch_reports_source_failure_and_keeps_database_available(database, monkeypatch):
    class FailingAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url):
            raise httpx.ConnectError("offline", request=httpx.Request("GET", url))

    monkeypatch.setattr("backend.services.news.httpx.AsyncClient", FailingAsyncClient)
    with database() as db:
        result = asyncio.run(fetch_rss(db))
        assert result["inserted"] == 0
        assert len(result["failures"]) == 2
        assert all(item["error"] == "ConnectError" for item in result["failures"])
