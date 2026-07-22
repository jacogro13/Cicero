"""Config-selection of the summarizer (ADR-018): an OpenAI-compatible endpoint
when ``LLM_BASE_URL`` is set, the zero-config mock otherwise.
"""

from __future__ import annotations

from cicero.adapters.summarization.mock import MockSummarizer
from cicero.adapters.summarization.openai import OpenAISummarizer
from cicero.entrypoints.dependencies import make_summarizer
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
    assert isinstance(make_summarizer(_settings()), MockSummarizer)


def test_selects_openai_when_a_base_url_is_configured():
    summarizer = make_summarizer(
        _settings(llm_base_url="https://llm.test/v1", llm_model="some-model")
    )

    assert isinstance(summarizer, OpenAISummarizer)
