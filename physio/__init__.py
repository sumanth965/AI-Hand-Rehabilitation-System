"""
Zero-Keyboard AI Physiotherapy System — physio package.
Re-exports key classes and the main() entry point.
"""

from physio.game import PhysioSystem, main
from physio.models import GameState, AgeGroup, HandData
from physio.constants import WINDOW_WIDTH, WINDOW_HEIGHT

__all__ = [
    "PhysioSystem",
    "main",
    "GameState",
    "AgeGroup",
    "HandData",
    "WINDOW_WIDTH",
    "WINDOW_HEIGHT",
]
