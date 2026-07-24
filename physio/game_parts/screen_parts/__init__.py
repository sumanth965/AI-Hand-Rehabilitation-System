"""Focused screen modules used by :class:`physio.game.PhysioSystem`."""

from .registration import RegistrationScreenMixin
from .navigation import NavigationScreenMixin
from .pain import PainScreenMixin
from .history import HistoryScreenMixin
from .calibration import CalibrationScreenMixin
from .results import ResultsScreenMixin

__all__ = [
    "RegistrationScreenMixin",
    "NavigationScreenMixin",
    "PainScreenMixin",
    "HistoryScreenMixin",
    "CalibrationScreenMixin",
    "ResultsScreenMixin",
]
