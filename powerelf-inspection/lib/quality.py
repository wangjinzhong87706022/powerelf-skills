"""
Quality assessment module for water conservancy inspection tasks.

Covers:
  - Completion rate
  - Timeliness rate
  - Defect discovery rate
  - Route coverage
  - Composite quality score with grading (A-E)
  - Quality alert detection
"""

from typing import Any, Dict, List, Optional

# check_percent 字段语义（H1 默认处置：完成率；详见 references/business_rules.md）
CHECK_PERCENT_SEMANTICS = "completion"


# ---------------------------------------------------------------------------
# Individual dimension helpers
# ---------------------------------------------------------------------------

def compute_completion_rate(plan_points: int, actual_points: int) -> float:
    """Compute inspection completion rate.

    Args:
        plan_points: Number of planned inspection points.
        actual_points: Number of actually inspected points.

    Returns:
        Rate in [0, 1].
    """
    if plan_points <= 0:
        return 0.0
    return min(actual_points / plan_points, 1.0)


def compute_timeliness_rate(on_time_count: int, total_count: int) -> float:
    """Compute timeliness (on-time completion) rate.

    Args:
        on_time_count: Number of tasks completed on time.
        total_count: Total number of tasks.

    Returns:
        Rate in [0, 1].
    """
    if total_count <= 0:
        return 0.0
    return on_time_count / total_count


def compute_defect_discovery_rate(defects_found: int, real_checkitems: int) -> float:
    """缺陷发现率 = 缺陷数 / 实际巡检项数（real_objitem）。详见 quality-assessment.md。

    Args:
        defects_found: Number of defects found.
        real_checkitems: Number of actual inspection items (real_objitem).

    Returns:
        Rate in [0, 1].
    """
    if real_checkitems <= 0:
        return 0.0
    return defects_found / real_checkitems


def compute_route_coverage(covered_points: int, total_points: int) -> float:
    """Compute route coverage rate.

    Args:
        covered_points: Number of points actually visited.
        total_points: Total points on the route.

    Returns:
        Rate in [0, 1].
    """
    if total_points <= 0:
        return 0.0
    return covered_points / total_points


# ---------------------------------------------------------------------------
# Composite quality score
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS = {
    "completion": 0.30,
    "timeliness": 0.25,
    "defect_rate": 0.25,
    "coverage": 0.20,
}


def _score_completion(rate: float) -> float:
    """Map completion rate to a score (max 30)."""
    if rate >= 0.95:
        return 30
    if rate >= 0.90:
        return 25
    if rate >= 0.80:
        return 20
    if rate >= 0.70:
        return 15
    return 10


def _score_timeliness(rate: float) -> float:
    """Map timeliness rate to a score (max 25)."""
    if rate >= 0.95:
        return 25
    if rate >= 0.90:
        return 20
    if rate >= 0.80:
        return 15
    return 10


def _score_defect_rate(rate: float) -> float:
    """Map defect discovery rate to a score (max 25).

    Optimal range: 1-5%.  Too low may mean missed defects; too high may
    indicate aging equipment.
    """
    if 0.01 <= rate <= 0.05:
        return 25
    if 0.05 < rate <= 0.10:
        return 20
    if 0.10 < rate <= 0.20:
        return 15
    if rate > 0.20:
        return 10
    # rate < 0.01 — possible missed defects
    return 15


def _score_coverage(rate: float) -> float:
    """Map route coverage to a score (max 20)."""
    if rate >= 0.95:
        return 20
    if rate >= 0.90:
        return 15
    if rate >= 0.80:
        return 10
    return 5


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "E"


def compute_quality_score(
    completion: float,
    timeliness: float,
    defect_rate: float,
    coverage: float,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute the composite inspection quality score.

    Args:
        completion: Completion rate (0-1).
        timeliness: Timeliness rate (0-1).
        defect_rate: Defect discovery rate (0-1).
        coverage: Route coverage rate (0-1).
        weights: Optional dimension weights overriding defaults.

    Returns:
        Dict with ``total_score`` (0-100), ``grade`` (A-E), and
        ``dimension_scores`` breakdown.
    """
    w = weights if weights else _DEFAULT_WEIGHTS

    raw_scores = {
        "completion": _score_completion(completion),
        "timeliness": _score_timeliness(timeliness),
        "defect_rate": _score_defect_rate(defect_rate),
        "coverage": _score_coverage(coverage),
    }

    # The raw scores already encode the weight (max 30+25+25+20=100).
    # But if custom weights are supplied we re-normalise.
    _MAX = {"completion": 30.0, "timeliness": 25.0, "defect_rate": 25.0, "coverage": 20.0}
    if weights:
        # 按各维度满分归一化后再加权 × 100（C1 自定义权重分支修正）
        total_score = sum(
            (raw_scores[dim] / _MAX[dim]) * weights.get(dim, 0) * 100.0
            for dim in raw_scores
        )
    else:
        total_score = sum(raw_scores.values())

    total_score = round(total_score, 2)

    dimension_scores = {
        dim: {
            "rate": round(
                [completion, timeliness, defect_rate, coverage][
                    ["completion", "timeliness", "defect_rate", "coverage"].index(dim)
                ],
                4,
            ),
            "score": raw_scores[dim],
        }
        for dim in raw_scores
    }

    return {
        "total_score": total_score,
        "grade": _grade(total_score),
        "dimension_scores": dimension_scores,
    }


# ---------------------------------------------------------------------------
# Quality alerts
# ---------------------------------------------------------------------------

def check_quality_alerts(task_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Inspect task data for quality-related alerts.

    Expected keys in *task_data*:
      - ``overtime``: number of overtime tasks
      - ``total``: total tasks
      - ``plan_points``: planned inspection points
      - ``actual_points``: actually inspected points
      - ``defects_found``: number of defects found
      - ``total_checks``: total checks performed
      - ``consecutive_defect_tasks``: list of recent tasks that had defects

    Returns:
        List of alert dicts, each with ``type`` and ``description``.
    """
    alerts: List[Dict[str, Any]] = []
    total = task_data.get("total", 0)

    # --- Overtime alert ---
    overtime = task_data.get("overtime", 0)
    if total > 0 and overtime / total > 0.30:
        alerts.append({
            "type": "overtime",
            "description": (
                f"Overtime ratio {overtime}/{total} = "
                f"{overtime/total:.0%} exceeds 30% threshold"
            ),
        })

    # --- Omission alert ---
    plan = task_data.get("plan_points", 0)
    actual = task_data.get("actual_points", 0)
    if plan > 0:
        omission_rate = 1 - actual / plan
        if omission_rate > 0.20:
            alerts.append({
                "type": "omission",
                "description": (
                    f"Omission rate {omission_rate:.0%} exceeds 20% — "
                    f"only {actual}/{plan} points inspected"
                ),
            })

    # --- Defect backlog alert ---
    defects_found = task_data.get("defects_found", 0)
    total_checks = task_data.get("total_checks", 0)
    if defects_found > 0 and total_checks > 0:
        defect_rate = defects_found / total_checks
        if defect_rate > 0.20:
            alerts.append({
                "type": "defect_backlog",
                "description": (
                    f"High defect rate {defect_rate:.0%} suggests possible "
                    f"equipment degradation or backlog"
                ),
            })

    # --- Consecutive defects alert ---
    consecutive = task_data.get("consecutive_defect_tasks", [])
    if len(consecutive) >= 3:
        alerts.append({
            "type": "consecutive_defects",
            "description": (
                f"Defects found in {len(consecutive)} consecutive tasks — "
                f"possible systematic issue"
            ),
        })

    return alerts
