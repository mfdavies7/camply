"""
Web UI request handling (no network)
"""

import json

from camply.web import handle_api


def _search(**body):
    return handle_api("POST", "/api/search", "", json.dumps(body).encode())


def test_parks_listed() -> None:
    status, parks = handle_api("GET", "/api/parks", "", b"")
    assert status == 200
    assert {"id": 1, "name": "Long Point Region", "location": "Ontario, CA"} in parks
    assert {
        "id": "aspira-3",
        "name": "Saskatchewan Provincial Parks",
        "location": "Saskatchewan, CA",
    } in parks


def test_aspira_booking_categories() -> None:
    status, categories = handle_api(
        "GET", "/api/booking_categories", "rec_area=aspira-1", b""
    )
    assert status == 200 and categories == [{"id": 0, "name": "Campsite"}]


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
