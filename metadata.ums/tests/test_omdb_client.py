import json
import socket
import urllib.error
from unittest.mock import MagicMock, patch

from omdb_client import OmdbClient, OmdbRatings, parse_rt_rating, parse_mc_rating


def _make_response(body_dict: dict) -> MagicMock:
    """Create a mock urllib response that works as a context manager."""
    body_bytes = json.dumps(body_dict).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body_bytes
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_raw_response(raw_body: bytes) -> MagicMock:
    """Create a mock urllib response with raw bytes."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = raw_body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


FULL_OMDB_RESPONSE = {
    "Title": "The Shawshank Redemption",
    "Year": "1994",
    "imdbRating": "9.3",
    "imdbVotes": "2,700,000",
    "Ratings": [
        {"Source": "Internet Movie Database", "Value": "9.3/10"},
        {"Source": "Rotten Tomatoes", "Value": "91%"},
        {"Source": "Metacritic", "Value": "82/100"},
    ],
    "Response": "True",
}


class TestGetRatingsSuccess:
    def test_full_ratings(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt0111161")

        assert result is not None
        assert isinstance(result, OmdbRatings)
        assert result.imdb_rating == "9.3"
        assert result.imdb_votes == "2,700,000"
        assert result.rotten_tomatoes == "91%"
        assert result.metacritic == "82"
        logger.info.assert_called()

    def test_url_contains_apikey_and_imdb_id(self):
        client = OmdbClient(api_key="my_secret_key")
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client.get_ratings("tt0111161")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        url = request_obj.full_url
        assert "apikey=my_secret_key" in url
        assert "i=tt0111161" in url
        assert "type=movie" in url

    def test_timeout_is_3_seconds(self):
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client.get_ratings("tt0111161")

        call_args = mock_urlopen.call_args
        assert call_args[1].get("timeout") == 3 or call_args[0][1] == 3


class TestMissingRatings:
    def test_no_rotten_tomatoes(self):
        data = {
            "Title": "Some Movie",
            "imdbRating": "7.5",
            "imdbVotes": "100,000",
            "Ratings": [
                {"Source": "Internet Movie Database", "Value": "7.5/10"},
            ],
            "Response": "True",
        }
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt1234567")

        assert result is not None
        assert result.imdb_rating == "7.5"
        assert result.rotten_tomatoes == ""
        assert result.metacritic == ""

    def test_empty_ratings_array(self):
        data = {
            "Title": "Some Movie",
            "imdbRating": "6.0",
            "imdbVotes": "50,000",
            "Ratings": [],
            "Response": "True",
        }
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt1234567")

        assert result is not None
        assert result.rotten_tomatoes == ""
        assert result.metacritic == ""

    def test_no_ratings_key(self):
        data = {
            "Title": "Some Movie",
            "imdbRating": "6.0",
            "imdbVotes": "50,000",
            "Response": "True",
        }
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt1234567")

        assert result is not None
        assert result.rotten_tomatoes == ""
        assert result.metacritic == ""


class TestApiError:
    def test_response_false(self):
        data = {
            "Response": "False",
            "Error": "Movie not found!",
        }
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt9999999")

        assert result is None
        logger.warning.assert_called()
        # Should log the OMDb error message
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("Movie not found!" in c for c in warning_calls)

    def test_response_false_no_retry(self):
        """API error (Response=False) should NOT be retried."""
        data = {
            "Response": "False",
            "Error": "Invalid API key!",
        }
        client = OmdbClient(api_key="bad_key")
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = client.get_ratings("tt0111161")

        assert result is None
        # Should only call urlopen once -- no retry for API errors
        assert mock_urlopen.call_count == 1


class TestNetworkFailures:
    def test_timeout_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        timeout_exc = urllib.error.URLError(socket.timeout("timed out"))

        with patch("urllib.request.urlopen", side_effect=timeout_exc):
            result = client.get_ratings("tt0111161")

        assert result is None
        logger.warning.assert_called()

    def test_http_error_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        http_exc = urllib.error.HTTPError(
            "https://www.omdbapi.com/", 503, "Service Unavailable", {}, None
        )

        with patch("urllib.request.urlopen", side_effect=http_exc):
            result = client.get_ratings("tt0111161")

        assert result is None
        logger.warning.assert_called()

    def test_connection_refused_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        url_exc = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_exc):
            result = client.get_ratings("tt0111161")

        assert result is None

    def test_generic_exception_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        with patch("urllib.request.urlopen", side_effect=RuntimeError("VPN down")):
            result = client.get_ratings("tt0111161")

        assert result is None
        logger.warning.assert_called()

    def test_retry_on_network_error(self):
        """Network error should trigger 1 retry, then return None."""
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        url_exc = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_exc) as mock_urlopen:
            result = client.get_ratings("tt0111161")

        assert result is None
        # 1 initial + 1 retry = 2 calls
        assert mock_urlopen.call_count == 2

    def test_retry_success_on_second_attempt(self):
        """First attempt fails, second succeeds."""
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        url_exc = urllib.error.URLError("Connection refused")
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", side_effect=[url_exc, mock_resp]):
            result = client.get_ratings("tt0111161")

        assert result is not None
        assert result.imdb_rating == "9.3"


class TestInvalidJson:
    def test_malformed_json(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        mock_resp = _make_raw_response(b"not valid json {{{")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt0111161")

        assert result is None
        logger.warning.assert_called()

    def test_empty_body(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        mock_resp = _make_raw_response(b"")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt0111161")

        assert result is None


class TestEmptyImdbId:
    def test_empty_string(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.get_ratings("")

        assert result is None
        logger.warning.assert_called()

    def test_whitespace_only(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.get_ratings("   ")

        assert result is None
        logger.warning.assert_called()

    def test_none_value(self):
        """Passing None should not raise."""
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.get_ratings(None)  # type: ignore[arg-type]

        assert result is None


class TestNoLogger:
    def test_works_without_logger(self):
        """Client should work fine when no logger is provided."""
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_ratings("tt0111161")

        assert result is not None
        assert result.imdb_rating == "9.3"

    def test_failure_without_logger(self):
        """Failure should not crash when no logger is provided."""
        client = OmdbClient(api_key="test_key")

        with patch("urllib.request.urlopen", side_effect=RuntimeError("fail")):
            result = client.get_ratings("tt0111161")

        assert result is None


class TestSanitizeUrl:
    def test_api_key_is_masked(self):
        client = OmdbClient(api_key="secret123")
        sanitized = client._sanitize_url(
            "https://www.omdbapi.com/?apikey=secret123&i=tt0111161"
        )
        assert "secret123" not in sanitized
        assert "***" in sanitized

    def test_empty_api_key(self):
        client = OmdbClient(api_key="")
        url = "https://www.omdbapi.com/?apikey=&i=tt0111161"
        sanitized = client._sanitize_url(url)
        assert sanitized == url  # nothing to sanitize


# ---------------------------------------------------------------------------
# Tests for get_episode_rating
# ---------------------------------------------------------------------------

class TestGetEpisodeRatingSuccess:
    def test_valid_rating(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        data = {
            "Title": "Pilot",
            "imdbRating": "9.0",
            "Response": "True",
        }
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_episode_rating("tt0903747", season=1, episode=1)

        assert result == 9.0
        logger.info.assert_called()

    def test_url_contains_season_and_episode(self):
        client = OmdbClient(api_key="test_key")
        data = {
            "Title": "Pilot",
            "imdbRating": "8.5",
            "Response": "True",
        }
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client.get_episode_rating("tt0903747", season=2, episode=5)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        url = request_obj.full_url
        assert "Season=2" in url
        assert "Episode=5" in url
        assert "i=tt0903747" in url


class TestGetEpisodeRatingEmpty:
    def test_empty_imdb_id_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.get_episode_rating("", season=1, episode=1)

        assert result is None
        logger.warning.assert_called()

    def test_whitespace_imdb_id_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.get_episode_rating("   ", season=1, episode=1)

        assert result is None


class TestGetEpisodeRatingApiError:
    def test_response_false_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        data = {
            "Response": "False",
            "Error": "Episode not found!",
        }
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_episode_rating("tt0903747", season=1, episode=1)

        assert result is None
        logger.warning.assert_called()

    def test_imdb_rating_na_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        data = {
            "Title": "Upcoming Episode",
            "imdbRating": "N/A",
            "Response": "True",
        }
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_episode_rating("tt0903747", season=5, episode=10)

        assert result is None


class TestGetEpisodeRatingNetworkError:
    def test_retry_then_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        url_exc = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_exc) as mock_urlopen:
            result = client.get_episode_rating("tt0903747", season=1, episode=1)

        assert result is None
        # 1 initial + 1 retry = 2 calls
        assert mock_urlopen.call_count == 2

    def test_retry_success_on_second_attempt(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        url_exc = urllib.error.URLError("Connection refused")
        data = {
            "Title": "Pilot",
            "imdbRating": "9.5",
            "Response": "True",
        }
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", side_effect=[url_exc, mock_resp]):
            result = client.get_episode_rating("tt0903747", season=1, episode=1)

        assert result == 9.5


class TestGetEpisodeRatingInvalidJson:
    def test_malformed_json_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        mock_resp = _make_raw_response(b"not valid json {{{")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_episode_rating("tt0903747", season=1, episode=1)

        assert result is None
        logger.warning.assert_called()

    def test_empty_body_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)
        mock_resp = _make_raw_response(b"")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_episode_rating("tt0903747", season=1, episode=1)

        assert result is None


# ---------------------------------------------------------------------------
# Tests for parse_rt_rating
# ---------------------------------------------------------------------------

class TestParseRtRating:
    def test_valid_percentage(self):
        assert parse_rt_rating("91%") == 91.0

    def test_zero_percent(self):
        assert parse_rt_rating("0%") == 0.0

    def test_hundred_percent(self):
        assert parse_rt_rating("100%") == 100.0

    def test_no_percent_sign(self):
        assert parse_rt_rating("85") == 85.0

    def test_whitespace(self):
        assert parse_rt_rating("  91%  ") == 91.0

    def test_empty_string(self):
        assert parse_rt_rating("") is None

    def test_na_string(self):
        assert parse_rt_rating("N/A") is None

    def test_text_value(self):
        assert parse_rt_rating("Fresh") is None

    def test_logs_on_success(self):
        logger = MagicMock()
        parse_rt_rating("91%", logger)
        logger.debug.assert_called_once()

    def test_logs_on_failure(self):
        logger = MagicMock()
        parse_rt_rating("N/A", logger)
        logger.debug.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for parse_mc_rating
# ---------------------------------------------------------------------------

class TestParseMcRating:
    def test_valid_number(self):
        assert parse_mc_rating("82") == 82.0

    def test_zero(self):
        assert parse_mc_rating("0") == 0.0

    def test_hundred(self):
        assert parse_mc_rating("100") == 100.0

    def test_whitespace(self):
        assert parse_mc_rating("  82  ") == 82.0

    def test_empty_string(self):
        assert parse_mc_rating("") is None

    def test_na_string(self):
        assert parse_mc_rating("N/A") is None

    def test_text_value(self):
        assert parse_mc_rating("tbd") is None

    def test_logs_on_success(self):
        logger = MagicMock()
        parse_mc_rating("82", logger)
        logger.debug.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for fetch_ratings_raw
# ---------------------------------------------------------------------------

class TestFetchRatingsRawSuccess:
    def test_returns_dict(self):
        """fetch_ratings_raw returns the raw dict, not OmdbRatings."""
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.fetch_ratings_raw("tt0111161")

        assert result is not None
        assert isinstance(result, dict)
        assert result["imdbRating"] == "9.3"
        assert result["Response"] == "True"

    def test_returns_full_response_dict(self):
        """The returned dict contains all OMDb fields, not just ratings."""
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.fetch_ratings_raw("tt0111161")

        assert result is not None
        assert result["Title"] == "The Shawshank Redemption"
        assert result["Year"] == "1994"
        assert result["imdbVotes"] == "2,700,000"
        assert len(result["Ratings"]) == 3


class TestFetchRatingsRawFailures:
    def test_empty_imdb_id_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.fetch_ratings_raw("")

        assert result is None
        logger.warning.assert_called()

    def test_whitespace_imdb_id_returns_none(self):
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.fetch_ratings_raw("   ")

        assert result is None

    def test_none_imdb_id_returns_none(self):
        client = OmdbClient(api_key="test_key")

        result = client.fetch_ratings_raw(None)  # type: ignore[arg-type]

        assert result is None

    def test_response_false_returns_none(self):
        data = {
            "Response": "False",
            "Error": "Movie not found!",
        }
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.fetch_ratings_raw("tt9999999")

        assert result is None

    def test_response_false_no_retry(self):
        """API error (Response=False) should NOT be retried."""
        data = {
            "Response": "False",
            "Error": "Invalid API key!",
        }
        client = OmdbClient(api_key="bad_key")
        mock_resp = _make_response(data)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = client.fetch_ratings_raw("tt0111161")

        assert result is None
        assert mock_urlopen.call_count == 1

    def test_network_error_returns_none(self):
        client = OmdbClient(api_key="test_key")
        url_exc = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_exc):
            result = client.fetch_ratings_raw("tt0111161")

        assert result is None

    def test_retry_on_network_error(self):
        """Network error should trigger 1 retry, then return None."""
        client = OmdbClient(api_key="test_key")
        url_exc = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_exc) as mock_urlopen:
            result = client.fetch_ratings_raw("tt0111161")

        assert result is None
        assert mock_urlopen.call_count == 2

    def test_retry_success_on_second_attempt(self):
        """First attempt fails, second succeeds -- returns raw dict."""
        client = OmdbClient(api_key="test_key")
        url_exc = urllib.error.URLError("Connection refused")
        mock_resp = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", side_effect=[url_exc, mock_resp]):
            result = client.fetch_ratings_raw("tt0111161")

        assert result is not None
        assert isinstance(result, dict)
        assert result["imdbRating"] == "9.3"

    def test_malformed_json_returns_none(self):
        client = OmdbClient(api_key="test_key")
        mock_resp = _make_raw_response(b"not valid json {{{")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.fetch_ratings_raw("tt0111161")

        assert result is None


# ---------------------------------------------------------------------------
# Tests for parse_ratings (public wrapper)
# ---------------------------------------------------------------------------

class TestParseRatings:
    def test_full_ratings(self):
        """parse_ratings converts raw dict to OmdbRatings."""
        logger = MagicMock()
        client = OmdbClient(api_key="test_key", logger=logger)

        result = client.parse_ratings(FULL_OMDB_RESPONSE, "tt0111161")

        assert isinstance(result, OmdbRatings)
        assert result.imdb_rating == "9.3"
        assert result.imdb_votes == "2,700,000"
        assert result.rotten_tomatoes == "91%"
        assert result.metacritic == "82"

    def test_missing_ratings(self):
        """parse_ratings handles missing Ratings array."""
        client = OmdbClient(api_key="test_key")
        data = {
            "Title": "Some Movie",
            "imdbRating": "7.5",
            "imdbVotes": "100,000",
            "Response": "True",
        }

        result = client.parse_ratings(data, "tt1234567")

        assert isinstance(result, OmdbRatings)
        assert result.imdb_rating == "7.5"
        assert result.rotten_tomatoes == ""
        assert result.metacritic == ""

    def test_missing_imdb_fields(self):
        """parse_ratings defaults to N/A for missing imdb fields."""
        client = OmdbClient(api_key="test_key")
        data = {"Response": "True"}

        result = client.parse_ratings(data, "tt0000000")

        assert result.imdb_rating == "N/A"
        assert result.imdb_votes == "N/A"
        assert result.rotten_tomatoes == ""
        assert result.metacritic == ""


# ---------------------------------------------------------------------------
# Tests for fetch_ratings_raw + parse_ratings roundtrip
# ---------------------------------------------------------------------------

class TestFetchParsRoundtrip:
    def test_roundtrip_equals_get_ratings(self):
        """fetch_ratings_raw + parse_ratings produces same result as get_ratings."""
        client = OmdbClient(api_key="test_key")
        mock_resp1 = _make_response(FULL_OMDB_RESPONSE)
        mock_resp2 = _make_response(FULL_OMDB_RESPONSE)

        with patch("urllib.request.urlopen", return_value=mock_resp1):
            via_get = client.get_ratings("tt0111161")

        with patch("urllib.request.urlopen", return_value=mock_resp2):
            raw = client.fetch_ratings_raw("tt0111161")
            via_roundtrip = client.parse_ratings(raw, "tt0111161")

        assert via_get == via_roundtrip
