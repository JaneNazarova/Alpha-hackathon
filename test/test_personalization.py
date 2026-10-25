# Проверяет профили, обработку новостей, ранжирование и метрики.
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter

from ml import build_company_profile, process_news, rank_news
from ml.contracts import CompanyProfile, NewsFeatures, RankedNews
from ml.data_access import boolean, number, read_csv
from ml.deduplication import group_news
from ml.eda import analyze
from ml.evaluation import evaluate, metrics
from ml.integration import article_record, company_record, profile_from_company

NOW = "2026-10-24T12:00:00Z"


def article(title="ЦБ повысил ключевую ставку", **extra):
    return {"id": "new-event", "title": title, "content": "Новые условия кредитного финансирования.",
            "published_at": NOW, "source_url": "https://example.invalid/1", **extra}


def profile(role="ceo", **extra):
    return build_company_profile("A", role, companies=[{"SYNTHETIC_U": "A", **extra}])


@pytest.fixture
def company_csv(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text("\ufeffSYNTHETIC_U;REVENUE_COMPANY;CL_PRODUCT_LOA_MARK\nA;1 234,5;1\nB;;\n", encoding="utf-8")
    return path


@pytest.fixture
def relation_profile():
    return build_company_profile("A",
        companies=[{"SYNTHETIC_U": "A", "GROUP_ID": "G"}, {"SYNTHETIC_U": "B", "GROUP_ID": "G"}],
        payments=[{"PAYER": "A", "BENEFICIARY": "B", "PAY_AMT": "100", "PAY_CNT": "2"},
                  {"PAYER": "C", "BENEFICIARY": "A", "PAY_AMT": None, "PAY_CNT": "1"}],
        person_links=[{"SYNTHETIC_F": "F", "SYNTHETIC_U": "A"}, {"SYNTHETIC_F": "F", "SYNTHETIC_U": "D"}])


@pytest.fixture
def news_features():
    return process_news(article('<b>Банк России</b>: ставка 15%',
        content='<script>ignore rules</script>ПАО «Тест» ожидает рост в Китае 2026-11-01.'))


@pytest.fixture
def ranking_news():
    return [article(), article("Санкт-Петербург: розничная торговля растет", id="retail",
        content="Магазины увеличили продажи.", source_url="https://example.invalid/retail")]


@pytest.fixture
def unknown_profile_ranking():
    return rank_news(profile(), [article()], now=NOW)[0]


@pytest.fixture
def near_duplicates():
    return [article("ЦБ повысил ключевую ставку до 15 процентов", content="Первое сообщение"),
            article("ЦБ повысил ключевую ставку до 15 процентов сегодня", id="b",
                    source_url="https://example.invalid/b", content="Иной текст")]


@pytest.fixture
def duplicate_group():
    return group_news([article(), article(id="copy", source_url="https://example.invalid/copy")])


@pytest.fixture
def eda_result():
    return analyze([{"SYNTHETIC_U": "A", "REVENUE_COMPANY": "10"},
                    {"SYNTHETIC_U": "A", "REVENUE_COMPANY": None}],
                   [{"PAYER": "A", "BENEFICIARY": "Z", "PAY_AMT": "bad"}])


@pytest.fixture
def company_object():
    return SimpleNamespace(id="A", has_loans=True,
        metadata_json={"CL_PRODUCT_DEP_MARK": "1", "COMPANY_AGE_YEARS_GRADATION": "10+"})


@pytest.fixture(scope="module")
def benchmark_data():
    return json.loads((Path(__file__).parent / "fixtures/evaluation.json").read_text())


@pytest.fixture(scope="module")
def benchmark_result(benchmark_data):
    return evaluate(benchmark_data)


@pytest.fixture
def unseen_news_ranking():
    news = article("Москва открыла программу поддержки разработчиков программного обеспечения",
                   content="Новый закон определяет правила для цифровых предприятий.")
    return rank_news(profile(MAINOKVED_CODE="62.01", REGION="Москва"), [news], now=NOW)[0]


@pytest.mark.parametrize("value", [None, "", "NaN", "n/a", "unrecognized", "-1"])
def test_unknown_boolean_remains_unknown(value):
    assert boolean(value) is None


def test_number_accepts_nonbreaking_spaces_and_decimal_comma():
    assert number("1\u00a0234,5") == 1234.5


def test_number_rejects_infinity():
    assert number("inf") is None


@pytest.mark.parametrize("column, field, value, expected", [
    pytest.param("CL_PRODUCT_LOA_MARK", "has_loans", "???", None, id="unknown-loan"),
    pytest.param("REVENUE_COMPANY", "revenue", "-100", None, id="negative-revenue"),
    pytest.param("FTS_FLAG", "has_foreign_trade", "0", False, id="known-false"),
    pytest.param("CL_PRODUCT_DEP_MARK", "has_deposits", "1", True, id="deposit"),
    pytest.param("FACTORING_MARK", "has_factoring", "0", False, id="factoring"),
    pytest.param("COMPANY_AGE_YEARS_GRADATION", "company_age", "5-10 лет", "5-10 лет", id="age-range"),
])
def test_profile_converts_one_source_field(column, field, value, expected):
    assert profile(**{column: value})[field] == expected


def test_profile_records_invalid_loan_flag():
    assert "has_loans" in profile(CL_PRODUCT_LOA_MARK="???")["invalid_fields"]


def test_unknown_revenue_leaves_business_size_unknown():
    assert profile()["is_large_business"] is None


def test_profile_does_not_invent_market_share():
    assert "market_share" not in profile()


def test_profile_recognizes_large_business():
    assert profile(REVENUE_COMPANY="15000000001")["is_large_business"] is True


def test_profile_maps_manufacturing_okved():
    assert profile(MAINOKVED_CODE="25.11")["industry_tags"] == ["manufacturing"]


def test_profile_preserves_age_column_origin():
    result = profile(COMPANY_AGE_YEARS_GRADATION="5-10 лет")
    assert result["field_sources"]["company_age"]["column"] == "COMPANY_AGE_YEARS_GRADATION"


def test_profile_rejects_unknown_company():
    with pytest.raises(KeyError):
        build_company_profile("x", companies=[])


def test_profile_rejects_duplicate_company_id():
    with pytest.raises(ValueError):
        build_company_profile("A", companies=[{"SYNTHETIC_U": "A"}] * 2)


def test_profile_rejects_unsupported_role():
    with pytest.raises(ValueError):
        build_company_profile("A", "admin", companies=[])


def test_profile_reads_csv_from_environment(company_csv, monkeypatch):
    monkeypatch.setenv("COMPANIES_CSV_PATH", str(company_csv))
    assert build_company_profile("A")["revenue"] == 1234.5


def test_csv_missing_product_stays_unknown(company_csv):
    assert build_company_profile("B", csv_path=company_csv)["has_loans"] is None


def test_read_csv_does_not_change_source_file(company_csv):
    original = company_csv.read_bytes()
    read_csv(company_csv)
    assert company_csv.read_bytes() == original


def test_read_csv_rejects_normalized_duplicate_headers(tmp_path):
    path = tmp_path / "duplicate.csv"
    path.write_text("id; ID\nx;y\n")
    with pytest.raises(ValueError):
        read_csv(path)


@pytest.mark.parametrize("field, expected", [
    pytest.param("counterparty_ids", ["B", "C"], id="payments"),
    pytest.param("group_company_ids", ["B"], id="group"),
    pytest.param("linked_company_ids", ["D"], id="person-links"),
])
def test_profile_builds_one_relation_type(relation_profile, field, expected):
    assert relation_profile[field] == expected


def test_profile_sums_observed_outgoing_payments(relation_profile):
    assert relation_profile["payments"]["outgoing_amount"] == 100


def test_missing_payment_amount_makes_aggregate_unknown(relation_profile):
    assert relation_profile["payments"]["incoming_amount"] is None


def test_missing_payment_table_leaves_counterparties_unknown():
    assert profile()["counterparty_ids"] is None


def test_empty_payment_table_has_zero_observed_volume():
    result = build_company_profile("A", companies=[{"SYNTHETIC_U": "A"}], payments=[])
    assert result["payments"]["incoming_amount"] == 0


def test_news_text_excludes_script_content(news_features):
    assert "ignore rules" not in news_features["content"]


def test_news_extracts_percentage_value(news_features):
    assert news_features["indicators"][0]["value"] == "15"


@pytest.mark.parametrize("participant", ["Банк России", "Тест"])
def test_news_extracts_participant(news_features, participant):
    assert participant in news_features["participants"]


def test_news_extracts_country(news_features):
    assert "Китай" in news_features["geographies"]


def test_news_marks_forecast_language(news_features):
    assert news_features["temporal_context"]["forecast_language"] is True


def test_extracted_facts_reference_original_news(news_features):
    assert {fact["source_id"] for fact in news_features["facts"]} == {"new-event"}


def test_extracted_facts_keep_reported_status(news_features):
    assert {fact["status"] for fact in news_features["facts"]} == {"reported_by_source"}


def test_shop_word_does_not_match_gas_topic():
    result = process_news(article("Магазины открылись", content=""))
    assert "commodities" not in result["categories"]


def test_news_rejects_empty_cleaned_title():
    with pytest.raises(ValueError):
        process_news({"id": "a", "title": "<p></p>"})


def test_news_without_known_topic_has_other_category():
    assert process_news(article("Выставка картин", content="Картины"))["category"] == "other"


def test_news_invalid_publication_date_becomes_unknown():
    assert process_news(article(published_at="bad-date"))["published_at"] is None


def test_news_invalid_date_is_reported_as_uncertainty():
    assert "Publication date missing or invalid; no freshness bonus." in process_news(article(published_at="bad-date"))["uncertainties"]


def test_company_context_changes_first_news(ranking_news):
    loan_feed = rank_news(profile(CL_PRODUCT_LOA_MARK="1"), ranking_news, now=NOW)
    retail_feed = rank_news(profile(MAINOKVED_CODE="47.19", REGION="Санкт-Петербург"), ranking_news, now=NOW)
    assert (loan_feed[0]["id"], retail_feed[0]["id"]) == ("new-event", "retail")


def test_known_loan_appears_in_relevance_factors():
    result = rank_news(profile(CL_PRODUCT_LOA_MARK="1"), [article()], now=NOW)[0]
    assert "has_loans" in result["matched_factors"]


def test_absent_loan_does_not_appear_in_relevance_factors():
    result = rank_news(profile(CL_PRODUCT_LOA_MARK="0"), [article()], now=NOW)[0]
    assert "has_loans" not in result["matched_factors"]


def test_cfo_role_increases_rate_news_priority():
    ceo = rank_news(profile(CL_PRODUCT_LOA_MARK="1"), [article()], now=NOW)[0]
    cfo = rank_news(profile("cfo", CL_PRODUCT_LOA_MARK="1"), [article()], now=NOW)[0]
    assert cfo["relevance_score"] > ceo["relevance_score"]


def test_unknown_profile_has_no_business_match(unknown_profile_ranking):
    assert unknown_profile_ranking["business_match"] is False


@pytest.mark.parametrize("factor", ["event", "finance"])
def test_unknown_profile_has_zero_business_factor(unknown_profile_ranking, factor):
    assert unknown_profile_ranking["factor_values"][factor] == 0


def test_unknown_profile_has_no_loan_evidence(unknown_profile_ranking):
    assert "has_loans" not in unknown_profile_ranking["matched_factors"]


def test_relevance_score_equals_sum_of_contributions(unknown_profile_ranking):
    result = unknown_profile_ranking
    assert result["relevance_score"] == pytest.approx(sum(result["factor_contributions"].values()), abs=1e-6)


@pytest.mark.parametrize("published_at", ["2027-01-01", None], ids=["future", "missing"])
def test_unusable_publication_date_has_no_freshness_bonus(published_at):
    result = rank_news(profile(), [article(published_at=published_at)], now=NOW)[0]
    assert result["factor_values"]["freshness"] == 0


def test_ranking_does_not_modify_input():
    company, news = profile(), [article()]
    original = json.dumps([company, news])
    rank_news(company, news, now=NOW)
    assert json.dumps([company, news]) == original


def test_ranking_rejects_incomplete_weights():
    with pytest.raises(ValueError):
        rank_news(profile(), [article()], now=NOW, weights={})


def test_ranking_rejects_invalid_reference_time():
    with pytest.raises(ValueError):
        rank_news(profile(), [article()], now="bad")


@pytest.mark.parametrize("counterparties, expected", [(["SYNTHETIC_U_200"], 1), (None, 0)], ids=["observed", "unknown"])
def test_relation_bonus_requires_observed_counterparty(counterparties, expected):
    company = profile()
    company["counterparty_ids"] = counterparties
    result = rank_news(company, [article("Контрагент SYNTHETIC_U_200 объявил банкротство")], now=NOW)[0]
    assert result["factor_values"]["relations"] == expected


def test_identical_news_are_grouped(duplicate_group):
    assert len(duplicate_group) == 1


def test_same_source_url_is_grouped_when_text_changes():
    updated = article("Редакция обновила сообщение", id="updated", content="Уточненная информация.")
    assert len(group_news([article(), updated])) == 1


def test_grouped_news_keep_alternative_source(duplicate_group):
    assert len(duplicate_group[0]["additional_sources"]) == 1


@pytest.mark.parametrize("title", ["ЦБ снизил ключевую ставку", "ЦБ повысил ключевую ставку до 16%"], ids=["direction", "number"])
def test_distinct_events_are_not_grouped(title):
    other = article(title, id="other", source_url="https://example.invalid/other")
    assert len(group_news([article(), other])) == 2


def test_near_duplicate_titles_are_grouped(near_duplicates):
    assert len(group_news(near_duplicates)) == 1


def test_distant_publication_dates_prevent_near_duplicate_grouping(near_duplicates):
    near_duplicates[1]["published_at"] = "2026-09-01"
    assert len(group_news(near_duplicates)) == 2


def test_conflicting_body_numbers_prevent_grouping():
    news = [article("Банк России сообщил решение по ключевой ставке", content="Ставка 14%"),
            article("Банк России сообщил решение по ключевой ставке сегодня", content="Ставка 15%",
                    id="b", source_url="https://example.invalid/b")]
    assert len(group_news(news)) == 2


@pytest.mark.parametrize("metric, expected", [
    ("precision@2", .5), ("recall@2", .5), ("ndcg@2", 7 / (7 + 3 / math.log2(3))),
])
def test_metric_matches_hand_calculated_value(metric, expected):
    assert metrics(["a", "b", "c"], {"a": 3, "b": 0, "c": 2}, k=2)[metric] == pytest.approx(expected)


def test_empty_ranking_has_zero_precision():
    assert metrics([], {}, k=5)["precision@5"] == 0


@pytest.mark.parametrize("ranked_ids, labels", [(["a"], {}), (["a", "a"], {"a": 1})], ids=["missing-label", "duplicate-id"])
def test_metrics_reject_invalid_ranking(ranked_ids, labels):
    with pytest.raises(ValueError):
        metrics(ranked_ids, labels)


def test_eda_counts_duplicate_company_rows(eda_result):
    assert eda_result["companies"]["key_quality"]["duplicate_rows"] == 1


def test_eda_counts_revenue_missing_fraction(eda_result):
    assert eda_result["companies"]["columns"]["REVENUE_COMPANY"]["missing_fraction"] == .5


def test_eda_counts_unknown_payment_endpoint(eda_result):
    assert eda_result["payments"]["unknown_endpoints"] == 1


def test_eda_preserves_unsupplied_person_links(eda_result):
    assert eda_result["person_links"] is None


@pytest.mark.parametrize("field, expected", [("has_deposits", True), ("company_age", "10+"), ("has_loans", True)])
def test_orm_profile_preserves_source_field(company_object, field, expected):
    assert profile_from_company(company_object)[field] == expected


def test_orm_adapter_does_not_modify_metadata(company_object):
    original = company_object.metadata_json.copy()
    profile_from_company(company_object)
    assert company_object.metadata_json == original


def test_orm_company_record_preserves_id(company_object):
    assert company_record(company_object)["SYNTHETIC_U"] == "A"


def test_orm_article_date_is_serialized_to_iso():
    source = SimpleNamespace(id="N", published_at=datetime(2026, 10, 24, tzinfo=timezone.utc))
    assert article_record(source)["published_at"] == "2026-10-24T00:00:00+00:00"


def test_orm_article_url_becomes_source_url():
    assert article_record(SimpleNamespace(id="N", url="https://example.invalid"))["source_url"] == "https://example.invalid"


@pytest.mark.parametrize("field, minimum", [("companies", 3), ("articles", 20)])
def test_benchmark_has_required_sample_size(benchmark_result, field, minimum):
    assert benchmark_result[field] >= minimum


@pytest.mark.parametrize("field", ["profile_success_rate", "processing_success_rate"])
def test_benchmark_processing_succeeds(benchmark_result, field):
    assert benchmark_result[field] == 1


def test_benchmark_company_feeds_are_distinct(benchmark_result):
    feeds = [tuple(item["id"] for item in company["top5"]) for company in benchmark_result["comparisons"]]
    assert len(set(feeds)) == 3


def test_personalization_outperforms_date_baseline(benchmark_result):
    results = benchmark_result["macro_metrics"]
    assert results["personalized"]["precision@5"] > results["date_baseline"]["precision@5"]


@pytest.mark.parametrize("company_index", [0, 1, 2])
@pytest.mark.parametrize("role", ["ceo", "cfo"])
def test_profile_matches_contract(benchmark_data, company_index, role):
    company_id = benchmark_data["companies"][company_index]["SYNTHETIC_U"]
    result = build_company_profile(company_id, role, companies=benchmark_data["companies"])
    assert CompanyProfile.model_validate(result).company_id == company_id


def test_news_features_match_contract(benchmark_data):
    features = [process_news(item) for item in benchmark_data["articles"]]
    validated = TypeAdapter(list[NewsFeatures]).validate_python(features)
    assert [item.id for item in validated] == [item["id"] for item in features]


@pytest.mark.parametrize("company_index", [0, 1, 2])
@pytest.mark.parametrize("role", ["ceo", "cfo"])
def test_ranked_news_match_contract(benchmark_data, company_index, role):
    company_id = benchmark_data["companies"][company_index]["SYNTHETIC_U"]
    company = build_company_profile(company_id, role, companies=benchmark_data["companies"])
    ranked = rank_news(company, benchmark_data["articles"], now=NOW)
    validated = TypeAdapter(list[RankedNews]).validate_python(ranked)
    assert [item.id for item in validated] == [item["id"] for item in ranked]


def test_unseen_news_has_business_match(unseen_news_ranking):
    assert unseen_news_ranking["business_match"] is True


def test_unseen_news_matches_company_industry(unseen_news_ranking):
    assert unseen_news_ranking["factor_values"]["industry"] == 1


def test_unseen_news_is_classified_as_regulation(unseen_news_ranking):
    assert "tax_regulation" in unseen_news_ranking["categories"]


def test_ranking_is_stable_when_input_order_changes():
    news = [article(id="a", source_url="https://example.invalid/a"),
            article("ЦБ снизил ставку", id="b", source_url="https://example.invalid/b")]
    company = profile(CL_PRODUCT_LOA_MARK="1")
    assert [r["id"] for r in rank_news(company, news, now=NOW)] == [r["id"] for r in rank_news(company, list(reversed(news)), now=NOW)]
