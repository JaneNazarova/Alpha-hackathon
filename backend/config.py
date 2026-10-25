from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Alpha Business News Analytics API"
    database_url: str = "sqlite:///./data/alpha_hack.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rss_feeds: str = "https://www.cbr.ru/rss/RssNews,https://www.cbr.ru/rss/eventrss"
    request_timeout_seconds: float = 8.0
    max_feed_items: int = 30
    news_refresh_token: str | None = None
    companies_csv_path: str = "data/sample/df_Uid_data_hack.csv"
    payments_csv_path: str = "data/sample/df_Uid_payment_hack.csv"
    person_links_csv_path: str = "data/sample/df_Fid_Uid_link_hack.csv"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def feeds(self) -> list[str]:
        return [feed.strip() for feed in self.rss_feeds.split(",") if feed.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
