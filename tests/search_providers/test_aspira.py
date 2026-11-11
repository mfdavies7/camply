"""
Aspira (ReserveAmerica) provider and search tests, offline
"""

from types import SimpleNamespace
from unittest import mock

import pytest

from camply.providers.aspira import aspira_provider
from camply.providers.aspira.aspira_provider import (
    Aspira,
    parse_campground_directory,
    parse_site_list,
)
from camply.search.search_aspira import SearchAspira

# Trimmed from parks.saskatchewan.ca pages
DIRECTORY = (
    "<td ><a href='/camping/cypress/r/campgroundDetails.do?contractCode=SKPP&amp;"
    "parkId=290125' class='book now'>Enter Date</a></td><td ><a href='/camping/"
    "cypress/r/facilityDetails.do?contractCode=SKPP&parkId=290125' tabindex='0'"
    "  >Cypress Hills Interprovincial Park<br></a></td>"
)


def _row(site_id: int, name: str, status: str) -> str:
    return (
        "<div class='br'><div class='td'><div id='maplinkicon_1'><a href='#sr_a'>"
        "Map</a></div><div class='siteListLabel'><a href='/camping/cypress/r/"
        f"campsiteDetails.do?contractCode=SKPP&amp;siteId={site_id}&amp;"
        f"parkId=290125'   aria-label='Site'  onclick='go(); return true;'>{name}"
        "</a></div></div><div class='td'>Meadows</div><div class='td'>Nightly "
        "Electric</div><div class='td maxPeopleCell'>6</div><div class='td'>32</div>"
        "<div class='td amenitiesicons'><img src='x.gif'></div><div class='td "
        f"sitescompareselectorbtn{site_id}'>{status}<br><a href='#'>x</a></div></div>"
    )


SITE_LIST = (
    "<div class='matchSummary mb5'>1 site(s) available out of 672  site(s)</div>"
    "<div id='shoppingitems' class='items'><div class='br hdr'></div>"
    + _row(1294, "M31", "available")
    + _row(1102, "Aspen50", "not available")
)


def test_parse_campground_directory():
    assert parse_campground_directory(DIRECTORY, "SKPP") == {
        290125: "Cypress Hills Interprovincial Park"
    }


def test_parse_site_list():
    available, taken = parse_site_list(SITE_LIST)
    assert available == {
        "site_id": 1294,
        "site_name": "M31",
        "loop": "Meadows",
        "site_type": "Nightly Electric",
        "max_people": 6,
        "available": True,
    }
    assert taken["available"] is False


def _response(url: str, text: str = "") -> SimpleNamespace:
    return SimpleNamespace(url=url, text=text, raise_for_status=lambda: None)


def test_request_waits_for_queue(monkeypatch):
    monkeypatch.setattr(aspira_provider, "QUEUE_POLL_SECONDS", 0)
    provider = Aspira()
    provider.session = mock.Mock()
    queue = _response("https://go.aspiraconnect.com/?c=aspira&e=snasosk02")
    provider.session.request.return_value = queue
    provider.session.get.side_effect = [
        queue,
        _response("https://parks.saskatchewan.ca/"),
    ]
    assert provider._request("https://parks.saskatchewan.ca/").url.startswith(
        "https://parks"
    )
    assert provider.session.get.call_count == 2


def test_request_queue_timeout(monkeypatch):
    monkeypatch.setattr(aspira_provider, "QUEUE_POLL_SECONDS", 0)
    monkeypatch.setattr(aspira_provider, "QUEUE_MAX_CHECKS", 2)
    provider = Aspira()
    provider.session = mock.Mock()
    provider.session.request.return_value = _response("https://go.aspiraconnect.com/")
    provider.session.get.return_value = _response("https://go.aspiraconnect.com/")
    with pytest.raises(aspira_provider.ProviderError):
        provider._request("https://parks.saskatchewan.ca/")


def test_list_available_sites(monkeypatch):
    provider = Aspira()
    monkeypatch.setattr(
        provider, "_request", lambda url, data=None: _response(url, SITE_LIST)
    )
    (site,) = provider.list_available_sites(
        3, 290125, mock.Mock(strftime=lambda f: "06/01/2023"), 2
    )
    assert site["site_id"] == 1294
    assert site["booking_url"].startswith(
        "https://parks.saskatchewan.ca/campsiteDetails.do?contractCode=SKPP"
    )


def test_continuous_search_refused():
    search = SearchAspira.__new__(SearchAspira)
    with pytest.raises(SystemExit):
        search.get_matching_campsites(continuous=True)
