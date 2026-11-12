"""
Trip search: chaining gap-free stays across campgrounds (no network)
"""

import datetime
import json
from typing import Dict, List, Optional, Set

import pytest
from pydantic import ValidationError

from spotsnagger.containers import AvailableCampsite
from spotsnagger.trip import (
    ProviderAvailability,
    Trip,
    TripLocation,
    find_itineraries,
)
from spotsnagger.web import handle_api

JUNE = datetime.date(2023, 6, 1)


def day(n: int) -> datetime.date:
    """
    June n, 2023
    """
    return JUNE.replace(day=n)


def site(campground: str, check_in: datetime.date, nights: int) -> AvailableCampsite:
    start = datetime.datetime.combine(check_in, datetime.time.min)
    return AvailableCampsite(
        campsite_id=1,
        campsite_site_name="A1",
        booking_date=start,
        booking_end_date=start + datetime.timedelta(days=nights),
        booking_nights=nights,
        campsite_loop_name="Unknown",
        campsite_type="Tent",
        campsite_occupancy=(1, 6),
        campsite_use_type="N/A",
        availability_status="Available",
        recreation_area="Long Point Region",
        recreation_area_id=1,
        facility_name=f"Campground {campground}",
        facility_id=campground,
        booking_url=f"https://example.invalid/{campground}",
    )


def fake_availability(free: Dict[str, Set[int]], calls: Optional[List] = None):
    """
    A campground's site is free for a stay when every night is in free[campground]
    """

    def available(location: TripLocation, check_in: datetime.date, nights: int):
        if calls is not None:
            calls.append((location.campgrounds[0], check_in, nights))
        return [
            site(c, check_in, nights)
            for c in location.campgrounds
            if all(check_in.day + i in free.get(c, set()) for i in range(nights))
        ]

    available.cache = {}  # like ProviderAvailability, which the CLI clears per poll
    return available


def plan(**trip) -> Trip:
    trip.setdefault("windows", [{"start_date": day(1), "end_date": day(30)}])
    return Trip.parse_obj(trip)


def legs(itinerary):
    return [(leg.stop, leg.check_in.day, leg.nights) for leg in itinerary.legs]


def test_back_to_back_with_flexible_nights() -> None:
    trip = plan(
        stops=[
            {"park": 1, "campgrounds": "a", "nights": "1-3"},
            {"park": 1, "campgrounds": "b", "nights": 2},
        ]
    )
    found = find_itineraries(
        trip, fake_availability({"a": {10, 11, 12}, "b": {13, 14}})
    )
    # stop 2 must start the day stop 1 checks out: June 13
    assert [legs(i) for i in found] == [
        [(0, 10, 3), (1, 13, 2)],
        [(0, 11, 2), (1, 13, 2)],
        [(0, 12, 1), (1, 13, 2)],
    ]


def test_alternatives_optional_stops_and_any_order() -> None:
    free = {"a": {5, 6}, "b": {7}, "c": {3, 4}}
    stops = [
        {
            "name": "Lake",
            "locations": [
                {"park": 1, "campgrounds": ["x"]},
                {"park": 1, "campgrounds": ["a"]},
            ],
            "nights": 2,
        },
        {"park": 1, "campgrounds": "b", "nights": "0-1"},
        {"park": 1, "campgrounds": "c", "nights": 2},
    ]
    in_order = find_itineraries(plan(stops=stops), fake_availability(free))
    assert in_order == []
    found = find_itineraries(plan(stops=stops, any_order=True), fake_availability(free))
    assert [legs(i) for i in found] == [
        [(2, 3, 2), (0, 5, 2)],  # stop 2 is optional
        [(2, 3, 2), (0, 5, 2), (1, 7, 1)],
    ]
    assert found[0].legs[1].sites[0].facility_id == "a"
    assert "Jun 05 - Jun 07, 2 nights: Campground a" in found[0].describe()


def test_trip_limits() -> None:
    free = {"a": set(range(1, 30))}
    stop = {"park": 1, "campgrounds": "a", "nights": "1-5"}
    found = find_itineraries(
        plan(stops=[stop], start_days=[4], min_total_nights=3, max_total_nights=4),
        fake_availability(free),
    )
    # June 2023 Fridays: 2, 9, 16, 23 (30 has no room before the end date)
    assert {i.legs[0].check_in.day for i in found} == {2, 9, 16, 23}
    assert {i.legs[0].nights for i in found} == {3, 4}
    assert (
        len(
            find_itineraries(plan(stops=[stop], max_results=3), fake_availability(free))
        )
        == 3
    )


