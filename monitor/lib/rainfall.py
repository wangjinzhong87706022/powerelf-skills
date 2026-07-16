"""Rainfall analysis module: intensity, classification, cumulative trend, validation."""


def rainfall_intensity(p_mm, dr_min):
    """Calculate rainfall intensity in mm/h.

    p_mm: rainfall amount in mm for the period.
    dr_min: duration of the period in MINUTES.
    Returns intensity in mm/h, or None if dr_min is None or 0.
    """
    if dr_min is None or dr_min == 0:
        return None
    if p_mm is None:
        return None
    return p_mm / (dr_min / 60)


def classify_intensity(intensity):
    """Classify rainfall by hourly intensity.

    Returns level name: '小雨', '中雨', '大雨', '暴雨', '大暴雨', '特大暴雨', or '无降雨'.
    Based on standard hourly intensity thresholds.
    """
    if intensity is None or intensity <= 0:
        return "无降雨"
    if intensity > 30:
        return "特大暴雨"
    if intensity > 16:
        return "大暴雨"
    if intensity > 8:
        return "暴雨"
    if intensity > 2.5:
        return "大雨"
    if intensity > 0.5:
        return "中雨"
    return "小雨"


def classify_24h_rainfall(dyp_mm):
    """Classify rainfall by 24-hour cumulative amount.

    Returns level name based on standard 24h thresholds:
    <0.1 无降雨, 0.1-9.9 小雨, 10-24.9 中雨, 25-49.9 大雨,
    50-99.9 暴雨, 100-249.9 大暴雨, >=250 特大暴雨.
    """
    if dyp_mm is None or dyp_mm < 0.1:
        return "无降雨"
    if dyp_mm >= 250:
        return "特大暴雨"
    if dyp_mm >= 100:
        return "大暴雨"
    if dyp_mm >= 50:
        return "暴雨"
    if dyp_mm >= 25:
        return "大雨"
    if dyp_mm >= 10:
        return "中雨"
    return "小雨"


def cumulative_trend(daily_values, days=3):
    """Check cumulative rainfall trend for alert conditions.

    daily_values: list of daily rainfall amounts (most recent first).
    days: number of days to sum (3 or 7).
    Returns a dict with cumulative (float) and is_alert (bool).
    Alert if 3-day total > 100mm or 7-day total > 200mm.
    """
    if not daily_values:
        return {"cumulative": 0.0, "is_alert": False}

    subset = daily_values[:days]
    total = sum(v for v in subset if v is not None)

    is_alert = False
    if days >= 7 and total > 200:
        is_alert = True
    elif days >= 3 and total > 100:
        is_alert = True

    return {"cumulative": round(total, 2), "is_alert": is_alert}


def validate_rainfall(p, dr, dyp):
    """Validate rainfall data for anomalies.

    p: period rainfall (mm).
    dr: duration (minutes).
    dyp: daily rainfall (mm).
    Returns a list of issue strings. Empty list means no issues.
    """
    issues = []

    if p is not None and p < 0:
        issues.append("时段雨量为负")

    if dr is not None and dr == 0 and p is not None and p > 0:
        issues.append("时段为0但有雨量，数据异常")

    if p is not None and dr is not None and dr >= 50 and p > 200:
        issues.append(f"单小时雨量 {p}mm > 200mm，数据异常或极端天气")

    if dyp is not None and dyp < 0:
        issues.append("日雨量为负")

    return issues
