"""The Settings contract (ADR-010): required infra config from the environment,
sensible defaults for the rest. ``_env_file=None`` ignores any developer ``.env``
so the test reads only what it sets.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pagemaster.entrypoints.settings import Settings

_REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@db:5432/pagemaster",
    "S3_ENDPOINT_URL": "http://minio:9000",
    "S3_ACCESS_KEY_ID": "key",
    "S3_SECRET_ACCESS_KEY": "secret",
}


def _set(monkeypatch, **env: str) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def test_reads_required_fields_from_the_environment(monkeypatch):
    _set(monkeypatch, **_REQUIRED)

    settings = Settings(_env_file=None)

    assert settings.database_url == _REQUIRED["DATABASE_URL"]
    assert settings.s3_endpoint_url == "http://minio:9000"
    assert settings.s3_access_key_id == "key"
    assert settings.s3_secret_access_key == "secret"


def test_bucket_and_region_have_defaults(monkeypatch):
    _set(monkeypatch, **_REQUIRED)

    settings = Settings(_env_file=None)

    assert settings.s3_bucket == "documents"
    assert settings.s3_region == "us-east-1"


def test_missing_required_field_is_a_validation_error(monkeypatch):
    for name in _REQUIRED:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
