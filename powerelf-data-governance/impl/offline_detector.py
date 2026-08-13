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

# 监测表白名单（应与 _shared/lib/db.py::ALLOWED_TABLES 单一事实源一致；
# 删除 schema.md 不存在的 10 个幽灵表名，补 GNSS 实表 dsm_dfr_srvrds_srhrds）
ALLOWED_TABLES = frozenset({
    "st_rsvr_r", "st_river_r", "st_pptn_r",
    "st_pressure_r", "st_percolation_r",
    "dsm_dfr_srvrds_srhrds",
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

# 表名 → 主站类型兜底映射（st_id 查不到 st_type 时用）
_TABLE_TO_STYPE = {
    "st_rsvr_r": "RR",
    "st_river_r": "ZZ",
    "st_pptn_r": "PP",
    "st_pressure_r": "YZ",
    "st_percolation_r": "YZ",
    "dsm_dfr_srvrds_srhrds": "GN",
    "rei_gate_r": "DD",
    "rei_pump_r": "DP",
}


def _lookup_st_type(engine, table, st_id):
    """st_id → eq_business_equip_relation.st_type。
    Why: 阈值按站类型配置（dg_equip_offline），需先解析设备所属站类型（评审 §6.1）。
    """
    if st_id is None:
        return None
    try:
        df = pd.read_sql(text(
            "SELECT st_type FROM eq_business_equip_relation "
            "WHERE st_id = :st_id LIMIT 1"
        ), engine, params={"st_id": st_id})
        return str(df.iloc[0]["st_type"]) if not df.empty else None
    except Exception:
        return None


def _lookup_dg_offline(engine, st_type):
    """st_type → dg_equip_offline.tm（离线阈值分钟；varchar 转 int）。
    Why: dg_equip_offline 是离线阈值配置的单一事实源（SP=360/PP=120/YZ=0…）。
    """
    try:
        df = pd.read_sql(text(
            "SELECT tm FROM dg_equip_offline "
            "WHERE st_type = :st_type AND deleted = 0 LIMIT 1"
        ), engine, params={"st_type": st_type})
        if df.empty or df.iloc[0]["tm"] is None:
            return None
        return int(str(df.iloc[0]["tm"]).strip())
    except Exception:
        return None


def resolve_threshold(engine, table, st_id, default=60):
    """按站类型从 dg_equip_offline 读离线阈值。
    解析链：st_id → eq_business_equip_relation.st_type → dg_equip_offline.tm
    → 回退 DEFAULT_THRESHOLDS[st_type] → 再回退 default。
    返回 0 表示该站类型配置为"不检测"（YZ 类）。
    Why: 旧代码 .get(table, 60) 键是站类型却查表名，配置从未生效（评审 §6.1）。
    """
    st_type = _lookup_st_type(engine, table, st_id)
    if st_type is None:
        st_type = _TABLE_TO_STYPE.get(table)
    if st_type:
        configured = _lookup_dg_offline(engine, st_type)
        if configured is not None:
            return configured
        if st_type in DEFAULT_THRESHOLDS:
            return DEFAULT_THRESHOLDS[st_type]
    return default


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
        threshold = resolve_threshold(engine, table, st_id)

    # YZ=0 短路：站类型配置为"不检测"时，不再按 0 分钟判离线（T3）
    if threshold == 0:
        return {
            "status": "NOT_MONITORED",
            "table": table,
            "st_id": st_id,
            "threshold_minutes": 0,
            "message": "该站类型离线阈值配置为 0（不检测）",
            "explanation": f"设备(st_id={st_id}) 站类型离线阈值=0，按配置不检测",
        }

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
