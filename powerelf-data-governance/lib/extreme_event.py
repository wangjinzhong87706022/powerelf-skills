"""
极端事件区分模块 — 区分真实极端事件和数据异常

极端事件（如汛期高水位）会被 MAD 标记为异常，但实际上是合法的。
本模块通过多维度判断来区分两者。
"""

from typing import List, Dict, Optional
from datetime import datetime
import math


def classify_extreme_event(
    value: float,
    indicator_type: str,
    timestamp: datetime,
    historical_stats: Optional[Dict] = None,
    rainfall_data: Optional[List[float]] = None,
) -> Dict:
    """判断一个被 MAD 标记的异常值是否为极端事件

    Args:
        value: 被标记的异常值
        indicator_type: 指标类型 (water_level/rainfall/seepage/pressure/gnss)
        timestamp: 数据时间
        historical_stats: 历史统计 {min, max, mean, std, p95, p99}
        rainfall_data: 同期降雨数据（用于水位异常判断）

    Returns:
        dict: {
            is_extreme: bool,           # 是否为极端事件
            confidence: float,          # 置信度 0-1
            reason: str,                # 判断理由
            suggested_action: str,      # 建议操作
        }
    """
    result = {
        "is_extreme": False,
        "confidence": 0.0,
        "reason": "",
        "suggested_action": "标记为数据异常，建议修复",
    }

    month = timestamp.month
    hour = timestamp.hour

    # ===== 规则1: 汛期水位判断 =====
    if indicator_type == "water_level":
        is_flood_season = month in [5, 6, 7, 8, 9]  # 5月也算汛前期
        has_rainfall_support = False

        if rainfall_data:
            # 检查近24小时是否有显著降雨
            recent_rainfall = sum(rainfall_data[-24:]) if len(rainfall_data) >= 24 else sum(rainfall_data)
            has_rainfall_support = recent_rainfall > 20  # 24小时累计>20mm

        if is_flood_season and has_rainfall_support:
            result["is_extreme"] = True
            result["confidence"] = 0.85
            result["reason"] = f"汛期({month}月)且有降雨支撑(近24h累计{recent_rainfall:.1f}mm)"
            result["suggested_action"] = "标记为极端天气事件，不触发修复，记录备案"

        elif is_flood_season:
            result["is_extreme"] = True
            result["confidence"] = 0.6
            result["reason"] = f"汛期({month}月)，但无降雨数据支撑"
            result["suggested_action"] = "建议人工确认，检查是否有上游来水"

        elif historical_stats and value > historical_stats.get("p99", float("inf")):
            result["is_extreme"] = True
            result["confidence"] = 0.7
            result["reason"] = f"超过历史99分位数({historical_stats['p99']:.2f})"
            result["suggested_action"] = "建议人工确认，可能是极端天气事件"

        # 高水位但不在汛期，也可能是极端事件
        if not result["is_extreme"] and historical_stats:
            if value > historical_stats.get("mean", 0) + 3 * historical_stats.get("std", 1):
                result["is_extreme"] = True
                result["confidence"] = 0.5
                result["reason"] = f"水位超过均值3σ({value:.2f}m vs 均值{historical_stats['mean']:.2f}m)"
                result["suggested_action"] = "建议人工确认"

    # ===== 规则2: 降雨极端值 =====
    elif indicator_type == "rainfall":
        # 24小时降雨量分级
        if value >= 250:
            result["is_extreme"] = True
            result["confidence"] = 0.95
            result["reason"] = "特大暴雨(≥250mm/24h)，国标GB/T 28592-2012"
            result["suggested_action"] = "记录为极端天气事件，触发防汛响应"
        elif value >= 100:
            result["is_extreme"] = True
            result["confidence"] = 0.9
            result["reason"] = "大暴雨(100-249mm/24h)"
            result["suggested_action"] = "记录为极端天气事件"
        elif value >= 50:
            # 暴雨，看是否在汛期
            if month in [6, 7, 8, 9]:
                result["is_extreme"] = True
                result["confidence"] = 0.7
                result["reason"] = f"汛期暴雨({value:.1f}mm/24h)"
                result["suggested_action"] = "记录为汛期降雨事件"

    # ===== 规则3: 渗压/渗流关联判断 =====
    elif indicator_type in ["seepage_pressure", "seepage_flow"]:
        # 单独的渗压/渗流异常需要结合其他指标判断
        # 具体逻辑在 correlation.py 中实现
        result["reason"] = "渗压/渗流异常需结合相关性分析判断"
        result["suggested_action"] = "结合渗压+渗流相关性分析"

    # ===== 规则4: GNSS 位移 =====
    elif indicator_type == "gnss":
        # GNSS 位移通常不会出现"极端但合法"的情况
        # 除非是地震等极端事件
        if historical_stats and abs(value) > historical_stats.get("p99", float("inf")) * 3:
            result["is_extreme"] = True
            result["confidence"] = 0.5
            result["reason"] = "位移量超过历史99分位数3倍，可能是地震等极端事件"
            result["suggested_action"] = "建议人工确认，检查是否有地震等外部因素"

    # ===== 规则5: 时间维度判断 =====
    # 凌晨2-4点的异常更可能是传感器故障（维护窗口）
    if hour in [2, 3, 4] and not result["is_extreme"]:
        result["confidence"] = max(result["confidence"], 0.3)
        result["reason"] += "（凌晨时段，可能是维护窗口）"

    return result


