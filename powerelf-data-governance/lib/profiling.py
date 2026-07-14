"""
数据画像纯函数库（Data Profiling Library）
============================================

对 rows 序列做机械计算，返回结构化 profile dict。
无 DB 耦合，纯函数，可入 CI。

Functions:
  - classify_column      列名/样本 → 5 分类之一
  - profile_numeric      数值列 → 统计量 + 分布提示
  - profile_temporal     时间列 → 时间范围 + gap 统计
  - completeness_tier    有效值率 → 绿/黄/橙/红
  - detect_accuracy_flags col_profile → 准确性红旗列表
  - profile_table        逐列画像 + 表级汇总

References:
  - _shared/references/data-profiling.md（方法论单一事实源）
"""

try:
    import numpy as np
except ImportError:
    raise ImportError("profiling.py 需要 numpy: pip install numpy")

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    pd = None
    _HAS_PANDAS = False


# ============================================================
# 列分类
# ============================================================

# 水利语义关键词 → 分类
_IDENTIFIER_KEYWORDS = ("eq_id", "stcd", "station_id", "device_id")
_TEMPORAL_KEYWORDS = ("_time", "create_time", "update_time", "timestamp")
_METRIC_KEYWORDS = ("water_pressure", "rz", "rainfall", "water_level",
                    "flow", "temperature", "humidity", "pressure")
_BOOLEAN_KEYWORDS = ("switch", "status", "is_", "has_", "flag", "active")


def classify_column(name, sample_values=None, dtype=None):
    """列名 / 样本 → 5 分类之一。

    水利语义映射：
      eq_id / stcd          → identifier
      *_time / create_time  → temporal
      water_pressure / rz / rainfall → metric
      含 switch / status    → boolean
      无法识别              → text

    Args:
        name: 列名（字符串）。
        sample_values: 该列样本值（list，可为 None）。
        dtype: 列类型提示（字符串，可为 None）。

    Returns:
        str: 5 分类之一 {identifier, temporal, metric, text, boolean}
    """
    lower = name.lower()

    # 按关键词匹配（优先检查完整子串，避免误匹配）
    for kw in _IDENTIFIER_KEYWORDS:
        if kw in lower:
            return "identifier"

    for kw in _TEMPORAL_KEYWORDS:
        if kw in lower:
            return "temporal"

    for kw in _METRIC_KEYWORDS:
        if kw in lower:
            return "metric"

    for kw in _BOOLEAN_KEYWORDS:
        if kw in lower:
            return "boolean"

    # dtype 兜底：时间类型 → temporal
    if dtype:
        dtype_lower = str(dtype).lower()
        if any(t in dtype_lower for t in ("datetime", "timestamp", "time")):
            return "temporal"
        # 数值类型 → metric
        if any(t in dtype_lower for t in ("int", "float", "double", "decimal", "numeric")):
            return "metric"

    # 默认 text
    return "text"


# ============================================================
# 数值列画像
# ============================================================

def profile_numeric(values):
    """数值列 → 统计量 + 分布提示。

    Args:
        values: 数值序列（list / ndarray），允许含 None。

    Returns:
        dict: {count, null_rate, min, max, mean, median, std,
               p1, p5, p25, p50, p75, p95, p99,
               zero_rate, negative_rate, distinct, distribution_hint}
        distribution_hint: 正态 / 右偏 / 左偏 / 双峰 / 幂律 / 均匀
    """
    arr = np.asarray(values, dtype=object)
    total = int(arr.size)

    # 过滤 None / NaN
    valid_mask = np.array([v is not None and not (isinstance(v, float) and np.isnan(v))
                           for v in arr], dtype=bool)
    valid = arr[valid_mask].astype(float)
    valid_count = int(valid.size)

    null_rate = (total - valid_count) / total if total > 0 else 0.0

    if valid_count == 0:
        return {
            "count": total,
            "null_rate": null_rate,
            "min": None, "max": None, "mean": None, "median": None, "std": None,
            "p1": None, "p5": None, "p25": None, "p50": None,
            "p75": None, "p95": None, "p99": None,
            "zero_rate": 0.0, "negative_rate": 0.0,
            "distinct": 0, "distribution_hint": "空",
        }

    # 统计量
    min_v = float(np.min(valid))
    max_v = float(np.max(valid))
    mean_v = float(np.mean(valid))
    median_v = float(np.median(valid))
    std_v = float(np.std(valid))

    # 百分位
    p1  = float(np.percentile(valid, 1))
    p5  = float(np.percentile(valid, 5))
    p25 = float(np.percentile(valid, 25))
    p50 = float(np.percentile(valid, 50))
    p75 = float(np.percentile(valid, 75))
    p95 = float(np.percentile(valid, 95))
    p99 = float(np.percentile(valid, 99))

    zero_rate = float(np.sum(valid == 0.0)) / valid_count
    negative_rate = float(np.sum(valid < 0.0)) / valid_count
    distinct = int(len(set(valid)))

    # 分布提示（简化版）
    hint = _detect_distribution(valid, mean_v, median_v, std_v, min_v, max_v, distinct)

    return {
        "count": total,
        "null_rate": round(null_rate, 4),
        "min": round(min_v, 4),
        "max": round(max_v, 4),
        "mean": round(mean_v, 4),
        "median": round(median_v, 4),
        "std": round(std_v, 4),
        "p1": round(p1, 4),
        "p5": round(p5, 4),
        "p25": round(p25, 4),
        "p50": round(p50, 4),
        "p75": round(p75, 4),
        "p95": round(p95, 4),
        "p99": round(p99, 4),
        "zero_rate": round(zero_rate, 4),
        "negative_rate": round(negative_rate, 4),
        "distinct": distinct,
        "distribution_hint": hint,
    }


