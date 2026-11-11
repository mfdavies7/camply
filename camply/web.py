"""
A tiny browser UI for non-technical users: pick a park, dates and nights, see open sites.

Runs on the standard library HTTP server, bound to localhost only.
"""

import datetime
import json
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, urlparse

from camply.containers import SearchWindow
from camply.providers import Aspira, GoingToCamp
from camply.providers.aspira.aspira_provider import (
    RECREATION_AREAS as ASPIRA_RECREATION_AREAS,
)
from camply.providers.going_to_camp.going_to_camp_provider import (
    booking_category_name,
)
from camply.providers.going_to_camp.rec_areas import RECREATION_AREAS
from camply.search import SearchAspira, SearchGoingToCamp

logger = logging.getLogger(__name__)

# Park IDs are GoingToCamp ints, or "aspira-<id>" (Aspira IDs overlap GoingToCamp's)
ASPIRA_PREFIX = "aspira-"

RESULT_FIELDS = {
    "facility_name",
    "campsite_site_name",
    "booking_date",
    "booking_end_date",
    "booking_nights",
    "booking_url",
}


def _parse_park(rec_area: Any) -> Tuple[bool, int]:
    """
    (is it an Aspira park, its rec area ID) from a web UI park ID
    """
    value = str(rec_area)
    is_aspira = value.startswith(ASPIRA_PREFIX)
    return is_aspira, int(value[len(ASPIRA_PREFIX) :] if is_aspira else value)


def list_parks() -> list:
    """
    All GoingToCamp and Aspira parks, sorted by name
    """
    parks = [(a.recreation_area_id, a) for a in RECREATION_AREAS.values()]
    parks += [
        (f"{ASPIRA_PREFIX}{i}", a) for i, (_, _, a) in ASPIRA_RECREATION_AREAS.items()
    ]
    return sorted(
        (
            {
                "id": park_id,
                "name": a.recreation_area,
                "location": a.recreation_area_location,
            }
            for park_id, a in parks
        ),
        key=lambda p: p["name"],
    )


def list_booking_categories(rec_area: Any) -> list:
    """
    Reservation services of one park (Campsite, Backcountry, Roofed, ...)
    """
    is_aspira, rec_area = _parse_park(rec_area)
    if is_aspira:
        return [{"id": 0, "name": "Campsite"}]
    return [
        {"id": c["bookingCategoryId"], "name": booking_category_name(c)}
        for c in sorted(
            GoingToCamp().list_booking_categories(rec_area),
            key=lambda c: c["bookingCategoryId"],
        )
    ]


def list_campgrounds(rec_area: Any, booking_category: int = 0) -> list:
    """
    Campgrounds within one park offering a reservation service (calls the API)
    """
    is_aspira, rec_area = _parse_park(rec_area)
    if is_aspira:
        facilities = Aspira().find_campgrounds(rec_area_id=[rec_area])
    else:
        facilities = GoingToCamp().find_campgrounds(
            rec_area_id=[rec_area], booking_category_id=booking_category
        )
    return sorted(
        ({"id": f.facility_id, "name": f.facility_name} for f in facilities),
        key=lambda c: c["name"],
    )


def search(body: Dict[str, Any]) -> list:
    """
    Run a single (non-continuous) campsite search from the form fields
    """
    is_aspira, rec_area = _parse_park(body["rec_area"])
    known = (
        ASPIRA_RECREATION_AREAS.keys()
        if is_aspira
        else {a.recreation_area_id for a in RECREATION_AREAS.values()}
    )
    if rec_area not in known:
        raise ValueError("Unknown park")
    start = datetime.date.fromisoformat(body["start_date"])
    end = datetime.date.fromisoformat(body["end_date"])
    nights = int(body.get("nights") or 1)
    if end <= start:
        raise ValueError("The end date must be after the start date")
    if not 1 <= nights <= (end - start).days:
        raise ValueError("Nights must fit between the start and end dates")
    campground = str(body.get("campground") or "")
    if not campground:
        # GoingToCamp and Aspira only allow searching one campground at a time
        raise ValueError("Please choose a campground")
    window = SearchWindow(start_date=start, end_date=end)
    if is_aspira:
        camp_search = SearchAspira(
            search_window=window,
            recreation_area=[rec_area],
            campgrounds=[campground],
            nights=nights,
        )
    else:
        camp_search = SearchGoingToCamp(
            search_window=window,
            recreation_area=[rec_area],
            campgrounds=[campground],
            nights=nights,
            booking_category_id=int(body.get("booking_category") or 0),
        )
    found = camp_search.get_matching_campsites(log=False)
    results = [c.dict(include=RESULT_FIELDS) for c in found]
    return sorted(results, key=lambda r: (r["booking_date"], r["facility_name"]))


