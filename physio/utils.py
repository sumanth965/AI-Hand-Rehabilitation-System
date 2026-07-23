"""
Utility functions for the Zero-Keyboard AI Physiotherapy System.
"""

import math
import numpy as np
from typing import Tuple
from collections import deque


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation"""
    return a + (b - a) * t


def weighted_average(values: deque) -> float:
    """Calculate weighted average (recent values weighted more)"""
    if not values:
        return 0
    weights = np.linspace(0.5, 1.0, len(values))
    return np.average(list(values), weights=weights)


def recovery_category(score: float) -> str:
    if score <= 25:
        return "Poor"
    if score <= 50:
        return "Fair"
    if score <= 75:
        return "Good"
    return "Excellent"


def functional_recovery_score(
    rom: float,
    accuracy: float,
    pain_after: float,
    consistency: float,
    movement_smoothness: float,
) -> float:
    """Simple 0-100 clinical monitoring score; does not replace readiness logic."""
    score = (
        0.30 * max(0.0, min(1.0, rom / 90.0))
        + 0.25 * max(0.0, min(1.0, accuracy / 100.0))
        + 0.20 * max(0.0, min(1.0, (10.0 - pain_after) / 10.0))
        + 0.15 * max(0.0, min(1.0, consistency))
        + 0.10 * max(0.0, min(1.0, movement_smoothness))
    ) * 100.0
    return round(max(0.0, min(100.0, score)), 1)
