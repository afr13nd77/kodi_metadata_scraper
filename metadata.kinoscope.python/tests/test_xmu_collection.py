"""Тестовый набор X-Men Universe (XMU) — коллекционный prefix XMU###-."""

from unittest.mock import MagicMock
from utils import clean_title
import pytest


XMU_CASES = [
    ("XMU001-X-Men (2000)", "X-Men", "2000"),
    ("XMU002-X2 X-Men United (2003)", "X2 X-Men United", "2003"),
    ("XMU003-X-Men The Last Stand (2006)", "X-Men The Last Stand", "2006"),
    ("XMU004-X-Men Origins Wolverine (2009)", "X-Men Origins Wolverine", "2009"),
    ("XMU005-X-Men First Class (2011)", "X-Men First Class", "2011"),
    ("XMU006-The Wolverine (2013)", "The Wolverine", "2013"),
    ("XMU007-X-Men Days of Future Past (2014)", "X-Men Days of Future Past", "2014"),
    ("XMU008-Deadpool (2016)", "Deadpool", "2016"),
    ("XMU009-X-Men Apocalypse (2016)", "X-Men Apocalypse", "2016"),
    ("XMU010-Logan (2017)", "Logan", "2017"),
    ("XMU011-Deadpool 2 (2018)", "Deadpool 2", "2018"),
    ("XMU012-Dark Phoenix (2019)", "Dark Phoenix", "2019"),
    ("XMU013-The New Mutants (2020)", "The New Mutants", "2020"),
]


@pytest.mark.parametrize(
    "raw,expected_title,expected_year",
    XMU_CASES,
    ids=[c[0] for c in XMU_CASES],
)
def test_xmu_prefix_stripped(raw, expected_title, expected_year):
    """XMU###- prefix должен удаляться, title должен остаться чистым."""
    logger = MagicMock()
    candidates, year = clean_title(raw, logger)
    assert expected_title in candidates, f"Expected '{expected_title}' in {candidates}"
    assert year == expected_year
