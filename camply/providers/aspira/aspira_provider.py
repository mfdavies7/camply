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
from camply.utils import make_list
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
        ),
    ),
    2: (
        "www.peiprovincialparks.ca",
        "PE",
        RecreationArea(
            recreation_area="Prince Edward Island Provincial Parks",
            recreation_area_id=2,
            recreation_area_location="Prince Edward Island, CA",
        ),
    ),
    3: (
        "parks.saskatchewan.ca",
        "SKPP",
        RecreationArea(
            recreation_area="Saskatchewan Provincial Parks",
            recreation_area_id=3,
            recreation_area_location="Saskatchewan, CA",
        ),
    ),
}

# Queue-it waiting room: reload until it redirects back to the park site,
# for up to QUEUE_MAX_CHECKS * QUEUE_POLL_SECONDS
QUEUE_HOST = "go.aspiraconnect.com"
QUEUE_POLL_SECONDS = 15
QUEUE_MAX_CHECKS = 120

PAGE_SIZE = 10
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
        cls, search_string: Optional[str] = None, **kwargs
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

    def find_campgrounds(
        self,
        search_string: Optional[str] = None,
        rec_area_id: Optional[List[int]] = None,
        campground_id: Optional[List[int]] = None,
        **kwargs,
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

        Returns
        -------
        List[CampgroundFacility]
        """
        if not rec_area_id:
            logger.error("This provider requires --rec-area to search campgrounds")
            sys.exit(1)
        rec_area_id = make_list(rec_area_id, coerce=int)[0]
        hostname, contract, rec_area = self.rec_area_lookup(rec_area_id)
        names: Dict[int, str] = {}
        start, total = 0, 1
        while start < total:
            page = self._request(
                f"https://{hostname}/campgroundDirectoryList.do"
                f"?contractCode={contract}&startIdx={start}"
            ).text
            names.update(parse_campground_directory(page, contract))
            total = int(_TOTAL.search(page).group(1)) if _TOTAL.search(page) else 0
            start += PAGE_SIZE
        wanted = {str(c) for c in make_list(campground_id or [])}
        campgrounds = [
            CampgroundFacility(
                facility_name=name,
                recreation_area=rec_area.recreation_area,
                facility_id=park_id,
                recreation_area_id=rec_area_id,
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
    ) -> List[Dict[str, Any]]:
        """
        Sites of a park available for every night of a stay

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
