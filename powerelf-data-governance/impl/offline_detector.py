#!/usr/bin/env python3
"""
离线检测算子（基于 lib/offline.py）
直接调用，Agent 不需要自己写 SQL 或理解算法细节。

用法:
  python3 offline_detector.py --db "$DB_URL" \
    --table st_rsvr_r --st-id 128 --threshold 360

  python3 offline_detector.py --db "..." --table st_pressure_r --st-id 201

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
from lib.offline import determine_status, progressive_alert, classify_offline_duration


DEFAULT_THRESHOLDS = {
    "SP": 360,
    "GN": 60,
    "EL": 60,
    "ZS": 60,
    "WQ": 60,
    "PP": 60,
    "DP": 60,
    "DD": 60,
    "YZ": 60,
}


def load_latest_time(engine, table, st_id=None, time_field="tm"):
    """加载设备最新采集时间"""
    if table not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    if time_field not in ALLOWED_TIME_FIELDS:
        raise ValueError(f"非法时间字段: {time_field}")
    where = ""
    params = {}
    if st_id:
        where = "WHERE st_id = :st_id"
        params["st_id"] = st_id
    sql = f"SELECT MAX({time_field}) AS latest FROM {table} {where}"
    try:
        df = pd.read_sql(text(sql), engine, params=params)
        return df.iloc[0]["latest"] if not df.empty else None
    except Exception:
        return None


def run_detection(engine, table, st_id=None, threshold=None):
    """执行离线检测"""
    now = datetime.now()
    latest = load_latest_time(engine, table, st_id)
    if latest is None:
        return {
            "status": "NO_DATA",
            "table": table,
            "st_id": st_id,
            "message": "无数据记录",
        }

    if isinstance(latest, str):
        latest = datetime.fromisoformat(latest)

    if threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(table, 60)

    offline_status = determine_status(latest, threshold, now)
    deadline = latest + timedelta(minutes=threshold)
    alert = progressive_alert(deadline, threshold, now)

    offline_hours = 0
    if offline_status == "OFFLINE":
        offline_hours = (now - latest).total_seconds() / 3600
    severity = classify_offline_duration(offline_hours)

    return {
        "status": offline_status,
        "table": table,
        "st_id": st_id,
        "threshold_minutes": threshold,
        "latest_record": str(latest),
        "deadline": str(deadline),
        "offline_hours": round(offline_hours, 2),
        "severity": severity,
        "alert": alert,
        "explanation": (
            f"设备(st_id={st_id})最新记录: {latest}, "
            f"阈值: {threshold}分钟, "
            f"状态: {offline_status}, "
            f"离线时长: {offline_hours:.1f}h, "
            f"严重级别: {severity}"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="离线检测算子")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--st-id", type=int, default=None, help="测站ID")
    parser.add_argument("--threshold", type=int, default=None, help="离线阈值(分钟)")
    args = parser.parse_args()

    engine = create_engine(args.db)
    result = run_detection(engine, args.table, args.st_id, args.threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
