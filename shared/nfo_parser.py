from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NfoParseResult:
    kinopoisk_id: int = 0
    imdb_id: str = ""


class NfoParser:

    _PATTERNS = [
        (
            "kinopoisk_url",
            re.compile(r"kinopoisk\.ru/(?:film|series)/(\d+)", re.IGNORECASE),
            "kinopoisk_id",
        ),
        (
            "kinopoisk_uniqueid",
            re.compile(
                r'<uniqueid\s+type=["\']kinopoisk["\']>(\d+)</uniqueid>',
                re.IGNORECASE,
            ),
            "kinopoisk_id",
        ),
        (
            "imdb_url",
            re.compile(r"(tt\d{7,8})", re.IGNORECASE),
            "imdb_id",
        ),
        (
            "imdb_uniqueid",
            re.compile(
                r'<uniqueid\s+type=["\']imdb["\']>(tt\d{7,8})</uniqueid>',
                re.IGNORECASE,
            ),
            "imdb_id",
        ),
    ]

    def __init__(self, logger):
        self._logger = logger

    def parse(self, nfo_content: str) -> NfoParseResult:
        self._logger.info("NfoParser.parse: parsing NFO content")
        result = NfoParseResult()

        for name, pattern, field_name in self._PATTERNS:
            match = pattern.search(nfo_content)
            if match:
                value = match.group(1)
                self._logger.debug(f"NfoParser.parse: matched {name} = {value}")

                if field_name == "kinopoisk_id" and not result.kinopoisk_id:
                    result.kinopoisk_id = int(value)
                elif field_name == "imdb_id" and not result.imdb_id:
                    result.imdb_id = value

        self._logger.info(
            f"NfoParser.parse: result kp={result.kinopoisk_id}, "
            f"imdb={result.imdb_id}"
        )
        return result