def handle_api(method: str, path: str, query: str, body: bytes) -> Tuple[int, Any]:
    """
    Route an API request; returns (HTTP status, JSON-able payload)
    """
    routes = {
        ("GET", "/api/parks"): lambda: list_parks(),
        ("GET", "/api/booking_categories"): lambda: list_booking_categories(
            parse_qs(query)["rec_area"][0]
        ),
        ("GET", "/api/campgrounds"): lambda: list_campgrounds(
            parse_qs(query)["rec_area"][0],
            int(parse_qs(query).get("booking_category", ["0"])[0]),
        ),
        ("POST", "/api/search"): lambda: search(json.loads(body or b"{}")),
    }
    route = routes.get((method, path))
    if route is None:
        return 404, {"error": "Not found"}
    try:
        return 200, route()
    except (KeyError, ValueError, TypeError) as e:
        return 400, {"error": f"Please check your choices: {e}"}
    except SystemExit:
        # the search layer calls sys.exit() on bad input; never let it kill the server
        return 400, {"error": "That search isn't valid. Please check your choices."}
    except Exception as e:
        logger.exception("Web UI request failed")
        return 502, {"error": f"Something went wrong talking to the booking site: {e}"}


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _route(self, method: str) -> None:
        url = urlparse(self.path)
        if method == "GET" and url.path == "/":
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        status, payload = handle_api(method, url.path, url.query, body)
        self._send(
            status, json.dumps(payload, default=str).encode(), "application/json"
        )

    def do_GET(self) -> None:
        self._route("GET")

    def do_POST(self) -> None:
        self._route("POST")

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format, *args)


