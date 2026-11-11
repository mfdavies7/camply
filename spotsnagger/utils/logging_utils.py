"""
Logging Utilities for Pushover Variables
"""

import logging
from typing import Any, List, Union

from spotsnagger.containers import CampgroundFacility, RecreationArea
from spotsnagger.containers.base_container import GoingToCampEquipment

logger = logging.getLogger(__name__)


def format_log_string(response: Union[CampgroundFacility, RecreationArea, str]) -> str:
    """
    Generate a formatted string for logging

    Parameters
    ----------
    response: Union[CampgroundFacility]

    Returns
    -------
    str
    """
    if isinstance(response, CampgroundFacility):
        if isinstance(response.facility_id, int):
            facil = f"#{response.facility_id}"
        else:
            facil = response.facility_id
        return (
            f"{response.recreation_area} (#{response.recreation_area_id}) - "
            f"{response.facility_name} ({facil})"
        )
    elif isinstance(response, RecreationArea):
        return (
            f"{response.recreation_area}, {response.recreation_area_location} "
            f"(#{response.recreation_area_id})"
        )
    elif isinstance(response, GoingToCampEquipment):
        return f"{response.equipment_name} (#{response.equipment_type_id})"
    elif isinstance(response, str):
        return response
    else:
        raise NotImplementedError


def log_sorted_response(response_array: List[Any]) -> None:
    """
    Log Some Statements in a Nice Sorted way

    Parameters
    ----------
    response_array: List[str]

    Returns
    -------
    None
    """
    log_array = [format_log_string(obj) for obj in response_array]
    sorted_logs = sorted(log_array)
    for log_response in sorted_logs:
        logger.info(log_response)


def log_spotsnagger(self: logging.Logger, message: str, *args, **kwargs) -> None:
    """
    Custom Logging Notification Level for Pushover Logging

    Between logging.ERROR and logging.CRITICAL (45)

    Parameters
    ----------
    self: logging.Logger
    message: str
        Message String
    args
    kwargs

    Returns
    -------
    None
    """
    notification_level = logging.INFO + 1
    logging.addLevelName(level=notification_level, levelName="SPOTSNAGGER")
    if self.isEnabledFor(level=notification_level):
        self._log(level=notification_level, msg=message, args=args, **kwargs)
