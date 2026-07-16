"""
5-layer anomaly determination module for water conservancy inspection.

Layers:
  1. Threshold check (ew_info_rules extend conditions)
  2. Change rate (sudden shift detection)
  3. Trend detection (consecutive monotonic movement)
  4. MAD statistical anomaly (Modified Z-Score)
  5. Correlation contradiction (multi-indicator logic conflicts)
"""

import json
import math
import statistics
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Layer 1 - Threshold
# ---------------------------------------------------------------------------

def layer1_threshold(value: float, rules: List[dict]) -> List[dict]:
    """Layer 1: Threshold check against ew_info_rules extend conditions.

    Each rule dict must contain:
      - 'extend': JSON string with {"content": ["248", null], "condition": ">"}
      - 'level_r': severity level (1=critical, 2=severe, 3=warning)

    Args:
        value: The current sensor reading.
        rules: List of ew_info_rules dicts.

    Returns:
        List of triggered rule dicts with layer/type/confidence info.
    """
    results: List[dict] = []
    for rule in rules:
        try:
            extend = json.loads(rule["extend"]) if isinstance(rule.get("extend"), str) else rule.get("extend")
            condition = extend.get("condition", ">")
            content = extend.get("content") or []
            raw_threshold = content[0] if len(content) > 0 else None
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue  # 跳过格式坏的规则（B5 阈值存在性/健壮性）

        threshold = float(raw_threshold) if raw_threshold is not None else None
        level = rule.get("level_r", 3)

        triggered = False
        if threshold is not None:
            if condition == ">" and value > threshold:
                triggered = True
            elif condition == ">=" and value >= threshold:
                triggered = True
            elif condition == "<" and value < threshold:
                triggered = True
            elif condition == "<=" and value <= threshold:
                triggered = True
            elif condition == "=" and value == threshold:
                triggered = True

        if triggered:
            results.append({
                "layer": 1,
                "type": "threshold",
                "level": level,
                "value": value,
                "threshold": threshold,
                "condition": condition,
                "confidence": 0.95,
            })
    return results


# ---------------------------------------------------------------------------
# Layer 2 - Change Rate
# ---------------------------------------------------------------------------

_DEFAULT_CHANGE_THRESHOLDS: Dict[str, Dict[str, Optional[float]]] = {
    "water_level": {"abs": 0.5, "rel": 0.05},
    "pressure":    {"abs": 5.0, "rel": 0.10},
    "gnss":        {"abs": 2.0, "rel": None},
    "flow":        {"abs": None, "rel": 0.20},
}


def layer2_change_rate(
    current: float,
    previous: float,
    thresholds: Optional[Dict[str, Dict[str, Optional[float]]]] = None,
) -> Dict[str, Any]:
    """Layer 2: Change rate detection for sudden shifts.

    Args:
        current: Current reading.
        previous: Previous reading.
        thresholds: Optional custom thresholds dict mapping indicator type to
            {"abs": ..., "rel": ...}.  Defaults to water-level/pressure/gnss/flow.

    Returns:
        Dict with ``is_anomaly``, ``rate``, and ``threshold`` per indicator.
        If *thresholds* covers multiple indicator types the result contains
        a key per type.
    """
    if thresholds is None:
        thresholds = _DEFAULT_CHANGE_THRESHOLDS

    if previous is None or previous == 0:
        # Can't compute rate; return neutral result for each indicator.
        return {
            ind: {"is_anomaly": False, "rate": None, "threshold": None}
            for ind in thresholds
        }

    abs_change = abs(current - previous)
    rel_change = abs_change / abs(previous)

    result: Dict[str, Any] = {}
    for ind, t in thresholds.items():
        abs_t, rel_t = t.get("abs"), t.get("rel")
        abs_trig = abs_t is not None and abs_change > abs_t
        rel_trig = rel_t is not None and rel_change > rel_t

        # 报告实际触发的那个阈值（都触发则报更严的 rel）
        if rel_trig:
            rate, threshold = rel_change, rel_t
        elif abs_trig:
            rate, threshold = abs_change, abs_t
        else:
            rate, threshold = (rel_change if rel_t else abs_change), (rel_t or abs_t)

        result[ind] = {
            "is_anomaly": abs_trig or rel_trig,
            "rate": rate,
            "threshold": threshold,
            "abs_change": abs_change,
            "rel_change": rel_change,
        }
    return result


