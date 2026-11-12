"""
Going to Camp Web Searching Utilities
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from fake_useragent import UserAgent
from pydantic import ValidationError

from spotsnagger.containers import AvailableResource, CampgroundFacility, RecreationArea
from spotsnagger.containers.base_container import GoingToCampEquipment
from spotsnagger.containers.gtc_api_responses import ResourceLocation
from spotsnagger.providers.base_provider import BaseProvider, ProviderSearchError
from spotsnagger.providers.going_to_camp.rec_areas import RECREATION_AREAS
from spotsnagger.utils import make_list
from spotsnagger.utils.logging_utils import log_sorted_response

logger = logging.getLogger(__name__)

# "Campsite" (frontcountry) booking category; the default on every GoingToCamp site
DEFAULT_BOOKING_CATEGORY = 0

ENDPOINTS = {
    "CAMP_DETAILS": "https://{}/api/maps",
    "DAILY_AVAILABILITY": "https://{}/api/availability/resourcedailyavailability",
    "LIST_CAMPGROUNDS": "https://{}/api/resourceLocation",
    "LIST_EQUIPMENT": "https://{}/api/equipment",
    "LIST_RESOURCE_CATEGORY": "https://{}/api/resourcecategory",
    "LIST_RESOURCE_STATUS": "https://{}/api/availability/resourcestatus",
    "MAPDATA": "https://{}/api/availability/map",
    "SITE_DETAILS": "https://{}/api/resourcelocation/resources",
    "ATTRIBUTE_DETAILS": "https://{}/api/attribute/filterable",
    "LIST_BOOKING_CATEGORIES": "https://{}/api/bookingcategories",
}


class GoingToCamp(BaseProvider):
    """
    Going To Camp API provider
    """

    @classmethod
    def find_recreation_areas(
        cls, search_string: Optional[str] = None, **kwargs
    ) -> List[RecreationArea]:
        """
        Find Matching Recreation Areas based on search string

        Parameters
        ----------
        search_string: Optional[str]
            Search Keyword(s)

        Returns
        -------
        filtered_responses: List[RecreationArea]
            Array of Matching Recreation Areas
        """
        if search_string is not None:
            logger.info(f'Searching for Recreation Areas matching: "{search_string}"')

        if not search_string or search_string == "":
            rec_areas = RECREATION_AREAS.values()
            log_sorted_response(rec_areas)
            return rec_areas

        rec_areas = []
        for _, rec_area in RECREATION_AREAS.items():
            if (
                search_string.lower() in rec_area.recreation_area.lower()
                or search_string.lower() in rec_area.recreation_area_location.lower()
            ):
                rec_areas.append(rec_area)

        log_sorted_response(rec_areas)

        return rec_areas

    def rec_area_lookup(self, rec_area_id: int) -> Tuple[str, RecreationArea]:
        """
        Lookup a recreation area by ID

        Parameters
        ----------
        rec_area_id: int
            The recreation area ID to lookup

        Returns
        -------
        domain_name, rec_ara: Tuple[str, RecreationArea]
            The rec area's domain name and the recreation area object
        """
        for domain_name, rec_area in RECREATION_AREAS.items():
            if str(rec_area.recreation_area_id) == str(rec_area_id):
                return domain_name, rec_area

    def find_campgrounds(
        self,
        search_string: Optional[str] = None,
        rec_area_id: Optional[List[int]] = None,
        campground_id: Optional[List[int]] = None,
        campsite_id: Optional[List[int]] = None,
        booking_category_id: int = DEFAULT_BOOKING_CATEGORY,
        **kwargs,
    ) -> List[CampgroundFacility]:
        """
        Find Campgrounds Given a Set of Search Criteria

        Parameters
        ----------
        search_string: Optional[str]
            Search Keyword(s)
        rec_area_id: Optional[List[int]]
            Recreation Area ID by which to filter
        campground_id: Optional[List[int]]
            ID of the Campground
        booking_category_id: int
            Reservation service (Campsite, Backcountry, Roofed, ...), see
            `list_booking_categories`

        Returns
        -------
        facilities: List[CampgroundFacility]
            Array of Matching Campgrounds
        """
        if rec_area_id in (None, [], ()):
            logger.error(
                "This provider requires --rec-area to be specified when seaching for campsites"
            )
            sys.exit(1)

        return self.find_facilities_per_recreation_area(
            rec_area_id=rec_area_id,
            campground_id=campground_id,
            search_string=search_string,
            booking_category_id=booking_category_id,
        )

    def list_booking_categories(
        self, rec_area_id: int, log: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List the reservation services (booking categories) a recreation area offers

        e.g. Campsite (frontcountry), Backcountry, Roofed Accommodation, Group.
        IDs and the resource types they cover differ per recreation area.

        Parameters
        ----------
        rec_area_id: int
            The ID of the recreation area
        log: bool
            Log the categories

        Returns
        -------
        List[Dict[str, Any]]
            Raw `/api/bookingcategories` entries that are enabled
        """
        if not hasattr(self, "_booking_categories"):
            self._booking_categories = {}
        rec_area_id = int(rec_area_id)
        if rec_area_id not in self._booking_categories:
            self._booking_categories[rec_area_id] = [
                category
                for category in self._api_request(
                    rec_area_id, "LIST_BOOKING_CATEGORIES"
                )
                if not category.get("isDisabled")
            ]
        categories = self._booking_categories[rec_area_id]
        if log:
            for category in sorted(categories, key=lambda c: c["bookingCategoryId"]):
                logger.info(
                    f"{category['bookingCategoryId']}: {booking_category_name(category)}"
                )
        return categories

    def get_booking_category(
        self, rec_area_id: int, booking_category_id: int
    ) -> Dict[str, Any]:
        """
        Look up one booking category of a recreation area, exiting if it doesn't exist
        """
        for category in self.list_booking_categories(rec_area_id):
            if str(category["bookingCategoryId"]) == str(booking_category_id):
                return category
        logger.error(
            f"Booking category '{booking_category_id}' does not exist for this "
            "recreation area. List them with "
            f"`spotsnagger booking-categories --rec-area {rec_area_id}`"
        )
        sys.exit(1)

    def get_equipment_category_id(
        self, rec_area_id: int, booking_category_id: int
    ) -> Optional[int]:
        """
        Equipment category a booking category books with (None for e.g. roofed / day use)
        """
        equipment = self.get_booking_category(rec_area_id, booking_category_id)[
            "allowedEquipmentCategories"
        ]
        return equipment[0]["equipmentCategoryId"] if equipment else None

    def _get_attr_val(self, attribute, attribute_detail) -> any:
        for attr_value in attribute.get("values", []):
            for attribute_enum_detail in attribute_detail.get("values"):
                if attribute_enum_detail["enumValue"] == attr_value:
                    return _fetch_nested_key(
                        attribute_enum_detail, "localizedValues", 0, "displayName"
                    )

    def get_site_details(
        self, rec_area_id: int, resource_id: int, resource_location_id: int
    ):
        """
        Get the details about a site in a recreation area

        Parameters
        ----------
        rec_area_id: int
            Recreation Area ID by which to filter
        resource_id: int
        resource_location_id: int
            Campground (resource location) the site belongs to

        Returns
        -------
        details: Dict[str, str]
            The details about the site
        """
        if not hasattr(self, "_attribute_details"):
            self._attribute_details = self._api_request(
                rec_area_id, "ATTRIBUTE_DETAILS"
            )
        attribute_details = self._attribute_details

        # /api/resource/details was removed; fetch all sites per campground once
        if not hasattr(self, "_location_resources"):
            self._location_resources = {}
        if resource_location_id not in self._location_resources:
            self._location_resources[resource_location_id] = self._api_request(
                rec_area_id,
                "SITE_DETAILS",
                {"resourceLocationId": resource_location_id},
            )
        site_details = self._location_resources[resource_location_id][str(resource_id)]
        site_attributes = {}
        for attribute in site_details["definedAttributes"]:
            # /attribute/filterable omits non-filterable attributes sites can carry
            attribute_detail = attribute_details.get(
                f"{attribute['attributeDefinitionId']}"
            )
            if attribute_detail is None:
                continue
            attribute_name = _fetch_nested_key(
                attribute_detail, "localizedValues", 0, "displayName"
            )
            attribute_value = attribute.get("value")
            attribute_values = []
            # Attribute a multi-value enum
            if not attribute_value:
                attr_value = self._get_attr_val(attribute, attribute_detail)
                if not attr_value:
                    continue
                attribute_values.append(attr_value)
            else:
                attribute_values.append(f"{attribute_value}")

            site_attributes[attribute_name] = ",".join(attribute_values)
        site_details["site_attributes"] = site_attributes

        return site_details

    def get_reservation_link(
        self,
        rec_area_domain_name,
        resource_location_id,
        map_id,
        equipment_id,
        sub_equipment_id,
        party_size,
        start_date,
        end_date,
        booking_category_id=DEFAULT_BOOKING_CATEGORY,
    ):
        """
        Generate a URL which a site can be booked

        Returns
        -------
        url: str
            The reservation link URL

        """
        if not sub_equipment_id:
            sub_equipment_id = ""
        if equipment_id is None:
            equipment_id = ""

        return (
            "https://%s/create-booking/results?mapId=%s"
            "&bookingCategoryId=%s"
            "&startDate=%s"
            "&endDate=%s"
            "&isReserving=true"
            "&equipmentId=%s"
            "&subEquipmentId=%s"
            "&partySize=%s"
            "&resourceLocationId=%s"
            % (
                rec_area_domain_name,
                map_id,
                booking_category_id,
                start_date.isoformat(),
                end_date.isoformat(),
                equipment_id,
                sub_equipment_id,
                party_size,
                resource_location_id,
            )
        )

    def find_facilities_per_recreation_area(
        self,
        rec_area_id: Optional[Union[List[int], int]] = None,
        campground_id: Optional[Union[List[int], int]] = None,
        search_string: Optional[str] = None,
        booking_category_id: int = DEFAULT_BOOKING_CATEGORY,
        **kwargs,
    ) -> List[CampgroundFacility]:
        """
        Find Matching Campsites by Recreation Area

        Parameters
        ----------
        rec_area_id: Optional[Union[List[int], int]]
            Recreation Area ID
        campground_id: Optional[Union[List[int], int]]
            Campground IDs
        search_string: Optional[str]
            A string to search for in the facility name
        booking_category_id: int
            Only return campgrounds offering this reservation service

        Returns
        -------
        campgrounds: List[CampgroundFacility]
            Array of Matching Campsites
        """
        rec_area_id = make_list(rec_area_id, coerce=int)[0]
        logger.info(
            f"Retrieving Facility Information for Recreation Area ID: `{rec_area_id}`."
        )

        rec_area = None
        for _, ra in RECREATION_AREAS.items():
            if str(ra.recreation_area_id) == str(rec_area_id):
                rec_area = ra
        if not rec_area:
            logger.error(f"Recreation area '{rec_area_id}' does not exist.")
            sys.exit(1)

        self.campground_details = {}
        api_response = self._api_request(rec_area_id, "LIST_CAMPGROUNDS")

        allowed_resource_categories = self.get_booking_category(
            rec_area_id, booking_category_id
        )["allowedResourceCategoryIds"]
        filtered_facilities = self._filter_facilities_responses(
            rec_area_id,
            facilities=api_response,
            allowed_resource_categories=allowed_resource_categories,
        )

        campgrounds = []
        self._load_campground_details(rec_area_id)

        # If a search string is provided, make sure every facility name contains
        # the search string
        if search_string and search_string not in [[], (), ""]:
            filtered_facilities = [
                f
                for f in filtered_facilities
                if search_string.lower() in f.resource_location_name.lower()
            ]

        for facility in filtered_facilities:
            _, campground_facility = self._process_facilities_responses(
                rec_area, facility=facility
            )
            if not campground_facility:
                continue
            if not campground_id:
                campgrounds.append(campground_facility)
            campground_strings = make_list(campground_id, coerce=str)
            if (
                campground_id
                and str(campground_facility.facility_id) in campground_strings
            ):
                campgrounds.append(campground_facility)
        logger.info(f"{len(campgrounds)} Matching Campgrounds Found")
        log_sorted_response(response_array=campgrounds)
        return campgrounds

    def _load_campground_details(self, rec_area_id: int) -> None:
        """
        Fetch campground (map) details for all facilities into `campground_details`
        """
        for camp_details in self._api_request(rec_area_id, "CAMP_DETAILS"):
            self.campground_details[camp_details["resourceLocationId"]] = camp_details
            # Some sites (e.g. Parks Canada) only link locations to maps via mapLinks
            for link in camp_details.get("mapLinks") or []:
                if link.get("resourceLocationId") is not None:
                    self.campground_details.setdefault(
                        link["resourceLocationId"], {"mapId": link["childMapId"]}
                    )

    def _hostname_for(self, recreation_area_id: int) -> str:
        for hostname, recreation_area in RECREATION_AREAS.items():
            if str(recreation_area.recreation_area_id) == str(recreation_area_id):
                return hostname
        return None

    def _api_request(
        self,
        rec_area_id: int,
        endpoint_name: str,
        params: Optional[Dict[str, str]] = None,
    ) -> str:
        if params is None:
            params = {}

        hostname = self._hostname_for(rec_area_id)
        endpoint = ENDPOINTS.get(endpoint_name)
        url = None
        if endpoint:
            url = endpoint.format(hostname)
        headers = {
            "User-Agent": UserAgent(browsers=["chrome"]).random,
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = self.session.get(url=url, headers=headers, params=params, timeout=30)
        if response.ok is False:
            error_message = f"Receiving bad data from GoingToCamp API: status_code: {response.status_code}: {response.text}"
            logger.error(error_message)
            raise ConnectionError(error_message)

        return json.loads(response.content)

    def _filter_facilities_responses(
        self,
        rec_area_id: int,
        facilities: List[Dict[str, Any]],
        allowed_resource_categories: List[int],
    ) -> List[ResourceLocation]:
        """
        Filter Facilities to Actual Reservable Campsites

        Parameters
        ----------
        rec_area_id: int
            Recreation Area ID
        facilities: List[Dict[str, Any]]
            List of facilities
        allowed_resource_categories: List[int]
            Resource categories of the booking category being searched

        Returns
        -------
        List[ResourceLocation]
        """
        filtered_facilities = []
        for facil in facilities:
            try:
                location_name = _fetch_nested_key(
                    facil, "localizedValues", 0, "fullName"
                )
                park_alerts = _fetch_nested_key(
                    facil, "park_alerts", "en-US", 0, "messageTitle"
                )
                if not park_alerts:
                    park_alerts = _fetch_nested_key(
                        facil, "park_alerts", "en-CA", 0, "messageTitle"
                    )

                region_name = _fetch_nested_key(facil, "region")

                facility = ResourceLocation(
                    id=None,
                    region_name=region_name if region_name else "",
                    park_alerts=park_alerts,
                    rec_area_id=rec_area_id,
                    resource_categories=facil.get("resourceCategoryIds"),
                    resource_location_id=facil.get("resourceLocationId"),
                    resource_location_name=location_name,
                )
            except ValidationError as ve:
                logger.error("That doesn't look like a valid Campground Facility")
                logger.error(facil)
                raise ProviderSearchError(
                    "Invalid Campground Facility Returned"
                ) from ve

            if not facility.resource_categories:
                continue

            # Resource category IDs differ per site; match the booking category's
            if set(facility.resource_categories) & set(allowed_resource_categories):
                filtered_facilities.append(facility)

        return filtered_facilities

    def _process_facilities_responses(
        self, rec_area: RecreationArea, facility: ResourceLocation
    ) -> Tuple[dict, Optional[CampgroundFacility]]:
        """
        Process Facilities Responses to be More Usable

        Parameters
        ----------
        facility: dict

        Returns
        -------
        Tuple[dict, CampgroundFacility]
        """
        # Some facilities (e.g. Parks Canada) are listed but have no camp details
        if facility.resource_location_id not in self.campground_details:
            return facility, None
        facility.id = _fetch_nested_key(
            self.campground_details, facility.resource_location_id, "mapId"
        )
        if facility.region_name:
            formatted_recreation_area = (
                f"{rec_area.recreation_area}, {facility.region_name}"
            )
        else:
            formatted_recreation_area = f"{rec_area.recreation_area}"

        campground_facility = CampgroundFacility(
            facility_name=facility.resource_location_name,
            recreation_area=formatted_recreation_area,
            facility_id=facility.resource_location_id,
            recreation_area_id=facility.rec_area_id,
            map_id=facility.id,
        )
        return facility, campground_facility

    def _find_matching_resources(self, rec_area_id: int, search_filter: Dict[str, any]):
        results = self._api_request(rec_area_id, "MAPDATA", search_filter)
        availability_details = {
            search_filter["mapId"]: results["resourceAvailabilities"]
        }

        return availability_details, list(results["mapLinkAvailabilities"].keys())

    def list_equipment_types(self, rec_area_id: int) -> Dict[str, int]:
        """
        List equipment types available for a recreation area

        Params
        ------
        rec_area_id: int
            The ID of the recreation area

        Returns
        -------
        types: List[GoingToCampEquipment]
            A list of equipment types available to this rec area
        """
        results = self._api_request(rec_area_id, "LIST_EQUIPMENT")

        equipment_types = []
        # Only allow equipment from non-group equipment category (the 0th
        # element in results)
        for sub_category in results[0]["subEquipmentCategories"]:
            equipment_name = _fetch_nested_key(
                sub_category, "localizedValues", 0, "name"
            )
            equipment_id = sub_category["subEquipmentCategoryId"]
            equipment_types.append(
                GoingToCampEquipment(
                    equipment_name=equipment_name, equipment_type_id=equipment_id
                )
            )

        log_sorted_response(response_array=equipment_types)
        return equipment_types

    def list_site_availability(
        self,
        campground: CampgroundFacility,
        start_date: datetime.date,
        end_date: datetime.date,
        equipment_type_id: Optional[str],
        booking_category_id: int = DEFAULT_BOOKING_CATEGORY,
        party_size: int = 1,
        tents: int = 1,
    ) -> List[AvailableResource]:
        """
        Retrieve the Availability for all Sites in a Camp Area

        Sites are filtered on the provided date range and compatible
        equipment.

        Returns
        -------
        available_sites: List[AvailableResource]
            The list of available sites
        """
        search_filter = {
            "mapId": campground.map_id,
            "resourceLocationId": campground.facility_id,
            "bookingCategoryId": booking_category_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "isReserving": True,
            "getDailyAvailability": False,
            "partySize": party_size,
            "numEquipment": tents,
            "filterData": [],
        }
        equipment_category_id = self.get_equipment_category_id(
            campground.recreation_area_id, booking_category_id
        )
        if equipment_category_id is not None:
            search_filter["equipmentCategoryId"] = equipment_category_id
        if equipment_type_id:
            search_filter["subEquipmentCategoryId"] = equipment_type_id

        resources, additional_resources = self._find_matching_resources(
            campground.recreation_area_id, search_filter
        )

        # Resources are often deeply nested; fetch nested resources
        for map_id in additional_resources:
            search_filter["mapId"] = map_id
            avail, _ = self._find_matching_resources(
                campground.recreation_area_id, search_filter
            )
            resources.update(avail)

        availabilities = []
        for map_id, resource_details in resources.items():
            for resource_id, availability_details in resource_details.items():
                if availability_details[0]["availability"] == 0:
                    ar = AvailableResource(resource_id=resource_id, map_id=map_id)
                    availabilities.append(ar)

        return availabilities


def booking_category_name(category: Dict[str, Any]) -> str:
    """
    Display name of a raw booking category
    """
    name = _fetch_nested_key(category, "localizedValues", 0, "name")
    return (name or f"Booking Category {category['bookingCategoryId']}").strip()


def _fetch_nested_key(obj: Union[dict, list, object], *keys: str) -> Any:
    """
    Fetch nested keys from dictionaries/lists if the keys exist

    Example
    -------
        mydict = {
            'foo': {
                'bar': 'baz'
            }
        }
        val = _fetch_nested_key(mydict, 'foo', 'bar')
        print(f"Value: {val}")
        Prints: Value: baz
    """
    if (
        not isinstance(obj, dict)
        and not isinstance(obj, list)
        and not isinstance(obj, object)
    ):
        raise AttributeError(
            "`obj` must be of type `dict`, `list`, or `object`, but is not"
        )
    if len(keys) == 0:
        raise AttributeError(
            "At least one key must be specified in `keys:`. None were provided"
        )

    _element = obj
    for key in keys:
        try:
            _element = _element[key]
            if not _element:
                _element = getattr(_element, key)
        except (KeyError, TypeError, AttributeError):
            return None

    return _element
