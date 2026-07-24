"""Compatibility entry point that composes the focused screen modules."""

from .screen_parts import (
    CalibrationScreenMixin,
    HistoryScreenMixin,
    NavigationScreenMixin,
    PainScreenMixin,
    RegistrationScreenMixin,
    ResultsScreenMixin,
)


class ScreenMixin(
    RegistrationScreenMixin,
    NavigationScreenMixin,
    PainScreenMixin,
    HistoryScreenMixin,
    CalibrationScreenMixin,
    ResultsScreenMixin,
):
    """All screen capabilities retained under the original public API."""

