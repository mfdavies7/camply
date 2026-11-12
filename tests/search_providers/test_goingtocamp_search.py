"""
GoingToCamp Testing Provider
"""

import logging
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from spotsnagger.containers import AvailableCampsite, SearchWindow
from spotsnagger.search import SearchGoingToCamp
from tests.conftest import vcr_cassette

logger = logging.getLogger(__name__)


@pytest.fixture
def search_window() -> SearchWindow:
    """
    Get A Search Window For September 2023

    Returns
    -------
    SearchWindow
    """
    search_window = SearchWindow(
        start_date=datetime(2023, 9, 1),
        end_date=datetime(2023, 9, 2),
    )
    return search_window


@pytest.fixture
def going_to_camp_finder(search_window) -> SearchGoingToCamp:
    """
    Assemble The Searching Class

    Returns
    -------
    SearchGoingToCamp
    """
    gtc_finder = SearchGoingToCamp(
        search_window=search_window,
        recreation_area=[1],  # Long Point Region, Ontario
        campgrounds="-2147483643",  # Waterford North Conservation Area
    )
    logger.info("GoingToCamp Campsite Searcher Established.")
    logger.info(f"Search Months: {gtc_finder.search_months}")
    return gtc_finder


@vcr_cassette
def test_going_to_camp_get_all_campsites(
    going_to_camp_finder: SearchGoingToCamp,
) -> None:
    """
    Get all GTC sites for the rec area
    """
    logger.info("Searching for Campsites")
    all_campsites = going_to_camp_finder.get_all_campsites()
    assert all_campsites
    for camp in all_campsites:
        assert isinstance(camp, AvailableCampsite)


def test_going_to_camp_party_size_filter(search_window: SearchWindow) -> None:
    """
    The GoingToCamp API ignores partySize, so sites that don't fit are dropped here
    """
    search = SearchGoingToCamp.__new__(SearchGoingToCamp)
    search.search_window = [search_window]
    search.campgrounds = [SimpleNamespace(facility_name="Lake", facility_id=-1)]
    search._recreation_area_id = 1
    search.equipment_id = None
    search.booking_category_id = 0
    search.party_size = 4
    search.tents = 1
    finder = search.campsite_finder = mock.Mock()
    capacities = {1: (None, 6), 2: (1, 3), 3: (5, 8), 4: (1, 4)}
    finder.list_site_availability.return_value = [
        SimpleNamespace(resource_id=r, map_id=-1) for r in capacities
    ]
    finder.get_site_details.side_effect = lambda area, r, cg: {
        "resourceId": r,
        "localizedValues": [{"name": str(r)}],
        "site_attributes": {},
        "minCapacity": capacities[r][0],
        "maxCapacity": capacities[r][1],
    }
    finder.rec_area_lookup.return_value = (
        "x",
        SimpleNamespace(recreation_area="Long Point"),
    )
    finder.get_reservation_link.return_value = "https://x"
    sites = search.get_all_campsites()
    assert [s.campsite_id for s in sites] == [1, 4]
    assert finder.list_site_availability.call_args.kwargs["party_size"] == 4
