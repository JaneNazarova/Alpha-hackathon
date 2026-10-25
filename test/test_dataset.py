# Проверяет загрузку данных, индексы и массовую валидацию профилей.
import json

import pytest

from ml.company_profile import build_company_profile
from ml.dataset import CompanyDataset
from ml.eda import analyze
from ml.news_processing import process_news
from ml.ranking import rank_news
from ml.validate_dataset import validate


@pytest.fixture
def relation_data():
    companies = [{"SYNTHETIC_U": "A", "GROUP_ID": "G"}, {"SYNTHETIC_U": "B", "GROUP_ID": "G"}]
    payments = [{"PAYER": "A", "BENEFICIARY": "B", "PAY_AMT": "10,5", "PAY_CNT": "2"},
                {"PAYER": "X", "BENEFICIARY": "A", "PAY_AMT": "20", "PAY_CNT": "1"}]
    links = [{"SYNTHETIC_U": "A", "SYNTHETIC_F": "F"}, {"SYNTHETIC_U": "B", "SYNTHETIC_F": "F"}]
    return companies, payments, links


@pytest.fixture
def indexed_dataset(relation_data):
    companies, payments, links = relation_data
    return CompanyDataset(iter(companies), iter(payments), iter(links))


@pytest.fixture
def ambiguous_dataset():
    return CompanyDataset([{"SYNTHETIC_U": "A", "GROUP_ID": "G"},
                           {"SYNTHETIC_U": "A", "GROUP_ID": "H"},
                           {"SYNTHETIC_U": "B", "GROUP_ID": "G"}])


@pytest.fixture
def invalid_payment_dataset():
    return CompanyDataset([{"SYNTHETIC_U": "A"}], [
        {"PAYER": "A", "BENEFICIARY": "A", "PAY_AMT": "5", "PAY_CNT": "1"},
        {"PAYER": "A", "BENEFICIARY": "X", "PAY_AMT": "bad", "PAY_CNT": "1.5"},
        {"PAYER": "A", "BENEFICIARY": "X", "PAY_AMT": "10", "PAY_CNT": "2"}])


@pytest.fixture
def country_profile():
    return build_company_profile("A", companies=[{"SYNTHETIC_U": "A", "FTS_COUNTRY_NAME": "КИТАЙ, ТУРЦИЯ;КИТАЙ"}])


@pytest.fixture
def streaming_eda_result():
    return analyze(iter([{"SYNTHETIC_U": "A"}]),
        iter([{"PAYER": "A", "BENEFICIARY": "A", "PAY_AMT": "1", "PAY_CNT": "1.5"}] * 2),
        iter([{"SYNTHETIC_F": "F", "SYNTHETIC_U": "A"}] * 2))


