"""The retry policy shared by the outbound httpx adapters (ADR-029).

The delay is pure policy, so it is pinned here rather than through an adapter: the
growth, the ceiling, the jitter, and the server's own ``Retry-After``. Nothing here
sleeps — the call sites' behaviour is asserted in each adapter's own tests.
"""

from __future__ import annotations

from cicero.adapters.http.retry import RetryPolicy, retry_delay


class TestRetryDelay:
    def test_backs_off_exponentially_within_the_jitter_window(self):
        policy = RetryPolicy(backoff=1.0)

        assert all(0.0 <= retry_delay(1, policy) <= 1.0 for _ in range(50))
        assert all(0.0 <= retry_delay(3, policy) <= 4.0 for _ in range(50))

    def test_jitters_so_callers_do_not_retry_in_lockstep(self):
        policy = RetryPolicy(backoff=1.0)

        assert len({retry_delay(3, policy) for _ in range(50)}) > 1

    def test_never_waits_longer_than_the_ceiling(self):
        policy = RetryPolicy(backoff=1.0, max_backoff=2.0)

        assert all(retry_delay(10, policy) <= 2.0 for _ in range(50))

    def test_a_retry_after_the_server_named_wins_over_the_backoff(self):
        assert retry_delay(1, RetryPolicy(backoff=1.0), retry_after=7.0) == 7.0

    def test_a_retry_after_is_capped_like_any_other_wait(self):
        # An upstream asking for an hour must not hold a worker for one.
        assert retry_delay(1, RetryPolicy(max_backoff=2.0), retry_after=3600.0) == 2.0
