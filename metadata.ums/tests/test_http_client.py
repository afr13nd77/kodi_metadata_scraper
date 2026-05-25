import time
from unittest.mock import patch, MagicMock
import urllib.error
from http_client import RateLimiter, HttpClient, HttpError


class TestRateLimiter:
    def test_acquire_no_block(self):
        rl = RateLimiter(10.0)
        start = time.monotonic()
        rl.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    def test_tokens_deplete(self):
        rl = RateLimiter(2.0)
        rl.acquire()
        rl.acquire()
        # Third acquire should block briefly
        start = time.monotonic()
        rl.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04  # should need at least some wait


class TestHttpError:
    def test_properties(self):
        err = HttpError(429, "Rate limited", "https://example.com/api")
        assert err.status_code == 429
        assert err.message == "Rate limited"
        assert err.url == "https://example.com/api"
        assert "429" in str(err)


class TestHttpClient:
    def test_get_json_success(self):
        client = HttpClient(base_url="https://api.example.com", rate_limiter=None)
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.get_json("v1/test")
            assert result == {"result": "ok"}

    def test_get_json_non_retryable_error(self):
        exc = urllib.error.HTTPError(
            "https://api.example.com/v1/test", 401, "Unauthorized", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=exc):
            client = HttpClient(base_url="https://api.example.com", rate_limiter=None)
            try:
                client.get_json("v1/test")
                assert False, "Should have raised HttpError"
            except HttpError as e:
                assert e.status_code == 401

    @patch("http_client.time.sleep")
    def test_get_json_retry_on_429(self, mock_sleep):
        exc = urllib.error.HTTPError(
            "https://api.example.com/v1/test", 429, "Too Many Requests", {}, None
        )
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", side_effect=[exc, mock_response]):
            client = HttpClient(base_url="https://api.example.com", rate_limiter=None)
            result = client.get_json("v1/test")
            assert result == {"ok": True}
            assert mock_sleep.call_count == 1

    @patch("http_client.time.sleep")
    def test_get_json_all_retries_exhausted(self, mock_sleep):
        exc = urllib.error.HTTPError(
            "https://api.example.com/v1/test", 500, "Server Error", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=[exc, exc, exc]):
            client = HttpClient(base_url="https://api.example.com", rate_limiter=None)
            try:
                client.get_json("v1/test")
                assert False, "Should have raised"
            except HttpError as e:
                assert e.status_code == 500
            assert mock_sleep.call_count == 2

    def test_build_url_with_params(self):
        client = HttpClient(base_url="https://api.example.com")
        url = client._build_url("v1/test", {"key": "value", "page": "1"})
        assert url.startswith("https://api.example.com/v1/test?")
        assert "key=value" in url
        assert "page=1" in url

    def test_build_url_no_params(self):
        client = HttpClient(base_url="https://api.example.com")
        url = client._build_url("v1/test")
        assert url == "https://api.example.com/v1/test"
