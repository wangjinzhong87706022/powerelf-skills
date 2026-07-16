"""
MAD Anomaly Detection Module
=============================

Implements the Median Absolute Deviation (MAD) anomaly detection algorithm
used in the data-governance engine for water conservancy equipment monitoring.

Algorithms:
  - Modified Z-score based on MAD for robust outlier detection
  - Adaptive window sizing for sliding-window analysis
  - Change-rate detection for gradual drift anomalies
  - Composite judgment combining MAD and change-rate results

References:
  - Modified Z-score: 0.6745 * |value - median| / MAD
  - 0.6745 is the normal-distribution normalization factor (Phi^-1(3/4))
  - MAD = median(|Xi - median(X)|)
"""

import math

try:
    import numpy as np

    def _median(values):
        """Compute median using numpy."""
        return float(np.median(values))
except ImportError:
    def _median(values):
        """Compute median using pure Python (fallback)."""
        s = sorted(values)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        else:
            return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _adaptive_window(n):
    """Compute adaptive window size based on data length.

    Formula: windowSize = min(max(N * 0.15, 10), 50)

    For small datasets (N < 10), uses the full dataset as the window.
    """
    if n < 10:
        return n
    return int(min(max(n * 0.15, 10), 50))


def detect_anomalies(values, threshold=4.0, window_size=None):
    """Detect anomalies using MAD-based modified Z-score with sliding window.

    For each data point, a local window is used to compute the median and MAD.
    The modified Z-score is then compared against the threshold.

    Formula:
        MAD = median(|Xi - median(X)|)
        Modified Z-score = 0.6745 * |value - median| / MAD

    When MAD = 0 (all values in window are identical), any value differing
    from the median is flagged as an anomaly.

    Args:
        values: List of numeric values to analyze.
        threshold: Modified Z-score threshold for anomaly detection.
            Recommended values by metric type:
            - Water level (rz): 3.0
            - Rainfall (p): 5.0
            - Seepage pressure: 4.0 (default)
            - GNSS: 3.5
            - Flow: 4.0
        window_size: Sliding window size. If None, uses adaptive sizing:
            window = min(max(N * 0.15, 10), 50)

    Returns:
        List of dicts, one per input value, each containing:
        - index: Position in the input list
        - value: The original value
        - score: The modified Z-score (0.0 if MAD was 0)
        - is_anomaly: True if the value is an anomaly
    """
    n = len(values)
    if n == 0:
        return []

    if window_size is None:
        window_size = _adaptive_window(n)

    half_window = window_size // 2
    results = []

    for i in range(n):
        start = max(0, i - half_window)
        end = min(n, i + half_window + 1)
        window = values[start:end]

        med = _median(window)
        abs_deviations = [abs(x - med) for x in window]
        mad = _median(abs_deviations)

        if mad > 0:
            modified_z_score = 0.6745 * abs(values[i] - med) / mad
            is_anomaly = modified_z_score > threshold
        else:
            # MAD = 0: all values in window are the same.
            # Any deviation from the median is an anomaly.
            modified_z_score = 0.0
            is_anomaly = abs(values[i] - med) > 0

        results.append({
            "index": i,
            "value": values[i],
            "score": round(modified_z_score, 4),
            "is_anomaly": is_anomaly,
        })

    return results


def detect_change_rate(values, thresholds=None):
    """Detect anomalies based on consecutive value change rate.

    Formula:
        changeRate = |Xi - Xi-1| / |Xi-1|

    A point is flagged as suspicious when the change rate exceeds the
    configured threshold for that metric type.

    Args:
        values: List of numeric values to analyze.
        thresholds: Dict mapping metric type to change-rate threshold.
            Defaults:
            - water_level: 0.05 (5%)
            - rainfall: None (not applicable, can spike)
            - pressure: 0.03 (3%)
            - gnss: 0.02 (2%)
            - flow: 0.10 (10%)

    Returns:
        List of dicts, one per input value, each containing:
        - index: Position in the input list
        - value: The original value
        - change_rate: Computed change rate from previous value (0.0 for first)
        - is_suspicious: True if change rate exceeds the applied threshold
    """
    if thresholds is None:
        thresholds = {
            "water_level": 0.05,
            "rainfall": None,
            "pressure": 0.03,
            "gnss": 0.02,
            "flow": 0.10,
        }

    # Use the first non-None threshold as the active threshold.
    active_threshold = None
    for v in thresholds.values():
        if v is not None:
            active_threshold = v
            break

    n = len(values)
    results = []

    for i in range(n):
        if i == 0 or values[i - 1] == 0:
            change_rate = 0.0
        else:
            change_rate = abs(values[i] - values[i - 1]) / abs(values[i - 1])

        is_suspicious = False
        if active_threshold is not None and i > 0:
            is_suspicious = change_rate > active_threshold

        results.append({
            "index": i,
            "value": values[i],
            "change_rate": round(change_rate, 6),
            "is_suspicious": is_suspicious,
        })

    return results


def composite_judge(mad_results, change_rate_results):
    """Combine MAD anomaly detection and change-rate detection results.

    Composite judgment rules:
        - MAD anomaly AND change-rate suspicious -> high confidence anomaly
        - MAD anomaly AND change-rate normal     -> medium confidence anomaly
        - MAD normal AND change-rate suspicious   -> low confidence (needs review)
        - MAD normal AND change-rate normal        -> normal

    Args:
        mad_results: Output from detect_anomalies().
        change_rate_results: Output from detect_change_rate().

    Returns:
        List of dicts, one per input value, each containing:
        - index: Position in the input list
        - value: The original value
        - is_anomaly: True if any detection flagged this point
        - confidence: 'high', 'medium', 'low', or None
        - mad_score: The MAD modified Z-score
        - change_rate: The change rate
    """
    results = []

    for mad_r, cr_r in zip(mad_results, change_rate_results):
        is_mad_anomaly = mad_r["is_anomaly"]
        is_cr_suspicious = cr_r["is_suspicious"]

        if is_mad_anomaly and is_cr_suspicious:
            confidence = "high"
            is_anomaly = True
        elif is_mad_anomaly and not is_cr_suspicious:
            confidence = "medium"
            is_anomaly = True
        elif not is_mad_anomaly and is_cr_suspicious:
            confidence = "low"
            is_anomaly = True
        else:
            confidence = None
            is_anomaly = False

        results.append({
            "index": mad_r["index"],
            "value": mad_r["value"],
            "is_anomaly": is_anomaly,
            "confidence": confidence,
            "mad_score": mad_r["score"],
            "change_rate": cr_r["change_rate"],
        })

    return results
