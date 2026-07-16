"""Trend detection module: Mann-Kendall test, change point detection, periodicity detection."""

import math


def mann_kendall(values):
    """Simplified Mann-Kendall trend test.

    values: time series as a list of numbers.
    Returns a dict with S (statistic), trend ('increasing'/'decreasing'/'no_trend'),
    and is_significant (bool at 95% confidence).
    """
    n = len(values)
    if n < 4:
        return {"S": 0, "trend": "no_trend", "is_significant": False}

    # Calculate S statistic
    S = 0
    for i in range(n):
        for j in range(i + 1, n):
            if values[j] > values[i]:
                S += 1
            elif values[j] < values[i]:
                S -= 1

    # Determine trend direction
    if S > 0:
        trend = "increasing"
    elif S < 0:
        trend = "decreasing"
    else:
        trend = "no_trend"

    # Significance at 95% confidence
    variance = n * (n - 1) * (2 * n + 5) / 18
    critical = 1.96 * math.sqrt(variance)
    significant = abs(S) > critical

    return {"S": S, "trend": trend, "is_significant": significant}


def change_point_detection(values, threshold=None):
    """Detect change points where the mean shifts significantly.

    values: time series as a list of numbers.
    threshold: minimum absolute difference in means to count as a change point.
               If None, defaults to 0.3 * standard_deviation of the series.
    Returns a list of dicts with index, left_mean, right_mean, diff.
    """
    n = len(values)
    if n < 10:
        return []

    # Compute standard deviation
    mean_val = sum(values) / n
    variance = sum((v - mean_val) ** 2 for v in values) / (n - 1)
    std = math.sqrt(variance)

    if threshold is None:
        threshold = std * 0.3

    change_points = []

    for i in range(1, n - 1):
        left_mean = sum(values[:i]) / i
        right_mean = sum(values[i:]) / (n - i)
        diff = abs(right_mean - left_mean)

        if diff > threshold:
            change_points.append({
                "index": i,
                "left_mean": round(left_mean, 4),
                "right_mean": round(right_mean, 4),
                "diff": round(diff, 4),
            })

    # Merge nearby change points (within 5 indices)
    filtered = []
    for cp in change_points:
        if not filtered or cp["index"] - filtered[-1]["index"] > 5:
            filtered.append(cp)

    return filtered


def periodicity_detection(values, max_lag=None):
    """Detect periodicity using the autocorrelation function (ACF).

    values: time series as a list of numbers.
    max_lag: maximum lag to check. Defaults to len(values) // 3.
    Returns a dict with has_periodicity (bool), period (int or None),
    and acf_values (list of (lag, acf) tuples).
    """
    n = len(values)
    if n < 6:
        return {"has_periodicity": False, "period": None, "acf_values": []}

    if max_lag is None:
        max_lag = n // 3

    if max_lag < 1:
        return {"has_periodicity": False, "period": None, "acf_values": []}

    mean_val = sum(values) / n
    variance = sum((v - mean_val) ** 2 for v in values) / n

    if variance == 0:
        return {"has_periodicity": False, "period": None, "acf_values": []}

    acf_values = []
    for lag in range(1, max_lag + 1):
        cov = sum(
            (values[i] - mean_val) * (values[i - lag] - mean_val)
            for i in range(lag, n)
        ) / n
        acf = cov / variance
        acf_values.append((lag, round(acf, 4)))

    # Find peaks where ACF > 0.3 and is a local maximum
    peaks = []
    for i in range(1, len(acf_values) - 1):
        if (
            acf_values[i][1] > acf_values[i - 1][1]
            and acf_values[i][1] > acf_values[i + 1][1]
            and acf_values[i][1] > 0.3
        ):
            peaks.append(acf_values[i])

    if not peaks:
        return {"has_periodicity": False, "period": None, "acf_values": acf_values}

    best_peak = max(peaks, key=lambda x: x[1])
    return {
        "has_periodicity": True,
        "period": best_peak[0],
        "acf_values": acf_values,
    }
