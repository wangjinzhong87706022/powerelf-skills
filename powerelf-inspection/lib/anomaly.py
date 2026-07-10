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
        extend = json.loads(rule["extend"])
        condition = extend["condition"]
        raw_threshold = extend["content"][0]
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
        triggered = False
        if t.get("abs") is not None and abs_change > t["abs"]:
            triggered = True
        if t.get("rel") is not None and rel_change > t["rel"]:
            triggered = True

        # Pick the tighter threshold for reporting.
        rate = rel_change if t.get("rel") else abs_change
        threshold = t.get("rel") if t.get("rel") else t.get("abs")

        result[ind] = {
            "is_anomaly": triggered,
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

    Uses the last value in *values* as the current reading and the rest as
    the historical window.

    Args:
        values: List of historical readings (last element = current).
        threshold: Modified Z-Score threshold (default 4.0).

    Returns:
        Dict with ``is_anomaly`` and ``score`` (the Modified Z-Score).
    """
    if len(values) < 4:
        return {"is_anomaly": False, "score": 0.0}

    current_value = values[-1]
    historical = values[:-1]

    median = statistics.median(historical)
    abs_devs = [abs(v - median) for v in historical]
    mad = statistics.median(abs_devs) * 1.4826

    if mad == 0:
        return {"is_anomaly": False, "score": 0.0}

    z_score = abs(current_value - median) / mad

    return {
        "is_anomaly": z_score > threshold,
        "score": round(z_score, 4),
    }


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

    Args:
        layer_results: Mapping from layer number (1-5) to that layer's output.
            Each value may be a single dict or a list of dicts; each should
            contain ``confidence`` and (optionally) ``is_anomaly`` / trigger info.

    Returns:
        Dict with ``is_anomaly``, ``confidence`` (0-1), ``triggered_layers``,
        and human-readable ``description``.
    """
    weighted_sum = 0.0
    weight_total = 0.0
    triggered_layers: List[int] = []

    for layer_num in range(1, 6):
        entry = layer_results.get(layer_num)
        if entry is None:
            continue

        # Normalise to list.
        entries = entry if isinstance(entry, list) else [entry]

        # Determine if this layer triggered.
        layer_confidences: List[float] = []
        for e in entries:
            if isinstance(e, dict):
                # A layer "triggered" if it has an anomaly indicator.
                is_anomaly = e.get("is_anomaly", False) or e.get("triggered", False)
                conf = e.get("confidence", 0.5)
                if is_anomaly:
                    layer_confidences.append(conf)

        if layer_confidences:
            max_conf = max(layer_confidences)
            weighted_sum += _LAYER_WEIGHTS[layer_num] * max_conf
            weight_total += _LAYER_WEIGHTS[layer_num]
            triggered_layers.append(layer_num)

    confidence = (weighted_sum / weight_total) if weight_total > 0 else 0.0

    # Multiple layers triggering increases confidence.
    if len(triggered_layers) >= 3:
        confidence = min(confidence * 1.15, 1.0)

    is_anomaly = confidence > 0.5 or len(triggered_layers) >= 2

    descriptions = []
    layer_names = {
        1: "threshold",
        2: "change_rate",
        3: "trend",
        4: "MAD_statistical",
        5: "correlation",
    }
    for ln in triggered_layers:
        descriptions.append(layer_names.get(ln, f"layer_{ln}"))

    return {
        "is_anomaly": is_anomaly,
        "confidence": round(confidence, 4),
        "triggered_layers": triggered_layers,
        "description": (
            f"Anomaly detected via {', '.join(descriptions)}"
            if descriptions
            else "No anomaly detected"
        ),
    }
