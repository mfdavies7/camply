"""
Saved searches and trips: the shared store, the web API and the CLI (no network)
"""

import json

import pytest

from spotsnagger import saved
from spotsnagger.web import handle_api
from tests.test_trip import fake_availability

SEARCH = {
    "rec_area": 1,
    "booking_category": 0,
    "campground": "-2147483643",
    "start_date": "2023-06-10",
    "end_date": "2023-06-12",
    "nights": 2,
    "party_size": 1,
    "tents": 1,
}
TRIP = {
    "windows": [{"start_date": "2023-06-01", "end_date": "2023-06-30"}],
    "stops": [{"park": 1, "campgrounds": "-1", "nights": 2}],
}


@pytest.fixture(autouse=True)
def saved_file(tmp_path, monkeypatch):
    path = tmp_path / "saved.json"
    monkeypatch.setattr(saved, "SAVED_FILE", path)
    return path


def test_store_round_trip(saved_file) -> None:
    saved.save("b trip", "trip", TRIP)
    saved.save("A search", "search", {**SEARCH, "extra": "dropped"})
    assert [i["name"] for i in saved.list_saved()] == ["A search", "b trip"]
    assert saved.get_saved("A search")["params"] == SEARCH
    stop = saved.get_saved("b trip")["params"]["stops"][0]
    assert (stop["min_nights"], stop["max_nights"]) == (2, 2)
    saved.save("A search", "search", {**SEARCH, "nights": 1})  # replaces
    assert saved.get_saved("A search")["params"]["nights"] == 1
    saved.delete("A search")
    assert [i["name"] for i in saved.list_saved()] == ["b trip"]
    with pytest.raises(KeyError):
        saved.delete("A search")


def test_store_rejects_bad_input(saved_file) -> None:
    with pytest.raises(ValueError, match="name"):
        saved.save("  ", "search", SEARCH)
    with pytest.raises(ValueError, match="kind"):
        saved.save("x", "nope", SEARCH)
    with pytest.raises(ValueError, match="Unknown park"):
        saved.save("x", "search", {**SEARCH, "rec_area": 99999})
    with pytest.raises(ValueError):
        saved.save("x", "trip", {**TRIP, "stops": []})
    assert not saved_file.exists()


def test_unreadable_file_is_never_overwritten(saved_file) -> None:
    saved_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Can't read"):
        saved.save("x", "search", SEARCH)
    assert saved_file.read_text(encoding="utf-8") == "{not json"


def test_web_saved_api() -> None:
    body = json.dumps({"name": "Lake", "kind": "search", "params": SEARCH}).encode()
    status, item = handle_api("POST", "/api/saved", "", body)
    assert status == 200 and item["name"] == "Lake"
    assert handle_api("GET", "/api/saved", "", b"")[1][0]["params"] == SEARCH
    assert handle_api("DELETE", "/api/saved", "name=Lake", b"")[0] == 200
    assert handle_api("GET", "/api/saved", "", b"")[1] == []
    assert handle_api("DELETE", "/api/saved", "name=Lake", b"")[0] == 400
    bad = json.dumps({"name": "x", "kind": "search", "params": {}}).encode()
    assert handle_api("POST", "/api/saved", "", bad)[0] == 400


def test_cli_save_and_rerun_trip(cli_runner, monkeypatch) -> None:
    monkeypatch.setattr(
        "spotsnagger.cli.ProviderAvailability",
        lambda *_: fake_availability({"-1": {9, 10}}),
    )
    result = cli_runner.run_spotsnagger_command(
        """
        spotsnagger trip --start-date 2023-06-01 --end-date 2023-06-30
            --stop "park=1 campground=-1 nights=2" --save Weekend
        """
    )
    assert result.exit_code == 0, result.output
    assert saved.get_saved("Weekend")["kind"] == "trip"
    listed = cli_runner.run_spotsnagger_command("spotsnagger saved list")
    assert "Weekend (trip, 1 stops" in listed.output
    rerun = cli_runner.run_spotsnagger_command("spotsnagger saved run Weekend")
    assert rerun.exit_code == 0, rerun.output
    assert "Fri Jun 09 to Sun Jun 11 (2 nights)" in rerun.output
    deleted = cli_runner.run_spotsnagger_command("spotsnagger saved delete Weekend")
    assert deleted.exit_code == 0 and saved.list_saved() == []
    missing = cli_runner.run_spotsnagger_command("spotsnagger saved run Weekend")
    assert missing.exit_code != 0 and "No saved search" in missing.output


def test_cli_save_and_rerun_search(cli_runner, monkeypatch) -> None:
    calls = []

    class FakeSearch:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def get_matching_campsites(self, **kwargs):
            return []

    monkeypatch.setattr(
        "spotsnagger.cli.CAMPSITE_SEARCH_PROVIDER",
        {"GoingToCamp": FakeSearch, "Aspira": FakeSearch},
    )
    result = cli_runner.run_spotsnagger_command(
        """
        spotsnagger campsites --rec-area 3 --provider Aspira --campground 7
            --start-date 2023-06-10 --end-date 2023-06-13 --nights 2 --save Sask
        """
    )
    assert result.exit_code == 0, result.output
    assert saved.get_saved("Sask")["params"]["rec_area"] == "aspira-3"
    rerun = cli_runner.run_spotsnagger_command("spotsnagger saved run Sask")
    assert rerun.exit_code == 0, rerun.output
    assert calls[-1]["recreation_area"] == [3] and calls[-1]["nights"] == 2
    refused = cli_runner.run_spotsnagger_command(
        """
        spotsnagger campsites --rec-area 1 --campground 7 --weekends
            --start-date 2023-06-10 --end-date 2023-06-13 --save Nope
        """
    )
    assert refused.exit_code != 0 and "--weekends" in refused.output
