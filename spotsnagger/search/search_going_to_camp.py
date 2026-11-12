"""
Going To Camp API search utilities
"""

import logging
import sys
from datetime import datetime, time
from typing import Any, List, Optional, Union

from spotsnagger.containers import (
    AvailableCampsite,
    CampgroundFacility,
    RecreationArea,
    SearchWindow,
)
from spotsnagger.providers import GoingToCamp
from spotsnagger.providers.going_to_camp.going_to_camp_provider import (
    DEFAULT_BOOKING_CATEGORY,
)
from spotsnagger.search.base_search import BaseCampingSearch
from spotsnagger.utils import make_list
from spotsnagger.utils.general_utils import is_list_like

logger = logging.getLogger(__name__)


class SearchGoingToCamp(BaseCampingSearch):
    """
    Searches on GoingToCamp.com for Campsites
    """

    provider_class = GoingToCamp
    campsite_finder: GoingToCamp
    list_campsites_supported: bool = False

    @classmethod
    def find_recreation_areas(
        cls, search_string: str, **kwargs
    ) -> List[RecreationArea]:
        """
        Return the GoingToCamp Recreation Areas
        """
        return GoingToCamp.find_recreation_areas(search_string=search_string)

    # noinspection PyUnusedLocal
    def __init__(
        self,
        search_window: Union[SearchWindow, List[SearchWindow]],
        recreation_area: List[int],
        campsites: Optional[Union[List[int], int]] = None,
        weekends_only: bool = False,
        campgrounds: Optional[Union[List[str], str]] = None,
        equipment_id: Optional[int] = None,
        nights: int = 1,
        booking_category_id: Optional[int] = None,
        party_size: int = 1,
        tents: int = 1,
        **kwargs,
    ) -> None:
        """
        Initialize with Search Parameters

        Parameters
        ----------
        search_window: Union[SearchWindow, List[SearchWindow]]
            Search Window tuple containing start date and End Date
        recreation_area: List[int]
            The ID of the recreation area to be searched. This type of this is a
            List[int], but only for compatability with the BaseCampingSeach API.
            This list is validated to contain a single recreation area.
        weekends_only: bool
            Whether to only search for Camping availabilities on the weekends (Friday /
            Saturday nights)
        campgrounds: Union[List[int], int]
            Campground ID or List of Campground IDs
        nights: int
            minimum number of consecutive nights to search per campsite,defaults to 1
        booking_category_id: Optional[int]
            Reservation service to search (Campsite, Backcountry, Roofed, Group, ...).
            Defaults to 0, "Campsite". List them with `spotsnagger booking-categories`.
        party_size: int
            Number of people, defaults to 1
        tents: int
            Number of tents (pieces of equipment), defaults to 1. Sent to the API
            but not filtered on: sites don't list a tent limit
        """
        self.provider = GoingToCamp
        super().__init__(
            search_window=search_window,
            weekends_only=weekends_only,
            nights=nights,
            **kwargs,
        )

        self._recreation_area_id = self._validate_rec_area(recreation_area)
        self._campgrounds = campgrounds
        self.weekends_only = weekends_only
        assert (
            any(
                [
                    campsites not in [[], None],
                    campgrounds not in [[], None],
                    recreation_area is not None,
                ]
            )
            is True
        )
        self.campsites = make_list(campsites)
        self.party_size = int(party_size or 1)
        self.tents = int(tents or 1)
        self.booking_category_id = int(
            DEFAULT_BOOKING_CATEGORY
            if booking_category_id in (None, "")
            else booking_category_id
        )
        self.equipment_id = self._validate_equipment(
            equipment_id, self._recreation_area_id
        )
        self.campgrounds = self._get_searchable_campgrounds()

    @classmethod
    def _validate_rec_area(cls, recreation_area: int) -> int:
        if recreation_area in [(), [], None]:
            logger.error("At least one --rec-area must be provided")
            sys.exit(1)
        if is_list_like(recreation_area) is True and len(recreation_area) > 1:
            logger.error(
                "Going To Camp only allows a single recreation area to be searched at a time"
            )
            sys.exit(1)
        return int(make_list(recreation_area)[0])

    @classmethod
    def _validate_equipment(cls, equipment_id: Optional[int], rec_area: int):
        if not equipment_id:
            return

        try:
            return int(equipment_id)
        except ValueError:
            logger.error(
                "Invalid equipment ID. Use the follwoing to get list of "
                "equipment types: "
                f"`spotsnagger equipment-types --provider goingtocamp --rec-area {rec_area}`"
            )
            sys.exit(1)

    def get_all_campsites(self) -> List[AvailableCampsite]:
        """
        Search for all campsites matching search criteria.

        Because Going To Camp has no efficient way of filtering
        campsites for multiple campgrounds, this function is limited to listening
        all campsites _within_ a cammpground. Iterating through all sites for
        all campgrounds would likely lead to abuse complaints.

        Returns
        -------
        List[AvailableCampsite]
        """
        available_sites = []
        for search_window in self.search_window:
            current_start_date = search_window.get_current_start_date()
            for i, campground in enumerate(self.campgrounds, 1):
                logger.info(
                    f"Searching {campground.facility_name} ({i} of "
                    f"{len(self.campgrounds)}) from {current_start_date} "
                    f"to {search_window.end_date}"
                )
                sites = self.campsite_finder.list_site_availability(
                    campground=campground,
                    start_date=current_start_date,
                    end_date=search_window.end_date,
                    equipment_type_id=self.equipment_id,
                    booking_category_id=self.booking_category_id,
                    party_size=self.party_size,
                    tents=self.tents,
                )
                for site in sites:
                    site_details = self.campsite_finder.get_site_details(
                        self._recreation_area_id,
                        site.resource_id,
                        campground.facility_id,
                    )
                    nights = (search_window.end_date - current_start_date).days
                    start_dt = datetime.combine(current_start_date, time.min)
                    end_dt = datetime.combine(search_window.end_date, time.min)
                    (
                        rec_area_domain_name,
                        rec_area,
                    ) = self.campsite_finder.rec_area_lookup(
                        rec_area_id=self._recreation_area_id
                    )
                    booking_url = self.campsite_finder.get_reservation_link(
                        rec_area_domain_name,
                        resource_location_id=campground.facility_id,
                        map_id=site.map_id,
                        equipment_id=self.campsite_finder.get_equipment_category_id(
                            self._recreation_area_id, self.booking_category_id
                        ),
                        sub_equipment_id=self.equipment_id,
                        party_size=self.party_size,
                        start_date=current_start_date,
                        end_date=search_window.end_date,
                        booking_category_id=self.booking_category_id,
                    )

                    # Some rec areas have zero-capacity sites, which should not
                    # be viable for camping. Skip all zero-capacity sites.
                    # A null minCapacity just means no minimum (e.g. Parks Canada)
                    if not site_details["maxCapacity"]:
                        continue
                    # the availability API ignores partySize, so filter here
                    if not (
                        (site_details["minCapacity"] or 1)
                        <= self.party_size
                        <= site_details["maxCapacity"]
                    ):
                        continue

                    available_sites.append(
                        AvailableCampsite(
                            campsite_id=site_details["resourceId"],
                            campsite_site_name=site_details["localizedValues"][0][
                                "name"
                            ],
                            booking_date=start_dt,
                            booking_end_date=end_dt,
                            booking_nights=nights,
                            campsite_loop_name="Unknown",
                            campsite_type=site_details["site_attributes"].get(
                                "Service Type", "Unknown"
                            ),
                            campsite_occupancy=(
                                site_details["minCapacity"] or 1,
                                site_details["maxCapacity"],
                            ),
                            campsite_use_type="N/A",
                            availability_status="Available",
                            recreation_area=rec_area.recreation_area,
                            recreation_area_id=self._recreation_area_id,
                            facility_name=campground.facility_name,
                            facility_id=campground.facility_id,
                            booking_url=booking_url,
                        )
                    )

        return available_sites

    def _get_searchable_campgrounds(self) -> List[CampgroundFacility]:
        """
        Return a List of Campgrounds to search

        Returns
        -------
        searchable_campgrounds: List[CampgroundFacility]
            List of searchable campgrounds
        """
        if not self._recreation_area_id:
            logger.error(
                "You must provide a Recreation Area to search campsites with this provider"
            )
            sys.exit(1)

        if self.campsites not in [(), [], None]:
            self.campsites = [int(campsite_id) for campsite_id in self.campsites]
            return self._get_campgrounds_by_campsite_id()

        return self._get_campgrounds_by_recreation_area_id()

    def _get_campgrounds_by_recreation_area_id(self) -> List[CampgroundFacility]:
        """
        Return a List of Campgrounds to search when provided with Recreation Area IDs

        Returns
        -------
        campgrounds: List[CampgroundFacility]
        """
        if self._campgrounds not in [(), [], None]:
            return self.campsite_finder.find_campgrounds(
                rec_area_id=self._recreation_area_id,
                campground_id=self._campgrounds,
                booking_category_id=self.booking_category_id,
            )

        return self.campsite_finder.find_campgrounds(
            rec_area_id=self._recreation_area_id,
            booking_category_id=self.booking_category_id,
        )

    def list_campsite_units(self) -> Any:
        """
        List Campsite Units

        Returns
        -------
        Any
        """
        raise NotImplementedError
