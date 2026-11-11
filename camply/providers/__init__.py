"""
providers __init__ file
"""

from typing import Union

from .base_provider import BaseProvider
from .going_to_camp.going_to_camp_provider import GoingToCamp

ProviderType = Union[GoingToCamp]

__all__ = [
    "BaseProvider",
    "ProviderType",
    "GoingToCamp",
]
