"""
A tiny browser UI for non-technical users: pick a park, dates and nights, see open sites.

Runs on the standard library HTTP server, bound to localhost only.
"""

import json
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from spotsnagger import saved
from spotsnagger.providers import Aspira, GoingToCamp
from spotsnagger.providers.aspira.aspira_provider import (
    BACKCOUNTRY,
    CAMPING,
    INTERESTS,
)
from spotsnagger.providers.aspira.aspira_provider import (
    RECREATION_AREAS as ASPIRA_RECREATION_AREAS,
)
from spotsnagger.providers.going_to_camp.going_to_camp_provider import (
    booking_category_name,
)
from spotsnagger.providers.going_to_camp.rec_areas import RECREATION_AREAS
from spotsnagger.trip import (
    ASPIRA_PREFIX,
    ProviderAvailability,
    Trip,
    find_itineraries,
    make_search,
    parse_park,
    parse_search_body,
)

logger = logging.getLogger(__name__)

RESULT_FIELDS = {
    "facility_name",
    "campsite_site_name",
    "booking_date",
    "booking_end_date",
    "booking_nights",
    "booking_url",
}


def list_parks() -> List[Dict[str, Any]]:
    """
    All GoingToCamp and Aspira parks, sorted by name
    """
    parks = [(a.recreation_area_id, d, a) for d, a in RECREATION_AREAS.items()]
    parks += [
        (f"{ASPIRA_PREFIX}{i}", d, a)
        for i, (d, _, a) in ASPIRA_RECREATION_AREAS.items()
    ]
    return sorted(
        (
            {
                "id": park_id,
                "name": a.recreation_area,
                "location": a.recreation_area_location,
                "url": f"https://{domain}/",
            }
            for park_id, domain, a in parks
        ),
        key=lambda p: p["name"],
    )


def list_booking_categories(rec_area: Any) -> List[Dict[str, Any]]:
    """
    Reservation services of one park (Campsite, Backcountry, Roofed, ...)
    """
    is_aspira, rec_area = parse_park(rec_area)
    if is_aspira:
        host, contract, _ = ASPIRA_RECREATION_AREAS[rec_area]
        interest = {v: k for k, v in INTERESTS.items()}
        return [
            {
                **c,
                "url": f"https://{host}/campgroundDirectoryList.do?contractCode={contract}"
                if c["id"] == CAMPING
                else f"https://{host}/unifSearch.do?interest={interest[c['id']]}"
                f"&contractCode={contract}",
            }
            for c in Aspira().list_booking_categories(rec_area)
        ]
    domain, _ = GoingToCamp().rec_area_lookup(rec_area)
    return [
        {
            "id": c["bookingCategoryId"],
            "name": booking_category_name(c),
            "url": f"https://{domain}/create-booking/results"
            f"?bookingCategoryId={c['bookingCategoryId']}",
        }
        for c in sorted(
            GoingToCamp().list_booking_categories(rec_area),
            key=lambda c: c["bookingCategoryId"],
        )
    ]


def list_campgrounds(rec_area: Any, booking_category: int = 0) -> List[Dict[str, Any]]:
    """
    Campgrounds within one park offering a reservation service (calls the API)
    """
    is_aspira, rec_area = parse_park(rec_area)
    if is_aspira:
        host, contract, _ = ASPIRA_RECREATION_AREAS[rec_area]
        page = (
            "wildernessAreaDetails.do?page=detail&"
            if booking_category == BACKCOUNTRY
            else "campgroundDetails.do?"
        )
        facilities = Aspira().find_campgrounds(
            rec_area_id=[rec_area], booking_category_id=booking_category
        )
        url = f"https://{host}/{page}contractCode={contract}&parkId={{f.facility_id}}"
    else:
        domain, _ = GoingToCamp().rec_area_lookup(rec_area)
        facilities = GoingToCamp().find_campgrounds(
            rec_area_id=[rec_area], booking_category_id=booking_category
        )
        url = (
            f"https://{domain}/create-booking/results?bookingCategoryId={booking_category}"
            "&mapId={f.map_id}&resourceLocationId={f.facility_id}"
        )
    return sorted(
        (
            {"id": f.facility_id, "name": f.facility_name, "url": url.format(f=f)}
            for f in facilities
        ),
        key=lambda c: c["name"].casefold(),
    )


