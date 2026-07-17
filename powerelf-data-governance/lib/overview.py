"""一次性数据治理概览（One-shot Overview）
============================================

取代"逐表试探 N 步"的入口脚本。一次连接即给出全貌，避免 7/16 那样
22 次往返还卡在 schema 不一致上的死循环。

一次取完：
  1. 6 张监测表的行数 + 时间范围（`deleted = 0`）
  2. 业务映射 `eq_business_equip_relation`：business_table ↔ eq_id ↔ st_id ↔ st_type
  3. 每个映射设备的 `eq_equip_base` 在线状态 / 类型
  4. 红旗清单：空表、设备已删、设备离线、站类型与设备类型错配

设计：`build_overview(conn)` 只查询不打印，返回 dict（可单测、可被 report.py 复用）；
`main()` 负责 CLI / 打印。与 profiling.py（纯函数）、device_context.py（事后富化）互补。

用法:
    source _shared/bootstrap.sh
    python3 powerelf-data-governance/lib/overview.py            # 文本报告
    python3 powerelf-data-governance/lib/overview.py --format json
    python3 powerelf-data-governance/lib/overview.py --table st_rsvr_r   # 只看某表

References:
    - _shared/references/schema.md（表结构唯一事实源，2026-07-16 全表复核）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

# 监测表 → (中文标签, 主检测字段)。与 schema.md / business_rules.md 对齐。
MONITOR_TABLES: Dict[str, tuple] = {
    "st_rsvr_r": ("水库水位", "rz"),
    "st_river_r": ("河道水位", "z"),
    "st_pptn_r": ("雨量", "p"),
    "st_pressure_r": ("渗压", "ext_pressure"),
    "st_percolation_r": ("渗流", "percolation"),
    "dsm_dfr_srvrds_srhrds": ("GNSS位移", "wgs84_delta_h"),
}

# 水位类业务表 → 这些表若映射到渗压类设备（type_flag 3 或 20，或名称含 渗压/pressure）
# 视为错配（来自 7/16 实测：st_river_r 的 eq_id=157 是振弦渗压计 type_flag=20）。
_WATER_LEVEL_TABLES = {"st_rsvr_r", "st_river_r"}
_PRESSURE_TYPE_FLAGS = {3, 20}
_PRESSURE_NAME_HINTS = ("渗压", "pressure", "渗流", "percolation")


def _table_overview(conn, table: str) -> Dict:
    """单表：行数 + tm 时间范围（deleted=0）。表不存在/无 tm 列则记 error。"""
    cur = conn.cursor()
    out = {"table": table}
    try:
        cur.execute(
            f"SELECT COUNT(*) AS c, MIN(tm) AS mn, MAX(tm) AS mx "
            f"FROM `{table}` WHERE deleted = 0"
        )
        row = cur.fetchone() or {}
        out["rows"] = int(row.get("c") or 0)
        out["min_tm"] = _dt_str(row.get("mn"))
        out["max_tm"] = _dt_str(row.get("mx"))
        out["error"] = None
    except Exception as e:  # 表不存在 / 无 tm 列等
        out["rows"] = None
        out["min_tm"] = None
        out["max_tm"] = None
        out["error"] = str(e)
    return out


def _device_mappings(conn) -> List[Dict]:
    """业务映射 + 设备状态 LEFT JOIN（设备可能已删 → NULL）。"""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT r.business_table, r.st_type, r.eq_id, r.st_id, "
            "       e.name, e.code, e.type_flag, e.status, e.deleted AS eq_deleted "
            "FROM eq_business_equip_relation r "
            "LEFT JOIN eq_equip_base e ON e.id = r.eq_id "
            "ORDER BY r.business_table, r.st_type"
        )
        rows = cur.fetchall() or []
    except Exception:
        return []
    out = []
    for r in rows:
        found = r.get("name") is not None
        out.append({
            "business_table": r.get("business_table"),
            "st_type": r.get("st_type"),
            "eq_id": r.get("eq_id"),
            "st_id": r.get("st_id"),
            "dev_name": r.get("name"),
            "dev_code": r.get("code"),
            "type_flag": _as_int(r.get("type_flag")),
            "status": _as_int(r.get("status")),
            "eq_deleted": _bit_to_bool(r.get("eq_deleted")),
            "found": found,
        })
    return out


def _red_flags(tables: List[Dict], mappings: List[Dict]) -> List[Dict]:
    """从 overview 数据派生红旗。severity: high(影响数据可用性) / warn / info。"""
    flags: List[Dict] = []
    rows_by_table = {t["table"]: t.get("rows") for t in tables}
    mapped_tables = {m["business_table"] for m in mappings}

    # 1) 空表但有映射 —— 有站点配置却无数据（采集断链/设备未装）
    for t in tables:
        if t.get("rows") == 0 and t["table"] in mapped_tables:
            flags.append({
                "severity": "high",
                "category": "empty_with_mapping",
                "message": f"{t['table']} 完全为空，但在 eq_business_equip_relation 有映射 —— "
                           "采集未开始/已中断或设备未装",
            })
    # 2) 映射的设备已删（LEFT JOIN 为 NULL 或 eq_deleted=1）
    for m in mappings:
        if not m["found"]:
            flags.append({
                "severity": "warn",
                "category": "device_deleted",
                "message": f"{m['business_table']} st_type={m['st_type']} eq_id={m['eq_id']} "
                           "映射的设备在 eq_equip_base 中已删除",
            })
        elif m["eq_deleted"]:
            flags.append({
                "severity": "warn",
                "category": "device_deleted",
                "message": f"{m['dev_name']}({m['dev_code']}) eq_id={m['eq_id']} 已逻辑删除",
            })
    # 3) 设备离线（status=0）
    for m in mappings:
        if m["found"] and not m["eq_deleted"] and m["status"] == 0:
            flags.append({
                "severity": "warn",
                "category": "device_offline",
                "message": f"{m['dev_name']}({m['dev_code']}) eq_id={m['eq_id']} 离线(status=0)",
            })
    # 4) 水位表映射到渗压类设备 —— 类型错配
    for m in mappings:
        if not m["found"]:
            continue
        if m["business_table"] in _WATER_LEVEL_TABLES:
            name = (m["dev_name"] or "")
            if m["type_flag"] in _PRESSURE_TYPE_FLAGS or any(h in name.lower() for h in _PRESSURE_NAME_HINTS):
                flags.append({
                    "severity": "warn",
                    "category": "type_mismatch",
                    "message": f"{m['business_table']} 映射到 {m['dev_name']}("
                               f"type_flag={m['type_flag']})，疑似渗压计错配为水位设备",
                })
    order = {"high": 0, "warn": 1, "info": 2}
    flags.sort(key=lambda f: order.get(f["severity"], 9))
    return flags


def build_overview(conn) -> Dict:
    """主入口：查库 + 派生红旗，返回结构化 dict（不打印）。"""
    tables = [_table_overview(conn, t) for t in MONITOR_TABLES]
    mappings = _device_mappings(conn)
    flags = _red_flags(tables, mappings)
    return {
        "database": _db_name(conn),
        "tables": tables,
        "mappings": mappings,
        "red_flags": flags,
        "totals": {
            "monitor_tables": len(tables),
            "mappings": len(mappings),
            "red_flags": len(flags),
            "high_severity": sum(1 for f in flags if f["severity"] == "high"),
        },
    }


# ----------------------------- helpers -----------------------------

def _dt_str(v) -> Optional[str]:
    return str(v) if v is not None else None

def _as_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def _bit_to_bool(v) -> bool:
    """MySQL BIT(1) 经 pymysql 可能返回 b'\\x00'/b'\\x01' 或 0/1。"""
    if isinstance(v, (bytes, bytearray)):
        return v == b"\x01" or v == b"1"
    return bool(v)

def _db_name(conn) -> Optional[str]:
    try:
        cur = conn.cursor()
        cur.execute("SELECT DATABASE() AS d")
        r = cur.fetchone() or {}
        return r.get("d")
    except Exception:
        return None


# ----------------------------- CLI / 打印 -----------------------------

def render_text(ov: Dict, only_table: Optional[str] = None) -> str:
    lines: List[str] = []
    lines.append(f"=== 数据治理概览（库: {ov['database']}）===")
    lines.append("")
    lines.append("【1】监测表全貌（deleted=0）")
    lines.append(f"  {'表':<26}{'标签':<10}{'行数':>12}    时间范围")
    for t in ov["tables"]:
        if only_table and t["table"] != only_table:
            continue
        if t.get("error"):
            lines.append(f"  {t['table']:<26}{'-':<10}{'-':>12}    [错误] {t['error']}")
            continue
        rng = f"{t['min_tm']} ~ {t['max_tm']}" if t["rows"] else "—（空表）"
        label = dict(MONITOR_TABLES).get(t["table"], ("",))[0]
        lines.append(f"  {t['table']:<26}{label:<10}{t['rows']:>12,}    {rng}")

    if not only_table:
        lines.append("")
        lines.append("【2】业务映射 ↔ 设备状态")
        for m in ov["mappings"]:
            if m["found"]:
                st = {0: "离线", 1: "在线", 2: "异常"}.get(m["status"], str(m["status"]))
                tag = " [已删]" if m["eq_deleted"] else ""
                lines.append(f"  {m['business_table']:<24}st_type={str(m['st_type']):<4}"
                             f"eq_id={str(m['eq_id']):<5}→ {m['dev_name']}({m['dev_code']}) "
                             f"type_flag={m['type_flag']} {st}{tag}")
            else:
                lines.append(f"  {m['business_table']:<24}st_type={str(m['st_type']):<4}"
                             f"eq_id={str(m['eq_id']):<5}→ 设备已删除(无记录)")

    flags = [f for f in ov["red_flags"] if not only_table or True]
    lines.append("")
    lines.append(f"【3】红旗清单（共 {len(flags)}，高严重 {ov['totals']['high_severity']}）")
    if not flags:
        lines.append("  （无）")
    for f in flags:
        lines.append(f"  [{f['severity'].upper():<5}] {f['category']}: {f['message']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="一次性数据治理概览（取代逐表试探）")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--table", default=None, help="只看某张监测表（如 st_rsvr_r）")
    args = parser.parse_args(argv)

    # 复用 skill 内 db shim（转发到 _shared/lib/db.py）
    _lib = os.path.dirname(os.path.abspath(__file__))
    if _lib not in sys.path:
        sys.path.insert(0, _lib)
    from db import get_connection  # noqa: E402

    conn = get_connection()
    try:
        ov = build_overview(conn)
    finally:
        conn.close()

    if args.format == "json":
        print(json.dumps(ov, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_text(ov, only_table=args.table))
    # 非零退出码便于 CI/脚本捕获"有高严重红旗"
    return 1 if ov["totals"]["high_severity"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
