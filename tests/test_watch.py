"""
Continuous checking of saved searches and trips (no network)
"""

import datetime
import json
from typing import Any, List

import pytest

from spotsnagger import saved, watch
from spotsnagger.web import handle_api
from tests.test_saved import SEARCH, TRIP
from tests.test_trip import fake_availability, site


@pytest.fixture(autouse=True)
def saved_file(tmp_path, monkeypatch):
    monkeypatch.setattr(saved, "SAVED_FILE", tmp_path / "saved.json")


class FakeNotifier:
    sent: List[Any] = []

    def __init__(self, provider: Any) -> None:
        self.provider = provider

    def send_message(self, message: str, **kwargs: Any) -> None:
        FakeNotifier.sent.append(message)

    def send_campsites(self, campsites: List[Any], **kwargs: Any) -> None:
        FakeNotifier.sent.extend(campsites)


@pytest.fixture
def sent(monkeypatch) -> List[Any]:
    FakeNotifier.sent = []
    monkeypatch.setattr(watch, "MultiNotifierProvider", FakeNotifier)
    return FakeNotifier.sent


def _watched(name: str, kind: str, params: Any) -> None:
    saved.save(name, kind, params)
    saved.set_watch(name, True, 15, ["pushover"])


def test_set_watch_validation() -> None:
    saved.save("Lake", "search", SEARCH)
    with pytest.raises(ValueError, match="15 minutes"):
        saved.set_watch("Lake", True, 14, ["pushover"])
    with pytest.raises(ValueError, match="Unknown"):
        saved.set_watch("Lake", True, 60, ["carrier-pigeon"])
    with pytest.raises(ValueError, match="at least one"):
        saved.set_watch("Lake", True, 60, [])
    with pytest.raises(KeyError):
        saved.set_watch("Nope", False)
    assert saved.set_watch("Lake", False)["watch"]["interval_minutes"] == 60


def test_search_notifies_only_new_openings(sent, monkeypatch) -> None:
    open_now = [site("a", datetime.date(2023, 6, 10), 2)]
    monkeypatch.setattr(
        watch,
        "make_search",
        lambda **kw: type(
            "S", (), {"get_matching_campsites": lambda s, log: open_now}
        )(),
    )
    _watched("Lake", "search", SEARCH)
    watch.check(saved.list_saved()[0])
    assert sent[0].startswith("1 new campsite") and sent[1] is open_now[0]
    sent.clear()
    watch.check(saved.list_saved()[0])  # still open: nothing new
    assert sent == []
    open_now = []
    watch.check(saved.list_saved()[0])  # booked
    open_now = [site("a", datetime.date(2023, 6, 10), 2)]
    watch.check(saved.list_saved()[0])  # freed up again
    assert len(sent) == 2
    w = saved.get_saved("Lake")["watch"]
    assert w["last_found"] == 1 and w["last_error"] is None and w["last_checked"]


def test_failed_check_keeps_results_and_records_error(sent, monkeypatch) -> None:
    def boom(**kw: Any) -> None:
        raise SystemExit(1)

    monkeypatch.setattr(watch, "make_search", boom)
    _watched("Lake", "search", SEARCH)
    watch.check(saved.list_saved()[0])
    w = saved.get_saved("Lake")["watch"]
    assert w["last_error"] == "1" and "seen" not in w and w["enabled"]


def test_trip_notifies_new_itineraries(sent, monkeypatch) -> None:
    monkeypatch.setattr(
        watch,
        "ProviderAvailability",
        lambda party, tents: fake_availability({"-1": {5, 6}}),
    )
    _watched("Trip", "trip", TRIP)
    watch.check(saved.list_saved()[0])
    assert len(sent) == 1 and "1 new trip option(s)" in sent[0]
    assert saved.get_saved("Trip")["watch"]["seen"] == ["0:2023-06-05:2"]


def test_due_and_expired(sent) -> None:
    _watched("Lake", "search", SEARCH)
    now = datetime.datetime.now()
    w = saved.get_saved("Lake")["watch"]
    assert watch._due(w, now)
    w["last_checked"] = now.isoformat()
    assert not watch._due(w, now + datetime.timedelta(minutes=14))
    assert watch._due(w, now + datetime.timedelta(minutes=15))
    _watched("Old", "search", SEARCH)
    item = {**saved.get_saved("Old"), "name": "Old"}
    item["params"]["end_date"] = "2023-04-28"  # saved long ago, now in the past
    watch.check(item)
    old = saved.get_saved("Old")["watch"]
    assert not old["enabled"] and "passed" in old["last_error"] and sent == []


def test_resaving_keeps_settings_but_resets_results() -> None:
    _watched("Lake", "search", SEARCH)
    saved.record_check("Lake", seen=["x"])
    saved.save("Lake", "search", {**SEARCH, "nights": 1})
    assert saved.get_saved("Lake")["watch"] == {
        "enabled": True,
        "interval_minutes": 15,
        "notifications": ["pushover"],
    }


def test_web_watch_api() -> None:
    saved.save("Lake", "search", SEARCH)
    body = {
        "name": "Lake",
        "enabled": True,
        "interval_minutes": 30,
        "notifications": ["slack"],
    }
    status, item = handle_api("POST", "/api/saved/watch", "", json.dumps(body).encode())
    assert status == 200 and item["watch"]["interval_minutes"] == 30
    body["interval_minutes"] = 5
    assert (
        handle_api("POST", "/api/saved/watch", "", json.dumps(body).encode())[0] == 400
    )
    status, notifiers = handle_api("GET", "/api/notifiers", "", b"")
    assert status == 200 and {"id": "pushover", "configured": True} in notifiers
