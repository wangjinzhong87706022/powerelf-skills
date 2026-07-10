"""
Missing Data Detection Module
===============================

Implements missing data detection algorithms for water conservancy
equipment monitoring. Detects gaps in time-series data based on
expected collection frequency, classifies severity of consecutive
missing periods, and identifies missing-data patterns.

Algorithms:
  - Expected-count comparison for gap detection
  - Consecutive missing period classification (INFO/WARNING/ERROR/CRITICAL)
  - Pattern recognition: periodic vs random missing
"""

import math


def detect_missing(expected_count, actual_count, collection_frequency_min):
    """Detect missing data periods by comparing expected vs actual counts.

    Formula:
        missing_periods = max(0, expected_count - actual_count)
        missing_rate = missing_periods / expected_count

    Args:
        expected_count: Number of data points expected based on the
            collection frequency and time range.
        actual_count: Number of data points actually collected.
        collection_frequency_min: Collection frequency in minutes
            (e.g., 60 for hourly collection).

    Returns:
        Dict containing:
        - missing_periods: Number of missing data periods (int).
        - missing_rate: Fraction of expected data that is missing (float, 0-1).
            Returns 0.0 if expected_count is 0.
    """
    if expected_count <= 0:
        return {"missing_periods": 0, "missing_rate": 0.0}

    missing_periods = max(0, expected_count - actual_count)
    missing_rate = missing_periods / expected_count

    return {
        "missing_periods": missing_periods,
        "missing_rate": round(missing_rate, 6),
    }


def classify_consecutive_missing(count):
    """Classify the severity of consecutive missing data periods.

    Classification rules:
        1-2 periods  -> 'INFO'      (brief gap, may be network hiccup)
        3-5 periods  -> 'WARNING'   (sustained gap, needs attention)
        6-10 periods -> 'ERROR'     (significant data loss)
        > 10 periods -> 'CRITICAL'  (prolonged outage, urgent action needed)

    Args:
        count: Number of consecutive missing data periods.

    Returns:
        Severity level string: 'INFO', 'WARNING', 'ERROR', or 'CRITICAL'.
    """
    if count <= 0:
        return "INFO"
    elif count <= 2:
        return "INFO"
    elif count <= 5:
        return "WARNING"
    elif count <= 10:
        return "ERROR"
    else:
        return "CRITICAL"


def detect_missing_pattern(missing_timestamps):
    """Identify whether missing data follows a periodic or random pattern.

    Analysis:
        - Computes intervals between consecutive missing timestamps.
        - If the coefficient of variation (CV = std/mean) of intervals is
          below 0.3, the pattern is classified as 'periodic' (consistent gaps,
          e.g., daily maintenance windows).
        - Otherwise, the pattern is classified as 'random' (e.g., network
          instability, intermittent device failures).

    Requires at least 3 timestamps to perform analysis; returns 'unknown'
    for fewer timestamps.

    Args:
        missing_timestamps: List of datetime objects (or any comparable
            objects supporting subtraction) representing when data went missing.
            Should be sorted chronologically.

    Returns:
        Pattern string: 'periodic', 'random', or 'unknown'.
    """
    if len(missing_timestamps) < 3:
        return "unknown"

    # Compute intervals between consecutive timestamps
    intervals = []
    for i in range(1, len(missing_timestamps)):
        delta = missing_timestamps[i] - missing_timestamps[i - 1]
        # Convert to minutes if timedelta, otherwise use numeric value
        if hasattr(delta, "total_seconds"):
            interval = delta.total_seconds() / 60.0
        else:
            interval = float(delta)
        intervals.append(interval)

    if not intervals:
        return "unknown"

    n = len(intervals)
    mean_interval = sum(intervals) / n

    if mean_interval == 0:
        return "periodic"  # All timestamps are identical

    variance = sum((x - mean_interval) ** 2 for x in intervals) / n
    std_interval = math.sqrt(variance)

    cv = std_interval / mean_interval

    if cv < 0.3:
        return "periodic"
    else:
        return "random"
