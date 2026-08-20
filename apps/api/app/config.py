from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VALORA_", extra="ignore")

    # Default to a local SQLite file for zero-friction local dev; docker-compose
    # / production sets VALORA_DATABASE_URL to Postgres (PRD 8.1).
    database_url: str = "sqlite:///./valora.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    storage_dir: str = "./storage"  # local filesystem stand-in for S3-compatible object storage
    default_forecast_years: int = 5
    terminal_value_threshold_pct: float = 0.75
    balance_sheet_tolerance_pct: float = 0.005


@lru_cache
def get_settings() -> Settings:
    return Settings()
