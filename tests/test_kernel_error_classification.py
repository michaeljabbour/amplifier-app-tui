"""WS8 phase 1: ProviderNotice classification + scrub-at-the-boundary.

The provider-notice branch of ``kernel/events.normalize`` is the single
place raw provider failures become typed records: the verbatim message
is scrubbed (never truncated), the failure is classified into an
app-local category, and the provider id is preserved when known.
"""

from __future__ import annotations

import pytest

from amplifier_app_tui.kernel.events import ProviderNotice, normalize
from amplifier_app_tui.model.redaction import REDACTION_PLACEHOLDER

SID = {"session_id": "sess-1", "parent_id": None}


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        # auth
        ({"message": "AuthenticationError: invalid api key"}, "auth"),
        ({"error_type": "AuthenticationError", "message": "invalid API key"}, "auth"),
        ({"error": {"type": "auth", "message": "HTTP 401 unauthorized"}}, "auth"),
        ({"status_code": 401, "message": "boom"}, "auth"),
        ({"status_code": "403", "message": "forbidden"}, "auth"),
        # quota
        ({"message": "RateLimitError: rate limit exceeded, retry after 30s"}, "quota"),
        ({"error_type": "RateLimitError", "message": "slow down"}, "quota"),
        ({"status_code": 429, "message": "too many requests"}, "quota"),
        ({"message": "insufficient_quota: billing hard limit reached"}, "quota"),
        # timeout
        ({"message": "APITimeoutError: request timed out"}, "timeout"),
        ({"error_type": "APITimeoutError", "message": "boom"}, "timeout"),
        ({"status_code": 408, "message": "boom"}, "timeout"),
        ({"status_code": 504, "message": "gateway timeout"}, "timeout"),
        ({"message": "connection timed out after 60s"}, "timeout"),
        # network
        ({"message": "APIConnectionError: connection refused"}, "network"),
        ({"error_type": "APIConnectionError", "message": "boom"}, "network"),
        ({"message": "Error communicating with API: [Errno 61] Connection refused"}, "network"),
        ({"message": "dns resolution failed for api.anthropic.com"}, "network"),
        # model
        ({"message": "NotFoundError: 404 model not found"}, "model"),
        ({"error_type": "NotFoundError", "message": "boom"}, "model"),
        ({"message": "no such model: claude-99"}, "model"),
        ({"message": "model_not_found: claude-99 does not exist"}, "model"),
        # precedence: a timeout that mentions connection classifies timeout
        ({"message": "Connection timeout while streaming"}, "timeout"),
    ],
)
def test_category_classification(payload: dict, expected: str) -> None:
    event = normalize("provider:error", {**SID, **payload})
    assert isinstance(event, ProviderNotice)
    assert event.category == expected


def test_unknown_garbage_message_stays_unknown() -> None:
    event = normalize("provider:error", {**SID, "message": "blorp zagnut frumious"})
    assert isinstance(event, ProviderNotice)
    assert event.category == "unknown"


def test_secret_scrubbed_at_boundary() -> None:
    secret = "sk-ant-" + "fake-12345"
    message = f"AuthenticationError: invalid api key '{secret}' for account"
    event = normalize("provider:error", {**SID, "message": message})
    assert isinstance(event, ProviderNotice)
    assert secret not in event.message
    assert REDACTION_PLACEHOLDER in event.message
    assert event.category == "auth"


def test_message_never_truncated() -> None:
    long_message = "APIConnectionError: connection dropped mid-stream. " + ("details " * 90)
    assert len(long_message) > 500
    event = normalize("provider:error", {**SID, "message": long_message})
    assert isinstance(event, ProviderNotice)
    assert event.message == long_message
    assert event.category == "network"


def test_provider_id_preserved() -> None:
    event = normalize(
        "provider:error",
        {**SID, "provider": "anthropic", "status_code": 429, "message": "rate limit"},
    )
    assert isinstance(event, ProviderNotice)
    assert event.provider == "anthropic"
    assert event.category == "quota"


def test_provider_defaults_empty_when_absent() -> None:
    event = normalize("provider:error", {**SID, "message": "boom"})
    assert isinstance(event, ProviderNotice)
    assert event.provider == ""


def test_retry_and_throttle_also_classify() -> None:
    retry = normalize("provider:retry", {**SID, "message": "rate limit, retrying"})
    throttle = normalize("provider:throttle", {**SID, "message": "rate limit, backing off"})
    assert isinstance(retry, ProviderNotice)
    assert isinstance(throttle, ProviderNotice)
    assert retry.category == "quota"
    assert throttle.category == "quota"


def test_envelope_fields_unchanged() -> None:
    """Regression: adding category/provider must not disturb the old shape."""
    event = normalize(
        "provider:error",
        {"session_id": "sess-9", "parent_id": "root", "message": "boom"},
    )
    assert isinstance(event, ProviderNotice)
    assert event.kind == "provider_notice"
    assert event.notice == "error"
    assert event.message == "boom"
    assert event.session_id == "sess-9"
    assert event.parent_id == "root"
    assert event.event_id
    assert event.ts > 0
    assert set(event.model_dump()) == {
        "kind",
        "notice",
        "message",
        "category",
        "provider",
        "event_id",
        "session_id",
        "parent_id",
        "ts",
    }
