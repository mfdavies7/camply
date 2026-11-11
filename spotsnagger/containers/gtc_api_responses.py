"""
GoingToCamp provider containers
"""
from typing import List, Optional

from spotsnagger.containers.base_container import SpotSnaggerModel


class ResourceLocation(SpotSnaggerModel):
    """
    /api/maps
    """

    id: Optional[int]
    rec_area_id: int
    park_alerts: Optional[str]
    resource_categories: Optional[List[int]]
    resource_location_id: Optional[int]
    resource_location_name: str
    region_name: str