# ---------------------------------------------------------------------------
# Layer 3 - Trend Detection
# ---------------------------------------------------------------------------

def layer3_trend(values: List[float], min_consecutive: int = 3) -> Dict[str, Any]:
    """Layer 3: Trend detection via consecutive monotonic movement.

    Args:
        values: Chronologically ordered sensor readings.
        min_consecutive: Minimum consecutive count to flag a trend.

    Returns:
        Dict with ``is_trend``, ``direction`` (``"rise"``/``"fall"``/``None``),
        and ``count`` of consecutive same-direction moves.
    """
    if len(values) < 2:
        return {"is_trend": False, "direction": None, "count": 0}

    # Count consecutive rise from the end.
    consecutive_rise = 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] > values[i - 1]:
            consecutive_rise += 1
        else:
            break

    # Count consecutive fall from the end.
    consecutive_fall = 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] < values[i - 1]:
            consecutive_fall += 1
        else:
            break

    max_count = max(consecutive_rise, consecutive_fall)
    direction = "rise" if consecutive_rise > consecutive_fall else (
        "fall" if consecutive_fall > consecutive_rise else None
    )

    return {
        "is_trend": max_count >= min_consecutive,
        "direction": direction,
        "count": max_count,
    }


# ---------------------------------------------------------------------------
# Layer 4 - MAD Statistical
# ---------------------------------------------------------------------------

def layer4_mad_statistical(
    values: List[float],
    threshold: float = 4.0,
) -> Dict[str, Any]:
    """Layer 4: Statistical anomaly detection via Modified Z-Score (MAD).

    委托给 mad_anomaly() 统一实现（M2 去重）。

    Args:
        values: List of historical readings (last element = current).
        threshold: Modified Z-Score threshold (default 4.0).

    Returns:
        Dict with ``is_anomaly`` and ``score`` (the Modified Z-Score).
    """
    return mad_anomaly(values, threshold=threshold, min_samples=4)


# ---------------------------------------------------------------------------
# Layer 5 - Correlation Contradiction
# ---------------------------------------------------------------------------

def layer5_correlation(indicator_pairs: List[dict]) -> Dict[str, Any]:
    """Layer 5: Multi-indicator contradiction detection.

    Each *indicator_pairs* entry describes a logical relationship to check.
    Supported pair schemas:

    - ``{"a_trend": "rise", "b_trend": "rise", "label": "water_level/seepage",
        "desc": "water level rising and seepage also rising is suspicious"}``

    Args:
        indicator_pairs: List of dicts, each with ``a_trend``, ``b_trend``,
            optional ``label``, and ``desc`` explaining the contradiction.

    Returns:
        Dict with ``is_anomaly`` and ``description`` summarising contradictions.
    """
    if not indicator_pairs:
        return {"is_anomaly": False, "description": "no indicators"}

    contradictions: List[str] = []
    for pair in indicator_pairs:
        a = pair.get("a_trend")
        b = pair.get("b_trend")
        desc = pair.get("desc", "")

        # Default contradiction heuristic: both rising when they should be
        # inversely correlated.
        if a == "rise" and b == "rise":
            label = pair.get("label", "unknown_pair")
            contradictions.append(f"{label}: {desc}" if desc else f"{label}: contradictory rise")

    return {
        "is_anomaly": len(contradictions) > 0,
        "description": "; ".join(contradictions) if contradictions else "no contradiction",
    }


# ---------------------------------------------------------------------------
# Composite Anomaly Judge
# ---------------------------------------------------------------------------

_LAYER_WEIGHTS = {
    1: 0.30,
    2: 0.20,
    3: 0.20,
    4: 0.15,
    5: 0.15,
}


