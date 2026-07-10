#!/usr/bin/env python3
"""
MAD 异常检测算子（基于 rules/anomaly-detection.md）
直接调用，Agent 不需要自己写 SQL 或理解算法细节。

用法:
  python3 anomaly_detector.py --db "$DB_URL" \
    --table st_pressure_r --field water_pressure --threshold 4.0

  python3 anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --threshold 3.0 --st-id 128

  python3 anomaly_detector.py --db "$DB_URL" --table st_pptn_r --field p --threshold 5.0 --days 7

输出: JSON 格式的检测结果，包含 median, MAD, z_score, 异常点列表, 判定依据。
"""

import argparse
import json
import sys
from datetime import datetime

try:
    import pandas as pd
    import numpy as np
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("需要安装: pip install pandas numpy sqlalchemy pymysql")
    sys.exit(1)


# ============================================================
# 分指标默认阈值（来自 rules/anomaly-detection.md）
# ============================================================

DEFAULT_THRESHOLDS = {
    "rz": 3.0,           # 水位
    "z": 3.0,            # 河道水位
    "p": 5.0,            # 雨量
    "water_pressure": 4.0,  # 渗压
    "ext_pressure": 4.0,    # 渗压(外部)
    "percolation": 4.0,     # 渗流
    "wgs84_delta_h": 3.5,   # GNSS位移
    "inq": 4.0,            # 入库流量
    "otq": 4.0,            # 出库流量
}

# 变化率阈值
CHANGE_RATE_THRESHOLDS = {
    "rz": 0.05,           # 水位 5%
    "water_pressure": 0.03,  # 渗压 3%
    "wgs84_delta_h": 0.02,   # GNSS 2%
    "inq": 0.10,            # 流量 10%
    "otq": 0.10,
}

ALLOWED_TABLES = frozenset({
    "st_rsvr_r", "st_river_r", "st_pptn_r", "st_pressure_r",
    "st_percolation_r", "st_deformation_r", "st_gnss_r",
    "st_seepage_r", "st_rain_r", "st_wind_r", "st_temp_r",
    "st_strlevel_r", "st_strain_r", "st_tilt_r",
    "st_environment_r",
})
ALLOWED_FIELDS = frozenset({
    "rz", "z", "p", "water_pressure", "ext_pressure",
    "percolation", "wgs84_delta_h", "inq", "otq",
    "temperature", "humidity", "wind_speed", "wind_direction",
    "strain", "tilt_x", "tilt_y", "displacement",
})
ALLOWED_TIME_FIELDS = frozenset({"tm", "time", "timestamp", "collect_time"})


def load_data(engine, table, field, st_id=None, days=30, time_field="tm"):
    """从数据库加载传感器数据"""
    if table not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table} (不在允许列表中)")
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"非法字段名: {field} (不在允许列表中)")
    if time_field not in ALLOWED_TIME_FIELDS:
        raise ValueError(f"非法时间字段: {time_field}")
    where_parts = [f"{time_field} >= NOW()-INTERVAL :days DAY"]
    params = {"days": days}
    if st_id:
        where_parts.append("st_id = :st_id")
        params["st_id"] = st_id
    where = " AND ".join(where_parts)
    sql = f"SELECT {field}, {time_field} FROM {table} WHERE {where} ORDER BY {time_field} DESC LIMIT 20000"
    try:
        df = pd.read_sql(text(sql), engine, params=params)
        return df
    except Exception as e:
        return pd.DataFrame()


def compute_mad(values):
    """计算 MAD (Median Absolute Deviation)"""
    median = np.median(values)
    abs_devs = np.abs(values - median)
    mad = np.median(abs_devs) * 1.4826  # 归一化因子
    return median, mad


def detect_anomalies(values, threshold):
    """对数据序列做 MAD 异常检测"""
    median, mad = compute_mad(values)

    if mad == 0:
        # MAD=0 时退化为与中位数的绝对差判断
        anomalies = [i for i, v in enumerate(values) if abs(v - median) > 0]
        z_scores = [0.0] * len(values)
    else:
        z_scores = [0.6745 * abs(v - median) / mad for v in values]
        anomalies = [i for i, z in enumerate(z_scores) if z > threshold]

    return {
        "median": round(float(median), 4),
        "mad": round(float(mad), 4),
        "z_scores": [round(z, 4) for z in z_scores],
        "anomaly_indices": anomalies,
        "anomaly_count": len(anomalies),
        "total_points": len(values),
    }


