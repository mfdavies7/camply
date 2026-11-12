"""
Aspira (ReserveAmerica) search: Alberta, PEI and Saskatchewan provincial parks
"""

import logging
import sys
from datetime import datetime, time
from typing import Any, List, Optional, Union

from spotsnagger.containers import AvailableCampsite, RecreationArea, SearchWindow
from spotsnagger.providers.aspira.aspira_provider import (
    BACKCOUNTRY,
    DAY_USE,
    DAY_USE_LOOKING_FOR,
    Aspira,
)
from spotsnagger.search.base_search import BaseCampingSearch
from spotsnagger.utils import make_list

logger = logging.getLogger(__name__)


class SearchAspira(BaseCampingSearch):
    """
    Searches Aspira (Alberta, PEI and Saskatchewan Parks) for Campsites
    """

    provider_class = Aspira
    campsite_finder: Aspira
    list_campsites_supported: bool = False

    @classmethod
    def find_recreation_areas(
        cls, search_string: Optional[str] = None, **kwargs: Any
    ) -> List[RecreationArea]:
        """
        Return the Aspira Recreation Areas
        """
        return Aspira.find_recreation_areas(search_string=search_string)

    def __init__(
        self,
        search_window: Union[SearchWindow, List[SearchWindow]],
        recreation_area: List[int],
        campgrounds: Optional[Union[List[int], int]] = None,
        campsites: Optional[Union[List[int], int]] = None,
        weekends_only: bool = False,
        nights: int = 1,
        booking_category_id: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize with Search Parameters

        Parameters
        ----------
        search_window: Union[SearchWindow, List[SearchWindow]]
            Search Window tuple containing start date and End Date
        recreation_area: List[int]
            A single recreation area (province) ID
        campgrounds: Union[List[int], int]
            Campground (park) ID(s); defaults to all of them
        campsites: Union[List[int], int]
            Only these campsite IDs
        weekends_only: bool
            Only search Friday / Saturday nights
        nights: int
            minimum number of consecutive nights to search per campsite
        booking_category_id: Optional[int]
            0 camping (default), 1 day use or 2 backcountry permits
        """
        super().__init__(
            search_window=search_window,
            weekends_only=weekends_only,
            nights=nights,
            **kwargs,
        )
        rec_areas = make_list(recreation_area, coerce=int) or []
        # no campgrounds means every campground in the park
        campground_ids = make_list(campgrounds, coerce=int) or None
        if len(rec_areas) != 1:
            logger.error("Aspira searches need exactly one --rec-area")
            sys.exit(1)
        self._recreation_area_id: int = rec_areas[0]
        self.booking_category_id = int(booking_category_id or 0)
        self.campsites = set(make_list(campsites, coerce=int) or [])
        self.campgrounds = self.campsite_finder.find_campgrounds(
            rec_area_id=rec_areas,
            campground_id=campground_ids,
            booking_category_id=self.booking_category_id,
        )

    def get_matching_campsites(  # type: ignore[override]
        self, continuous: bool = False, search_once: bool = False, **kwargs: Any
    ) -> List[AvailableCampsite]:
        """
        Search, refusing continuous searches: these sites sit behind a queue
        """
        if continuous and not search_once:
            logger.error(
                "Aspira parks are behind a waiting-room queue and can't be "
                "searched continuously; search them once instead"
            )
            sys.exit(1)
        return super().get_matching_campsites(
            continuous=continuous, search_once=search_once, **kwargs
        )

    def get_all_campsites(self) -> List[AvailableCampsite]:
        """
        Sites available for each search window's whole remaining stay
        """
        available_sites = []
        _, _, rec_area = self.campsite_finder.rec_area_lookup(self._recreation_area_id)
        for search_window in self.search_window:
            start_date = search_window.get_current_start_date()
            nights = (search_window.end_date - start_date).days
            for i, campground in enumerate(self.campgrounds, 1):
                logger.info(
                    f"Searching {campground.facility_name} ({i} of "
                    f"{len(self.campgrounds)}) from {start_date} "
                    f"to {search_window.end_date}"
                )
                if self.booking_category_id == BACKCOUNTRY:
                    sites = self.campsite_finder.list_backcountry_sites(
                        rec_area_id=self._recreation_area_id,
                        park_id=int(campground.facility_id),
                        start_date=start_date,
                        nights=nights,
                    )
                else:
                    sites = self.campsite_finder.list_available_sites(
                        rec_area_id=self._recreation_area_id,
                        park_id=int(campground.facility_id),
                        start_date=start_date,
                        nights=nights,
                        looking_for=DAY_USE_LOOKING_FOR
                        if self.booking_category_id == DAY_USE
                        else None,
                    )
                for site in sites:
                    if self.campsites and site["site_id"] not in self.campsites:
                        continue
                    available_sites.append(
                        AvailableCampsite(
                            campsite_id=site["site_id"],
                            campsite_site_name=site["site_name"],
                            booking_date=datetime.combine(start_date, time.min),
                            booking_end_date=datetime.combine(
                                search_window.end_date, time.min
                            ),
                            booking_nights=nights,
                            campsite_loop_name=site["loop"],
                            campsite_type=site["site_type"],
                            campsite_occupancy=(1, site["max_people"]),
                            campsite_use_type="N/A",
                            availability_status="Available",
                            recreation_area=rec_area.recreation_area,
                            recreation_area_id=self._recreation_area_id,
                            facility_name=campground.facility_name,
                            facility_id=campground.facility_id,
                            booking_url=site["booking_url"],
                            permitted_equipment=None,
                            campsite_attributes=None,
                        )
                    )
        return available_sites

    def list_campsite_units(self) -> Any:
        """
        List Campsite Units
        """
        raise NotImplementedError
