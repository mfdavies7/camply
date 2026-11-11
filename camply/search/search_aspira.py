"""
Aspira (ReserveAmerica) search: Alberta, PEI and Saskatchewan provincial parks
"""

import logging
import sys
from datetime import datetime, time
from typing import Any, List, Optional, Union

from camply.containers import AvailableCampsite, RecreationArea, SearchWindow
from camply.providers.aspira.aspira_provider import Aspira
from camply.search.base_search import BaseCampingSearch
from camply.utils import make_list

logger = logging.getLogger(__name__)


class SearchAspira(BaseCampingSearch):
    """
    Searches Aspira (Alberta, PEI and Saskatchewan Parks) for Campsites
    """

    provider_class = Aspira
    list_campsites_supported: bool = False

    @classmethod
    def find_recreation_areas(
        cls, search_string: Optional[str] = None, **kwargs
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
        **kwargs,
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
            Campground (park) ID(s); required
        campsites: Union[List[int], int]
            Only these campsite IDs
        weekends_only: bool
            Only search Friday / Saturday nights
        nights: int
            minimum number of consecutive nights to search per campsite
        """
        super().__init__(
            search_window=search_window,
            weekends_only=weekends_only,
            nights=nights,
            **kwargs,
        )
        recreation_area = make_list(recreation_area)
        if len(recreation_area) != 1 or not make_list(campgrounds):
            logger.error(
                "Aspira searches need exactly one --rec-area and at least one --campground"
            )
            sys.exit(1)
        self._recreation_area_id = int(recreation_area[0])
        self.campsites = {int(c) for c in make_list(campsites or [])}
        self.campgrounds = self.campsite_finder.find_campgrounds(
            rec_area_id=self._recreation_area_id, campground_id=campgrounds
        )

    def get_matching_campsites(
        self, continuous: bool = False, search_once: bool = False, **kwargs
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
            for campground in self.campgrounds:
                for site in self.campsite_finder.list_available_sites(
                    rec_area_id=self._recreation_area_id,
                    park_id=campground.facility_id,
                    start_date=start_date,
                    nights=nights,
                ):
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
                        )
                    )
        return available_sites

    def list_campsite_units(self) -> Any:
        """
        List Campsite Units
        """
        raise NotImplementedError
