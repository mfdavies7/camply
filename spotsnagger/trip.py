"""
Trips: back-to-back stays at several campgrounds, with no gaps between them.

A trip has one or more date ranges it may fall in and an ordered (or unordered)
list of stops. Each stop names one or more alternative locations and a range of
nights. The search chains exact-length stays so each checkout is the next check-in.
"""

import datetime
import logging
from itertools import permutations
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import Field, root_validator, validator

from spotsnagger.containers import AvailableCampsite, SearchWindow
from spotsnagger.containers.base_container import SpotSnaggerModel
from spotsnagger.providers.aspira.aspira_provider import (
    RECREATION_AREAS as ASPIRA_RECREATION_AREAS,
)
from spotsnagger.providers.going_to_camp.rec_areas import RECREATION_AREAS
from spotsnagger.search.base_search import BaseCampingSearch
from spotsnagger.search.search_aspira import SearchAspira
from spotsnagger.search.search_going_to_camp import SearchGoingToCamp

logger = logging.getLogger(__name__)

# Park IDs are GoingToCamp ints, or "aspira-<id>" (Aspira IDs overlap GoingToCamp's)
ASPIRA_PREFIX = "aspira-"


def parse_park(rec_area: Any) -> Tuple[bool, int]:
    """
    (is it an Aspira park, its rec area ID) from a park ID, rejecting unknown parks
    """
    value = str(rec_area)
    is_aspira = value.startswith(ASPIRA_PREFIX)
    park = int(value[len(ASPIRA_PREFIX) :] if is_aspira else value)
    known = (
        ASPIRA_RECREATION_AREAS.keys()
        if is_aspira
        else {a.recreation_area_id for a in RECREATION_AREAS.values()}
    )
    if park not in known:
        raise ValueError(f"Unknown park {rec_area}")
    return is_aspira, park


def make_search(
    park: Any,
    campgrounds: List[str],
    booking_category: int,
    window: SearchWindow,
    nights: int = 1,
) -> BaseCampingSearch:
    """
    The GoingToCamp or Aspira search object for one park's campgrounds
    """
    is_aspira, rec_area = parse_park(park)
    if is_aspira:
        return SearchAspira(
            search_window=window,
            recreation_area=[rec_area],
            campgrounds=[int(c) for c in campgrounds],
            nights=nights,
            booking_category_id=booking_category,
            verbose=False,
        )
    return SearchGoingToCamp(
        search_window=window,
        recreation_area=[rec_area],
        campgrounds=list(campgrounds),
        nights=nights,
        booking_category_id=booking_category,
        verbose=False,
    )


SEARCH_FIELDS = (
    "rec_area",
    "booking_category",
    "campground",
    "start_date",
    "end_date",
    "nights",
)


