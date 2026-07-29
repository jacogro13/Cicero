"""Config-selection of the metadata inferer (ADR-028), mirroring the summarizer
(ADR-018): an OpenAI-compatible endpoint when ``LLM_BASE_URL`` is set, the zero-config
mock otherwise — so enrichment infers nothing until a model is wired, never failing.
"""

from __future__ import annotations

from cicero.adapters.enrichment.metadata.mock import MockMetadataInferer
from cicero.adapters.enrichment.metadata.openai import OpenAIMetadataInferer
from cicero.entrypoints.dependencies import make_metadata_inferer
from cicero.entrypoints.settings import Settings

_REQUIRED = {
    "database_url": "postgresql+asyncpg://u:p@db:5432/cicero",
    "s3_endpoint_url": "http://minio:9000",
    "s3_access_key_id": "key",
    "s3_secret_access_key": "secret",
}


def _settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, **{**_REQUIRED, **overrides})


def test_defaults_to_the_mock_without_an_llm_endpoint():
    assert isinstance(make_metadata_inferer(_settings()), MockMetadataInferer)


def test_selects_openai_when_a_base_url_is_configured():
    inferer = make_metadata_inferer(
        _settings(llm_base_url="https://llm.test/v1", llm_model="some-model")
    )

    assert isinstance(inferer, OpenAIMetadataInferer)
