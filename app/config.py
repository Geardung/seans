import os

from pydantic import model_validator
from pydantic_settings import BaseSettings


def _env_lookup(*names: str) -> str | None:
    lowered = {k.lower(): v for k, v in os.environ.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value:
            return value
    return None


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://seans:seans@db:5432/seans"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://seans:seans@db:5432/seans"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://seans:seans@db:5432/seans_test"
    JWT_SECRET: str = "change-me"
    JWT_TTL_DAYS: int = 7
    S3_ENDPOINT: str = "https://s3.regru.cloud"
    S3_BUCKET: str = "seans"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"
    KP_API_TOKEN: str = ""
    TMDB_API_TOKEN: str = ""  # v3 API-ключ с themoviedb.org
    JACRED_URL: str = "http://localhost:9117"
    JACRED_API_KEY: str = ""
    PROWLARR_URL: str = "http://localhost:9696"
    PROWLARR_API_KEY: str = ""
    WORKER_REG_SECRET: str = "change-me"
    DEFAULT_QUOTA_BYTES: int = 10737418240
    LEASE_MINUTES: int = 10
    HEARTBEAT_MAX_GAP_MINUTES: int = 10

    # extra=ignore: production .env still has legacy jackett_* keys that must not crash Settings.
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _map_legacy_jackett_env(self) -> "Settings":
        jackett_url = _env_lookup("jackett_url")
        if jackett_url and (
            not self.JACRED_URL or self.JACRED_URL.startswith("http://localhost")
        ):
            self.JACRED_URL = jackett_url
        jackett_key = _env_lookup("jackett_api_key")
        if jackett_key and not self.JACRED_API_KEY:
            self.JACRED_API_KEY = jackett_key
        return self


settings = Settings()
