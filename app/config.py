from pydantic_settings import BaseSettings


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
    INDEXER_PROVIDER: str = "mock"
    JACKETT_URL: str = "http://localhost:9117"
    JACKETT_API_KEY: str = ""
    WORKER_REG_SECRET: str = "change-me"
    DEFAULT_QUOTA_BYTES: int = 10737418240
    LEASE_MINUTES: int = 10
    HEARTBEAT_MAX_GAP_MINUTES: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
