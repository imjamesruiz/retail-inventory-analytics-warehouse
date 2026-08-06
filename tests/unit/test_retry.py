import httpx
import pytest

from inventory_pipeline.retry import RetryConfig, with_retry


def test_returns_result_on_first_success():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result = with_retry(fn, RetryConfig(max_retries=3, base_delay_seconds=0))
    assert result == "ok"
    assert len(calls) == 1


def test_retries_then_succeeds():
    calls = {"count": 0}

    def fn():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("transient")
        return "ok"

    result = with_retry(fn, RetryConfig(max_retries=5, base_delay_seconds=0))
    assert result == "ok"
    assert calls["count"] == 3


def test_gives_up_after_max_retries():
    def fn():
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError, match="always fails"):
        with_retry(fn, RetryConfig(max_retries=2, base_delay_seconds=0))


def test_does_not_retry_on_404():
    calls = {"count": 0}

    def fn():
        calls["count"] += 1
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    with pytest.raises(httpx.HTTPStatusError):
        with_retry(fn, RetryConfig(max_retries=5, base_delay_seconds=0))
    assert calls["count"] == 1
