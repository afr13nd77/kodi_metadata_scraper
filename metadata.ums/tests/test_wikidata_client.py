from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from wikidata_client import WikidataClient


def _make_sparql_response(bindings: list) -> bytes:
    """Helper: create SPARQL JSON response bytes."""
    data = {"results": {"bindings": bindings}}
    return json.dumps(data).encode("utf-8")


def _make_mock_response(raw_bytes: bytes) -> MagicMock:
    """Helper: create a mock urllib response that works as a context manager."""
    mock_response = MagicMock()
    mock_response.read.return_value = raw_bytes
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestGetImdbIdSuccess:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_imdb_id_success(self, mock_urlopen: MagicMock) -> None:
        """Успешный запрос: возвращает IMDB ID и логирует info с 'найден IMDB ID'."""
        bindings = [{"imdb": {"value": "tt0073486"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(500)

        assert result == "tt0073486"
        info_calls = [str(c) for c in logger.info.call_args_list]
        assert any("найден IMDB ID" in c for c in info_calls)

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_imdb_id_not_found(self, mock_urlopen: MagicMock) -> None:
        """Пустой список bindings: возвращает пустую строку."""
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response([]))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(500)

        assert result == ""


class TestGetImdbIdNetworkErrors:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_imdb_id_timeout(self, mock_urlopen: MagicMock) -> None:
        """URLError (timeout): возвращает None и логирует warning."""
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(500)

        assert result is None
        logger.warning.assert_called()

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_imdb_id_http_error(self, mock_urlopen: MagicMock) -> None:
        """HTTPError 500: возвращает None."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://query.wikidata.org/sparql", 500, "Server Error", {}, None
        )

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(500)

        assert result is None


class TestGetImdbIdParseErrors:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_imdb_id_invalid_json(self, mock_urlopen: MagicMock) -> None:
        """Невалидный JSON в ответе: возвращает None."""
        mock_urlopen.return_value = _make_mock_response(b"not json")

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(500)

        assert result is None

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_imdb_id_invalid_imdb_format(self, mock_urlopen: MagicMock) -> None:
        """IMDB ID без префикса 'tt': возвращает '' и логирует warning с 'невалидный формат'."""
        bindings = [{"imdb": {"value": "12345"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(500)

        assert result == ""
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("невалидный формат" in c for c in warning_calls)


class TestSparqlQueryContents:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_sparql_query_contains_kp_id(self, mock_urlopen: MagicMock) -> None:
        """SPARQL-запрос содержит P2603 и переданный kp_id."""
        bindings = [{"imdb": {"value": "tt0073486"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        client.get_imdb_id_by_kp_id(500)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        url = request_obj.full_url
        assert "P2603" in url
        assert "500" in url

    @patch("wikidata_client.urllib.request.urlopen")
    def test_user_agent_header(self, mock_urlopen: MagicMock) -> None:
        """Request содержит корректный User-Agent header."""
        bindings = [{"imdb": {"value": "tt0073486"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        client.get_imdb_id_by_kp_id(500)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert request_obj.get_header("User-agent") == "UMS-Kodi/3.16 (metadata scraper)"
