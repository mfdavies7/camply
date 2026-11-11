"""
Web UI request handling (no network)
"""

import json

from spotsnagger.containers import CampgroundFacility
from spotsnagger.providers import Aspira, GoingToCamp
from spotsnagger.web import handle_api


def _search(**body):
    return handle_api("POST", "/api/search", "", json.dumps(body).encode())


def test_parks_listed() -> None:
    status, parks = handle_api("GET", "/api/parks", "", b"")
    assert status == 200
    assert {
        "id": 1,
        "name": "Long Point Region",
        "location": "Ontario, CA",
        "url": "https://longpoint.goingtocamp.com/",
    } in parks
    assert {
        "id": "aspira-3",
        "name": "Saskatchewan Provincial Parks",
        "location": "Saskatchewan, CA",
        "url": "https://parks.saskatchewan.ca/",
    } in parks


def test_aspira_booking_categories(monkeypatch) -> None:
    monkeypatch.setattr(
        Aspira,
        "list_booking_categories",
        lambda self, r: [{"id": 2, "name": "Backcountry Camping"}],
    )
    status, categories = handle_api(
        "GET", "/api/booking_categories", "rec_area=aspira-1", b""
    )
    assert status == 200 and categories == [
        {
            "id": 2,
            "name": "Backcountry Camping",
            "url": "https://shop.albertaparks.ca/unifSearch.do?interest=permit"
            "&contractCode=ABPP",
        }
    ]


def test_campground_links(monkeypatch) -> None:
    facility = CampgroundFacility(
        facility_name="Backus",
        recreation_area="Long Point Region",
        facility_id=-7,
        recreation_area_id=1,
        map_id=-9,
    )
    monkeypatch.setattr(GoingToCamp, "find_campgrounds", lambda self, **kw: [facility])
    monkeypatch.setattr(Aspira, "find_campgrounds", lambda self, **kw: [facility])
    _, [gtc] = handle_api("GET", "/api/campgrounds", "rec_area=1", b"")
    assert gtc["url"] == (
        "https://longpoint.goingtocamp.com/create-booking/results"
        "?bookingCategoryId=0&mapId=-9&resourceLocationId=-7"
    )
    _, [asp] = handle_api(
        "GET", "/api/campgrounds", "rec_area=aspira-1&booking_category=2", b""
    )
    assert asp["url"] == (
        "https://shop.albertaparks.ca/wildernessAreaDetails.do?page=detail"
        "&contractCode=ABPP&parkId=-7"
    )


def test_search_validation() -> None:
    base = {"rec_area": 1, "campground": "-2147483648", "nights": 1}
    status, body = _search(**base, start_date="2023-06-10", end_date="2023-06-09")
    assert status == 400 and "after the start date" in body["error"]
    status, body = _search(
        **{**base, "nights": 5}, start_date="2023-06-10", end_date="2023-06-12"
    )
    assert status == 400 and "Nights" in body["error"]
    status, body = _search(
        **{**base, "campground": ""}, start_date="2023-06-10", end_date="2023-06-12"
    )
    assert status == 400 and "campground" in body["error"]
    status, body = _search(
        **{**base, "rec_area": 99999}, start_date="2023-06-10", end_date="2023-06-12"
    )
    assert status == 400 and "Unknown park" in body["error"]
    status, body = _search(
        **{**base, "rec_area": "aspira-99"},
        start_date="2023-06-10",
        end_date="2023-06-12",
    )
    assert status == 400 and "Unknown park" in body["error"]


def test_unknown_route() -> None:
    assert handle_api("GET", "/api/nope", "", b"")[0] == 404
