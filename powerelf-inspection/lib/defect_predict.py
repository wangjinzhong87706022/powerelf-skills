"""
Defect prediction module for water conservancy inspection.

Covers:
  - Linear trend forecasting (least-squares regression)
  - Seasonal analysis (flood season / winter patterns)
  - Bayesian equipment hotspot scoring
"""

import math
from typing import Any, Dict, List

# 启发式阈值（M3：未经标定，仅参考；建议按历史分布校准）
HOTSPOT_THRESHOLDS = {"high": 0.3, "medium": 0.1}


# ---------------------------------------------------------------------------
# 4.1 Linear Trend Prediction
# ---------------------------------------------------------------------------

def linear_trend(historical_counts: List[float]) -> Dict[str, Any]:
    """Simple linear regression on defect counts over time.

    Fits y = slope * x + intercept where x = month index (0, 1, 2, ...).

    Args:
        historical_counts: Chronologically ordered defect counts per period.

    Returns:
        Dict with ``slope``, ``intercept``, ``predicted_next``,
        ``trend_direction`` (``"rising"``/``"falling"``/``"stable"``), and
        ``r_squared``.
    """
    n = len(historical_counts)
    if n == 0:
        return {
            "slope": 0.0,
            "intercept": 0.0,
            "predicted_next": 0,
            "trend_direction": "stable",
            "r_squared": 0.0,
        }

    if n == 1:
        return {
            "slope": 0.0,
            "intercept": historical_counts[0],
            "predicted_next": round(max(0, historical_counts[0])),
            "trend_direction": "stable",
            "r_squared": 1.0,
        }

    x = list(range(n))
    y = historical_counts

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        slope = 0.0
        intercept = sum_y / n
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

    # R-squared
    y_mean = sum_y / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

    predicted = slope * n + intercept

    if slope > 0.5:
        direction = "rising"
    elif slope < -0.5:
        direction = "falling"
    else:
        direction = "stable"

    return {
        "slope": round(slope, 6),
        "intercept": round(intercept, 6),
        "predicted_next": round(max(0, predicted)),
        "trend_direction": direction,
        "r_squared": round(r_squared, 6),
    }


# ---------------------------------------------------------------------------
# 4.2 Seasonal Analysis
# ---------------------------------------------------------------------------

_SEASON_LABELS = {
    1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
    6: "flood", 7: "flood", 8: "flood", 9: "flood",
    10: "autumn", 11: "autumn", 12: "winter",
}


def seasonal_analysis(monthly_data: Dict[int, List[float]]) -> Dict[str, Any]:
    """Identify seasonal patterns in defect counts.

    Water conservancy context: flood season (Jun-Sep) and winter (Dec-Feb)
    typically have higher defect rates.

    Args:
        monthly_data: Mapping of month number (1-12) to a list of defect
            counts for that month across multiple years.
            Example: {1: [5, 4, 6], 2: [3, 5, 4], ...}

    Returns:
        Dict with ``peak_months`` (top 3), ``trough_months`` (bottom 3),
        and ``seasonal_factor`` mapping (month -> factor relative to the
        overall mean).
    """
    monthly_avg: Dict[int, float] = {}
    for month in range(1, 13):
        values = monthly_data.get(month, [])
        monthly_avg[month] = sum(values) / len(values) if values else 0.0

    overall_avg = sum(monthly_avg.values()) / 12 if any(monthly_avg.values()) else 0.0

    seasonal_factor: Dict[int, float] = {}
    for m, avg in monthly_avg.items():
        seasonal_factor[m] = round(avg / overall_avg, 4) if overall_avg > 0 else 1.0

    sorted_months = sorted(seasonal_factor.items(), key=lambda kv: kv[1], reverse=True)
    peak_months = sorted_months[:3]
    trough_months = sorted_months[-3:]

    return {
        "peak_months": [
            {"month": m, "factor": f, "label": _SEASON_LABELS.get(m, "")}
            for m, f in peak_months
        ],
        "trough_months": [
            {"month": m, "factor": f, "label": _SEASON_LABELS.get(m, "")}
            for m, f in trough_months
        ],
        "seasonal_factor": seasonal_factor,
    }


# ---------------------------------------------------------------------------
# 4.3 Bayesian Equipment Hotspot Prediction
# ---------------------------------------------------------------------------

def bayesian_hotspot(
    defect_history: List[Dict[str, Any]],
    equipment_importance: Dict[str, float],
) -> List[Dict[str, Any]]:
    """Bayesian hotspot scoring for equipment defect prediction.

    Uses Laplace-smoothed Bayesian probability::

        P(equip_i has defect next period) = (defect_count_i + 1) / (total_months + n_equips)

    Args:
        defect_history: List of dicts, each with at least ``equip_id`` and
            ``defect_count`` (historical defect count for that equipment).
        equipment_importance: Mapping of equip_id to importance weight
            (e.g., 4.0 = dam core, 3.0 = major electromechanical, 1.0 = general).

    Returns:
        List of dicts sorted by hotspot_score descending, each with
        ``equip_id``, ``hotspot_score``, ``risk_level`` (high/medium/low),
        ``probability``, and ``importance_weight``.
    """
    if not defect_history:
        return []

    n_equips = len(defect_history)

    # Infer total_months from data or default to max defect_count span.
    total_months = max(d.get("total_months", 0) for d in defect_history)
    if total_months <= 0:
        # Fallback: assume at least 12 months of history.
        total_months = 12

    results: List[Dict[str, Any]] = []
    for equip in defect_history:
        equip_id = equip["equip_id"]
        defect_count = equip.get("defect_count", 0)
        importance = equipment_importance.get(equip_id, 1.0)

        # Laplace-smoothed probability.
        probability = (defect_count + 1) / (total_months + n_equips)

        # Hotspot score = probability * importance weight.
        hotspot_score = round(probability * importance, 4)

        # 使用启发式阈值（M3：未经标定，建议按历史分布校准）
        if hotspot_score > HOTSPOT_THRESHOLDS["high"]:
            risk_level = "high"
        elif hotspot_score > HOTSPOT_THRESHOLDS["medium"]:
            risk_level = "medium"
        else:
            risk_level = "low"

        results.append({
            "equip_id": equip_id,
            "defect_count": defect_count,
            "probability": round(probability, 4),
            "importance_weight": importance,
            "hotspot_score": hotspot_score,
            "risk_level": risk_level,
        })

    return sorted(results, key=lambda r: r["hotspot_score"], reverse=True)