def build_seasonal_baseline(
    values: List[float],
    timestamps: List[datetime],
    method: str = "monthly",
) -> Dict[str, Dict]:
    """构建季节性基线

    Args:
        values: 历史数据序列
        timestamps: 时间戳序列
        method: 分组方法 ("monthly"/"hourly"/"monthly_hourly")

    Returns:
        dict: {group_key: {mean, std, min, max, p5, p95, count}}
    """
    groups = {}
    for val, ts in zip(values, timestamps):
        if method == "monthly":
            key = f"{ts.month:02d}"
        elif method == "hourly":
            key = f"{ts.hour:02d}"
        elif method == "monthly_hourly":
            key = f"{ts.month:02d}_{ts.hour:02d}"
        else:
            key = "all"

        groups.setdefault(key, []).append(val)

    baselines = {}
    for key, vals in groups.items():
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        mean_val = sum(vals) / n
        variance = sum((x - mean_val) ** 2 for x in vals) / n
        std_val = variance ** 0.5
        p5_idx = max(0, int(n * 0.05))
        p95_idx = min(n - 1, int(n * 0.95))

        baselines[key] = {
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "min": vals_sorted[0],
            "max": vals_sorted[-1],
            "p5": vals_sorted[p5_idx],
            "p95": vals_sorted[p95_idx],
            "count": n,
        }

    return baselines


def check_against_baseline(
    value: float,
    timestamp: datetime,
    baselines: Dict[str, Dict],
    method: str = "monthly",
    sigma_threshold: float = 3.0,
) -> Dict:
    """检查值是否超出季节性基线

    Args:
        value: 待检查的值
        timestamp: 时间戳
        baselines: build_seasonal_baseline 的输出
        method: 分组方法
        sigma_threshold: 标准差倍数阈值

    Returns:
        dict: {
            is_outlier: bool,
            group: str,
            baseline_mean: float,
            baseline_std: float,
            deviation_sigma: float,
            reason: str,
        }
    """
    if method == "monthly":
        key = f"{timestamp.month:02d}"
    elif method == "hourly":
        key = f"{timestamp.hour:02d}"
    elif method == "monthly_hourly":
        key = f"{timestamp.month:02d}_{timestamp.hour:02d}"
    else:
        key = "all"

    if key not in baselines:
        return {
            "is_outlier": False,
            "group": key,
            "reason": f"无基线数据(分组={key})",
        }

    baseline = baselines[key]
    mean_val = baseline["mean"]
    std_val = baseline["std"]

    if std_val == 0:
        deviation = 0
    else:
        deviation = abs(value - mean_val) / std_val

    return {
        "is_outlier": deviation > sigma_threshold,
        "group": key,
        "baseline_mean": mean_val,
        "baseline_std": std_val,
        "deviation_sigma": round(deviation, 2),
        "reason": f"偏离基线{deviation:.1f}σ (基线均值={mean_val:.2f}, 标准差={std_val:.2f})" if deviation > sigma_threshold else "在基线范围内",
    }
