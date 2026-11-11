"""
providers __init__ file
"""

from typing import Union

from .aspira.aspira_provider import Aspira
from .base_provider import BaseProvider
from .going_to_camp.going_to_camp_provider import GoingToCamp

ProviderType = Union[GoingToCamp, Aspira]

__all__ = [
    "Aspira",
    "BaseProvider",
    "ProviderType",
    "GoingToCamp",
]
