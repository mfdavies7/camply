"""
Aspira (ReserveAmerica) provider and search tests, offline
"""

from datetime import date
from types import SimpleNamespace
from unittest import mock

import pytest

from spotsnagger.providers.aspira import aspira_provider
from spotsnagger.providers.aspira.aspira_provider import (
    Aspira,
    parse_campground_directory,
    parse_interests,
    parse_permit_calendar,
    parse_search_results,
    parse_site_list,
)
from spotsnagger.search.search_aspira import SearchAspira

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


def test_parse_interests():
    page = (
        "<select name='interest' id='interest'><option selected='selected' "
        "value='select'>-- Please Select --</option><option  value='camping'>"
        "Camping &amp; Lodging</option><option  value='permit'>Backcountry Camping"
        "</option><option  value='tour'>Tours</option><option  value='dayuse'>"
        "Day Use</option></select>"
    )
    assert parse_interests(page) == [
        {"id": 0, "name": "Camping & Lodging"},
        {"id": 2, "name": "Backcountry Camping"},
        {"id": 1, "name": "Day Use"},
    ]
    assert parse_interests("") == [{"id": 0, "name": "Camping"}]


def test_parse_search_results():
    page = (
        "<a href='/permits/x/r/unifSearchInterface.do?interface=%2FwildernessArea"
        "Details.do&page=detail&contractCode=ABPP&parkId=331051' class='facility_link'"
        " title='Bow Valley &amp; Wildland'>"
    )
    assert parse_search_results(page) == {331051: "Bow Valley & Wildland"}


def test_parse_permit_calendar():
    def cell(status, day):
        link = (
            f"<a href='/entranceDetails.do?entranceId=57715&amp;arvdate=07/{day}/2027'>"
            if status == "a"
            else "<div class='permitStatus'>X</div>"
        )
        return f"<div class='status {status} avail_cell' title='A<br># 1'> {link}</div>"

    page = (
        "<div class='avail_row header_dates'><div class='date'>10</div></div>"
        "<div class='avail_row'> <div class='stiPermitRow avail_cell'><span "
        "class='entranceCode'>Lillian Lake</span></div>"
        + cell("x", 10)
        + cell("a", 11)
        + "</div>"
    )
    first = date(2027, 7, 10)
    assert parse_permit_calendar(page, first) == {
        "Lillian Lake": {
            date(2027, 7, 11): "/entranceDetails.do?entranceId=57715&arvdate=07/11/2027"
        }
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
    unlisted = SITE_LIST.replace(
        "<div class='td maxPeopleCell'>6</div>", "<div class='td maxPeopleCell'></div>"
    )
    assert parse_site_list(unlisted)[0]["max_people"] is None


def test_party_size_filter():
    search = SearchAspira.__new__(SearchAspira)
    search.campsite_finder = mock.Mock()
    search.campsite_finder.rec_area_lookup.return_value = (
        "",
        "",
        SimpleNamespace(recreation_area="Sask"),
    )
    search.campsite_finder.list_available_sites.return_value = [
        {
            "site_id": i,
            "site_name": str(i),
            "loop": None,
            "site_type": None,
            "max_people": cap,
            "booking_url": "https://x",
        }
        for i, cap in enumerate([2, 6, None])
    ]
    search.search_window = [
        mock.Mock(
            get_current_start_date=lambda: date(2027, 7, 10), end_date=date(2027, 7, 12)
        )
    ]
    search.campgrounds = [SimpleNamespace(facility_name="Park", facility_id="1")]
    search._recreation_area_id = 3
    search.booking_category_id = 0
    search.campsites = set()
    search.party_size = 4
    sites = search.get_all_campsites()
    # too small skipped; unlisted capacity kept
    assert [(s.campsite_id, s.campsite_occupancy) for s in sites] == [
        (1, (1, 6)),
        (2, (1, 4)),
    ]


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


def test_list_backcountry_sites(monkeypatch):
    provider = Aspira()
    monkeypatch.setattr(provider, "_request", lambda url, data=None: _response(url))
    nights = {
        date(2027, 7, 10): "/entranceDetails.do?entranceId=57715&arvdate=07/10/2027",
        date(2027, 7, 11): "/b",
    }
    monkeypatch.setattr(
        aspira_provider,
        "parse_permit_calendar",
        lambda page, first: {"Lillian Lake": nights, "Ribbon Falls": {first: "/c"}},
    )
    (site,) = provider.list_backcountry_sites(1, 331053, date(2027, 7, 10), 2)
    assert site["site_id"] == 57715 and site["site_name"] == "Lillian Lake"
    assert site["booking_url"] == (
        "https://shop.albertaparks.ca/entranceDetails.do?entranceId=57715"
        "&arvdate=07/10/2027"
    )
