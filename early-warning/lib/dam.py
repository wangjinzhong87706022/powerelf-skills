"""Dam safety warning module.

Implements multi-point multi-indicator evaluation, direction analysis,
and consistency checking for dam structural monitoring.
"""

from decimal import Decimal

from .threshold import evaluate_condition


def evaluate_dam_points(dam_values, rule_extend, trigger_number):
    """Evaluate all monitoring points on a dam cross-section.

    For each point, check every sub-rule. A point triggers if any sub-rule
    matches. The overall warning fires if the number of triggered points
    meets or exceeds trigger_number.

    Args:
        dam_values: List of dicts, each representing a monitoring point.
            Keys include: pointId, wgs84DeltaH, wgs84DeltaX, wgs84DeltaY,
            wgs84TotalX, wgs84TotalY, wgs84TotalH.
        rule_extend: List of sub-rules, each with keys:
            field (str), content (list), condition (str).
        trigger_number: Minimum number of trigger points to issue a warning.

    Returns:
        dict with keys:
            is_warning (bool): True if trigger_count >= trigger_number.
            trigger_count (int): Number of points that triggered.
            trigger_points (list): Details of each triggered point.
            trigger_fields (list): Aggregated list of all triggered fields.
    """
    trigger_points = []
    all_trigger_fields = []

    for point in dam_values:
        is_warning = False
        point_fields = []

        for sub_rule in rule_extend:
            field = sub_rule["field"]
            raw_value = point.get(field)
            if raw_value is None:
                continue

            # Displacement values use absolute value for threshold comparison
            abs_value = abs(Decimal(str(raw_value)))
            content = sub_rule["content"]
            condition = sub_rule["condition"]

            if evaluate_condition(abs_value, condition, content):
                is_warning = True
                point_fields.append(field)
                if field not in all_trigger_fields:
                    all_trigger_fields.append(field)

        if is_warning:
            trigger_points.append({
                "pointId": point.get("pointId"),
                "triggerFields": point_fields,
            })

    trigger_count = len(trigger_points)

    return {
        "is_warning": trigger_count >= trigger_number,
        "trigger_count": trigger_count,
        "trigger_points": trigger_points,
        "trigger_fields": all_trigger_fields,
    }


def direction_analysis(delta_x, delta_y, delta_h):
    """Analyze displacement direction for a single monitoring point.

    Uses signed original values to determine direction of movement.

    Args:
        delta_x: Horizontal X displacement (positive = downstream).
        delta_y: Horizontal Y displacement (positive = left).
        delta_h: Vertical displacement (positive = subsidence).

    Returns:
        dict with direction labels and raw values.
    """
    dx = Decimal(str(delta_x))
    dy = Decimal(str(delta_y))
    dh = Decimal(str(delta_h))

    return {
        "x_direction": (
            "downstream" if dx > 0
            else "upstream" if dx < 0
            else "stable"
        ),
        "y_direction": (
            "left" if dy > 0
            else "right" if dy < 0
            else "stable"
        ),
        "h_direction": (
            "subsidence" if dh > 0
            else "uplift" if dh < 0
            else "stable"
        ),
        "delta_x": float(dx),
        "delta_y": float(dy),
        "delta_h": float(dh),
    }


def consistency_check(points_directions):
    """Check directional consistency across multiple monitoring points.

    If all non-stable points share the same direction, it indicates
    possible overall sliding (more severe). If adjacent points move
    in opposite directions, it indicates possible local deformation.

    Args:
        points_directions: List of direction dicts from direction_analysis(),
            each with x_direction, y_direction, h_direction keys.

    Returns:
        dict with keys:
            is_overall_sliding (bool): True if consistent direction detected.
            is_local_deformation (bool): True if opposing directions detected.
            summary (str): Human-readable summary of the analysis.
    """
    x_dirs = [
        d["x_direction"]
        for d in points_directions
        if d["x_direction"] != "stable"
    ]
    h_dirs = [
        d["h_direction"]
        for d in points_directions
        if d["h_direction"] != "stable"
    ]

    is_overall_sliding = False
    is_local_deformation = False
    warnings = []

    # Overall sliding: all non-stable points share the same direction
    if len(x_dirs) >= 2 and len(set(x_dirs)) == 1:
        is_overall_sliding = True
        warnings.append(f"X方向整体偏移: {x_dirs[0]}")

    if len(h_dirs) >= 2 and len(set(h_dirs)) == 1:
        is_overall_sliding = True
        warnings.append(f"H方向整体: {h_dirs[0]}")

    # Local deformation: adjacent points have opposite directions
    for dirs, axis in [(x_dirs, "X"), (h_dirs, "H")]:
        if len(dirs) >= 2 and len(set(dirs)) > 1:
            is_local_deformation = True
            warnings.append(f"{axis}方向局部变形: 方向不一致")

    summary = "; ".join(warnings) if warnings else "方向一致，无异常"

    return {
        "is_overall_sliding": is_overall_sliding,
        "is_local_deformation": is_local_deformation,
        "summary": summary,
    }