def detect_change_rate(values, field):
    """变化率检测"""
    threshold = CHANGE_RATE_THRESHOLDS.get(field, 0.10)
    changes = []
    for i in range(1, len(values)):
        prev = values[i-1]
        curr = values[i]
        if prev != 0:
            rate = abs(curr - prev) / abs(prev)
            if rate > threshold:
                changes.append({
                    "index": i,
                    "prev": round(float(prev), 4),
                    "curr": round(float(curr), 4),
                    "rate": round(float(rate), 4),
                    "threshold": threshold,
                })
    return changes


def comprehensive_judge(mad_result, change_rate_result, threshold):
    """综合判定（MAD + 变化率交叉验证）"""
    has_mad_anomaly = mad_result["anomaly_count"] > 0
    has_rate_anomaly = len(change_rate_result) > 0

    if has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "CRITICAL",
            "confidence": "high",
            "message": "MAD异常 + 变化率超标，确认异常",
        }
    elif has_mad_anomaly and not has_rate_anomaly:
        return {
            "level": "WARNING",
            "confidence": "medium",
            "message": "MAD异常但变化率正常，可能异常，检查是否为正常波动峰值",
        }
    elif not has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "INFO",
            "confidence": "low",
            "message": "MAD正常但变化率超标，可疑，标记待人工确认",
        }
    else:
        return {
            "level": "OK",
            "confidence": "high",
            "message": "MAD正常且变化率正常，数据在历史分布范围内",
        }


def run_detection(engine, table, field, threshold=None, st_id=None, days=30):
    """执行完整的 MAD 异常检测流程"""

    # 默认阈值
    if threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(field, 4.0)

    # 加载数据
    df = load_data(engine, table, field, st_id, days)
    if df.empty:
        return {
            "status": "NO_DATA",
            "message": f"表 {table} 无数据（st_id={st_id}, days={days}）",
        }

    clean_series = pd.to_numeric(df[field], errors='coerce').dropna()
    values = clean_series.values
    if len(values) < 10:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"数据点不足: {len(values)}个（需要至少10个）",
            "data_points": len(values),
        }

    # MAD 检测
    mad_result = detect_anomalies(values, threshold)

    # 变化率检测
    change_rate_result = detect_change_rate(values, field)

    # 综合判定
    judgment = comprehensive_judge(mad_result, change_rate_result, threshold)

    # 构建异常点详情
    tm_cols = [c for c in df.columns if c != field]
    tm_col = tm_cols[0] if tm_cols else None
    anomaly_details = []
    for idx in mad_result["anomaly_indices"]:
        original_idx = clean_series.index[idx]
        detail = {
            "index": int(original_idx),
            "value": round(float(values[idx]), 4),
            "z_score": mad_result["z_scores"][idx],
        }
        if tm_col and original_idx in df.index:
            detail["time"] = str(df.loc[original_idx, tm_col])
        anomaly_details.append(detail)

    # 解释集
    explanation = (
        f"对 {table}.{field} 做 MAD 异常检测: "
        f"数据点{mad_result['total_points']}个, "
        f"中位数{mad_result['median']}, "
        f"MAD={mad_result['mad']}, "
        f"阈值={threshold}, "
        f"发现{mad_result['anomaly_count']}个异常点。"
        f"综合判定: {judgment['message']} (置信度{judgment['confidence']})"
    )

    return {
        "status": "OK",
        "table": table,
        "field": field,
        "st_id": st_id,
        "days": days,
        "threshold": threshold,
        "data_points": mad_result["total_points"],
        "mad_analysis": {
            "median": mad_result["median"],
            "mad": mad_result["mad"],
            "anomaly_count": mad_result["anomaly_count"],
            "anomaly_rate": f"{mad_result['anomaly_count']/mad_result['total_points']*100:.1f}%",
        },
        "change_rate_analysis": {
            "exceed_count": len(change_rate_result),
            "threshold": CHANGE_RATE_THRESHOLDS.get(field, 0.10),
            "exceed_details": change_rate_result[:5],  # 最多5条
        },
        "judgment": judgment,
        "anomaly_details": anomaly_details[:10],  # 最多10条
        "explanation": explanation,
    }


def main():
    parser = argparse.ArgumentParser(description="MAD 异常检测算子")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--field", required=True, help="检测字段名")
    parser.add_argument("--threshold", type=float, default=None, help="MAD阈值（默认按字段自动选择）")
    parser.add_argument("--st-id", type=int, default=None, help="测站ID")
    parser.add_argument("--days", type=int, default=30, help="检测天数")
    args = parser.parse_args()

    engine = create_engine(args.db)
    result = run_detection(engine, args.table, args.field, args.threshold, args.st_id, args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
