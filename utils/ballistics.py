"""Ballistic calculation utilities."""

import math
from typing import List


def calculate_es(velocities: List[float]) -> float:
    """Calculate Extreme Spread (max - min)."""
    if len(velocities) < 2:
        return 0.0
    return max(velocities) - min(velocities)


def calculate_sd(velocities: List[float]) -> float:
    """Calculate Standard Deviation."""
    if len(velocities) < 2:
        return 0.0
    n = len(velocities)
    mean = sum(velocities) / n
    variance = sum((v - mean) ** 2 for v in velocities) / (n - 1)
    return math.sqrt(variance)


def calculate_mean(velocities: List[float]) -> float:
    """Calculate mean velocity."""
    if not velocities:
        return 0.0
    return sum(velocities) / len(velocities)


def es_color(es: float) -> str:
    """Return color code based on ES value."""
    if es < 15:
        return "green"
    elif es <= 30:
        return "orange"
    else:
        return "red"


def charge_warning_level(charge_gr: float, max_charge: float) -> str:
    """Return warning level for charge relative to max.
    Returns: 'safe', 'caution', 'danger'
    """
    if max_charge <= 0:
        return "safe"
    ratio = charge_gr / max_charge
    if ratio > 1.0:
        return "danger"
    elif ratio > 0.95:
        return "caution"
    return "safe"
