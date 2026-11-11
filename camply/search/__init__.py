"""
camply search __init__ file
"""

from typing import Dict, List, Type

from camply.search.base_search import BaseCampingSearch
from camply.search.search_aspira import SearchAspira
from camply.search.search_going_to_camp import SearchGoingToCamp

# Register Providers Here with their Search class
__search_providers__: List[Type[BaseCampingSearch]] = [
    SearchGoingToCamp,
    SearchAspira,
]

CAMPSITE_SEARCH_PROVIDER: Dict[str, Type[BaseCampingSearch]] = {
    provider.provider_class.__name__: provider for provider in __search_providers__
}