class _Progress(logging.Handler):
    """
    Keeps the latest search log line ("Searching <campground> (3 of 80)...")
    """

    # shortcut: one global message, fine for this single-user localhost UI
    message = ""

    def emit(self, record: logging.LogRecord) -> None:
        _Progress.message = record.getMessage()


logging.getLogger("spotsnagger.search").addHandler(_Progress(logging.INFO))


def _reset_progress(run: Any) -> Any:
    _Progress.message = ""
    return run()


def search(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Run a single (non-continuous) campsite search from the form fields
    """
    camp_search = make_search(**parse_search_body(body))
    found = camp_search.get_matching_campsites(log=False)
    results = [c.dict(include=RESULT_FIELDS) for c in found]
    return sorted(results, key=lambda r: (r["booking_date"], r["facility_name"]))


def search_trip(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Run a single trip search; the body is a Trip (see spotsnagger.trip)
    """
    trip = Trip.parse_obj(body)
    return [
        {
            "legs": [
                {
                    **leg.dict(exclude={"sites"}),
                    "sites": [s.dict(include=RESULT_FIELDS) for s in leg.sites],
                }
                for leg in itinerary.legs
            ]
        }
        for itinerary in find_itineraries(trip, ProviderAvailability())
    ]


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
        ("POST", "/api/search"): lambda: _reset_progress(
            lambda: search(json.loads(body or b"{}"))
        ),
        ("POST", "/api/trip"): lambda: _reset_progress(
            lambda: search_trip(json.loads(body or b"{}"))
        ),
        ("GET", "/api/progress"): lambda: {"message": _Progress.message},
        ("GET", "/api/saved"): saved.list_saved,
        ("POST", "/api/saved"): lambda: saved.save(**json.loads(body or b"{}")),
        ("DELETE", "/api/saved"): lambda: saved.delete(parse_qs(query)["name"][0]),
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

    def do_DELETE(self) -> None:
        self._route("DELETE")

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format, *args)


