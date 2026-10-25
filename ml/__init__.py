# Экспортирует основные функции ML-модуля.
from ml.company_profile import build_company_profile
from ml.news_processing import process_news
from ml.ranking import rank_news

__all__ = ["build_company_profile", "process_news", "rank_news"]
