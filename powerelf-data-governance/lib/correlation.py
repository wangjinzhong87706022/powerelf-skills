"""
相关性异常检测模块 — 跨指标关联分析

单指标都在正常范围内，但物理上不可能同时发生的组合。
例如：渗压上升 + 渗流下降 = 物理矛盾（水压增大应该导致渗流增加）。
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime


# ===== 物理规则定义 =====

PHYSICS_RULES = [
    {
        "id": "pressure_flow_contradiction",
        "name": "渗压-渗流矛盾",
        "description": "渗压上升时渗流应该上升，反之亦然",
        "indicators": ["seepage_pressure", "seepage_flow"],
        "condition": lambda changes: changes["seepage_pressure"] > 0 and changes["seepage_flow"] < 0,
        "severity": "HIGH",
        "confidence": 0.9,
        "reason": "渗压上升但渗流下降，物理上不可能",
    },
    {
        "id": "water_level_seepage_contradiction",
        "name": "水位-渗流矛盾",
        "description": "水位上升时渗流应该上升（水头增大）",
        "indicators": ["water_level", "seepage_flow"],
        "condition": lambda changes: changes["water_level"] > 0.5 and changes["seepage_flow"] < -0.1,
        "severity": "MEDIUM",
        "confidence": 0.7,
        "reason": "水位上升({wl_change:+.2f}m)但渗流下降({flow_change:+.4f}L/s)",
    },
    {
        "id": "rainfall_level_contradiction",
        "name": "降雨-水位矛盾",
        "description": "持续降雨但水位下降（无排水情况下）",
        "indicators": ["rainfall", "water_level"],
        "condition": lambda changes: changes["rainfall"] > 30 and changes["water_level"] < -1.0,
        "severity": "MEDIUM",
        "confidence": 0.6,
        "reason": "24h降雨{rainfall:.1f}mm但水位下降{wl_change:.2f}m",
    },
    {
        "id": "pump_flow_contradiction",
        "name": "泵站功率-流量矛盾",
        "description": "泵站功率正常但流量为零",
        "indicators": ["pump_power", "pump_flow"],
        "condition": lambda changes: changes["pump_power"] > 10 and changes["pump_flow"] == 0,
        "severity": "HIGH",
        "confidence": 0.85,
        "reason": "泵站功率{power:.1f}kW但流量为0",
    },
    {
        "id": "gate_flow_contradiction",
        "name": "闸门开度-流量矛盾",
        "description": "闸门关闭但有过闸流量",
        "indicators": ["gate_opening", "gate_flow"],
        "condition": lambda changes: changes["gate_opening"] == 0 and changes["gate_flow"] > 0,
        "severity": "HIGH",
        "confidence": 0.95,
        "reason": "闸门关闭但流量{flow:.2f}m³/s（可能漏水）",
    },
]


def detect_correlation_anomaly(
    indicator_data: Dict[str, Dict],
    rules: Optional[List[Dict]] = None,
) -> List[Dict]:
    """检测相关性异常

    Args:
        indicator_data: 指标数据，格式:
            {
                "seepage_pressure": {"current": 53.0, "previous": 48.0, "change": 5.0},
                "seepage_flow": {"current": 0.20, "previous": 0.35, "change": -0.15},
                ...
            }
        rules: 自定义规则列表（默认使用 PHYSICS_RULES）

    Returns:
        list of dict: [{
            rule_id, rule_name, severity, confidence,
            reason, indicators, changes, suggested_action
        }]
    """
    if rules is None:
        rules = PHYSICS_RULES

    results = []

    for rule in rules:
        # 检查所有必需指标是否都有数据
        indicators = rule["indicators"]
        if not all(ind in indicator_data for ind in indicators):
            continue

        # 构建 changes 字典
        changes = {}
        for ind in indicators:
            data = indicator_data[ind]
            changes[ind] = data.get("change", data.get("current", 0) - data.get("previous", 0))

        # 检查条件
        try:
            if rule["condition"](changes):
                # 格式化原因 — 追加实际数值
                reason = rule["reason"]
                detail_parts = []
                for key, val in changes.items():
                    detail_parts.append(f"{key}={val:+.4f}")
                if detail_parts:
                    reason += f" ({', '.join(detail_parts)})"

                results.append({
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "severity": rule["severity"],
                    "confidence": rule["confidence"],
                    "reason": reason,
                    "indicators": indicators,
                    "changes": {k: round(v, 4) for k, v in changes.items()},
                    "suggested_action": _get_suggested_action(rule["id"]),
                })
        except Exception:
            continue

    return results


def _get_suggested_action(rule_id: str) -> str:
    """根据规则ID返回建议操作"""
    actions = {
        "pressure_flow_contradiction": "检查渗压计和渗流计是否故障，或检查防渗体是否损坏",
        "water_level_seepage_contradiction": "检查水位计和渗流计是否正常，或检查排水设施",
        "rainfall_level_contradiction": "检查水位计是否正常，或确认是否有排水/放水操作",
        "pump_flow_contradiction": "检查泵站是否空转，或流量计是否故障",
        "gate_flow_contradiction": "检查闸门是否漏水，或流量计是否故障",
    }
    return actions.get(rule_id, "建议人工现场核查")


def compute_correlation_coefficient(
    values_a: List[float],
    values_b: List[float],
) -> float:
    """计算两个序列的皮尔逊相关系数

    Args:
        values_a: 序列A
        values_b: 序列B

    Returns:
        float: 相关系数 [-1, 1]
    """
    n = min(len(values_a), len(values_b))
    if n < 3:
        return 0.0

    a = values_a[:n]
    b = values_b[:n]

    mean_a = sum(a) / n
    mean_b = sum(b) / n

    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
    std_a = (sum((x - mean_a) ** 2 for x in a) / n) ** 0.5
    std_b = (sum((x - mean_b) ** 2 for x in b) / n) ** 0.5

    if std_a == 0 or std_b == 0:
        return 0.0

    return cov / (std_a * std_b)


def detect_correlation_break(
    values_a: List[float],
    values_b: List[float],
    window_size: int = 24,
    correlation_threshold: float = 0.5,
) -> List[Dict]:
    """检测相关性突变（两个指标的相关关系突然改变）

    Args:
        values_a: 序列A
        values_b: 序列B
        window_size: 滑动窗口大小
        correlation_threshold: 相关系数变化阈值

    Returns:
        list of dict: [{index, prev_corr, curr_corr, change, is_break}]
    """
    n = min(len(values_a), len(values_b))
    if n < window_size * 2:
        return []

    results = []
    for i in range(window_size, n - window_size):
        prev_corr = compute_correlation_coefficient(
            values_a[i - window_size:i],
            values_b[i - window_size:i],
        )
        curr_corr = compute_correlation_coefficient(
            values_a[i:i + window_size],
            values_b[i:i + window_size],
        )

        change = abs(curr_corr - prev_corr)
        if change > correlation_threshold:
            results.append({
                "index": i,
                "prev_corr": round(prev_corr, 4),
                "curr_corr": round(curr_corr, 4),
                "change": round(change, 4),
                "is_break": True,
                "reason": f"相关系数从{prev_corr:.2f}突变到{curr_corr:.2f}（变化{change:.2f}）",
            })

    return results
