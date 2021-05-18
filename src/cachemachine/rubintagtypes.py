"""Enum specifying different tag types for Rubin Science Platform Lab images,
and an Exception for attempted comparison between incomparable types.
"""
from enum import Enum, auto


class RubinTagType(Enum):
    DAILY = auto()
    WEEKLY = auto()
    RELEASE = auto()
    RELEASE_CANDIDATE = auto()
    EXPERIMENTAL = auto()
    ALIAS = auto()
    UNKNOWN = auto()


class IncomparableImageTypesError(Exception):
    pass