def test_unavailable_stays_are_not_extended() -> None:
    calls: List = []
    trip = plan(
        windows=[{"start_date": day(10), "end_date": day(20)}],
        stops=[{"park": 1, "campgrounds": "a", "nights": "1-7"}],
    )
    find_itineraries(trip, fake_availability({"a": {10}}, calls))
    # from June 10: 1 night is free, 2 isn't, so 3..7 are never asked for
    assert [c for c in calls if c[1] == day(10)] == [
        ("a", day(10), 1),
        ("a", day(10), 2),
    ]


def test_trip_validation() -> None:
    stop = {"park": 1, "campgrounds": "a"}
    with pytest.raises(ValidationError, match="Unknown park"):
        plan(stops=[{**stop, "park": 99999}])
    with pytest.raises(ValidationError, match="max_nights"):
        plan(stops=[{**stop, "min_nights": 3, "max_nights": 2}])
    with pytest.raises(ValidationError, match="end after it starts"):
        plan(stops=[stop], windows=[{"start_date": day(5), "end_date": day(5)}])
    with pytest.raises(ValidationError):
        plan(stops=[])
    assert plan(stops=[stop]).stops[0].max_nights == 1


def test_provider_availability_caches(monkeypatch) -> None:
    made = []

    class FakeSearch:
        def get_all_campsites(self):
            return [site("a", self.search_window[0].start_date, 1)]

    def fake_make_search(*args, **kwargs):
        made.append(args)
        return FakeSearch()

    monkeypatch.setattr("spotsnagger.trip.make_search", fake_make_search)
    available = ProviderAvailability()
    location = TripLocation(park="1", campgrounds=["a"])
    assert available(location, day(10), 1) == available(location, day(10), 1)
    assert available(location, day(11), 1)[0].booking_date.day == 11
    assert len(made) == 1 and len(available.cache) == 2


def test_web_trip(monkeypatch) -> None:
    monkeypatch.setattr(
        "spotsnagger.web.ProviderAvailability",
        lambda *_: fake_availability({"-1": {10, 11}, "-2": {12}}),
    )
    body = {
        "windows": [{"start_date": "2023-06-01", "end_date": "2023-06-30"}],
        "stops": [
            {
                "min_nights": 2,
                "max_nights": 2,
                "locations": [
                    {"park": "1", "booking_category": 0, "campgrounds": ["-1"]}
                ],
            },
            {
                "min_nights": 1,
                "max_nights": 1,
                "locations": [
                    {"park": "1", "booking_category": 0, "campgrounds": ["-2"]}
                ],
            },
        ],
    }
    status, trips = handle_api("POST", "/api/trip", "", json.dumps(body).encode())
    assert status == 200
    assert [(leg["check_in"], leg["nights"]) for leg in trips[0]["legs"]] == [
        (day(10), 2),
        (day(12), 1),
    ]
    assert set(trips[0]["legs"][0]["sites"][0]) >= {"booking_url", "campsite_site_name"}
    body["stops"][0]["locations"][0]["park"] = "aspira-99"
    status, error = handle_api("POST", "/api/trip", "", json.dumps(body).encode())
    assert status == 400 and "Unknown park" in error["error"]


def test_cli_trip(cli_runner, monkeypatch) -> None:
    monkeypatch.setattr(
        "spotsnagger.cli.ProviderAvailability",
        lambda *_: fake_availability({"-1": {9, 10}, "-2": {11, 12}}),
    )
    result = cli_runner.run_spotsnagger_command(
        """
        spotsnagger trip
            --start-date 2023-06-01 --end-date 2023-06-30
            --stop "park=1 campground=-1 nights=1-2 name=First"
            --stop "park=1 campground=-2,-3 nights=2"
            --start-day FRI
        """
    )
    assert result.exit_code == 0, result.output
    assert "Trip option 1" in result.output
    assert "Fri Jun 09 to Tue Jun 13 (4 nights)" in result.output
    bad = cli_runner.run_spotsnagger_command("spotsnagger trip --stop 'park=1 oops'")
    assert bad.exit_code != 0 and "key=value" in bad.output
