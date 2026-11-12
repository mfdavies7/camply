"""
Saved searches and trips, shared by the CLI and the web UI.

Stored as JSON in ~/.spotsnagger_saved.json: {name: {"kind", "params", "saved_at"}}.
A "search" holds the web UI's single-campground search body, a "trip" a Trip.
"""

import datetime
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from spotsnagger.config import FileConfig
from spotsnagger.trip import SEARCH_FIELDS, Trip, parse_search_body

SAVED_FILE = Path(FileConfig.HOME_PATH) / ".spotsnagger_saved.json"
KINDS = ("search", "trip")
_lock = threading.Lock()  # the web UI server is threaded


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
        saved[name] = item
        _write(saved)
    return {"name": name, **item}


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
