"""Process configuration, read from the environment (ADR-010).

12-factor settings: required infra coordinates, defaulted bucket/region. No secrets
live in code — ``.env.example`` carries placeholders. ``get_settings`` is cached so
the environment is read once per process.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket: str = "documents"
    s3_region: str = "us-east-1"
    job_queue_concurrency: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
