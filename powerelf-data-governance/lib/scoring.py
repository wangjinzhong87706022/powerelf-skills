"""
Quality Scoring Module
=======================

Implements the multi-dimensional quality scoring system for equipment
data quality assessment. The total score is composed of four weighted
dimensions:

  - Data quality (35%):       missing ratio + anomaly ratio
  - Operational stability (10%): offline date ratio + anomaly date ratio
  - Fault frequency (40%):    offline count + anomaly count penalty
  - Data completeness (15%):  actual vs expected records

Additional utilities:
  - Time-decay weighting for historical metrics
  - Score trend analysis (improving / declining / stable)

All formulas are from the data-governance engine specification.
Pure Python, no external dependencies.
"""

import math


def compute_quality_score(missing_ratio, anomaly_ratio):
    """Compute the data quality dimension score (weight: 35%).

    Formula:
        missingScore = max(0, (0.3 - missingRatio) * 10/3) * 0.6
        anomalyScore = max(0, (0.3 - anomalyRatio) * 10/3) * 0.4
        qualityScore = (missingScore + anomalyScore) * 0.35 * 100

    When missing_ratio + anomaly_ratio >= 30%, the quality score is 0.
    Missing ratio has a higher sub-weight (0.6) than anomaly ratio (0.4)
    because missing data impacts usability more than occasional anomalies.

    Example:
        missing_ratio=0.05, anomaly_ratio=0.03
        missingScore = (0.3 - 0.05) * 10/3 * 0.6 = 0.500
        anomalyScore = (0.3 - 0.03) * 10/3 * 0.4 = 0.360
        qualityScore = (0.500 + 0.360) * 0.35 * 100 = 30.1

    Args:
        missing_ratio: Fraction of missing data points (0.0 to 1.0).
        anomaly_ratio: Fraction of anomalous data points (0.0 to 1.0).

    Returns:
        Quality dimension score (float, 0 to 35).
    """
    missing_score = max(0, (0.3 - missing_ratio) * 10 / 3) * 0.6
    anomaly_score = max(0, (0.3 - anomaly_ratio) * 10 / 3) * 0.4
    quality_score = (missing_score + anomaly_score) * 0.35 * 100
    return round(quality_score, 2)


def compute_stability_score(offline_date_ratio, anomaly_date_ratio):
    """Compute the operational stability dimension score (weight: 10%).

    Formula:
        stabilityScore = ((1 - offlineDateRatio) * 0.5
                        + (1 - anomalyDateRatio) * 0.5) * 0.1 * 100

    Both offline and anomaly date ratios are equally weighted (0.5 each).

    Example:
        offline_date_ratio=0.10, anomaly_date_ratio=0.05
        stabilityScore = (0.9 * 0.5 + 0.95 * 0.5) * 0.1 * 100 = 9.25

    Args:
        offline_date_ratio: Fraction of days with offline events (0.0 to 1.0).
        anomaly_date_ratio: Fraction of days with anomaly events (0.0 to 1.0).

    Returns:
        Stability dimension score (float, 0 to 10).
    """
    stability_score = (
        (1 - offline_date_ratio) * 0.5 + (1 - anomaly_date_ratio) * 0.5
    ) * 0.1 * 100
    return round(stability_score, 2)


def compute_fault_score(offline_count, anomaly_count):
    """Compute the fault frequency dimension score (weight: 40%).

    Formula:
        penalty = offlineCount * 5 + anomalyCount * 5
        if penalty > 100:
            faultScore = 0
        else:
            faultScore = (100 - penalty) * 0.4

    Each offline or anomaly event incurs a 5-point penalty.
    More than 20 total events (100/5) results in a zero score.

    Example:
        offline_count=3, anomaly_count=2
        penalty = 3*5 + 2*5 = 25
        faultScore = (100 - 25) * 0.4 = 30.0

    Args:
        offline_count: Number of offline events in the scoring period.
        anomaly_count: Number of anomaly events in the scoring period.

    Returns:
        Fault dimension score (float, 0 to 40).
    """
    penalty = offline_count * 5 + anomaly_count * 5
    if penalty > 100:
        fault_score = 0.0
    else:
        fault_score = (100 - penalty) * 0.4
    return round(fault_score, 2)


