"""
Aspira (ReserveAmerica) provider: Alberta, PEI and Saskatchewan provincial parks

These sites are server-rendered HTML behind Aspira's Queue-it waiting room, so
campgrounds and availability are scraped from the same pages a browser sees.
"""

import datetime
import html
import logging
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from camply.containers import CampgroundFacility, RecreationArea
from camply.providers.base_provider import BaseProvider, ProviderError
from camply.utils.logging_utils import log_sorted_response

logger = logging.getLogger(__name__)

# rec area ID -> (hostname, contract code, RecreationArea)
RECREATION_AREAS: Dict[int, Tuple[str, str, RecreationArea]] = {
    1: (
        "shop.albertaparks.ca",
        "ABPP",
        RecreationArea(
            recreation_area="Alberta Parks",
            recreation_area_id=1,
            recreation_area_location="Alberta, CA",
            coordinates=None,
            description=None,
        ),
    ),
    2: (
        "www.peiprovincialparks.ca",
        "PE",
        RecreationArea(
            recreation_area="Prince Edward Island Provincial Parks",
            recreation_area_id=2,
            recreation_area_location="Prince Edward Island, CA",
            coordinates=None,
            description=None,
        ),
    ),
    3: (
        "parks.saskatchewan.ca",
        "SKPP",
        RecreationArea(
            recreation_area="Saskatchewan Provincial Parks",
            recreation_area_id=3,
            recreation_area_location="Saskatchewan, CA",
            coordinates=None,
            description=None,
        ),
    ),
}

# Queue-it waiting room: reload until it redirects back to the park site,
# for up to QUEUE_MAX_CHECKS * QUEUE_POLL_SECONDS
QUEUE_HOST = "go.aspiraconnect.com"
QUEUE_POLL_SECONDS = 15
QUEUE_MAX_CHECKS = 120

PAGE_SIZE = 10
# Booking categories: the site's top-level "interest" search options camply can search
CAMPING, DAY_USE, BACKCOUNTRY = 0, 1, 2
INTERESTS = {"camping": CAMPING, "dayuse": DAY_USE, "permit": BACKCOUNTRY}
# Day use areas are campground "sites" of this `lookingFor` type
DAY_USE_LOOKING_FOR = 9001
# The backcountry permit calendar shows this many nights per page
CALENDAR_DAYS = 14
_TOTAL = re.compile(r"id='resulttotal_top'>(\d+)<")
_AVAILABLE_COUNT = re.compile(r"(\d+) site\(s\) available out of")
_SITE_ID = re.compile(r"siteId=(\d+)[^']*'[^>]*>([^<]+)</a>")
_CELL = re.compile(r"<div class='td( maxPeopleCell)?'>([^<]*)</div>")
_STATUS = re.compile(r"class='td sitescompareselectorbtn\d+'>([^<]*)")