def parse_search_body(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a single-campground search (the web UI form / a saved "search")

    `campground` may be one ID, a list of them, or empty for the whole park.
    """
    start = datetime.date.fromisoformat(str(body["start_date"]))
    end = datetime.date.fromisoformat(str(body["end_date"]))
    nights = int(body.get("nights") or 1)
    if end <= start:
        raise ValueError("The end date must be after the start date")
    if not 1 <= nights <= (end - start).days:
        raise ValueError("Nights must fit between the start and end dates")
    campground = body.get("campground") or []
    # no campground means every campground in the park
    campgrounds = [
        str(c)
        for c in (campground if isinstance(campground, list) else [campground])
        if c
    ]
    parse_park(body["rec_area"])
    return {
        "park": body["rec_area"],
        "campgrounds": campgrounds,
        "booking_category": int(body.get("booking_category") or 0),
        "window": SearchWindow(start_date=start, end_date=end),
        "nights": nights,
    }


class TripLocation(SpotSnaggerModel):
    """
    One place a stop can happen: a park and one or more of its campgrounds
    """

    park: str
    campgrounds: List[str] = Field(..., min_items=1)
    booking_category: int = 0

    @validator("park", pre=True)
    @classmethod
    def known_park(cls, v: Any) -> str:
        """
        Fail early on parks spotsnagger doesn't know
        """
        parse_park(v)
        return str(v)

    @validator("campgrounds", pre=True)
    @classmethod
    def as_list(cls, v: Any) -> List[str]:
        """
        Accept a single campground or a comma-separated string
        """
        if isinstance(v, (str, int)):
            v = str(v).split(",")
        return [str(c).strip() for c in v if str(c).strip()]

    @property
    def key(self) -> Tuple[str, Tuple[str, ...], int]:
        """
        Hashable identity, used to cache availability lookups
        """
        return self.park, tuple(self.campgrounds), self.booking_category


class TripStop(SpotSnaggerModel):
    """
    One leg of a trip: any of `locations`, for min_nights..max_nights nights

    A min_nights of 0 makes the stop optional.
    """

    name: Optional[str] = None
    locations: List[TripLocation] = Field(..., min_items=1)
    min_nights: int = Field(1, ge=0)
    max_nights: Optional[int] = Field(None, ge=1)

    @root_validator(pre=True)
    @classmethod
    def shorthand(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allow `nights: 2` / `nights: "2-4"` and a single inline location
        """
        values = dict(values)
        nights = values.pop("nights", None)
        if nights not in (None, ""):
            low, _, high = str(nights).partition("-")
            values.setdefault("min_nights", int(low))
            values.setdefault("max_nights", int(high or low))
        if "locations" not in values and "park" in values:
            values["locations"] = [
                {
                    k: values.pop(k)
                    for k in ("park", "campgrounds", "booking_category")
                    if k in values
                }
            ]
        return values

    @root_validator(skip_on_failure=True)
    @classmethod
    def night_range(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        max_nights defaults to min_nights and can't be below it
        """
        low, high = values["min_nights"], values.get("max_nights")
        values["max_nights"] = high = high or max(low, 1)
        if high < low:
            raise ValueError("max_nights must be at least min_nights")
        return values


class Trip(SpotSnaggerModel):
    """
    Everything a trip search needs
    """

    name: Optional[str] = None
    windows: List[SearchWindow] = Field(..., min_items=1)
    stops: List[TripStop] = Field(..., min_items=1)
    any_order: bool = False
    start_days: List[int] = []
    min_total_nights: int = Field(1, ge=1)
    max_total_nights: Optional[int] = Field(None, ge=1)
    max_results: int = Field(25, ge=1, le=500)

    @validator("windows", each_item=True)
    @classmethod
    def window_has_nights(cls, v: SearchWindow) -> SearchWindow:
        """
        The end date is the last checkout, so it must follow the start
        """
        if v.end_date <= v.start_date:
            raise ValueError("each date range must end after it starts")
        return v

    @validator("start_days", each_item=True)
    @classmethod
    def weekday(cls, v: int) -> int:
        """
        Weekdays are 0 (Monday) .. 6 (Sunday)
        """
        if not 0 <= v <= 6:  # noqa: PLR2004
            raise ValueError("start days are 0 (Monday) to 6 (Sunday)")
        return v


class TripLeg(SpotSnaggerModel):
    """
    One booked stay within an itinerary, and every site free for it
    """

    stop: int
    stop_name: Optional[str]
    check_in: datetime.date
    check_out: datetime.date
    nights: int
    sites: List[AvailableCampsite]


class Itinerary(SpotSnaggerModel):
    """
    A gap-free run of legs
    """

    legs: List[TripLeg]

    @property
    def key(self) -> Tuple[Tuple[int, datetime.date, int], ...]:
        """
        Same stops on the same dates = same itinerary, whichever sites are free
        """
        return tuple((leg.stop, leg.check_in, leg.nights) for leg in self.legs)

    def describe(self) -> str:
        """
        Human-readable summary, for logs and notifications
        """
        first, last = self.legs[0], self.legs[-1]
        lines = [
            f"{first.check_in:%a %b %d} to {last.check_out:%a %b %d} "
            f"({sum(leg.nights for leg in self.legs)} nights)"
        ]
        for leg in self.legs:
            site = leg.sites[0]
            more = f" (+{len(leg.sites) - 1} more)" if len(leg.sites) > 1 else ""
            lines.append(
                f"  {leg.check_in:%b %d} - {leg.check_out:%b %d}, {leg.nights} "
                f"night{'s' if leg.nights != 1 else ''}: {site.facility_name} site "
                f"{site.campsite_site_name}{more} {site.booking_url}"
            )
        return "\n".join(lines)


Availability = Callable[[TripLocation, datetime.date, int], List[AvailableCampsite]]


class ProviderAvailability:
    """
    Ask the booking sites which sites are free for an exact stay, caching answers
    """

    def __init__(self) -> None:
        self.cache: Dict[Any, List[AvailableCampsite]] = {}
        self._searches: Dict[Any, BaseCampingSearch] = {}

    def __call__(
        self, location: TripLocation, check_in: datetime.date, nights: int
    ) -> List[AvailableCampsite]:
        """
        Sites at `location` free for every night from check_in for `nights`
        """
        cache_key = (location.key, check_in, nights)
        if cache_key not in self.cache:
            window = SearchWindow(
                start_date=check_in,
                end_date=check_in + datetime.timedelta(days=nights),
            )
            search = self._searches.get(location.key)
            if search is None:
                search = self._searches[location.key] = make_search(
                    location.park,
                    location.campgrounds,
                    location.booking_category,
                    window,
                )
            search.search_window = [window]
            self.cache[cache_key] = search.get_all_campsites()
        return self.cache[cache_key]


def find_itineraries(  # noqa: C901
    trip: Trip, available: Availability
) -> List[Itinerary]:
    """
    Every gap-free itinerary for the trip, earliest first, up to trip.max_results
    """
    found: Dict[Any, Itinerary] = {}
    max_total = trip.max_total_nights or float("inf")
    stop_ids = range(len(trip.stops))
    orders = list(permutations(stop_ids)) if trip.any_order else [tuple(stop_ids)]

    def extend(
        order: Tuple[int, ...],
        day: datetime.date,
        last_day: datetime.date,
        legs: List[TripLeg],
    ) -> None:
        if len(found) >= trip.max_results:
            return
        total = sum(leg.nights for leg in legs)
        if not order:
            if legs and total >= trip.min_total_nights:
                itinerary = Itinerary(legs=list(legs))
                found.setdefault(itinerary.key, itinerary)
            return
        index, rest = order[0], order[1:]
        stop = trip.stops[index]
        for nights in range(stop.min_nights, (stop.max_nights or stop.min_nights) + 1):
            if nights == 0:
                extend(rest, day, last_day, legs)
                continue
            check_out = day + datetime.timedelta(days=nights)
            if check_out > last_day or total + nights > max_total:
                break
            sites = [s for loc in stop.locations for s in available(loc, day, nights)]
            if not sites:
                break  # a site free for more nights is free for these, so none will be
            legs.append(
                TripLeg(
                    stop=index,
                    stop_name=stop.name,
                    check_in=day,
                    check_out=check_out,
                    nights=nights,
                    sites=sites,
                )
            )
            extend(rest, check_out, last_day, legs)
            legs.pop()

    today = datetime.date.today()
    for window in trip.windows:
        for day in window.get_date_range():
            if day < today or (
                trip.start_days and day.weekday() not in trip.start_days
            ):
                continue
            for order in orders:
                extend(order, day, window.end_date, [])
    return list(found.values())
