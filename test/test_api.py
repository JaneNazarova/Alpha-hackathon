import pytest

from backend.api.routes import news as news_routes

def test_frontend_is_served_with_static_assets(client):
    page = client.get("/")
    script = client.get("/static/app.js")
    styles = client.get("/static/styles.css")

    assert page.status_code == script.status_code == styles.status_code == 200
    assert "альфа" in page.text
    assert all(f'id="{section}"' in page.text for section in ("overview", "feed", "company-profile", "ml-quality"))
    assert 'id="refresh-button"' in page.text
    assert "company-select" in page.text
    assert 'id="ml-quality-button"' in page.text
    assert "addEventListener(\"click\", loadMlQuality)" in script.text
    assert "--ink" in styles.text

def test_health_reports_database_ready(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers.get("x-trace-id")


def test_company_list_search_profile_and_missing_company(client):
    response = client.get("/api/companies")
    assert response.status_code == 200
    assert [item["company_id"] for item in response.json()] == ["SYNTHETIC_U_001", "SYNTHETIC_U_002"]

    searched = client.get("/api/companies", params={"q": "002"})
    assert [item["company_id"] for item in searched.json()] == ["SYNTHETIC_U_002"]

    profile = client.get("/api/companies/SYNTHETIC_U_001", params={"role": "cfo"})
    assert profile.status_code == 200
    assert profile.json()["user_role"] == "cfo"
    assert profile.json()["has_loans"] is True
    assert 0 <= profile.json()["profile_completeness"] <= 1

    assert client.get("/api/companies/not-a-company").status_code == 404
    assert client.get("/api/companies/SYNTHETIC_U_001", params={"role": "investor"}).status_code == 422


def test_feed_ranks_articles_and_handles_empty_or_invalid_company(client, database):
    feed = client.get("/api/feed", params={"company_id": "SYNTHETIC_U_001", "role": "cfo"})
    assert feed.status_code == 200
    assert {article["id"] for article in feed.json()} == {"news-rate", "news-currency"}
    assert all(0 <= article["relevance_score"] <= 1 for article in feed.json())
    assert all(article["relevance_reasons"] for article in feed.json())

    assert client.get("/api/feed").status_code == 422
    assert client.get("/api/feed", params={"company_id": "missing"}).status_code == 404
    assert client.get("/api/feed", params={"company_id": "SYNTHETIC_U_001", "role": "other"}).status_code == 422

    from backend.models import NewsArticle
    with database() as db:
        db.query(NewsArticle).delete()
        db.commit()
    assert client.get("/api/feed", params={"company_id": "SYNTHETIC_U_001"}).json() == []


def test_news_detail_and_missing_news_or_company(client):
    response = client.get("/api/news/news-rate", params={"company_id": "SYNTHETIC_U_001"})
    assert response.status_code == 200
    assert response.json()["source_url"] == "https://example.test/rate"
    assert response.json()["relevance_score"] is not None

    assert client.get("/api/news/missing").status_code == 404
    assert client.get("/api/news/news-rate", params={"company_id": "missing"}).status_code == 404


def test_manual_news_refresh_success_forbidden_and_source_unavailable(client, monkeypatch):
    async def successful_refresh(_db):
        return {"inserted": 2, "skipped": 1, "failures": []}

    monkeypatch.setattr(news_routes, "fetch_rss", successful_refresh)
    response = client.post("/api/news/refresh")
    assert response.status_code == 200
    assert response.json()["inserted"] == 2

    monkeypatch.setattr(news_routes.settings, "news_refresh_token", "expected-token")
    assert client.post("/api/news/refresh").status_code == 403
    assert client.post("/api/news/refresh", headers={"X-Refresh-Token": "wrong"}).status_code == 403

    async def unavailable_refresh(_db):
        return {"inserted": 0, "skipped": 0, "failures": [{"source": "feed", "error": "ConnectError"}]}

    monkeypatch.setattr(news_routes, "fetch_rss", unavailable_refresh)
    response = client.post("/api/news/refresh", headers={"X-Refresh-Token": "expected-token"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "sources_unavailable"


def test_insight_is_saved_cached_and_supports_trace_and_questions(client):
    body = {"company_id": "SYNTHETIC_U_001", "article_id": "news-rate", "user_role": "cfo"}
    created = client.post("/api/insights", json=body)
    assert created.status_code == 200
    first = created.json()
    assert first["insight_id"]
    assert first["company_id"] == body["company_id"]
    assert first["article_id"] == body["article_id"]
    assert "trace_id" in first

    repeated = client.post("/api/insights", json=body)
    assert repeated.status_code == 200
    assert repeated.json()["insight_id"] == first["insight_id"]

    saved = client.get(f"/api/insights/{first['insight_id']}")
    assert saved.status_code == 200
    trace = client.get(f"/api/insights/{first['insight_id']}/trace")
    assert trace.status_code == 200
    assert trace.json()["trace_id"] == first["trace_id"]

    question = client.post(f"/api/insights/{first['insight_id']}/questions",
                           json={"question": "Как это повлияет на наши кредиты?"})
    assert question.status_code == 200
    assert question.json()["answer"]
    history = client.get(f"/api/insights/{first['insight_id']}/questions")
    assert history.status_code == 200
    assert len(history.json()) == 1

    assert client.get("/api/insights/missing").status_code == 404
    assert client.get("/api/insights/missing/trace").status_code == 404
    assert client.get("/api/insights/missing/questions").status_code == 404
    assert client.post("/api/insights/missing/questions", json={"question": "Есть вопрос"}).status_code == 404


@pytest.mark.parametrize("payload", [
    {},
    {"company_id": "SYNTHETIC_U_001", "article_id": "unknown-news", "user_role": "ceo"},
    {"company_id": "unknown-company", "article_id": "news-rate", "user_role": "ceo"},
])
def test_insight_creation_rejects_invalid_entities(client, payload):
    response = client.post("/api/insights", json=payload)
    assert response.status_code in {404, 422}


def test_insight_creation_rejects_unsupported_role(client):
    response = client.post("/api/insights", json={
        "company_id": "SYNTHETIC_U_001", "article_id": "news-rate", "user_role": "admin"})
    assert response.status_code == 400


@pytest.mark.parametrize("payload", [{}, {"question": "?"}, {"question": "x" * 1001}])
def test_question_validation_rejects_invalid_payload(client, payload):
    created = client.post("/api/insights", json={
        "company_id": "SYNTHETIC_U_001", "article_id": "news-rate", "user_role": "ceo"})
    response = client.post(f"/api/insights/{created.json()['insight_id']}/questions", json=payload)
    assert response.status_code == 422


def test_insight_generation_uses_optional_ai_module_once(client, monkeypatch):
    from backend.services import insights as insight_service

    calls = []

    def fake_agent(profile, article):
        calls.append((profile, article))
        return ({"what_happened": "Событие из AI", "bank_position": {"text": None, "source_ids": []},
                 "validation_status": "passed", "model_name": "allowed-model"},
                {"trace_id": "trace-test", "steps": [], "sources": [],
                 "matched_factors": [], "validation_status": "passed"}, "allowed-model")

    monkeypatch.setattr(insight_service, "_agent_result", fake_agent)
    body = {"company_id": "SYNTHETIC_U_001", "article_id": "news-rate", "user_role": "ceo"}
    first = client.post("/api/insights", json=body)
    second = client.post("/api/insights", json=body)

    assert first.status_code == second.status_code == 200
    assert first.json()["what_happened"] == "Событие из AI"
    assert first.json()["validation_status"] == "passed"
    assert first.json()["model_name"] == "allowed-model"
    assert len(calls) == 1


def test_profile_and_feed_use_indexed_ml_dataset(client):
    from backend.api.dependencies import get_ml_dataset
    from ml.dataset import CompanyDataset

    dataset = CompanyDataset(
        [
            {"SYNTHETIC_U": "CSV_A", "MAINOKVED_CODE": "25.11", "MAINOKVED_NAME": "Производство",
             "REGION": "Москва", "REVENUE_COMPANY": "1000000", "CL_PRODUCT_LOA_MARK": "1",
             "FTS_FLAG": "1", "FTS_COUNTRY_NAME": "КИТАЙ", "GROUP_ID": "GROUP_X"},
            {"SYNTHETIC_U": "CSV_B", "MAINOKVED_CODE": "47.19", "MAINOKVED_NAME": "Розничная торговля",
             "REGION": "Санкт-Петербург", "CL_PRODUCT_LOA_MARK": "0", "FTS_FLAG": "0"},
        ],
        [{"PAYER": "CSV_A", "BENEFICIARY": "CSV_B", "PAY_AMT": "500", "PAY_CNT": "2"}],
        [{"SYNTHETIC_F": "PERSON_1", "SYNTHETIC_U": "CSV_A"},
         {"SYNTHETIC_F": "PERSON_1", "SYNTHETIC_U": "CSV_B"}],
    )
    client.app.dependency_overrides[get_ml_dataset] = lambda: dataset

    profile = client.get("/api/companies/CSV_A", params={"role": "cfo"})
    assert profile.status_code == 200
    assert profile.json()["schema_version"] == "1.0"
    assert profile.json()["has_loans"] is True
    assert profile.json()["payments"]["outgoing_amount"] == 500
    assert profile.json()["linked_company_ids"] == ["CSV_B"]

    listed = client.get("/api/companies", params={"q": "Производство"})
    assert listed.status_code == 200
    assert {row["company_id"] for row in listed.json()} == {"CSV_A"}

    feed_a = client.get("/api/feed", params={"company_id": "CSV_A", "role": "cfo"})
    feed_b = client.get("/api/feed", params={"company_id": "CSV_B", "role": "cfo"})
    assert feed_a.status_code == feed_b.status_code == 200
    rate_a = next(item for item in feed_a.json() if item["id"] == "news-rate")
    rate_b = next(item for item in feed_b.json() if item["id"] == "news-rate")
    assert rate_a["algorithm_version"] == "rules-1.1"
    assert rate_a["factor_values"]["finance"] == 1
    assert rate_a["relevance_score"] > rate_b["relevance_score"]

    insight = client.post("/api/insights", json={
        "company_id": "CSV_A", "article_id": "news-rate", "user_role": "cfo"})
    assert insight.status_code == 200
    assert insight.json()["company_id"] == "CSV_A"


def test_ml_profile_rejects_duplicate_ids_and_unknown_company(client):
    from backend.api.dependencies import get_ml_dataset
    from ml.dataset import CompanyDataset

    dataset = CompanyDataset([
        {"SYNTHETIC_U": "CSV_DUP", "MAINOKVED_CODE": "25.11", "GROUP_ID": "G1"},
        {"SYNTHETIC_U": "CSV_DUP", "MAINOKVED_CODE": "47.19", "GROUP_ID": "G2"},
    ])
    client.app.dependency_overrides[get_ml_dataset] = lambda: dataset

    assert client.get("/api/companies/CSV_DUP").status_code == 409
    assert client.get("/api/companies/unknown").status_code == 404
    listed = client.get("/api/companies")
    assert all(row["company_id"] != "CSV_DUP" for row in listed.json())


def test_news_refresh_token_is_optional_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(news_routes.settings, "news_refresh_token", None)

    async def no_op_refresh(_db):
        return {"inserted": 0, "skipped": 0, "failures": []}

    monkeypatch.setattr(news_routes, "fetch_rss", no_op_refresh)
    assert client.post("/api/news/refresh").status_code == 200
