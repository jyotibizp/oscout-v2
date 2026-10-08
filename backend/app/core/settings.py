"""Process-level settings (environment). Strategy parameters live in the versioned strategy configuration, not here."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./oscout_v2.db"
    data_provider: str = "mock"  # mock | kite
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    initial_backfill_days: int = 30      # first-run history per symbol (calendar days)
    max_fetch_days: int = 90             # Kite allows ~100 days per 5m request
    start_scheduler: bool = True         # background auto-scan loop (disabled in tests)
    log_level: str = "INFO"
    log_json: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
