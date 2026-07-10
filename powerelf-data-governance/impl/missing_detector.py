#!/usr/bin/env python3
"""
缺失检测算子（基于 lib/missing.py）
直接调用，Agent 不需要自己写 SQL 或理解算法细节。

用法:
  python3 missing_detector.py --db "$DB_URL" \
    --table st_rsvr_r --st-id 128 --freq 60

  python3 missing_detector.py --db "..." --table st_pptn_r --days 7

输出: JSON 格式的检测结果。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

ALLOWED_TABLES = frozenset({
    "st_rsvr_r", "st_river_r", "st_pptn_r", "st_pressure_r",
    "st_percolation_r", "st_deformation_r", "st_gnss_r",
    "st_seepage_r", "st_rain_r", "st_wind_r", "st_temp_r",
    "st_strlevel_r", "st_strain_r", "st_tilt_r",
    "st_environment_r",
})
ALLOWED_TIME_FIELDS = frozenset({"tm", "time", "timestamp", "collect_time"})

try:
    import pandas as pd
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("需要安装: pip install pandas sqlalchemy pymysql")
    sys.exit(1)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.missing import detect_missing, classify_consecutive_missing, detect_missing_pattern


DEFAULT_FREQ = {
    "st_rsvr_r": 60,
    "st_river_r": 60,
    "st_pptn_r": 60,
    "st_pressure_r": 60,
    "st_percolation_r": 60,
}


def load_collect_times(engine, table, st_id=None, days=1, time_field="tm"):
    """从数据库加载采集时间列表"""
    if table not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    if time_field not in ALLOWED_TIME_FIELDS:
        raise ValueError(f"非法时间字段: {time_field}")
    where_parts = [f"{time_field} >= NOW()-INTERVAL :days DAY"]
    params = {"days": days}
    if st_id:
        where_parts.append("st_id = :st_id")
        params["st_id"] = st_id
    where = " AND ".join(where_parts)
    sql = f"SELECT {time_field} FROM {table} WHERE {where} ORDER BY {time_field} ASC"
    try:
        df = pd.read_sql(text(sql), engine, params=params)
        return df[time_field].tolist() if not df.empty else []
    except Exception:
        return []


def run_detection(engine, table, st_id=None, days=1, freq=None):
    """执行完整的缺失检测流程"""
    if freq is None:
        freq = DEFAULT_FREQ.get(table, 60)

    now = datetime.now()
    start_time = now - timedelta(days=days)

    collect_times = load_collect_times(engine, table, st_id, days)
    expected_count = int((now - start_time).total_seconds() / 60 / freq)
    expected_count = max(expected_count, 1)

    result = detect_missing(expected_count, len(collect_times), freq)
    missing_periods = result["missing_periods"]
    missing_rate = result["missing_rate"]

    severity = classify_consecutive_missing(missing_periods)

    pattern = detect_missing_pattern(collect_times)

    return {
        "status": "OK" if missing_periods == 0 else "MISSING_FOUND",
        "table": table,
        "st_id": st_id,
        "days": days,
        "frequency_min": freq,
        "expected_count": expected_count,
        "actual_count": len(collect_times),
        "missing_periods": missing_periods,
        "missing_rate": f"{missing_rate:.2%}",
        "severity": severity,
        "pattern": pattern,
        "explanation": (
            f"表 {table} 检测: 期望{expected_count}条, 实际{len(collect_times)}条, "
            f"缺失{missing_periods}条({missing_rate:.2%}), "
            f"严重级别: {severity}, 缺失模式: {pattern}"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="缺失检测算子")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--st-id", type=int, default=None, help="测站ID")
    parser.add_argument("--days", type=int, default=1, help="检测天数")
    parser.add_argument("--freq", type=int, default=None, help="采集频率(分钟)")
    args = parser.parse_args()

    engine = create_engine(args.db)
    result = run_detection(engine, args.table, args.st_id, args.days, args.freq)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