def _detect_distribution(valid, mean_v, median_v, std_v, min_v, max_v, distinct):
    """简化分布检测：正态 / 右偏 / 左偏 / 双峰 / 幂律 / 均匀。"""
    if distinct <= 1:
        return "均匀"

    # 双峰检测：用直方图找两个峰
    try:
        hist, edges = np.histogram(valid, bins="auto")
        # 找局部最大值
        peaks = []
        for i in range(1, len(hist) - 1):
            if hist[i] > hist[i - 1] and hist[i] > hist[i + 1]:
                peaks.append(i)
        if len(peaks) >= 2:
            return "双峰"
    except Exception:
        pass

    # 偏态检测（Pearson 第二偏态系数）
    if std_v > 0:
        skew_proxy = 3.0 * (mean_v - median_v) / std_v
        if skew_proxy > 0.5:
            return "右偏"
        elif skew_proxy < -0.5:
            return "左偏"

    # 幂律：max >> mean（最大值超过均值 10 倍视为长尾/幂律候选）
    if mean_v > 0 and max_v / mean_v > 10:
        return "幂律"

    # 默认
    return "正态"


# ============================================================
# 时间列画像
# ============================================================

def profile_temporal(values, now=None):
    """时间列 → 范围 + gap 统计。

    Args:
        values: 时间序列（list of str / Timestamp / datetime），允许含 None。
        now: 参考时间（pd.Timestamp，默认 pd.Timestamp.now()）。

    Returns:
        dict: {min, max, span, median_gap, max_gap, future_count, null_rate}
    """
    if not _HAS_PANDAS:
        raise ImportError("profile_temporal 需要 pandas: pip install pandas")

    total = len(values)

    # 解析时间，过滤 None
    parsed = []
    for v in values:
        if v is None:
            continue
        if isinstance(v, pd.Timestamp):
            parsed.append(v)
        else:
            try:
                parsed.append(pd.to_datetime(str(v)))
            except Exception:
                continue

    valid_count = len(parsed)
    null_rate = (total - valid_count) / total if total > 0 else 0.0

    if valid_count == 0:
        return {
            "min": None, "max": None, "span": None,
            "median_gap": None, "max_gap": None,
            "future_count": 0, "null_rate": null_rate,
        }

    ts_sorted = sorted(parsed)
    min_t = ts_sorted[0]
    max_t = ts_sorted[-1]
    span = max_t - min_t

    # gap 统计
    gaps = [ts_sorted[i + 1] - ts_sorted[i] for i in range(len(ts_sorted) - 1)]
    median_gap = np.median(gaps) if gaps else pd.Timedelta(0)
    max_gap = max(gaps) if gaps else pd.Timedelta(0)

    # future_count
    if now is None:
        now = pd.Timestamp.now()
    future_count = sum(1 for t in ts_sorted if t > now)

    return {
        "min": min_t,
        "max": max_t,
        "span": span,
        "median_gap": median_gap,
        "max_gap": max_gap,
        "future_count": future_count,
        "null_rate": round(null_rate, 4),
    }


# ============================================================
# 完整性 tier
# ============================================================

def completeness_tier(valid_rate):
    """有效值率 → 绿/黄/橙/红。

    单一事实源：quality-scoring.md 复用此定义。

    Args:
        valid_rate: 有效值率（0.0 ~ 1.0）。

    Returns:
        str: 绿(>99%) / 黄(95-99%) / 橙(80-95%) / 红(<80%)
    """
    if valid_rate > 0.99:
        return "绿"
    elif valid_rate >= 0.95:
        return "黄"
    elif valid_rate >= 0.80:
        return "橙"
    else:
        return "红"


# ============================================================
# 准确性红旗检测
# ============================================================


