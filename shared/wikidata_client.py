from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from logger import Logger


_IMDB_ID_RE = re.compile(r'^tt\d{7,8}$')


class WikidataClient:
    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    USER_AGENT = "UMS-Kodi/3.16 (metadata scraper)"
    TIMEOUT = 10

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def get_imdb_id_by_kp_id(self, kp_id: int) -> Optional[str]:
        """SPARQL query: P2603 (KP ID) -> P345 (IMDB ID).

        Returns:
            "tt0073486" -- success
            "" -- not found in Wikidata, or invalid IMDB format
            None -- network/parse error (should NOT be cached)
        """
        sparql = f'SELECT ?imdb WHERE {{ ?film wdt:P2603 "{kp_id}" . ?film wdt:P345 ?imdb . }}'
        params = urllib.parse.urlencode({"query": sparql, "format": "json"})
        url = f"{self.SPARQL_ENDPOINT}?{params}"

        self._logger.info(f"WikidataClient: запрос IMDB ID для kp_id={kp_id}")

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/sparql-results+json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as response:
                raw = response.read()
            data = json.loads(raw)
            bindings = data["results"]["bindings"]
        except urllib.error.HTTPError as exc:
            self._logger.warning(f"WikidataClient: HTTP ошибка kp_id={kp_id}: {exc.code} {exc.reason}")
            return None
        except urllib.error.URLError as exc:
            self._logger.warning(f"WikidataClient: сетевая ошибка kp_id={kp_id}: {exc.reason}")
            return None
        except (json.JSONDecodeError, KeyError) as exc:
            self._logger.warning(f"WikidataClient: ошибка разбора ответа kp_id={kp_id}: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(f"WikidataClient: неожиданная ошибка kp_id={kp_id}: {exc}")
            return None

        if not bindings:
            self._logger.info(f"WikidataClient: IMDB ID не найден для kp_id={kp_id}")
            return ""

        imdb_id = bindings[0]["imdb"]["value"]

        if not _IMDB_ID_RE.match(imdb_id):
            self._logger.warning(
                f"WikidataClient: невалидный формат IMDB ID '{imdb_id}' для kp_id={kp_id}"
            )
            return ""

        self._logger.info(f"WikidataClient: найден IMDB ID={imdb_id} для kp_id={kp_id}")
        return imdb_id
