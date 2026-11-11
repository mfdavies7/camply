"""
GoingToCamp booking categories (no network)
"""

import datetime

import pytest

from spotsnagger.containers import CampgroundFacility
from spotsnagger.providers import GoingToCamp

BOOKING_CATEGORIES = [
    {
        "bookingCategoryId": 0,
        "isDisabled": False,
        "localizedValues": [{"name": "Campsite"}],
        "allowedResourceCategoryIds": [-2147483648],
        "allowedEquipmentCategories": [
            {"equipmentCategoryId": -32768, "subEquipmentCategoryId": -32767}
        ],
    },
    {
        "bookingCategoryId": 5,
        "isDisabled": False,
        "localizedValues": [{"name": "Backcountry Campsite "}],
        "allowedResourceCategoryIds": [-2147483636],
        "allowedEquipmentCategories": [],
    },
    {
        "bookingCategoryId": 9,
        "isDisabled": True,
        "localizedValues": [{"name": "Retired"}],
        "allowedResourceCategoryIds": [],
        "allowedEquipmentCategories": [],
    },
]


def _location(location_id: int, name: str, category: int) -> dict:
    return {
        "resourceLocationId": location_id,
        "localizedValues": [{"fullName": name}],
        "resourceCategoryIds": [category],
    }


@pytest.fixture
def gtc(monkeypatch) -> GoingToCamp:
    """
    GoingToCamp provider answering from canned API responses
    """
    calls = []
    responses = {
        "LIST_BOOKING_CATEGORIES": BOOKING_CATEGORIES,
        "LIST_CAMPGROUNDS": [
            _location(1, "Frontcountry Loop", -2147483648),
            _location(2, "Backcountry Lakes", -2147483636),
        ],
        "CAMP_DETAILS": [
            {"resourceLocationId": 1, "mapId": 11},
            {"resourceLocationId": 2, "mapId": 22},
        ],
        "MAPDATA": {
            "resourceAvailabilities": {"7": [{"availability": 0}]},
            "mapLinkAvailabilities": {},
        },
    }

    def fake_request(self, rec_area_id, endpoint_name, params=None):
        calls.append((endpoint_name, params))
        return responses[endpoint_name]

    monkeypatch.setattr(GoingToCamp, "_api_request", fake_request)
    provider = GoingToCamp()
    provider.calls = calls
    return provider


def test_list_booking_categories_skips_disabled(gtc: GoingToCamp) -> None:
    categories = gtc.list_booking_categories(10)
    assert [c["bookingCategoryId"] for c in categories] == [0, 5]
    gtc.list_booking_categories(10)
    assert [c[0] for c in gtc.calls].count("LIST_BOOKING_CATEGORIES") == 1


def test_find_campgrounds_by_booking_category(gtc: GoingToCamp) -> None:
    default = gtc.find_campgrounds(rec_area_id=[10])
    assert [c.facility_name for c in default] == ["Frontcountry Loop"]
    backcountry = gtc.find_campgrounds(rec_area_id=[10], booking_category_id=5)
    assert [c.facility_name for c in backcountry] == ["Backcountry Lakes"]
    with pytest.raises(SystemExit):
        gtc.find_campgrounds(rec_area_id=[10], booking_category_id=9)


def test_site_availability_and_link_use_booking_category(gtc: GoingToCamp) -> None:
    campground = CampgroundFacility(
        facility_name="Backcountry Lakes",
        recreation_area="Gatineau Park",
        facility_id=2,
        recreation_area_id=10,
        map_id=22,
    )
    start, end = datetime.date(2023, 9, 1), datetime.date(2023, 9, 2)
    sites = gtc.list_site_availability(campground, start, end, None, 5)
    assert [s.resource_id for s in sites] == [7]
    params = next(p for name, p in gtc.calls if name == "MAPDATA")
    assert params["bookingCategoryId"] == 5
    assert "equipmentCategoryId" not in params

    gtc.list_site_availability(campground, start, end, None)
    params = [p for name, p in gtc.calls if name == "MAPDATA"][-1]
    assert params["bookingCategoryId"] == 0
    assert params["equipmentCategoryId"] == -32768

    link = gtc.get_reservation_link(
        "reservations.ncc-ccn.gc.ca", 2, 22, None, None, 1, start, end, 5
    )
    assert "bookingCategoryId=5&" in link and "equipmentId=&" in link
