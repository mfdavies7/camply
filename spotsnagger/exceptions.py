"""
SpotSnagger: Common Exceptions
"""


class SpotSnaggerError(Exception):
    """
    Base SpotSnagger Error
    """


class SearchError(SpotSnaggerError):
    """
    Generic Search Error
    """


class CampsiteNotFoundError(SearchError):
    """
    Campsite not found Error
    """
