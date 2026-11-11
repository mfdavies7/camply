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
from camply.providers import GoingToCamp
from camply.providers.going_to_camp.going_to_camp_provider import (
    booking_category_name,
)
from camply.providers.going_to_camp.rec_areas import RECREATION_AREAS
from camply.search import SearchGoingToCamp

logger = logging.getLogger(__name__)

RESULT_FIELDS = {
    "facility_name",
    "campsite_site_name",
    "booking_date",
    "booking_end_date",
    "booking_nights",
    "booking_url",
}


def list_parks() -> list:
    """
    All GoingToCamp parks, sorted by name
    """
    return sorted(
        (
            {
                "id": a.recreation_area_id,
                "name": a.recreation_area,
                "location": a.recreation_area_location,
            }
            for a in RECREATION_AREAS.values()
        ),
        key=lambda p: p["name"],
    )


def list_booking_categories(rec_area: int) -> list:
    """
    Reservation services of one park (Campsite, Backcountry, Roofed, ...)
    """
    return [
        {"id": c["bookingCategoryId"], "name": booking_category_name(c)}
        for c in sorted(
            GoingToCamp().list_booking_categories(rec_area),
            key=lambda c: c["bookingCategoryId"],
        )
    ]


def list_campgrounds(rec_area: int, booking_category: int = 0) -> list:
    """
    Campgrounds within one park offering a reservation service (calls the API)
    """
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
    rec_area = int(body["rec_area"])
    if rec_area not in {a.recreation_area_id for a in RECREATION_AREAS.values()}:
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
        # GoingToCamp only allows searching one campground at a time
        raise ValueError("Please choose a campground")
    camp_search = SearchGoingToCamp(
        search_window=SearchWindow(start_date=start, end_date=end),
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
            int(parse_qs(query)["rec_area"][0])
        ),
        ("GET", "/api/campgrounds"): lambda: list_campgrounds(
            int(parse_qs(query)["rec_area"][0]),
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
</style>
</head>
<body>
<main>
  <h1>&#127957; Campsite Finder</h1>
  <p class="lead">Find open campsites at Canadian parks. Pick a park and your dates, then press Search.</p>
  <form id="form">
    <label for="park">Park</label>
    <select id="park" required><option value="">Loading parks&hellip;</option></select>

    <label for="category">Type of stay <span class="hint">(campsite, backcountry, cabin&hellip;)</span></label>
    <select id="category" required disabled><option value="">Choose a park first</option></select>

    <label for="campground">Campground</label>
    <select id="campground" required disabled><option value="">Choose a park first</option></select>

    <div class="row">
      <div><label for="start">Arriving</label><input type="date" id="start" required></div>
      <div><label for="end">Leaving</label><input type="date" id="end" required></div>
    </div>

    <label for="nights">Nights in a row <span class="hint">(at least this many)</span></label>
    <input type="number" id="nights" min="1" value="1" required>

    <button id="go" type="submit">Search</button>
  </form>
  <div id="status" role="status" aria-live="polite"></div>
  <div id="results"></div>
</main>
<script>
const $ = (id) => document.getElementById(id);
const today = new Date().toISOString().slice(0, 10);
$("start").min = $("end").min = today;

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Something went wrong");
  return data;
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

api("/api/parks").then((parks) => {
  $("park").replaceChildren(option("", "Choose a park"),
    ...parks.map((p) => option(p.id, p.name + " (" + p.location + ")")));
}).catch((e) => setStatus(e.message, true));

$("park").addEventListener("change", async () => {
  const cat = $("category");
  cat.replaceChildren(option("", "Choose a type of stay"));
  cat.disabled = true;
  $("campground").replaceChildren(option("", "Choose a type of stay first"));
  $("campground").disabled = true;
  if (!$("park").value) return;
  try {
    const list = await api("/api/booking_categories?rec_area=" + encodeURIComponent($("park").value));
    cat.append(...list.map((c) => option(c.id, c.name)));
    cat.disabled = false;
    if (list.some((c) => c.id === 0)) { cat.value = "0"; cat.dispatchEvent(new Event("change")); }
  } catch (e) { setStatus(e.message, true); }
});

$("category").addEventListener("change", async () => {
  const cg = $("campground");
  cg.replaceChildren(option("", "Choose a campground"));
  cg.disabled = true;
  if (!$("category").value) return;
  try {
    const list = await api("/api/campgrounds?rec_area=" + encodeURIComponent($("park").value) +
                           "&booking_category=" + encodeURIComponent($("category").value));
    cg.append(...list.map((c) => option(c.id, c.name)));
    cg.disabled = false;
  } catch (e) { setStatus(e.message, true); }
});

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("go").disabled = true;
  $("results").replaceChildren();
  setStatus("Searching… this can take a minute.");
  try {
    const sites = await api("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rec_area: $("park").value, booking_category: $("category").value,
        campground: $("campground").value,
        start_date: $("start").value, end_date: $("end").value, nights: $("nights").value,
      }),
    });
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
  } finally {
    $("go").disabled = false;
  }
});
</script>
</body>
</html>
"""
