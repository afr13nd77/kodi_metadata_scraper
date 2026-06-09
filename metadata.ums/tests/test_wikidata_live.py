from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wikidata_client import WikidataClient


def _sparql_available() -> bool:
    """Проверить доступность Wikidata SPARQL endpoint."""
    import urllib.request
    import urllib.error
    req = urllib.request.Request(
        "https://query.wikidata.org/sparql?query=ASK%20%7B%7D&format=json",
        headers={"User-Agent": "UMS-Kodi/3.16 (test)", "Accept": "application/sparql-results+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


_skip_reason = "Wikidata SPARQL endpoint unavailable"
_sparql_ok = _sparql_available()

FILMS_WITH_IMDB = [
    (5212143, "tt23558280", "Elevation (2024)"),
    (462606, "tt1219289", "Limitless (2011)"),
    (507, "tt0088247", "The Terminator (1984)"),
]

FILMS_WITHOUT_IMDB = [
    (301, "The Matrix (1999)"),
    (1194671, "Silent Zone (2025)"),
]


@pytest.mark.timeout(30)
class TestWikidataLive:
    """Live-тесты WikidataClient: реальные SPARQL-запросы к query.wikidata.org."""

    @pytest.mark.skipif(not _sparql_ok, reason=_skip_reason)
    @pytest.mark.live
    @pytest.mark.parametrize(
        "kp_id,expected_imdb,title",
        FILMS_WITH_IMDB,
        ids=[f[2] for f in FILMS_WITH_IMDB],
    )
    def test_resolve_imdb_found(self, kp_id, expected_imdb, title):
        """Wikidata возвращает правильный IMDB ID для фильма с P2603."""
        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(kp_id)
        assert result == expected_imdb, (
            f"Для {title} (kp_id={kp_id}) ожидался {expected_imdb}, получен {result}"
        )

    @pytest.mark.skipif(not _sparql_ok, reason=_skip_reason)
    @pytest.mark.live
    @pytest.mark.parametrize(
        "kp_id,title",
        FILMS_WITHOUT_IMDB,
        ids=[f[1] for f in FILMS_WITHOUT_IMDB],
    )
    def test_resolve_imdb_not_found(self, kp_id, title):
        """Wikidata возвращает пустую строку для фильма без P2603."""
        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(kp_id)
        assert result == "", (
            f"Для {title} (kp_id={kp_id}) ожидалась пустая строка, получен {result}"
        )

    @pytest.mark.skipif(not _sparql_ok, reason=_skip_reason)
    @pytest.mark.live
    def test_nonexistent_kp_id_returns_empty(self):
        """KP ID, которого точно нет в Wikidata, должен вернуть пустую строку."""
        logger = MagicMock()
        client = WikidataClient(logger)
        result = client.get_imdb_id_by_kp_id(999999999)
        assert result == "", (
            f"Для несуществующего kp_id=999999999 ожидалась пустая строка, получен {result}"
        )