def serve(port: int = 8000, open_browser: bool = True) -> None:
    """
    Start the web UI on http://localhost:<port> and block until Ctrl+C
    """
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://localhost:{server.server_port}"
    logger.info(f"spotsnagger web UI running at {url} (press Ctrl+C to stop)")
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
<title>SpotSnagger 2.0</title>
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
  form, .site, .trip { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; }
  form[hidden] { display:none; }
  label { display:block; font-weight:600; margin:16px 0 6px; }
  .hint { font-weight:400; color:var(--muted); font-size:.9rem; }
  select, input { width:100%; padding:10px 12px; font:inherit; color:inherit; background:var(--bg);
                  border:1px solid var(--line); border-radius:8px; }
  input[type=checkbox] { width:auto; margin:0 6px 0 0; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  button { margin-top:20px; width:100%; padding:14px; font:inherit; font-weight:700; color:#fff;
           background:var(--accent); border:0; border-radius:8px; cursor:pointer; }
  @media (prefers-color-scheme: dark) { button { color:#0d140e; } }
  button.secondary { width:auto; margin-top:12px; padding:8px 14px; color:var(--accent); background:none;
                     border:1px solid var(--accent); font-weight:600; }
  button.link { width:auto; margin:8px 0 0; padding:0; color:var(--err); background:none; font-weight:600; font-size:.9rem; }
  button:disabled { opacity:.6; cursor:wait; }
  .tabs { display:flex; gap:8px; margin-bottom:16px; }
  .tabs button { margin:0; flex:1; padding:10px; color:var(--accent); background:var(--card); border:1px solid var(--line); }
  .tabs button[aria-selected=true] { color:var(--bg); background:var(--accent); border-color:var(--accent); }
  fieldset { margin:16px 0 0; padding:12px 16px 16px; border:1px solid var(--line); border-radius:10px; }
  legend { font-weight:700; padding:0 6px; }
  .alt { margin-top:12px; padding-top:4px; border-top:1px dashed var(--line); }
  .alt:first-child { margin-top:0; padding-top:0; border-top:0; }
  .alt-or { margin:12px 0 0; color:var(--muted); font-size:.9rem; font-weight:600; }
  .days { display:flex; flex-wrap:wrap; gap:4px 16px; }
  .days label { display:flex; align-items:center; margin:0; font-weight:400; }
  details { margin-top:20px; }
  summary { cursor:pointer; font-weight:700; }
  .check { display:flex; align-items:center; font-weight:400; }
  #status { margin:24px 0 12px; color:var(--muted); }
  #status.error { color:var(--err); font-weight:600; }
  .site { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px; padding:14px 16px; }
  .site strong { display:block; }
  .site span, .leg span { color:var(--muted); font-size:.9rem; }
  .site a, .leg a { flex:none; padding:8px 16px; border-radius:8px; background:var(--accent); color:var(--bg);
            text-decoration:none; font-weight:700; }
  .trip { margin-bottom:12px; padding:14px 16px; }
  .trip h2 { margin:0 0 8px; font-size:1.1rem; }
  .leg { padding:10px 0; border-top:1px solid var(--line); }
  .leg ul { list-style:none; margin:6px 0 0; padding:0; }
  .leg li { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:6px; }
  .leg a { padding:4px 12px; font-size:.9rem; }
  #saved { margin:0 0 16px; padding:14px 16px; background:var(--card); border:1px solid var(--line); border-radius:12px; }
  #saved[hidden], .saved-item[hidden], #saved-none[hidden] { display:none; }
  #saved summary { font-size:1.1rem; }
  #saved-filter { margin:12px 0 4px; }
  #saved-none { margin:8px 0 0; color:var(--muted); }
  .saved-item { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:8px 0; border-top:1px solid var(--line); }
  .saved-item:first-of-type { border-top:0; }
  .saved-item span { display:block; color:var(--muted); font-size:.9rem; }
  .saved-item div:last-child { display:flex; gap:12px; align-items:center; flex:none; }
  .saved-item button { margin:0; }
  .buttons { display:flex; gap:12px; align-items:flex-end; }
  .buttons button[type=submit] { flex:1; }
  .buttons button.secondary { padding:14px; }
  .site-link { display:inline-block; margin-top:4px; font-size:.9rem; color:var(--accent); }
  .site-link[hidden] { display:none; }
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
  <h1>SpotSnagger 2.0</h1>
  <p class="lead">Find open campsites at Canadian parks. Search one campground, or plan a trip across several with no gaps between stays.</p>
  <details id="saved" hidden>
    <summary>Saved searches <span class="hint" id="saved-count"></span></summary>
    <input type="search" id="saved-filter" placeholder="Search by name, type or date" aria-label="Search saved searches">
    <div id="saved-list"></div>
    <p id="saved-none" hidden>No saved searches match.</p>
  </details>
  <div class="tabs" role="tablist">
    <button type="button" role="tab" id="tab-single" aria-controls="form" aria-selected="true">One campground</button>
    <button type="button" role="tab" id="tab-trip" aria-controls="trip-form" aria-selected="false">Trip (several stops)</button>
  </div>
  <form id="form">
    <div id="single-picker"></div>
    <div class="row">
      <div><label for="start">Search Start Date</label><input type="date" id="start" required></div>
      <div><label for="end">Search End Date</label><input type="date" id="end" required></div>
    </div>

    <label for="nights">Nights in a row <span class="hint">(at least this many)</span></label>
    <input type="number" id="nights" min="1" value="1" required>

    <div class="buttons">
      <button type="submit" disabled>Search</button>
      <button type="button" class="secondary" id="save-search">Save</button>
    </div>
  </form>

  <form id="trip-form" hidden>
    <label>When could you go? <span class="hint">(the trip starts and ends inside one of these ranges)</span></label>
    <div id="windows"></div>
    <button type="button" class="secondary" id="add-window">Add another date range</button>

    <div id="stops"></div>
    <button type="button" class="secondary" id="add-stop">Add a stop</button>

    <details>
      <summary>More options</summary>
      <label class="check"><input type="checkbox" id="any-order"> Visit the stops in any order</label>
      <label>Trip can only start on <span class="hint">(leave all unticked for any day)</span></label>
      <div class="days" id="start-days"></div>
      <div class="row">
        <div><label for="min-total">Fewest nights in total</label><input type="number" id="min-total" min="1" placeholder="Any"></div>
        <div><label for="max-total">Most nights in total</label><input type="number" id="max-total" min="1" placeholder="Any"></div>
      </div>
      <label for="max-results">Show at most this many trips</label>
      <input type="number" id="max-results" min="1" max="500" value="25">
    </details>

    <div class="buttons">
      <button type="submit" disabled>Find trips</button>
      <button type="button" class="secondary" id="save-trip">Save</button>
    </div>
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
const DAY = 86400000;
const addDays = (iso, n) => new Date(Date.parse(iso) + n * DAY).toISOString().slice(0, 10);
let uid = 0;
const nextId = () => "f" + (++uid);

// Keep end after start (the end date is checkout, so it must be at least a day later).
// ISO date strings compare correctly as text.
function linkDates(start, end, after) {
  start.min = end.min = today;
  start.addEventListener("change", () => {
    if (!start.value) return;
    end.min = addDays(start.value, 1);
    if (!end.value || end.value < end.min) end.value = end.min;
    if (after) after();
  });
  end.addEventListener("change", () => after && after());
}
linkDates($("start"), $("end"), () => {
  const nights = $("nights"), max = Math.round((Date.parse($("end").value) - Date.parse($("start").value)) / DAY);
  nights.max = max;
  nights.value = Math.min(Math.max(parseInt(nights.value, 10) || 1, 1), max);
});
$("nights").addEventListener("change", () => $("start").dispatchEvent(new Event("change")));

let pending = 0;  // overlapping requests (e.g. park change chains category -> campground)
function setPending(delta) {
  pending += delta;
  $("loading").hidden = !pending;
  // nothing to submit until every dependent list has loaded
  document.querySelectorAll("button[type=submit]").forEach((b) => { b.disabled = pending > 0; });
}
// `poll`: a long search, so show the server's live "Searching <campground> (3 of 80)" line
async function api(path, options, message, poll) {
  $("loading-text").textContent = message;
  setPending(1);
  const timer = poll && setInterval(async () => {
    try {
      const progress = await (await fetch("/api/progress")).json();
      if (progress.message) $("loading-text").textContent = progress.message + "…";
    } catch (e) { /* keep the last message */ }
  }, 1000);
  try {
    const res = await fetch(path, options);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong");
    return data;
  } finally {
    clearInterval(timer);
    setPending(-1);
  }
}
const label = (sel) => sel.selectedOptions[0]?.textContent || "";
function setStatus(text, isError) {
  $("status").textContent = text;
  $("status").className = isError ? "error" : "";
}
function option(value, text, url) {
  const o = document.createElement("option");
  o.value = value; o.textContent = text;
  if (url) o.dataset.url = url;
  return o;
}

let parksRequest = null;
const loadParks = () => parksRequest || (parksRequest = api("/api/parks", undefined, "Loading the list of parks…"));

// Park -> type of stay -> campground, each with a link to the real booking site
function makePicker(allowAll = false) {
  const wrap = document.createElement("div");
  function field(text, hint) {
    const id = nextId(), label = document.createElement("label"), sel = document.createElement("select");
    label.htmlFor = sel.id = id;
    label.textContent = text;
    if (hint) { const h = document.createElement("span"); h.className = "hint"; h.textContent = " " + hint; label.append(h); }
    sel.required = true; sel.disabled = true;
    const link = document.createElement("a");
    link.className = "site-link"; link.target = "_blank"; link.rel = "noopener"; link.hidden = true;
    link.textContent = "Open on the booking site";
    const sync = () => {
      const url = sel.selectedOptions[0]?.dataset.url;
      link.hidden = !url;
      if (url) link.href = url;
    };
    sel.addEventListener("change", sync);
    new MutationObserver(sync).observe(sel, { childList: true });
    wrap.append(label, sel, link);
    return sel;
  }
  const park = field("Park"), cat = field("Type of stay", "(campsite, backcountry, cabin…)"), cg = field("Campground", allowAll ? "(Ctrl/Cmd-click to pick several, Ctrl/Cmd+A for all; pick none to search them all)" : "");
  cg.required = !allowAll;
  cg.multiple = allowAll;
  if (allowAll) cg.size = 8;
  // Ctrl/Cmd+A selects every campground (not every browser does this for a list box)
  cg.addEventListener("keydown", (e) => {
    if (!allowAll || !(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "a") return;
    e.preventDefault();
    for (const o of cg.options) o.selected = true;
    cg.dispatchEvent(new Event("change"));
  });
  park.append(option("", "Loading parks…"));
  cat.append(option("", "Choose a park first"));
  cg.append(option("", "Choose a park first"));
  loadParks().then((parks) => {
    park.replaceChildren(option("", "Choose a park"),
      ...parks.map((p) => option(p.id, p.name + " (" + p.location + ")", p.url)));
    park.disabled = false;
  }).catch((e) => {
    park.replaceChildren(option("", "Couldn't load parks"));
    setStatus(e.message, true);
  });
  park.addEventListener("change", async () => {
    cat.disabled = cg.disabled = true;
    cg.replaceChildren(option("", "Choose a type of stay first"));
    if (!park.value) { cat.replaceChildren(option("", "Choose a park first")); return; }
    cat.replaceChildren(option("", "Loading types of stay…"));
    try {
      const list = await api("/api/booking_categories?rec_area=" + encodeURIComponent(park.value),
                             undefined, "Loading the types of stay at " + label(park) + "…");
      cat.replaceChildren(option("", "Choose a type of stay"), ...list.map((c) => option(c.id, c.name, c.url)));
      cat.disabled = false;
      if (list.some((c) => c.id === 0)) { cat.value = "0"; cat.dispatchEvent(new Event("change")); }
    } catch (e) {
      cat.replaceChildren(option("", "Couldn't load types of stay"));
      setStatus(e.message, true);
    }
  });
  cat.addEventListener("change", async () => {
    cg.disabled = true;
    if (!cat.value) { cg.replaceChildren(option("", "Choose a type of stay first")); return; }
    cg.replaceChildren(option("", "Loading campgrounds…"));
    try {
      const list = await api("/api/campgrounds?rec_area=" + encodeURIComponent(park.value) +
                             "&booking_category=" + encodeURIComponent(cat.value),
                             undefined, "Loading campgrounds at " + label(park) + " with " + label(cat) + " bookings…");
      cg.replaceChildren(...(allowAll ? [] : [option("", "Choose a campground")]), ...list.map((c) => option(c.id, c.name, c.url)));
      cg.disabled = false;
    } catch (e) {
      cg.replaceChildren(option("", "Couldn't load campgrounds"));
      setStatus(e.message, true);
    }
  });
  const chosen = () => [...cg.selectedOptions].filter((o) => o.value);
  wrap.value = () => ({ park: park.value, booking_category: cat.value,
                        campground: allowAll ? chosen().map((o) => o.value) : cg.value,
                        name: chosen().map((o) => o.textContent).join(", "), parkName: label(park) });
  return wrap;
}

const singlePicker = makePicker(true);
$("single-picker").append(singlePicker);

// Tabs
function showTab(trip) {
  $("tab-single").setAttribute("aria-selected", String(!trip));
  $("tab-trip").setAttribute("aria-selected", String(trip));
  $("form").hidden = trip;
  $("trip-form").hidden = !trip;
  $("results").replaceChildren();
  setStatus("");
}
$("tab-single").addEventListener("click", () => showTab(false));
$("tab-trip").addEventListener("click", () => showTab(true));

// Trip form: date ranges
function removeButton(text, onClick) {
  const b = document.createElement("button");
  b.type = "button"; b.className = "link"; b.textContent = text;
  b.addEventListener("click", onClick);
  return b;
}
function addWindow() {
  const row = document.createElement("div");
  row.className = "window";
  const grid = document.createElement("div");
  grid.className = "row";
  const inputs = ["Earliest arrival", "Latest checkout"].map((text) => {
    const div = document.createElement("div"), label = document.createElement("label"), input = document.createElement("input");
    label.htmlFor = input.id = nextId(); label.textContent = text;
    input.type = "date"; input.required = true;
    div.append(label, input); grid.append(div);
    return input;
  });
  linkDates(inputs[0], inputs[1]);
  row.append(grid);
  if ($("windows").children.length) row.append(removeButton("Remove this date range", () => row.remove()));
  row.value = () => ({ start_date: inputs[0].value, end_date: inputs[1].value });
  $("windows").append(row);
}
$("add-window").addEventListener("click", addWindow);

// Trip form: stops, each with one or more alternative locations
function renumberStops() {
  [...$("stops").children].forEach((s, i) => { s.querySelector("legend").textContent = "Stop " + (i + 1); });
}
function numberField(text, hint, value, min) {
  const div = document.createElement("div"), label = document.createElement("label"), input = document.createElement("input");
  label.htmlFor = input.id = nextId(); label.textContent = text;
  if (hint) { const h = document.createElement("span"); h.className = "hint"; h.textContent = " " + hint; label.append(h); }
  input.type = "number"; input.min = min; input.value = value; input.required = true;
  div.append(label, input);
  return [div, input];
}
function addStop() {
  const stop = document.createElement("fieldset");
  stop.className = "stop";
  const legend = document.createElement("legend");
  const alts = document.createElement("div");
  function addAlt() {
    const alt = document.createElement("div");
    alt.className = "alt";
    if (alts.children.length) {
      const or = document.createElement("p"); or.className = "alt-or"; or.textContent = "or";
      alt.append(or);
    }
    const picker = makePicker();
    alt.append(picker);
    if (alts.children.length) alt.append(removeButton("Remove this alternative", () => alt.remove()));
    alt.value = picker.value;
    alts.append(alt);
  }
  addAlt();
  const addAltButton = document.createElement("button");
  addAltButton.type = "button"; addAltButton.className = "secondary";
  addAltButton.textContent = "Add an alternative campground";
  addAltButton.addEventListener("click", addAlt);
  const grid = document.createElement("div");
  grid.className = "row";
  const [minDiv, min] = numberField("Fewest nights", "(0 = optional stop)", 1, 0);
  const [maxDiv, max] = numberField("Most nights", "", 1, 1);
  min.addEventListener("change", () => { if (+max.value < +min.value) max.value = Math.max(+min.value, 1); });
  max.addEventListener("change", () => { if (+max.value < +min.value) min.value = max.value; });
  grid.append(minDiv, maxDiv);
  stop.append(legend, alts, addAltButton, grid);
  if ($("stops").children.length) stop.append(removeButton("Remove this stop", () => { stop.remove(); renumberStops(); }));
  stop.value = () => {
    const locations = [...alts.children].map((a) => a.value());
    return {
      name: locations[0].name,
      min_nights: +min.value, max_nights: +max.value,
      locations: locations.map((l) => ({ park: l.park, booking_category: +l.booking_category, campgrounds: [l.campground] })),
    };
  };
  $("stops").append(stop);
  renumberStops();
}
$("add-stop").addEventListener("click", addStop);
["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].forEach((d, i) => {
  const label = document.createElement("label"), box = document.createElement("input");
  box.type = "checkbox"; box.value = i;
  label.append(box, d);
  $("start-days").append(label);
});
addWindow();
addStop();
addStop();

// Results
const fmt = (d) => new Date(d + (d.length === 10 ? "T00:00" : "")).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
const plural = (n, word) => n + " " + word + (n === 1 ? "" : "s");
function bookLink(url) {
  const a = document.createElement("a");
  a.href = url; a.target = "_blank"; a.rel = "noopener"; a.textContent = "Book";
  return a;
}

function searchBody() {
  const where = singlePicker.value();
  return {
    rec_area: where.park, booking_category: where.booking_category, campground: where.campground,
    start_date: $("start").value, end_date: $("end").value, nights: $("nights").value,
  };
}
function searchWhat() {
  const where = singlePicker.value();
  const n = where.campground.length;
  if (!n) return "every campground at " + where.parkName;
  return (n > 3 ? plural(n, "campground") : where.name) + " at " + where.parkName;
}
$("form").addEventListener("submit", (event) => { event.preventDefault(); runSearch(searchBody(), searchWhat()); });
async function runSearch(body, what) {
  $("results").replaceChildren();
  setStatus("");
  try {
    const sites = await api("/api/search", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }, "Searching " + what + " for open sites, " + fmt(body.start_date) + " to " + fmt(body.end_date) + "…", true);
    setStatus(sites.length ? plural(sites.length, "open campsite") + " found."
                           : "No open campsites for those dates. Try other dates or another park.");
    $("results").replaceChildren(...sites.map((s) => {
      const div = document.createElement("div");
      div.className = "site";
      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = s.facility_name + " — Site " + s.campsite_site_name;
      const when = document.createElement("span");
      when.textContent = fmt(s.booking_date) + " to " + fmt(s.booking_end_date) + " · " + plural(s.booking_nights, "night");
      info.append(title, when);
      div.append(info, bookLink(s.booking_url));
      return div;
    }));
  } catch (e) {
    setStatus(e.message, true);
  }
}

function tripBody() {
  const num = (id) => ($(id).value ? +$(id).value : null);
  return {
    windows: [...$("windows").children].map((w) => w.value()),
    stops: [...$("stops").children].map((s) => s.value()),
    any_order: $("any-order").checked,
    start_days: [...$("start-days").querySelectorAll("input:checked")].map((b) => +b.value),
    min_total_nights: num("min-total") || 1,
    max_total_nights: num("max-total"),
    max_results: num("max-results") || 25,
  };
}
$("trip-form").addEventListener("submit", (event) => { event.preventDefault(); runTrip(tripBody()); });
async function runTrip(trip, what) {
  $("results").replaceChildren();
  setStatus("");
  try {
    const trips = await api("/api/trip", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(trip),
    }, "Searching " + (what || plural(trip.stops.length, "stop")) + " for gap-free trips across every combination of dates…", true);
    setStatus(trips.length ? plural(trips.length, "trip") + " found."
                           : "No gap-free trips for those dates. Try wider dates, more flexible nights or alternative campgrounds.");
    $("results").replaceChildren(...trips.map((t) => {
      const card = document.createElement("div");
      card.className = "trip";
      const first = t.legs[0], last = t.legs[t.legs.length - 1];
      const h = document.createElement("h2");
      h.textContent = fmt(first.check_in) + " to " + fmt(last.check_out) + " · " +
        plural(t.legs.reduce((n, l) => n + l.nights, 0), "night");
      card.append(h, ...t.legs.map((leg) => {
        const div = document.createElement("div");
        div.className = "leg";
        // a stop with alternative campgrounds can have sites at several of them
        const mixed = new Set(leg.sites.map((s) => s.facility_name)).size > 1;
        const title = document.createElement("strong");
        title.textContent = "Stop " + (leg.stop + 1) + (mixed ? "" : ": " + leg.sites[0].facility_name);
        const when = document.createElement("span");
        when.textContent = " " + fmt(leg.check_in) + " to " + fmt(leg.check_out) + " · " + plural(leg.nights, "night");
        const list = document.createElement("ul");
        list.append(...leg.sites.map((s) => {
          const li = document.createElement("li");
          li.append((mixed ? s.facility_name + " — " : "") + "Site " + s.campsite_site_name, bookLink(s.booking_url));
          return li;
        }));
        div.append(title, when, list);
        return div;
      }));
      return card;
    }));
  } catch (e) {
    setStatus(e.message, true);
  }
}

// Saved searches and trips (shared with the command line: `spotsnagger saved`)
let savedItems = [];
const quoted = (name) => "“" + name + "”";
function describeSaved(item) {
  const p = item.params;
  if (item.kind === "search") {
    return "Search · " + fmt(p.start_date) + " to " + fmt(p.end_date) + " · " + plural(+p.nights, "night") + " or more";
  }
  const starts = p.windows.map((w) => w.start_date).sort(), ends = p.windows.map((w) => w.end_date).sort();
  return "Trip · " + plural(p.stops.length, "stop") + " · " + fmt(starts[0]) + " to " + fmt(ends[ends.length - 1]);
}
async function loadSaved() {
  try {
    savedItems = await api("/api/saved", undefined, "Loading your saved searches…");
  } catch (e) {
    setStatus(e.message, true);
    return;
  }
  $("saved").hidden = !savedItems.length;
  $("saved-count").textContent = "(" + savedItems.length + ")";
  $("saved-list").replaceChildren(...savedItems.map((item) => {
    const row = document.createElement("div");
    row.className = "saved-item";
    const info = document.createElement("div"), name = document.createElement("strong"), what = document.createElement("span");
    name.textContent = item.name;
    what.textContent = describeSaved(item);
    row.dataset.text = (item.name + " " + what.textContent).toLowerCase();
    info.append(name, what);
    const actions = document.createElement("div");
    const run = document.createElement("button");
    run.type = "button"; run.className = "secondary"; run.textContent = "Search again";
    run.setAttribute("aria-label", "Search again: " + item.name);
    run.addEventListener("click", () => (item.kind === "trip" ? runTrip : runSearch)(item.params, "saved " + item.kind + " " + quoted(item.name)));
    const del = removeButton("Delete", async () => {
      if (!confirm("Delete the saved search " + quoted(item.name) + "?")) return;
      try {
        await api("/api/saved?name=" + encodeURIComponent(item.name), { method: "DELETE" }, "Deleting saved search " + quoted(item.name) + "…");
      } catch (e) {
        setStatus(e.message, true);
      }
      loadSaved();
    });
    del.setAttribute("aria-label", "Delete " + item.name);
    actions.append(run, del);
    row.append(info, actions);
    return row;
  }));
  filterSaved();
}
// every word typed must appear somewhere in the name or description
function filterSaved() {
  const words = $("saved-filter").value.toLowerCase().split(" ").filter(Boolean);
  let shown = 0;
  for (const row of $("saved-list").children) {
    row.hidden = !words.every((w) => row.dataset.text.includes(w));
    shown += !row.hidden;
  }
  $("saved-none").hidden = shown > 0 || !savedItems.length;
}
$("saved-filter").addEventListener("input", filterSaved);
async function saveCurrent(form, kind, params) {
  if (!form.reportValidity()) return;
  const name = (prompt("Name this " + kind + " so you can search it again later:") || "").trim();
  if (!name) return;
  if (savedItems.some((i) => i.name === name) && !confirm("Replace the saved search " + quoted(name) + "?")) return;
  try {
    await api("/api/saved", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, kind, params }),
    }, "Saving " + kind + " " + quoted(name) + "…");
    setStatus("Saved " + quoted(name) + ".");
  } catch (e) {
    setStatus(e.message, true);
  }
  loadSaved();
}
$("save-search").addEventListener("click", () => saveCurrent($("form"), "search", searchBody()));
$("save-trip").addEventListener("click", () => saveCurrent($("trip-form"), "trip", tripBody()));
loadSaved();
</script>
</body>
</html>
"""