def composite_anomaly_judge(layer_results: Dict[int, Any]) -> Dict[str, Any]:
    """Aggregate all 5 layer results into a single anomaly verdict.

    文档公式（DD1）：0.3×阈值 + 0.2×数据质量 + 0.2×趋势 + 0.2×历史 + 0.1×上下文
    层→因子映射：L1阈值 / L4数据质量(MAD) / L3趋势 / L2历史(变化率) / L5上下文(相关性)

    Args:
        layer_results: Mapping from layer number (1-5) to that layer's output.
            Each value may be a single dict or a list of dicts; each should
            contain ``confidence`` and (optionally) ``is_anomaly`` / trigger info.

    Returns:
        Dict with ``is_anomaly``, ``confidence`` (0-1), ``triggered_layers``,
        and human-readable ``description``.
    """
    # 文档权重（DD1）
    FACTOR_WEIGHT = {1: 0.30, 4: 0.20, 3: 0.20, 2: 0.20, 5: 0.10}
    triggered, factor_scores = [], {}

    for layer_num in range(1, 6):
        entry = layer_results.get(layer_num)
        if entry is None:
            continue
        entries = entry if isinstance(entry, list) else [entry]
        confs = [e.get("confidence", 0.5) for e in entries
                 if isinstance(e, dict) and (e.get("is_anomaly") or e.get("triggered"))]
        if confs:
            triggered.append(layer_num)
            factor_scores[layer_num] = max(confs)

    weight_present = sum(FACTOR_WEIGHT[l] for l in triggered)
    confidence = (sum(FACTOR_WEIGHT[l] * factor_scores[l] for l in triggered) / weight_present) if weight_present else 0.0

    names = {1: "threshold", 2: "change_rate", 3: "trend", 4: "MAD", 5: "correlation"}
    return {
        "is_anomaly": confidence > 0.5 or len(triggered) >= 2,
        "confidence": round(confidence, 4),
        "triggered_layers": triggered,
        "description": f"Anomaly via {', '.join(names[l] for l in triggered)}" if triggered else "No anomaly",
    }


# ---------------------------------------------------------------------------
# MAD Anomaly (standalone, reusable)
# ---------------------------------------------------------------------------

def mad_anomaly(values: List[float], threshold: float = 4.0, min_samples: int = 4) -> Dict[str, Any]:
    """Robust MAD outlier detection (aligned with _shared/algorithms/mad.md).

    The last element of *values* is treated as the current reading; the rest
    form the historical window.

    Args:
        values: Time-ordered readings (last = current).
        threshold: Modified Z-Score cutoff (default 4.0).
        min_samples: Minimum number of values required.

    Returns:
        Dict with ``is_anomaly``, ``score``, ``median``, ``mad``.
    """
    if len(values) < min_samples:
        return {"is_anomaly": False, "score": 0.0}

    try:
        import numpy as _np
        hist = _np.asarray(values[:-1], dtype=float)
        current = float(values[-1])
    except Exception:
        hist = values[:-1]
        current = values[-1]
        median = statistics.median(hist)
        mad = statistics.median([abs(v - median) for v in hist]) * 1.4826
    else:
        median = float(_np.median(hist))
        mad = float(_np.median(_np.abs(hist - median))) * 1.4826

    if mad == 0:
        return {"is_anomaly": False, "score": 0.0}

    z = abs(current - median) / mad
    return {
        "is_anomaly": z > threshold,
        "score": round(z, 4),
        "median": round(median, 4),
        "mad": round(mad, 4),
    }


def consecutive_monotonic(
    values: List[float],
    direction: str,
    min_consecutive: int,
) -> Dict[str, Any]:
    """Count consecutive monotonic moves from the end of *values*.

    Args:
        values: Time-ordered readings.
        direction: ``"rise"`` (strictly increasing) or ``"fall"`` (strictly decreasing).
        min_consecutive: Minimum consecutive count to flag a trend.

    Returns:
        Dict with ``is_trend`` and ``count``.
    """
    if len(values) < 2:
        return {"is_trend": False, "count": 0}

    count = 0
    for i in range(len(values) - 1, 0, -1):
        if direction == "rise" and values[i] > values[i - 1]:
            count += 1
        elif direction == "fall" and values[i] < values[i - 1]:
            count += 1
        else:
            break

    return {"is_trend": count >= min_consecutive, "count": count}
