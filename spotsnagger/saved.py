"""
Saved searches and trips, shared by the CLI and the web UI.

Stored as JSON in ~/.spotsnagger_saved.json: {name: {"kind", "params", "saved_at"}}.
A "search" holds the web UI's single-campground search body, a "trip" a Trip.
An optional "watch" re-runs the item every `interval_minutes` (see spotsnagger.watch).
"""

import datetime
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from spotsnagger.config import FileConfig
from spotsnagger.notifications import CAMPSITE_NOTIFICATIONS
from spotsnagger.trip import SEARCH_FIELDS, Trip, parse_search_body

SAVED_FILE = Path(FileConfig.HOME_PATH) / ".spotsnagger_saved.json"
KINDS = ("search", "trip")
_lock = threading.Lock()  # the web UI server is threaded
WATCH_MIN_MINUTES = 15
WATCH_DEFAULT_MINUTES = 60


def _read() -> Dict[str, Dict[str, Any]]:
    if not SAVED_FILE.exists():
        return {}
    try:
        return json.loads(SAVED_FILE.read_text(encoding="utf-8"))
    except ValueError as e:
        # never overwrite a file we can't read: it holds the user's saved searches
        raise RuntimeError(f"Can't read saved searches in {SAVED_FILE}: {e}") from e


def _write(saved: Dict[str, Dict[str, Any]]) -> None:
    tmp = SAVED_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    os.replace(tmp, SAVED_FILE)  # atomic, so a crash can't leave half a file


def list_saved() -> List[Dict[str, Any]]:
    """
    Every saved search and trip, sorted by name
    """
    return [
        {"name": n, **v}
        for n, v in sorted(_read().items(), key=lambda i: i[0].casefold())
    ]


def get_saved(name: str) -> Dict[str, Any]:
    """
    One saved item; KeyError if there's none by that name
    """
    saved = _read()
    if name not in saved:
        raise KeyError(f"No saved search called {name!r}")
    return saved[name]


def save(name: str, kind: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and save (or replace) a search or trip under `name`
    """
    name = str(name or "").strip()
    if not name:
        raise ValueError("Please give the saved search a name")
    if kind == "trip":
        params = json.loads(Trip.parse_obj(params).json())
    elif kind == "search":
        parsed = parse_search_body(params)
        params = {k: params.get(k) for k in SEARCH_FIELDS}
        params.update(party_size=parsed["party_size"], tents=parsed["tents"])
    else:
        raise ValueError(f"kind must be one of {KINDS}")
    item = {
        "kind": kind,
        "params": params,
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    with _lock:
        saved = _read()
        old_watch = saved.get(name, {}).get("watch")
        if old_watch:
            # keep the watch settings, but the old results don't apply to new params
            item["watch"] = {k: old_watch[k] for k in _WATCH_SETTINGS}
        saved[name] = item
        _write(saved)
    return {"name": name, **item}


_WATCH_SETTINGS = ("enabled", "interval_minutes", "notifications")


def set_watch(
    name: str,
    enabled: bool,
    interval_minutes: int = WATCH_DEFAULT_MINUTES,
    notifications: Sequence[str] = (),
) -> Dict[str, Any]:
    """
    Turn continuous checking of a saved item on or off, and pick where alerts go
    """
    interval_minutes = int(interval_minutes)
    if interval_minutes < WATCH_MIN_MINUTES:
        raise ValueError(f"Check at most every {WATCH_MIN_MINUTES} minutes")
    notifications = [str(n).lower() for n in notifications]
    unknown = set(notifications) - CAMPSITE_NOTIFICATIONS.keys()
    if unknown:
        raise ValueError(f"Unknown notification type(s): {', '.join(sorted(unknown))}")
    if enabled and not notifications:
        raise ValueError("Pick at least one place to send notifications")
    with _lock:
        saved = _read()
        if name not in saved:
            raise KeyError(f"No saved search called {name!r}")
        old = saved[name].get("watch") or {}
        watch = {
            **old,
            "enabled": bool(enabled),
            "interval_minutes": interval_minutes,
            "notifications": notifications,
        }
        if enabled and not old.get("enabled"):
            # turning it on checks right away and reports everything open now
            watch = {k: watch[k] for k in _WATCH_SETTINGS}
        saved[name]["watch"] = watch
        _write(saved)
    return {"name": name, **saved[name]}


def record_check(
    name: str,
    seen: Optional[List[str]] = None,
    error: Optional[str] = None,
    disable: bool = False,
) -> None:
    """
    Store a watch check's outcome; `seen` (what's open now) is kept on errors
    """
    with _lock:
        saved = _read()
        watch = saved.get(name, {}).get("watch")
        if not watch:
            return  # deleted or replaced while the check ran
        watch["last_checked"] = datetime.datetime.now().isoformat(timespec="seconds")
        watch["last_error"] = error
        if seen is not None:
            watch["seen"] = seen
            watch["last_found"] = len(seen)
        if disable:
            watch["enabled"] = False
        _write(saved)


def delete(name: str) -> None:
    """
    Remove a saved item; KeyError if there's none by that name
    """
    with _lock:
        saved = _read()
        if name not in saved:
            raise KeyError(f"No saved search called {name!r}")
        del saved[name]
        _write(saved)
