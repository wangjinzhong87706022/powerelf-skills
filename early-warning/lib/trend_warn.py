"""Trend warning module.

Detects consecutive monotonic changes in time-series data
and evaluates whether the trend exceeds per-indicator thresholds.
"""

from decimal import Decimal


# Per-indicator parameters for trend detection
INDICATOR_PARAMS = {
    "water_level": {"min_consecutive": 3, "rate_threshold": Decimal("0.01")},
    "seepage":     {"min_consecutive": 4, "rate_threshold": Decimal("0.02")},
    "gnss":        {"min_consecutive": 5, "rate_threshold": Decimal("0.005")},
    "flow":        {"min_consecutive": 3, "rate_threshold": Decimal("0.15")},
}

# Fallback for unknown indicator types
DEFAULT_PARAMS = {"min_consecutive": 3, "rate_threshold": Decimal("0.01")}


def detect_consecutive_monotonic(values, min_consecutive=3):
    """Detect whether values form a consecutive monotonic sequence.

    Args:
        values: List of numeric values in chronological order.
        min_consecutive: Minimum number of consecutive periods required.

    Returns:
        dict with keys:
            is_trend (bool): True if a monotonic trend is detected.
            direction (str|None): 'rising', 'falling', or None.
            consecutive_count (int): Length of the monotonic run.
            change_rate (Decimal): Absolute rate of change relative to
                the first value (0 if first value is zero).
    """
    if len(values) < min_consecutive:
        return {
            "is_trend": False,
            "direction": None,
            "consecutive_count": 0,
            "change_rate": Decimal("0"),
        }

    dec_values = [Decimal(str(v)) for v in values]

    # Check monotonically rising
    rising = all(dec_values[i] > dec_values[i - 1] for i in range(1, len(dec_values)))
    # Check monotonically falling
    falling = all(dec_values[i] < dec_values[i - 1] for i in range(1, len(dec_values)))

    if not rising and not falling:
        return {
            "is_trend": False,
            "direction": None,
            "consecutive_count": 0,
            "change_rate": Decimal("0"),
        }

    direction = "rising" if rising else "falling"
    count = len(dec_values)
    change = abs(dec_values[-1] - dec_values[0])
    rate = change / abs(dec_values[0]) if dec_values[0] != 0 else Decimal("0")

    return {
        "is_trend": True,
        "direction": direction,
        "consecutive_count": count,
        "change_rate": rate,
    }


def check_trend_warning(values, indicator_type):
    """Check whether a trend warning should be triggered for a given indicator.

    Uses per-indicator parameters for minimum consecutive count and
    rate-of-change threshold.

    Args:
        values: List of numeric values in chronological order.
        indicator_type: One of 'water_level', 'seepage', 'gnss', 'flow'.
            Also accepts legacy keys 'rz' (mapped to water_level params).

    Returns:
        dict with keys:
            is_warning (bool): True if trend warning should trigger.
            direction (str|None): 'rising' or 'falling' or None.
            rate (Decimal): Observed rate of change.
            params_used (dict): The indicator parameters applied.
    """
    # Normalize legacy indicator names
    legacy_map = {"rz": "water_level"}
    normalized_type = legacy_map.get(indicator_type, indicator_type)

    params = INDICATOR_PARAMS.get(normalized_type, DEFAULT_PARAMS)

    result = detect_consecutive_monotonic(values, params["min_consecutive"])

    is_warning = (
        result["is_trend"]
        and result["change_rate"] >= params["rate_threshold"]
    )

    return {
        "is_warning": is_warning,
        "direction": result["direction"],
        "rate": result["change_rate"],
        "params_used": params,
    }