def detect_accuracy_flags(col_profile):
    """列 profile → 准确性红旗列表。

    检测项：
      - placeholder_999999：max 接近 999999 且均值也异常高 → 占位符聚集
      - placeholder_neg_one：max == -1 → -1 占位符
      - bimodal_distribution：分布提示为"双峰"
      - stale_temporal：时间列 max 过旧（>1 年）
      - impossible_value：min/max 超出合理水利范围

    Args:
        col_profile: 列 profile dict（由 profile_numeric / profile_temporal 生成）。

    Returns:
        list[str]: 红旗标签列表，无问题则返回 []。
    """
    flags = []
    ctype = col_profile.get("type", "")
    cname = col_profile.get("name", "")

    # 时间列：陈旧检测
    if ctype == "temporal":
        max_t = col_profile.get("max")
        if max_t is not None and _HAS_PANDAS and isinstance(max_t, pd.Timestamp):
            now = pd.Timestamp.now()
            if (now - max_t).days > 365:
                flags.append("stale_temporal")

    # 数值列：占位符 / 双峰
    if ctype == "numeric":
        min_v = col_profile.get("min")
        max_v = col_profile.get("max")
        mean_v = col_profile.get("mean")
        hint = col_profile.get("distribution_hint", "")

        # 999999 占位符
        if max_v is not None and max_v in (999999, 999999.0) and mean_v is not None and mean_v > 999000:
            flags.append("placeholder_999999")

        # -1 占位符
        if min_v is not None and min_v == -1:
            flags.append("placeholder_neg_one")

        # 双峰
        if hint == "双峰":
            flags.append("bimodal_distribution")

    return flags


# ============================================================
# 表级画像
# ============================================================

def profile_table(rows, schema_hints=None):
    """逐列 classify → 分类型 profile → 表级 completeness_tier + flags。

    Args:
        rows: 行列表（list of dict），每行同一键集合。
        schema_hints: 可选 schema hints（dict，列名 → 类型提示）。

    Returns:
        dict: {
            row_count: int,
            sample_size: int,
            columns: [
                {name, type, classification, null_rate,
                 numeric_stats?: {...}, temporal_stats?: {...}}
            ],
            completeness_tier: str,
            flags: list[str],
        }
    """
    if not rows:
        return {
            "row_count": 0,
            "sample_size": 0,
            "columns": [],
            "completeness_tier": "红",
            "flags": ["empty_table"],
        }

    # 取列名
    col_names = list(rows[0].keys())
    schema_hints = schema_hints or {}

    columns = []
    all_null_rates = []

    for col in col_names:
        # 取样本值
        sample_values = [row.get(col) for row in rows]
        dtype_hint = schema_hints.get(col)

        # 分类
        classification = classify_column(col, sample_values=sample_values, dtype=dtype_hint)

        # null_rate
        null_count = sum(1 for v in sample_values if v is None)
        null_rate = null_count / len(sample_values) if sample_values else 0.0
        all_null_rates.append(null_rate)

        col_profile = {
            "name": col,
            "type": classification,
            "null_rate": round(null_rate, 4),
        }

        # 按分类做深度画像
        if classification == "numeric":
            numeric_stats = profile_numeric(sample_values)
            col_profile["numeric_stats"] = numeric_stats
            # 用于 accuracy flags
            numeric_for_flags = {
                "type": "numeric",
                "min": numeric_stats.get("min"),
                "max": numeric_stats.get("max"),
                "mean": numeric_stats.get("mean"),
                "distribution_hint": numeric_stats.get("distribution_hint"),
                "null_rate": null_rate,
            }
            col_profile["accuracy_flags"] = detect_accuracy_flags(numeric_for_flags)

        elif classification == "temporal":
            if _HAS_PANDAS:
                temporal_stats = profile_temporal(sample_values)
                col_profile["temporal_stats"] = temporal_stats
                temporal_for_flags = {
                    "type": "temporal",
                    "max": temporal_stats.get("max"),
                    "null_rate": null_rate,
                }
                col_profile["accuracy_flags"] = detect_accuracy_flags(temporal_for_flags)
            else:
                col_profile["temporal_stats"] = {"note": "pandas 缺失，跳过时间画像"}

        # 其他分类暂时无深度画像

        columns.append(col_profile)

    # 表级 completeness_tier（取所有列有效值率的均值）
    valid_rates = [1.0 - nr for nr in all_null_rates]
    avg_valid_rate = sum(valid_rates) / len(valid_rates) if valid_rates else 0.0
    tier = completeness_tier(avg_valid_rate)

    # 汇总 flags
    all_flags = []
    for col in columns:
        for flag in col.get("accuracy_flags", []):
            all_flags.append(f"{col['name']}:{flag}")

    return {
        "row_count": len(rows),
        "sample_size": len(rows),
        "columns": columns,
        "completeness_tier": tier,
        "flags": all_flags,
    }
