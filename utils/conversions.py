"""Conversion utilities for reloading measurements."""

MM_PER_INCH = 25.4
THOU_PER_INCH = 1000


def mm_to_inch(mm: float) -> float:
    return mm / MM_PER_INCH


def inch_to_mm(inch: float) -> float:
    return inch * MM_PER_INCH


def mm_to_thou(mm: float) -> float:
    return mm_to_inch(mm) * THOU_PER_INCH


def thou_to_mm(thou: float) -> float:
    return inch_to_mm(thou / THOU_PER_INCH)


def fps_to_ms(fps: float) -> float:
    return fps * 0.3048


def ms_to_fps(ms: float) -> float:
    return ms / 0.3048


def mm_to_moa(mm: float, distance_m: float) -> float:
    """Convert group size in mm to MOA at a given distance in meters."""
    if distance_m <= 0:
        return 0.0
    # 1 MOA ≈ 29.089 mm at 100m
    return mm / (29.089 * distance_m / 100.0)


def moa_to_mm(moa: float, distance_m: float) -> float:
    if distance_m <= 0:
        return 0.0
    return moa * 29.089 * distance_m / 100.0


def calculate_jump_mm(cbto_lands_mm: float, cbto_mm: float) -> float:
    """Calculate jump = lands CBTO - loaded CBTO."""
    return cbto_lands_mm - cbto_mm


def calculate_jump_thou(cbto_lands_mm: float, cbto_mm: float) -> float:
    return mm_to_thou(calculate_jump_mm(cbto_lands_mm, cbto_mm))
