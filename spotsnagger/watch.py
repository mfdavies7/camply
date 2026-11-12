"""
Continuous checking of saved searches and trips, run in the background by the web UI.

Each due item is searched again and anything newly open since its last check is
sent to the notifications picked for it.
"""

import datetime
import logging
import threading
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional

from spotsnagger import saved
from spotsnagger.notifications import CAMPSITE_NOTIFICATIONS, MultiNotifierProvider
from spotsnagger.search.base_search import BaseCampingSearch
from spotsnagger.trip import (
    ProviderAvailability,
    Trip,
    find_itineraries,
    make_search,
    parse_search_body,
)

logger = logging.getLogger(__name__)

THREAD_NAME = "spotsnagger-watch"
TICK_SECONDS = 30
MAX_TRIPS_PER_MESSAGE = 10


@lru_cache(maxsize=1)
def list_notifiers() -> List[Dict[str, Any]]:
    """
    Every notification type, and whether it's set up (credentials are read at startup)
    """

    def configured(cls: Any) -> bool:
        try:
            cls()
        except Exception:
            return False
        return True

    return [
        {"id": name, "configured": configured(cls)}
        for name, cls in CAMPSITE_NOTIFICATIONS.items()
        if name != "silent"
    ]


def _expired(item: Dict[str, Any], today: datetime.date) -> bool:
    params = item["params"]
    ends = (
        [w["end_date"] for w in params["windows"]]
        if item["kind"] == "trip"
        else [params["end_date"]]
    )
    return all(datetime.date.fromisoformat(str(e)) <= today for e in ends)


def _find(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    {stable key: campsite or itinerary} for everything open now
    """
    if item["kind"] == "trip":
        trip = Trip.parse_obj(item["params"])
        found = find_itineraries(
            trip, ProviderAvailability(trip.party_size, trip.tents)
        )
        return {"|".join(f"{s}:{d}:{n}" for s, d, n in i.key): i for i in found}
    sites = make_search(**parse_search_body(item["params"])).get_matching_campsites(
        log=False
    )
    return {
        f"{c.facility_id}|{c.campsite_id}|{c.booking_date:%Y-%m-%d}|{c.booking_nights}": c
        for c in sites
    }


def _notify(name: str, kind: str, new: List[Any], notifier: Any) -> None:
    if kind == "trip":
        shown = new[:MAX_TRIPS_PER_MESSAGE]
        more = len(new) - len(shown)
        notifier.send_message(
            f"{len(new)} new trip option(s) for saved trip {name!r}:\n\n"
            + "\n\n".join(i.describe() for i in shown)
            + (
                f"\n\n...and {more} more. Open SpotSnagger to see them all."
                if more
                else ""
            )
        )
        return
    notifier.send_message(f"{len(new)} new campsite(s) for saved search {name!r}")
    notifier.send_campsites(
        campsites=BaseCampingSearch._handle_too_many_campsites_found(
            notifier=notifier, logged_campsites=new
        )
    )


def check(item: Dict[str, Any]) -> None:
    """
    Search one saved item again and notify about anything newly open
    """
    name, watch = item["name"], item["watch"]
    if _expired(item, datetime.date.today()):
        saved.record_check(name, error="Its dates have passed", disable=True)
        return
    try:
        notifier = MultiNotifierProvider(watch["notifications"])
        found = _find(item)
        seen = set(watch.get("seen") or [])
        # a site that was booked and then freed up again counts as new
        new = [v for k, v in found.items() if k not in seen]
        logger.info(f"Watch {name!r}: {len(found)} open, {len(new)} new")
        if new:
            _notify(name, item["kind"], new, notifier)
    except (Exception, SystemExit) as e:  # the search layer can sys.exit()
        logger.exception(f"Watch {name!r} failed")
        # keep the old `seen` so whatever we failed to send goes out next time
        saved.record_check(name, error=str(e) or e.__class__.__name__)
        return
    saved.record_check(name, seen=sorted(found))


def _due(watch: Optional[Dict[str, Any]], now: datetime.datetime) -> bool:
    if not watch or not watch.get("enabled"):
        return False
    last = watch.get("last_checked")
    return not last or now >= datetime.datetime.fromisoformat(
        last
    ) + datetime.timedelta(minutes=watch["interval_minutes"])


def run_due() -> None:
    """
    Check every watched item whose interval has passed
    """
    for item in saved.list_saved():
        if _due(item.get("watch"), datetime.datetime.now()):
            check(item)


def start() -> threading.Thread:
    """
    Start the background checker (a daemon thread, so it stops with the server)
    """

    def loop() -> None:
        while True:
            try:
                run_due()
            except Exception:
                logger.exception("Watching saved searches failed")
            time.sleep(TICK_SECONDS)

    thread = threading.Thread(target=loop, name=THREAD_NAME, daemon=True)
    thread.start()
    return thread
