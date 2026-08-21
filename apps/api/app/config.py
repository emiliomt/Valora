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
    # Comma-separated list of allowed browser origins for the web frontend, e.g.
    # "http://localhost:3000,https://valora-web-production.up.railway.app".
    cors_origins: str = "http://localhost:3000"
    # Railway public URLs change per deploy (…-production-06cc3.up.railway.app). A regex
    # keeps CORS working when VALORA_CORS_ORIGINS hasn't been updated yet.
    cors_origin_regex: str = r"https://.*\.up\.railway\.app"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