@pytest.fixture
def csv_dataset(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text("SYNTHETIC_U;FTS_COUNTRY_NAME\nA;КИТАЙ, ТУРЦИЯ\n", encoding="utf-8")
    return CompanyDataset.from_csv(path), path


@pytest.fixture
def anonymized_news():
    return [{"id": "n", "title": "Контрагент U_200 сообщил о банкротстве",
             "content": "Условное событие, не реальная новость."}]


@pytest.fixture
def profile_validation():
    dataset = CompanyDataset([{"SYNTHETIC_U": "U_100", "MAINOKVED_CODE": "25.11"}], [], [])
    return validate(dataset)


@pytest.fixture
def failed_profile_validation(monkeypatch):
    dataset = CompanyDataset([{"SYNTHETIC_U": "U_100"}, {"SYNTHETIC_U": "U_200"}])
    original = dataset.profile

    def profile_with_error(company_id, user_role="ceo"):
        if company_id == "U_100":
            raise ValueError("Invalid source profile")
        return original(company_id, user_role)

    monkeypatch.setattr(dataset, "profile", profile_with_error)
    return validate(dataset)


@pytest.fixture
def supplied_news_validation():
    dataset = CompanyDataset([{"SYNTHETIC_U": "U_100", "MAINOKVED_CODE": "25.11"}])
    news = [{"id": "provided-only", "title": "Изменились условия производства металлических конструкций",
             "content": "Новые условия", "source_url": "https://example.invalid/provided"}]
    return validate(dataset, news, "2026-10-25T12:00:00Z")


@pytest.fixture
def cli_validation(tmp_path, monkeypatch):
    from ml.validate_dataset import main
    companies = tmp_path / "companies.csv"
    companies.write_text("SYNTHETIC_U;MAINOKVED_CODE\nU_100;25.11\n", encoding="utf-8")
    output = tmp_path / "validation.json"
    monkeypatch.setattr("sys.argv", ["validate_dataset", "--companies", str(companies), "--output", str(output)])
    main()
    return json.loads(output.read_text()), companies


@pytest.mark.parametrize("field", ["group_company_ids", "counterparty_ids", "linked_company_ids", "payments"])
def test_index_matches_direct_profile_field(indexed_dataset, relation_data, field):
    companies, payments, links = relation_data
    direct = build_company_profile("A", companies=companies, payments=payments, person_links=links)
    assert indexed_dataset.profile("A")[field] == direct[field]


def test_index_preserves_requested_role(indexed_dataset):
    assert indexed_dataset.profile("A", "cfo")["user_role"] == "cfo"


def test_index_counts_payment_rows(indexed_dataset):
    assert indexed_dataset.payment_rows == 2


def test_index_rejects_ambiguous_company(ambiguous_dataset):
    with pytest.raises(ValueError, match="Ambiguous"):
        ambiguous_dataset.profile("A")


def test_index_records_duplicate_details(ambiguous_dataset):
    assert ambiguous_dataset.duplicate_details["A"] == {"rows": 2, "conflicting_columns": {"GROUP_ID"}}


def test_index_rejects_unknown_company(indexed_dataset):
    with pytest.raises(KeyError):
        indexed_dataset.profile("unknown")


def test_ambiguous_company_is_excluded_from_group(ambiguous_dataset):
    assert ambiguous_dataset.profile("B")["group_company_ids"] == []


def test_unsupplied_payment_table_remains_unknown():
    assert CompanyDataset([{"SYNTHETIC_U": "A"}]).profile("A")["payments"] is None


def test_empty_payment_table_produces_zero_observed_volume():
    assert CompanyDataset([{"SYNTHETIC_U": "A"}], []).profile("A")["payments"]["incoming_amount"] == 0


def test_empty_person_links_produce_empty_connection_list():
    assert CompanyDataset([{"SYNTHETIC_U": "A"}], person_links=[]).profile("A")["linked_company_ids"] == []


def test_modifying_profile_errors_does_not_modify_index(invalid_payment_dataset):
    result = invalid_payment_dataset.profile("A")
    result["payments"]["invalid_or_missing_cells"]["outgoing_amount"] = 999
    assert invalid_payment_dataset.profile("A")["payments"]["invalid_or_missing_cells"]["outgoing_amount"] == 1


@pytest.mark.parametrize("field", ["outgoing_amount", "outgoing_count"])
def test_invalid_payment_cell_keeps_aggregate_unknown(invalid_payment_dataset, field):
    assert invalid_payment_dataset.profile("A")["payments"][field] is None


def test_self_payment_is_counted_as_incoming(invalid_payment_dataset):
    assert invalid_payment_dataset.profile("A")["payments"]["incoming_amount"] == 5


def test_self_payment_does_not_create_self_counterparty(invalid_payment_dataset):
    assert invalid_payment_dataset.profile("A")["counterparty_ids"] == ["X"]


def test_country_list_is_split_normalized_and_deduplicated(country_profile):
    assert country_profile["trade_countries"] == ["Китай", "Турция"]


def test_country_word_form_matches_profile_geography(country_profile):
    news = [{"id": "n", "title": "Изменились правила поставок из Китая", "content": "Новые правила"}]
    assert rank_news(country_profile, news, now="2026-10-24")[0]["factor_values"]["geography"] == 1


def test_streaming_eda_counts_duplicate_payments(streaming_eda_result):
    assert streaming_eda_result["payments"]["duplicate_records"] == 1


def test_streaming_eda_rejects_fractional_payment_counts(streaming_eda_result):
    assert streaming_eda_result["payments"]["invalid_counts"] == 2


def test_streaming_eda_counts_self_payments(streaming_eda_result):
    assert streaming_eda_result["payments"]["self_payment_rows"] == 2


def test_streaming_eda_counts_duplicate_person_links(streaming_eda_result):
    assert streaming_eda_result["person_links"]["duplicate_edges"] == 1


def test_csv_index_preserves_source_path(csv_dataset):
    dataset, path = csv_dataset
    assert dataset.profile("A")["field_sources"]["industry"]["source"] == str(path)


def test_csv_index_parses_multiple_countries(csv_dataset):
    dataset, _ = csv_dataset
    assert dataset.profile("A")["trade_countries"] == ["Китай", "Турция"]


def test_okved_overrides_ambiguous_industry_word():
    result = build_company_profile("A", companies=[{"SYNTHETIC_U": "A", "MAINOKVED_CODE": "35.11",
                                                   "MAINOKVED_NAME": "Производство электроэнергии"}])
    assert result["industry_tags"] == ["utilities"]


def test_unknown_okved_does_not_fall_back_to_industry_word():
    result = build_company_profile("A", companies=[{"SYNTHETIC_U": "A", "MAINOKVED_CODE": "99", "MAINOKVED_NAME": "Производство"}])
    assert result["industry_tags"] == []


def test_real_anonymized_id_is_extracted_from_news(anonymized_news):
    assert "U_200" in process_news(anonymized_news[0])["participants"]


def test_real_counterparty_id_creates_relation_bonus(anonymized_news):
    company = build_company_profile("U_100", companies=[{"SYNTHETIC_U": "U_100"}])
    company["counterparty_ids"] = ["U_200"]
    assert rank_news(company, anonymized_news, now="2026-10-24")[0]["factor_values"]["relations"] == 1


def test_profile_validation_counts_valid_profile(profile_validation):
    assert profile_validation["valid_profiles"] == 1


def test_profile_validation_without_news_does_not_generate_rankings(profile_validation):
    assert profile_validation["comparisons"] == []


def test_profile_validation_without_news_reports_not_run(profile_validation):
    assert profile_validation["news_evaluation"]["status"] == "not_run"


def test_profile_validation_without_news_counts_zero_articles(profile_validation):
    assert profile_validation["news_evaluation"]["article_count"] == 0


def test_profile_validation_records_individual_error(failed_profile_validation):
    assert failed_profile_validation["errors"] == [{"company_id": "U_100", "code": "ValueError"}]


def test_profile_validation_continues_after_individual_error(failed_profile_validation):
    assert failed_profile_validation["valid_profiles"] == 1


def test_supplied_news_are_reported_as_ranked(supplied_news_validation):
    assert supplied_news_validation["news_evaluation"]["status"] == "provided_news_ranked"


def test_supplied_news_are_checked_for_both_roles(supplied_news_validation):
    assert [row["role"] for row in supplied_news_validation["comparisons"]] == ["ceo", "cfo"]


def test_news_validation_uses_only_supplied_article_ids(supplied_news_validation):
    article_ids = {item["article_id"] for row in supplied_news_validation["comparisons"] for item in row["top5"]}
    assert article_ids == {"provided-only"}


def test_news_validation_rejects_empty_corpus():
    with pytest.raises(ValueError, match="nonempty list"):
        validate(CompanyDataset([{"SYNTHETIC_U": "A"}]), [])


def test_validation_cli_uses_requested_company_file(cli_validation):
    result, companies = cli_validation
    assert result["input_files"]["companies"] == str(companies)


def test_validation_cli_without_news_has_no_rankings(cli_validation):
    result, _ = cli_validation
    assert result["comparisons"] == []


def test_validation_cli_without_news_reports_not_run(cli_validation):
    result, _ = cli_validation
    assert result["news_evaluation"]["status"] == "not_run"


@pytest.mark.parametrize("args", [[], ["--output", "unused.json"]], ids=["no-arguments", "output-only"])
def test_evaluation_cli_rejects_missing_dataset(args, monkeypatch):
    from ml.evaluation import main
    monkeypatch.setattr("sys.argv", ["evaluation", *args])
    with pytest.raises(SystemExit, match="^2$"):
        main()


def test_evaluation_cli_names_missing_dataset_argument(monkeypatch, capsys):
    from ml.evaluation import main
    monkeypatch.setattr("sys.argv", ["evaluation"])
    with pytest.raises(SystemExit):
        main()
    assert "--dataset" in capsys.readouterr().err
