"""
Route optimization module for water conservancy inspection.

Covers:
  - Problem diagnosis from task statistics
  - Geographic clustering via K-Means (pure Python, Euclidean on lon/lat)
  - Time-balanced cluster assignment
  - Priority-based point selection
"""

import math
import random
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 5.1 Problem Diagnosis
# ---------------------------------------------------------------------------

def diagnose_problems(task_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Diagnose route / task problems from aggregate statistics.

    Expected keys in *task_stats*:
      - ``avg_omission_rate``: average omission rate (0-1)
      - ``point_count``: number of inspection points per route
      - ``avg_time_per_point``: average minutes per point
      - ``route_backtrack``: bool, whether route has significant backtracking
      - ``overtime_ratio``: fraction of tasks that ran over time (0-1)
      - ``avg_actual_time``: average actual task duration (minutes)
      - ``max_time``: configured maximum task duration (minutes)
      - ``defect_rate``: defect discovery rate (0-1)
      - ``nearby_route_defect_rate``: defect rate on nearby routes for comparison

    Returns:
        List of problem dicts with ``type``, ``cause``, and optional
        ``suggestion``.
    """
    issues: List[Dict[str, Any]] = []

    # --- High omission ---
    omission = task_stats.get("avg_omission_rate", 0)
    if omission > 0.20:
        causes: List[str] = []
        if task_stats.get("point_count", 0) > 10:
            causes.append("Too many inspection points (>10); consider splitting the route")
        if task_stats.get("avg_time_per_point", 0) > 30:
            causes.append("Average time per point >30 min; consider reducing check items")
        if task_stats.get("route_backtrack", False):
            causes.append("Significant route backtracking; reorder by geographic area")
        if not causes:
            causes.append("Omission rate high — review route design")
        issues.append({"type": "high_omission", "causes": causes})

    # --- Frequent overtime ---
    overtime_ratio = task_stats.get("overtime_ratio", 0)
    if overtime_ratio > 0.30:
        actual = task_stats.get("avg_actual_time", 0)
        max_time = task_stats.get("max_time", 0)
        if max_time > 0 and actual > max_time * 1.2:
            suggested = round(actual * 1.1)
            issues.append({
                "type": "frequent_overtime",
                "cause": (
                    f"Average actual time ({actual:.0f} min) significantly exceeds "
                    f"maxTime ({max_time} min)"
                ),
                "suggestion": f"Extend maxTime to {suggested} min",
            })
        else:
            issues.append({
                "type": "frequent_overtime",
                "cause": "Route order or check-item count needs optimisation",
                "suggestion": "Optimise route order or reduce check items",
            })

    # --- Low defect rate ---
    defect_rate = task_stats.get("defect_rate", 0)
    if defect_rate < 0.01:
        nearby_rate = task_stats.get("nearby_route_defect_rate", 0)
        if nearby_rate < 0.01:
            issues.append({
                "type": "low_defect_rate",
                "cause": "Equipment in this area is in good condition",
            })
        else:
            issues.append({
                "type": "low_defect_rate",
                "cause": (
                    "Nearby routes find more defects — possible execution "
                    "issue; consider rotating inspector"
                ),
            })

    return issues


# ---------------------------------------------------------------------------
# 5.2 Geographic Clustering (K-Means)
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres."""
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _euclidean(p1: Dict[str, float], p2: Dict[str, float]) -> float:
    """Euclidean distance on (lon, lat) plane (for small-area clustering)."""
    return math.sqrt((p1["lon"] - p2["lon"]) ** 2 + (p1["lat"] - p2["lat"]) ** 2)


def cluster_points(
    points: List[Dict[str, Any]],
    n_clusters: int = 3,
    max_iterations: int = 100,
    seed: Optional[int] = None,
) -> List[List[str]]:
    """Cluster inspection points by geographic proximity using K-Means.

    Pure-Python implementation with Euclidean distance on (lon, lat).

    Args:
        points: List of dicts with at least ``id``, ``lon``, ``lat``.
        n_clusters: Desired number of clusters.
        max_iterations: Maximum K-Means iterations.
        seed: Optional random seed for reproducibility.

    Returns:
        List of clusters, where each cluster is a list of point ``id`` values.
    """
    if not points:
        return []
    n_clusters = min(n_clusters, len(points))

    rng = random.Random(seed)

    # Initialise centroids by picking n_clusters distinct random points.
    init_indices = rng.sample(range(len(points)), n_clusters)
    centroids = [
        {"lon": points[i]["lon"], "lat": points[i]["lat"]}
        for i in init_indices
    ]

    assignments = [0] * len(points)

    for _ in range(max_iterations):
        # Assignment step.
        new_assignments = []
        for p in points:
            dists = [_euclidean(p, c) for c in centroids]
            new_assignments.append(dists.index(min(dists)))

        # Check convergence.
        if new_assignments == assignments:
            break
        assignments = new_assignments

        # Update step.
        for k in range(n_clusters):
            members = [
                points[i] for i in range(len(points)) if assignments[i] == k
            ]
            if members:
                centroids[k] = {
                    "lon": sum(m["lon"] for m in members) / len(members),
                    "lat": sum(m["lat"] for m in members) / len(members),
                }
            # If cluster is empty, centroid stays unchanged.

    # Build output clusters.
    clusters: List[List[str]] = [[] for _ in range(n_clusters)]
    for i, p in enumerate(points):
        clusters[assignments[i]].append(p["id"])

    # Remove empty clusters.
    return [c for c in clusters if c]


# ---------------------------------------------------------------------------
# 5.3 Time Balance
# ---------------------------------------------------------------------------

def time_balance(
    clusters: List[List[Dict[str, Any]]],
    max_time_minutes: float,
) -> Dict[str, Any]:
    """Rebalance clusters so each cluster's estimated time is similar.

    Uses a greedy bin-packing approach: points are sorted by estimated time
    (descending) and assigned to the cluster with the least total time.

    Args:
        clusters: List of clusters, each cluster a list of point dicts.
            Each point should have ``check_items`` (list) or ``est_time``
            (minutes).
        max_time_minutes: Maximum allowed time per cluster/route.

    Returns:
        Dict with ``routes`` (rebalanced clusters), ``avg_time``,
        ``max_deviation`` (fraction), and ``balanced`` (bool, True if
        max deviation < 20%).
    """
    # Flatten and estimate times.
    all_points: List[Dict[str, Any]] = []
    for cluster in clusters:
        for p in cluster:
            if "est_time" not in p:
                items = p.get("check_items", [])
                p["est_time"] = max(5, len(items) * 3)
            all_points.append(p)

    n_routes = len(clusters) if clusters else 1
    routes: List[Dict[str, Any]] = [
        {"points": [], "total_time": 0.0} for _ in range(n_routes)
    ]

    # Greedy: assign heaviest point to the lightest route.
    sorted_points = sorted(all_points, key=lambda p: p["est_time"], reverse=True)
    for point in sorted_points:
        lightest = min(routes, key=lambda r: r["total_time"])
        lightest["points"].append(point)
        lightest["total_time"] += point["est_time"]

    times = [r["total_time"] for r in routes]
    avg_time = sum(times) / len(times) if times else 0
    max_deviation = (
        max(abs(t - avg_time) / avg_time for t in times) if avg_time > 0 else 0
    )

    return {
        "routes": routes,
        "avg_time": round(avg_time, 2),
        "max_deviation": round(max_deviation, 4),
        "balanced": max_deviation < 0.20,
    }


# ---------------------------------------------------------------------------
# 5.4 Priority Selection
# ---------------------------------------------------------------------------

def priority_select(
    points: List[Dict[str, Any]],
    priority_scores: Dict[str, float],
    max_count: int,
) -> List[Dict[str, Any]]:
    """Select the top-*max_count* points sorted by priority score.

    Args:
        points: List of point dicts (each must have an ``id`` key).
        priority_scores: Mapping of point id to priority score (higher = more
            important).
        max_count: Maximum number of points to select.

    Returns:
        Selected points sorted by priority score descending, each annotated
        with its ``priority_score``.
    """
    for p in points:
        p["priority_score"] = priority_scores.get(p["id"], 0)

    sorted_points = sorted(points, key=lambda p: p["priority_score"], reverse=True)
    return sorted_points[:max_count]
