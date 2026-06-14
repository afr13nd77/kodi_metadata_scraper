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


# --- Tests for get_kp_id_by_imdb_id ---


class TestGetKpIdSuccess:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_success(self, mock_urlopen: MagicMock) -> None:
        """Успешный запрос: возвращает KP ID и логирует info с 'найден KP ID'."""
        bindings = [{"kpId": {"value": "326"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result == 326
        info_calls = [str(c) for c in logger.info.call_args_list]
        assert any("найден KP ID" in c for c in info_calls)

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_not_found(self, mock_urlopen: MagicMock) -> None:
        """Пустой список bindings: возвращает 0."""
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response([]))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result == 0


class TestGetKpIdInputValidation:
    def test_get_kp_id_invalid_imdb_id(self) -> None:
        """Невалидный формат IMDB ID: возвращает 0 и логирует warning."""
        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("12345")

        assert result == 0
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("невалидный формат IMDB ID" in c for c in warning_calls)

    def test_get_kp_id_empty_imdb_id(self) -> None:
        """Пустая строка IMDB ID: возвращает 0."""
        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("")

        assert result == 0


class TestGetKpIdNetworkErrors:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_timeout(self, mock_urlopen: MagicMock) -> None:
        """URLError (timeout): возвращает None и логирует warning."""
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result is None
        logger.warning.assert_called()

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_http_error(self, mock_urlopen: MagicMock) -> None:
        """HTTPError 500: возвращает None."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://query.wikidata.org/sparql", 500, "Server Error", {}, None
        )

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result is None


class TestGetKpIdParseErrors:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_invalid_json(self, mock_urlopen: MagicMock) -> None:
        """Невалидный JSON в ответе: возвращает None."""
        mock_urlopen.return_value = _make_mock_response(b"not json")

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result is None

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_invalid_kp_format(self, mock_urlopen: MagicMock) -> None:
        """Нечисловой KP ID: возвращает 0 и логирует warning с 'невалидный формат'."""
        bindings = [{"kpId": {"value": "not_a_number"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result == 0
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("невалидный формат KP ID" in c for c in warning_calls)

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_negative_value(self, mock_urlopen: MagicMock) -> None:
        """Отрицательный KP ID: возвращает 0 и логирует warning."""
        bindings = [{"kpId": {"value": "-5"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result == 0
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("невалидный KP ID" in c for c in warning_calls)

    @patch("wikidata_client.urllib.request.urlopen")
    def test_get_kp_id_zero_value(self, mock_urlopen: MagicMock) -> None:
        """KP ID = 0: возвращает 0 и логирует warning."""
        bindings = [{"kpId": {"value": "0"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_kp_id_by_imdb_id("tt0073486")

        assert result == 0
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("невалидный KP ID" in c for c in warning_calls)


class TestGetKpIdSparqlQueryContents:
    @patch("wikidata_client.urllib.request.urlopen")
    def test_sparql_query_contains_imdb_id(self, mock_urlopen: MagicMock) -> None:
        """SPARQL-запрос содержит P345 и переданный imdb_id."""
        bindings = [{"kpId": {"value": "326"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        client.get_kp_id_by_imdb_id("tt0073486")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        url = request_obj.full_url
        assert "P345" in url
        assert "tt0073486" in url

    @patch("wikidata_client.urllib.request.urlopen")
    def test_sparql_query_uses_p2603_for_kp(self, mock_urlopen: MagicMock) -> None:
        """SPARQL-запрос содержит P2603 для поиска KP ID."""
        bindings = [{"kpId": {"value": "326"}}]
        mock_urlopen.return_value = _make_mock_response(_make_sparql_response(bindings))

        logger = MagicMock()
        client = WikidataClient(logger)
        client.get_kp_id_by_imdb_id("tt0073486")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        url = request_obj.full_url
        assert "P2603" in url
