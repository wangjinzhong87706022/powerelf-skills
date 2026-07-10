"""
卡滞检测模块 — 检测传感器连续输出相同值的异常

卡滞（Stagnation）：传感器硬件故障导致采集卡死在某一固定值。
MAD 无法检测此类异常（方差为0，不偏离中位数）。
"""

from typing import List, Dict, Optional
from datetime import datetime


def detect_stagnation(
    values: List[float],
    timestamps: Optional[List[datetime]] = None,
    min_consecutive: int = 3,
    tolerance: float = 1e-6,
) -> List[Dict]:
    """检测连续相同值（卡滞）

    Args:
        values: 数值序列
        timestamps: 时间戳序列（可选，用于输出）
        min_consecutive: 最小连续次数阈值（默认3）
        tolerance: 浮点比较容差（默认1e-6）

    Returns:
        list of dict: [{start_idx, end_idx, value, count, start_time, end_time}]
    """
    if not values or len(values) < min_consecutive:
        return []

    results = []
    start_idx = 0
    count = 1

    for i in range(1, len(values)):
        if abs(values[i] - values[start_idx]) <= tolerance:
            count += 1
        else:
            if count >= min_consecutive:
                entry = {
                    "start_idx": start_idx,
                    "end_idx": start_idx + count - 1,
                    "value": values[start_idx],
                    "count": count,
                }
                if timestamps:
                    entry["start_time"] = timestamps[start_idx]
                    entry["end_time"] = timestamps[start_idx + count - 1]
                results.append(entry)
            start_idx = i
            count = 1

    # 处理最后一段
    if count >= min_consecutive:
        entry = {
            "start_idx": start_idx,
            "end_idx": start_idx + count - 1,
            "value": values[start_idx],
            "count": count,
        }
        if timestamps:
            entry["start_time"] = timestamps[start_idx]
            entry["end_time"] = timestamps[start_idx + count - 1]
        results.append(entry)

    return results


def detect_near_stagnation(
    values: List[float],
    timestamps: Optional[List[datetime]] = None,
    min_consecutive: int = 5,
    max_variation: float = 0.01,
) -> List[Dict]:
    """检测近似卡滞（值在极小范围内波动）

    Args:
        values: 数值序列
        timestamps: 时间戳序列（可选）
        min_consecutive: 最小连续次数阈值
        max_variation: 最大允许变异系数（相对于均值的比例）

    Returns:
        list of dict: [{start_idx, end_idx, mean_value, cv, count}]
    """
    if not values or len(values) < min_consecutive:
        return []

    results = []
    start_idx = 0

    for i in range(1, len(values)):
        window = values[start_idx:i + 1]
        mean_val = sum(window) / len(window)
        if mean_val == 0:
            cv = 0
        else:
            variance = sum((x - mean_val) ** 2 for x in window) / len(window)
            cv = (variance ** 0.5) / abs(mean_val)

        if cv > max_variation:
            # 波动超过阈值，结束当前窗口
            if i - start_idx >= min_consecutive:
                window = values[start_idx:i]
                mean_val = sum(window) / len(window)
                variance = sum((x - mean_val) ** 2 for x in window) / len(window)
                cv = (variance ** 0.5) / abs(mean_val) if mean_val != 0 else 0
                entry = {
                    "start_idx": start_idx,
                    "end_idx": i - 1,
                    "mean_value": round(mean_val, 4),
                    "cv": round(cv, 6),
                    "count": i - start_idx,
                }
                if timestamps:
                    entry["start_time"] = timestamps[start_idx]
                    entry["end_time"] = timestamps[i - 1]
                results.append(entry)
            start_idx = i

    # 处理最后一段
    if len(values) - start_idx >= min_consecutive:
        window = values[start_idx:]
        mean_val = sum(window) / len(window)
        variance = sum((x - mean_val) ** 2 for x in window) / len(window)
        cv = (variance ** 0.5) / abs(mean_val) if mean_val != 0 else 0
        if cv <= max_variation:
            entry = {
                "start_idx": start_idx,
                "end_idx": len(values) - 1,
                "mean_value": round(mean_val, 4),
                "cv": round(cv, 6),
                "count": len(values) - start_idx,
            }
            if timestamps:
                entry["start_time"] = timestamps[start_idx]
                entry["end_time"] = timestamps[-1]
            results.append(entry)

    return results


def classify_stagnation(count: int) -> str:
    """根据卡持续续时长分级

    Args:
        count: 连续相同值的次数

    Returns:
        str: 等级 (INFO/WARNING/ERROR/CRITICAL)
    """
    if count <= 2:
        return "INFO"
    elif count <= 6:
        return "WARNING"
    elif count <= 24:
        return "ERROR"
    else:
        return "CRITICAL"
