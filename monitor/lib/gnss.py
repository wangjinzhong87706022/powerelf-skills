"""GNSS deformation analysis module: displacement rate, direction, consistency, statistics."""


def displacement_rate(total_value, months):
    """Calculate displacement rate in cm/month.

    total_value: total displacement value (in meters, converted to cm by *100).
    months: number of months the data spans.
    Returns rate in cm/month, or None if months is 0.
    """
    if months is None or months == 0:
        return None
    if total_value is None:
        return None
    return round(abs(total_value) / months * 100, 2)


def classify_rate(rate_cm_per_month):
    """Classify displacement rate into severity level.

    Thresholds: <0.5 stable, 0.5-2 slow, 2-5 medium, >5 fast.
    Returns one of: 'stable', 'slow', 'medium', 'fast'.
    """
    if rate_cm_per_month is None:
        return None
    s = abs(rate_cm_per_month)
    if s > 5:
        return "fast"
    if s > 2:
        return "medium"
    if s > 0.5:
        return "slow"
    return "stable"


def direction_analysis(delta_x, delta_y, delta_h):
    """Analyze displacement direction from delta values.

    Returns a dict with x_direction, y_direction, h_direction as human-readable strings.
    """
    result = {"x_direction": None, "y_direction": None, "h_direction": None}

    if delta_x is not None:
        if delta_x > 0:
            result["x_direction"] = "向下游偏移"
        elif delta_x < 0:
            result["x_direction"] = "向上游偏移"
        else:
            result["x_direction"] = "无偏移"

    if delta_y is not None:
        if delta_y > 0:
            result["y_direction"] = "向右岸偏移"
        elif delta_y < 0:
            result["y_direction"] = "向左岸偏移"
        else:
            result["y_direction"] = "无偏移"

    if delta_h is not None:
        if delta_h > 0:
            result["h_direction"] = "下沉"
        elif delta_h < 0:
            result["h_direction"] = "上升(隆起)"
        else:
            result["h_direction"] = "无变化"

    return result


def consistency_check(deltas_list):
    """Check direction consistency for multiple points on the same section.

    deltas_list: list of dicts, each with 'delta_x', 'delta_y', 'delta_h'.
    Returns a dict with is_consistent, all_same_direction, direction_summary.
    """
    result = {
        "is_consistent": False,
        "all_same_direction": False,
        "direction_summary": "数据不足",
    }

    if not deltas_list or len(deltas_list) < 2:
        return result

    x_signs = []
    h_signs = []
    for p in deltas_list:
        dx = p.get("delta_x")
        dh = p.get("delta_h")
        if dx is not None:
            x_signs.append(dx > 0)
        if dh is not None:
            h_signs.append(dh > 0)

    if len(set(x_signs)) == 1 and len(x_signs) > 1:
        result["all_same_direction"] = True
        result["is_consistent"] = True
        result["direction_summary"] = "整体滑动：同断面测点偏移方向一致"
    elif len(set(x_signs)) > 1:
        result["is_consistent"] = False
        result["direction_summary"] = "局部变形：相邻测点偏移方向相反"
    else:
        result["direction_summary"] = "数据不足以判断"

    return result


def annual_stats(daily_values):
    """Compute annual statistics from a series of daily displacement values.

    daily_values: list of numeric values.
    Returns a dict with max, min, mean, amplitude.
    """
    if not daily_values:
        return {"max": None, "min": None, "mean": None, "amplitude": None}

    valid = [v for v in daily_values if v is not None]
    if not valid:
        return {"max": None, "min": None, "mean": None, "amplitude": None}

    max_val = max(valid)
    min_val = min(valid)
    mean_val = sum(valid) / len(valid)
    amplitude = max_val - min_val

    return {
        "max": round(max_val, 4),
        "min": round(min_val, 4),
        "mean": round(mean_val, 4),
        "amplitude": round(amplitude, 4),
    }


def compute_cumulative(deltas):
    """Compute cumulative values from a series of deltas.

    deltas: list of incremental values.
    Returns a list of cumulative sums (same length as input).
    """
    if not deltas:
        return []

    cumulative = []
    running = 0
    for d in deltas:
        if d is not None:
            running += d
        cumulative.append(round(running, 4))
    return cumulative
