"""What one storage call is allowed to cost (ADR-034).

botocore is happy to supply its own timeouts and attempt count; these pin the numbers
the app actually runs on. Constructing a boto3 client opens no connection, so this
needs no MinIO — the round trips are proven in `tests/integration/`.
"""

from cicero.adapters.storage.s3 import DEFAULT_STORAGE, S3DocumentStorage, StoragePolicy

_CREDENTIALS = {
    "endpoint_url": "http://localhost:9000",
    "access_key_id": "key",
    "secret_access_key": "secret",
    "bucket": "documents",
    "region_name": "us-east-1",
}


def _config(policy: StoragePolicy | None = None):
    kwargs = {} if policy is None else {"policy": policy}
    return S3DocumentStorage(**_CREDENTIALS, **kwargs)._client.meta.config


class TestStorageCallBudget:
    def test_the_client_is_built_from_the_policy(self):
        config = _config(StoragePolicy(connect_timeout=2.0, read_timeout=7.0, max_attempts=4))

        assert config.connect_timeout == 2.0
        assert config.read_timeout == 7.0

    def test_max_attempts_counts_tries_not_retries(self):
        # botocore's own `max_attempts` key counts retries, so 4 there would mean 5
        # calls. The policy means what it says.
        config = _config(StoragePolicy(max_attempts=4))

        assert config.retries["total_max_attempts"] == 4

    def test_a_storage_built_without_a_policy_still_states_its_numbers(self):
        config = _config()

        assert config.connect_timeout == DEFAULT_STORAGE.connect_timeout
        assert config.read_timeout == DEFAULT_STORAGE.read_timeout
        assert config.retries["total_max_attempts"] == DEFAULT_STORAGE.max_attempts
