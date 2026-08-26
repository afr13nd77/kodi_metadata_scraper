"""BL-71: Защита от false positive — фильмы с аббревиатурами в начале названия.
Ни один легитимный title НЕ должен обрезаться паттерном collection prefix."""

from unittest.mock import MagicMock
from utils import clean_title
import pytest


ABBREVIATION_CASES = [
    ("X-Men (2000)", "X-Men", "2000"),
    ("X-Men Days of Future Past (2014)", "X-Men Days of Future Past", "2014"),
    ("X-Files Fight the Future (1998)", "X-Files Fight the Future", "1998"),
    ("GI Joe The Rise of Cobra (2009)", "GI Joe The Rise of Cobra", "2009"),
    ("GI Joe Retaliation (2013)", "GI Joe Retaliation", "2013"),
    ("WALL-E (2008)", "WALL-E", "2008"),
    ("F9 The Fast Saga (2021)", "F9 The Fast Saga", "2021"),
    ("AI Artificial Intelligence (2001)", "AI Artificial Intelligence", "2001"),
    ("FBI Most Wanted (2020)", "FBI Most Wanted", "2020"),
    ("CIA Exiles (2022)", "CIA Exiles", "2022"),
    ("IT Chapter Two (2019)", "IT Chapter Two", "2019"),
    ("REC (2007)", "REC", "2007"),
    ("M3GAN (2023)", "M3GAN", "2023"),
    ("T2 Trainspotting (2017)", "T2 Trainspotting", "2017"),
]


@pytest.mark.parametrize(
    "raw,expected_title,expected_year",
    ABBREVIATION_CASES,
    ids=[c[0] for c in ABBREVIATION_CASES],
)
def test_abbreviation_title_not_stripped(raw, expected_title, expected_year):
    """Легитимные названия с аббревиатурами НЕ должны обрезаться."""
    logger = MagicMock()
    candidates, year = clean_title(raw, logger)
    assert expected_title in candidates, f"Expected '{expected_title}' in {candidates}"
    assert year == expected_year
