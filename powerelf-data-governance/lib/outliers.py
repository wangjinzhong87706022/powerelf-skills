"""
Outlier Detection Module (IQR + Percentile)
============================================

MAD 的互补离群检测方法，针对偏态分布（雨量、流量，零膨胀/长尾）。
MAD 适合正态/缓变指标（水位、GNSS、渗压）；IQR 与百分位法对偏态更稳健。

返回结构对齐 anomaly_detector.detect_anomalies() 的 dict 形态
（含 anomaly_count / anomaly_indices），便于 run_detection 统一格式化。

References:
  - _shared/algorithms/outlier-methods.md（单一事实源）
  - _shared/algorithms/mad.md（姊妹方法）
"""

try:
    import numpy as np
except ImportError:
    raise ImportError("outliers.py 需要 numpy: pip install numpy")


def detect_iqr(values, k=1.5):
    """IQR（四分位距）离群检测，对偏态分布稳健。

    边界: [Q1 - k*IQR, Q3 + k*IQR]，超出即离群。
      k=1.5 标准（温和）；k=3.0 激进（仅标记极端值）。

    Args:
        values: 数值序列（list / ndarray）。
        k: IQR 倍数，默认 1.5。k <= 0 视为非法，回退到 1.5。

    Returns:
        dict: {q1, q3, iqr, lower_bound, upper_bound,
               anomaly_count, anomaly_indices, total_points}
        IQR=0（所有值相同/四分位重合）时 lower=upper=中位水平，判定无离群。
    """
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    if n == 0:
        return {"q1": None, "q3": None, "iqr": 0.0,
                "lower_bound": None, "upper_bound": None,
                "anomaly_count": 0, "anomaly_indices": [], "total_points": 0}
    if k is None or k <= 0:
        k = 1.5

    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr

    if iqr == 0:
        anomaly_indices = []
    else:
        mask = (arr < lower) | (arr > upper)
        anomaly_indices = np.where(mask)[0].tolist()

    return {
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(float(iqr), 4),
        "lower_bound": round(float(lower), 4),
        "upper_bound": round(float(upper), 4),
        "anomaly_count": len(anomaly_indices),
        "anomaly_indices": anomaly_indices,
        "total_points": n,
    }


def detect_percentile(values, low=1, high=99):
    """百分位法离群检测，最简单，适合海量快速筛查。

    边界: [p_low, p_high]，超出即离群。注意：此法总会标记尾部，对非典型分布
    无理论保证，适合快速筛查而非精确定量。

    Args:
        values: 数值序列。
        low: 下尾百分位（默认 1 -> p1）。
        high: 上尾百分位（默认 99 -> p99）。

    Returns:
        dict: {low_bound, high_bound, anomaly_count, anomaly_indices, total_points}
    """
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    if n == 0:
        return {"low_bound": None, "high_bound": None,
                "anomaly_count": 0, "anomaly_indices": [], "total_points": 0}

    low = 0.0 if low is None else float(low)
    high = 100.0 if high is None else float(high)
    low = max(0.0, min(low, 100.0))
    high = max(0.0, min(high, 100.0))
    if low >= high:
        low, high = 1.0, 99.0

    low_bound = float(np.percentile(arr, low))
    high_bound = float(np.percentile(arr, high))

    mask = (arr < low_bound) | (arr > high_bound)
    anomaly_indices = np.where(mask)[0].tolist()

    return {
        "low_bound": round(low_bound, 4),
        "high_bound": round(high_bound, 4),
        "anomaly_count": len(anomaly_indices),
        "anomaly_indices": anomaly_indices,
        "total_points": n,
    }