def compute_completeness_score(actual_records, expected_records):
    """Compute the data completeness dimension score (weight: 15%).

    Formula:
        completenessRatio = actualRecords / expectedRecords

        if ratio >= 0.95:  score = 15
        if ratio >= 0.80:  score = ratio * 15
        else:              score = ratio * 10  (penalty for < 80%)

    Example:
        actual_records=22, expected_records=24
        ratio = 22/24 = 0.917
        score = 0.917 * 15 = 13.75

    Args:
        actual_records: Number of records actually collected.
        expected_records: Number of records expected based on collection frequency.

    Returns:
        Completeness dimension score (float, 0 to 15).
    """
    if expected_records <= 0:
        return 0.0

    ratio = actual_records / expected_records

    if ratio >= 0.95:
        completeness_score = 15.0
    elif ratio >= 0.80:
        completeness_score = ratio * 15
    else:
        completeness_score = ratio * 10  # Heavier penalty below 80%

    return round(completeness_score, 2)


def compute_total_score(quality, stability, fault, completeness):
    """Compute the weighted total score from all four dimensions.

    Formula:
        total = quality + stability + fault + completeness

    The weights are already embedded in each dimension's score, so the
    total is a simple sum. The theoretical maximum is 100.

    Args:
        quality: Data quality score (0 to 35).
        stability: Operational stability score (0 to 10).
        fault: Fault frequency score (0 to 40).
        completeness: Data completeness score (0 to 15).

    Returns:
        Total score (float, 0 to 100).
    """
    return round(quality + stability + fault + completeness, 2)


def time_decay_weight(days_ago, lambda_param=0.05):
    """Compute a time-decay weight for historical data weighting.

    Formula:
        weight = exp(-lambda * days_ago)

    Decay curve (lambda=0.05):
        days_ago=0   -> weight=1.000
        days_ago=3   -> weight=0.861
        days_ago=7   -> weight=0.705
        days_ago=14  -> weight=0.497
        days_ago=30  -> weight=0.223

    Usage:
        weightedMetric = sum(metric[i] * weight(i)) / sum(weight(i))

    Args:
        days_ago: Number of days in the past (0 = today).
        lambda_param: Decay rate (default 0.05). Higher values cause
            faster decay.

    Returns:
        Weight value (float, 0.0 to 1.0).
    """
    return math.exp(-lambda_param * days_ago)


def compute_score_trend(current_score, previous_score):
    """Determine the score trend direction.

    Formula:
        change = current_score - previous_score

        if change > 5:   -> 'improving'
        if change < -5:  -> 'declining'
        else:             -> 'stable'

    Args:
        current_score: The current period's total score.
        previous_score: The previous period's total score.

    Returns:
        Trend string: 'improving', 'declining', or 'stable'.
    """
    change = current_score - previous_score
    if change > 5:
        return "improving"
    elif change < -5:
        return "declining"
    else:
        return "stable"


def compute_equil_score(
    missing_ratio,
    anomaly_ratio,
    offline_date_ratio,
    anomaly_date_ratio,
    offline_count,
    anomaly_count,
    actual_records,
    expected_records,
):
    """All-in-one equipment quality score computation.

    Computes all four dimension scores and returns the total, along with
    individual dimension scores for detailed analysis.

    Args:
        missing_ratio: Fraction of missing data points (0.0 to 1.0).
        anomaly_ratio: Fraction of anomalous data points (0.0 to 1.0).
        offline_date_ratio: Fraction of days with offline events (0.0 to 1.0).
        anomaly_date_ratio: Fraction of days with anomaly events (0.0 to 1.0).
        offline_count: Number of offline events in the scoring period.
        anomaly_count: Number of anomaly events in the scoring period.
        actual_records: Number of records actually collected.
        expected_records: Number of records expected.

    Returns:
        Dict containing:
        - total: Weighted total score (0 to 100)
        - quality: Data quality dimension score (0 to 35)
        - stability: Operational stability dimension score (0 to 10)
        - fault: Fault frequency dimension score (0 to 40)
        - completeness: Data completeness dimension score (0 to 15)
    """
    quality = compute_quality_score(missing_ratio, anomaly_ratio)
    stability = compute_stability_score(offline_date_ratio, anomaly_date_ratio)
    fault = compute_fault_score(offline_count, anomaly_count)
    completeness = compute_completeness_score(actual_records, expected_records)
    total = compute_total_score(quality, stability, fault, completeness)

    return {
        "total": total,
        "quality": quality,
        "stability": stability,
        "fault": fault,
        "completeness": completeness,
    }