def serve(port: int = 8000, open_browser: bool = True) -> None:
    """
    Start the web UI on http://localhost:<port> and block until Ctrl+C
    """
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://localhost:{server.server_port}"
    logger.info(f"camply web UI running at {url} (press Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campsite Finder</title>
<style>
  :root { --bg:#f6f7f4; --card:#fff; --ink:#1d2a1f; --muted:#5b6b5e; --accent:#2f6b3a; --line:#dde3dc; --err:#a1260d; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#141a15; --card:#1d251f; --ink:#e7eee8; --muted:#a3b1a5; --accent:#7cc48a; --line:#2e3a31; --err:#ff8f73; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui, sans-serif; }
  main { max-width:720px; margin:0 auto; padding:24px 16px 64px; }
  h1 { margin:0 0 4px; font-size:1.8rem; }
  p.lead { margin:0 0 24px; color:var(--muted); }
  form, .site { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; }
  label { display:block; font-weight:600; margin:16px 0 6px; }
  label:first-child { margin-top:0; }
  .hint { font-weight:400; color:var(--muted); font-size:.9rem; }
  select, input { width:100%; padding:10px 12px; font:inherit; color:inherit; background:var(--bg);
                  border:1px solid var(--line); border-radius:8px; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  button { margin-top:20px; width:100%; padding:14px; font:inherit; font-weight:700; color:#fff;
           background:var(--accent); border:0; border-radius:8px; cursor:pointer; }
  @media (prefers-color-scheme: dark) { button { color:#0d140e; } }
  button:disabled { opacity:.6; cursor:wait; }
  #status { margin:24px 0 12px; color:var(--muted); }
  #status.error { color:var(--err); font-weight:600; }
  .site { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px; padding:14px 16px; }
  .site strong { display:block; }
  .site span { color:var(--muted); font-size:.9rem; }
  .site a { flex:none; padding:8px 16px; border-radius:8px; background:var(--accent); color:var(--bg);
            text-decoration:none; font-weight:700; }
  select:disabled, input:disabled { opacity:.5; cursor:not-allowed; }
  #loading { display:flex; align-items:center; gap:12px; margin-top:24px; color:var(--muted); }
  #loading[hidden] { display:none; }
  .spinner { flex:none; width:24px; height:24px; border:3px solid var(--line);
             border-top-color:var(--accent); border-radius:50%; animation:spin .8s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .spinner { animation-duration:3s; } }
</style>
</head>
<body>
<main>
  <h1>&#127957; Campsite Finder</h1>
  <p class="lead">Find open campsites at Canadian parks. Pick a park and your dates, then press Search.</p>
  <form id="form">
    <label for="park">Park</label>
    <select id="park" required disabled><option value="">Loading parks&hellip;</option></select>

    <label for="category">Type of stay <span class="hint">(campsite, backcountry, cabin&hellip;)</span></label>
    <select id="category" required disabled><option value="">Choose a park first</option></select>

    <label for="campground">Campground</label>
    <select id="campground" required disabled><option value="">Choose a park first</option></select>

    <div class="row">
      <div><label for="start">Search Start Date</label><input type="date" id="start" required></div>
      <div><label for="end">Search End Date</label><input type="date" id="end" required></div>
    </div>

    <label for="nights">Nights in a row <span class="hint">(at least this many)</span></label>
    <input type="number" id="nights" min="1" value="1" required>

    <button id="go" type="submit" disabled>Search</button>
  </form>
  <div id="loading" role="status" aria-live="polite" hidden>
    <div class="spinner" aria-hidden="true"></div><span id="loading-text"></span>
  </div>
  <div id="status" role="status" aria-live="polite"></div>
  <div id="results"></div>
</main>
<script>
const $ = (id) => document.getElementById(id);
const today = new Date().toISOString().slice(0, 10);
$("start").min = $("end").min = today;

// Keep end after start (the end date is checkout, so it must be at least a day later)
// and nights within 1..nights in the window. ISO date strings compare correctly as text.
const DAY = 86400000;
function syncDates() {
  const start = $("start").value, end = $("end"), nights = $("nights");
  if (!start) return;
  const minEnd = new Date(Date.parse(start) + DAY).toISOString().slice(0, 10);
  end.min = minEnd;
  if (!end.value || end.value < minEnd) end.value = minEnd;
  const maxNights = Math.round((Date.parse(end.value) - Date.parse(start)) / DAY);
  nights.max = maxNights;
  nights.value = Math.min(Math.max(parseInt(nights.value, 10) || 1, 1), maxNights);
}
["start", "end", "nights"].forEach((id) => $(id).addEventListener("change", syncDates));

let pending = 0;  // overlapping requests (e.g. park change chains category -> campground)
function setPending(delta) {
  pending += delta;
  $("loading").hidden = !pending;
  $("go").disabled = pending > 0;  // nothing to submit until every dependent list has loaded
}
async function api(path, options, message) {
  $("loading-text").textContent = message;
  setPending(1);
  try {
    const res = await fetch(path, options);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong");
    return data;
  } finally {
    setPending(-1);
  }
}
function setStatus(text, isError) {
  $("status").textContent = text;
  $("status").className = isError ? "error" : "";
}
function option(value, text) {
  const o = document.createElement("option");
  o.value = value; o.textContent = text;
  return o;
}

api("/api/parks", undefined, "Loading parks…").then((parks) => {
  $("park").replaceChildren(option("", "Choose a park"),
    ...parks.map((p) => option(p.id, p.name + " (" + p.location + ")")));
  $("park").disabled = false;
}).catch((e) => {
  $("park").replaceChildren(option("", "Couldn't load parks"));
  setStatus(e.message, true);
});

$("park").addEventListener("change", async () => {
  const cat = $("category");
  cat.disabled = true;
  $("campground").replaceChildren(option("", "Choose a type of stay first"));
  $("campground").disabled = true;
  if (!$("park").value) { cat.replaceChildren(option("", "Choose a park first")); return; }
  cat.replaceChildren(option("", "Loading types of stay…"));
  try {
    const list = await api("/api/booking_categories?rec_area=" + encodeURIComponent($("park").value),
                           undefined, "Loading types of stay…");
    cat.replaceChildren(option("", "Choose a type of stay"), ...list.map((c) => option(c.id, c.name)));
    cat.disabled = false;
    if (list.some((c) => c.id === 0)) { cat.value = "0"; cat.dispatchEvent(new Event("change")); }
  } catch (e) {
    cat.replaceChildren(option("", "Couldn't load types of stay"));
    setStatus(e.message, true);
  }
});

$("category").addEventListener("change", async () => {
  const cg = $("campground");
  cg.disabled = true;
  if (!$("category").value) { cg.replaceChildren(option("", "Choose a type of stay first")); return; }
  cg.replaceChildren(option("", "Loading campgrounds…"));
  try {
    const list = await api("/api/campgrounds?rec_area=" + encodeURIComponent($("park").value) +
                           "&booking_category=" + encodeURIComponent($("category").value),
                           undefined, "Loading campgrounds…");
    cg.replaceChildren(option("", "Choose a campground"), ...list.map((c) => option(c.id, c.name)));
    cg.disabled = false;
  } catch (e) {
    cg.replaceChildren(option("", "Couldn't load campgrounds"));
    setStatus(e.message, true);
  }
});

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("results").replaceChildren();
  setStatus("");
  try {
    const sites = await api("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rec_area: $("park").value, booking_category: $("category").value,
        campground: $("campground").value,
        start_date: $("start").value, end_date: $("end").value, nights: $("nights").value,
      }),
    }, "Searching for open campsites… this can take a minute.");
    setStatus(sites.length ? sites.length + " open campsite" + (sites.length === 1 ? "" : "s") + " found."
                           : "No open campsites for those dates. Try other dates or another park.");
    const fmt = (d) => new Date(d).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    $("results").replaceChildren(...sites.map((s) => {
      const div = document.createElement("div");
      div.className = "site";
      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = s.facility_name + " — Site " + s.campsite_site_name;
      const when = document.createElement("span");
      when.textContent = fmt(s.booking_date) + " to " + fmt(s.booking_end_date) + " · " +
        s.booking_nights + " night" + (s.booking_nights === 1 ? "" : "s");
      info.append(title, when);
      const link = document.createElement("a");
      link.href = s.booking_url; link.target = "_blank"; link.rel = "noopener";
      link.textContent = "Book";
      div.append(info, link);
      return div;
    }));
  } catch (e) {
    setStatus(e.message, true);
  }
});
</script>
</body>
</html>
"""