class Aspira(BaseProvider):
    """
    Aspira (ReserveAmerica) provider
    """

    @classmethod
    def find_recreation_areas(
        cls, search_string: Optional[str] = None, **kwargs: Any
    ) -> List[RecreationArea]:
        """
        Find Recreation Areas (provinces) matching a search string
        """
        rec_areas = [
            rec_area
            for _, _, rec_area in RECREATION_AREAS.values()
            if not search_string
            or search_string.lower()
            in f"{rec_area.recreation_area} {rec_area.recreation_area_location}".lower()
        ]
        log_sorted_response(rec_areas)
        return rec_areas

    @staticmethod
    def rec_area_lookup(rec_area_id: int) -> Tuple[str, str, RecreationArea]:
        """
        Hostname, contract code and RecreationArea of a rec area ID, exiting if unknown
        """
        try:
            return RECREATION_AREAS[int(rec_area_id)]
        except (KeyError, ValueError):
            logger.error(f"Recreation area '{rec_area_id}' does not exist.")
            sys.exit(1)

    def _request(
        self, url: str, data: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        GET (or POST `data`), waiting out the Aspira queue
        """
        method = "POST" if data else "GET"
        response = self.session.request(method, url, data=data, timeout=60)
        for _ in range(QUEUE_MAX_CHECKS):
            if urlparse(response.url).hostname != QUEUE_HOST:
                break
            logger.info("Waiting in the Aspira queue for %s...", urlparse(url).hostname)
            time.sleep(QUEUE_POLL_SECONDS)
            response = self.session.get(response.url, timeout=60)
        else:
            raise ProviderError(f"Timed out waiting in the Aspira queue for {url}")
        response.raise_for_status()
        return response

    def list_booking_categories(self, rec_area_id: int) -> List[Dict[str, Any]]:
        """
        Searchable booking categories (Camping, Day Use, Backcountry) of a rec area
        """
        hostname, _, _ = self.rec_area_lookup(rec_area_id)
        return parse_interests(self._request(f"https://{hostname}/").text)

    def _find_by_interest(
        self, hostname: str, contract: str, booking_category_id: int
    ) -> Dict[int, str]:
        """
        Park ID -> name of every park offering a non-camping booking category
        """
        interest = next(k for k, v in INTERESTS.items() if v == booking_category_id)
        # The first search of a session comes back empty until the home page is loaded
        self._request(f"https://{hostname}/")
        page = self._request(
            f"https://{hostname}/unifSearch.do",
            data={"interest": interest, "contractCode": contract},
        ).text
        shown = re.search(r"usearch_results_label'>Showing: \d+-(\d+) of (\d+)", page)
        if shown and shown.group(1) != shown.group(2):
            # shortcut: only the first results page is read (paging is stateful);
            # upgrade if a province lists more than 10 places for one category
            logger.warning(f"Only {shown.group(1)} of {shown.group(2)} parks listed")
        return parse_search_results(page)

    def find_campgrounds(
        self,
        search_string: Optional[str] = None,
        rec_area_id: Optional[List[int]] = None,
        campground_id: Optional[List[int]] = None,
        booking_category_id: Optional[int] = None,
        **kwargs: Any,
    ) -> List[CampgroundFacility]:
        """
        List the campgrounds (parks) of a recreation area

        Parameters
        ----------
        search_string: Optional[str]
            Only campgrounds whose name contains this
        rec_area_id: Optional[List[int]]
            Recreation area (province) to list; required
        campground_id: Optional[List[int]]
            Only these campground IDs
        booking_category_id: Optional[int]
            CAMPING (default), DAY_USE or BACKCOUNTRY

        Returns
        -------
        List[CampgroundFacility]
        """
        if not rec_area_id:
            logger.error("This provider requires --rec-area to search campgrounds")
            sys.exit(1)
        rec_area = int(rec_area_id[0])
        hostname, contract, recreation_area = self.rec_area_lookup(rec_area)
        names: Dict[int, str] = {}
        start, total = 0, 1
        if booking_category_id:
            names = self._find_by_interest(hostname, contract, booking_category_id)
            total = 0
        while start < total:
            page = self._request(
                f"https://{hostname}/campgroundDirectoryList.do"
                f"?contractCode={contract}&startIdx={start}"
            ).text
            names.update(parse_campground_directory(page, contract))
            match = _TOTAL.search(page)
            total = int(match.group(1)) if match else 0
            start += PAGE_SIZE
        wanted = {str(c) for c in campground_id or []}
        campgrounds = [
            CampgroundFacility(
                facility_name=name,
                recreation_area=recreation_area.recreation_area,
                facility_id=park_id,
                recreation_area_id=rec_area,
                map_id=None,
                coordinates=None,
            )
            for park_id, name in names.items()
            if (not wanted or str(park_id) in wanted)
            and (not search_string or search_string.lower() in name.lower())
        ]
        logger.info(f"{len(campgrounds)} Matching Campgrounds Found")
        log_sorted_response(campgrounds)
        return campgrounds

    def list_available_sites(
        self,
        rec_area_id: int,
        park_id: int,
        start_date: datetime.date,
        nights: int,
        looking_for: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Sites of a park available for every night of a stay

        `looking_for` limits the search to one type of site (e.g.
        DAY_USE_LOOKING_FOR); falsy searches every camping type

        Returns
        -------
        List[Dict[str, Any]]
            `site_id`, `site_name`, `loop`, `site_type`, `max_people`, `booking_url`
        """
        hostname, contract, _ = self.rec_area_lookup(rec_area_id)
        park_url = (
            f"https://{hostname}/campgroundDetails.do"
            f"?contractCode={contract}&parkId={park_id}"
        )
        # The date search only applies once the park page has opened a session
        self._request(park_url)
        page = self._request(
            park_url,
            data={
                "contractCode": contract,
                "parkId": park_id,
                "siteTypeFilter": "ALL",
                "submitSiteForm": "true",
                "search": "site",
                "campingDate": start_date.strftime("%m/%d/%Y"),
                "lengthOfStay": nights,
                "lookingFor": looking_for or "",
            },
        ).text
        match = _AVAILABLE_COUNT.search(page)
        if match is None:
            logger.warning(
                f"Aspira ignored the date search for park {park_id} "
                f"on {start_date} (outside the booking window?)"
            )
            return []
        available_count = int(match.group(1))
        sites = [s for s in parse_site_list(page) if s["available"]]
        # Results are sorted available-first, so page only until all are collected
        start = PAGE_SIZE
        while len(sites) < available_count:
            page = self._request(
                f"https://{hostname}/campsitePaging.do"
                f"?contractCode={contract}&parkId={park_id}&startIdx={start}"
            ).text
            page_sites = [s for s in parse_site_list(page) if s["available"]]
            if not page_sites:
                break
            sites += page_sites
            start += PAGE_SIZE
        for site in sites:
            site["booking_url"] = (
                f"https://{hostname}/campsiteDetails.do?contractCode={contract}"
                f"&parkId={park_id}&siteId={site['site_id']}"
                f"&arvdate={start_date.strftime('%m/%d/%Y')}&lengthOfStay={nights}"
            )
        return sites

    def list_backcountry_sites(
        self,
        rec_area_id: int,
        park_id: int,
        start_date: datetime.date,
        nights: int,
    ) -> List[Dict[str, Any]]:
        """
        Backcountry campgrounds of a permit area with a permit for every night of a stay

        Returns
        -------
        List[Dict[str, Any]]
            Same keys as `list_available_sites`
        """
        hostname, contract, _ = self.rec_area_lookup(rec_area_id)
        # The calendar only renders once the area page has set its permit type
        self._request(
            f"https://{hostname}/wildernessAreaDetails.do"
            f"?page=detail&contractCode={contract}&parkId={park_id}"
        )
        stay = {start_date + datetime.timedelta(days=n) for n in range(nights)}
        calendar: Dict[str, Dict[str, Any]] = {}
        page_start = start_date
        while page_start < start_date + datetime.timedelta(days=nights):
            page = self._request(
                f"https://{hostname}/singleTripPermitCalendar.do?page=calendar"
                f"&tripPlan=true&calarvdate={page_start.strftime('%m/%d/%Y')}"
                f"&contractCode={contract}&parkId={park_id}"
                "&entranceType=0&expandTable=false"
            ).text
            for name, row in parse_permit_calendar(page, page_start).items():
                site = calendar.setdefault(name, {"dates": {}})
                site["dates"].update(row)
            page_start += datetime.timedelta(days=CALENDAR_DAYS)
        sites = []
        for name, site in calendar.items():
            if not stay <= site["dates"].keys():
                continue
            url = site["dates"][start_date]
            entrance = re.search(r"entranceId=(\d+)", url)
            if not entrance:
                continue
            sites.append(
                {
                    "site_id": int(entrance.group(1)),
                    "site_name": name,
                    "loop": None,
                    "site_type": "Backcountry",
                    "max_people": 1,
                    "booking_url": f"https://{hostname}{url}",
                }
            )
        return sites


def parse_interests(page: str) -> List[Dict[str, Any]]:
    """
    Searchable booking categories ({"id", "name"}) from the home page `interest` select

    A site without that select (PEI) only offers camping
    """
    select = re.search(r"<select name='interest'.*?</select>", page, re.DOTALL)
    if not select:
        return [{"id": CAMPING, "name": "Camping"}]
    return [
        {"id": INTERESTS[value], "name": html.unescape(name).strip()}
        for value, name in re.findall(
            r"<option\s+(?:selected='selected'\s+)?value='(\w+)'>([^<]+)",
            select.group(0),
        )
        if value in INTERESTS
    ]


def parse_search_results(page: str) -> Dict[int, str]:
    """
    Park ID -> name from a `unifSearch.do` results page
    """
    pattern = r"parkId=(\d+)[^']*' class='facility_link' title='([^']+)'"
    return {
        int(park_id): html.unescape(name).strip()
        for park_id, name in re.findall(pattern, page)
    }


def parse_permit_calendar(
    page: str, first_date: datetime.date
) -> Dict[str, Dict[datetime.date, str]]:
    """
    Backcountry campground name -> {available night: booking path} from a permit calendar
    """
    calendar = {}
    for row in re.sub(r"\s+", " ", page).split("<div class='avail_row'>")[1:]:
        name = re.search(r"class='entranceCode'>([^<]+)", row)
        if not name:
            continue
        cells = re.findall(
            # titles hold markup ("Available<br># of Permits ...")
            r"class='status (\w+) avail_cell' title='[^']*'>\s*(?:<a href='([^']+)')?",
            row,
        )
        calendar[html.unescape(name.group(1)).strip()] = {
            first_date + datetime.timedelta(days=offset): html.unescape(link)
            for offset, (status, link) in enumerate(cells)
            if status == "a" and link
        }
    return calendar


def parse_campground_directory(page: str, contract: str) -> Dict[int, str]:
    """
    Park ID -> name from a `campgroundDirectoryList.do` page
    """
    # Name links use a raw `&` (the "Enter Date" links use `&amp;`)
    pattern = re.compile(rf"contractCode={contract}&parkId=(\d+)'[^>]*>([^<]+)")
    return {
        int(park_id): html.unescape(name).strip()
        for park_id, name in pattern.findall(page)
    }


def parse_site_list(page: str) -> List[Dict[str, Any]]:
    """
    Sites in the search results list of a `campgroundDetails.do` page

    Columns: Site, Loop, Type, Max # of people, Equipment length, Amenities, Status
    """
    start = page.find("<div id='shoppingitems'")
    if start == -1:
        return []
    sites = []
    for row in page[start:].split("<div class='br'>")[1:]:
        site = _SITE_ID.search(row)
        status = _STATUS.search(row)
        if not site or not status:
            continue
        cells = _CELL.findall(row)
        max_people = next((v for flag, v in cells if flag), "")
        texts = [html.unescape(v).strip() for flag, v in cells if not flag]
        sites.append(
            {
                "site_id": int(site.group(1)),
                "site_name": html.unescape(site.group(2)).strip(),
                "loop": texts[0] if texts else None,
                "site_type": texts[1] if len(texts) > 1 else None,
                "max_people": int(max_people) if max_people.isdigit() else 1,
                "available": status.group(1).strip().lower() == "available",
            }
        )
    return sites
