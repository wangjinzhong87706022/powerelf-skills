#!/usr/bin/env python3
"""
数据画像 CLI（Data Profiling CLI）
====================================

对指定表做结构化画像：列分类、统计量、完整性、准确性红旗。
只读，输出 JSON / text 到 stdout。

用法:
  # 画像全表（默认 sample 10000）
  python3 impl/profiler.py --db "$DB_URL" --table st_pressure_r

  # 指定字段 + 自定义采样量
  python3 impl/profiler.py --db "$DB_URL" --table st_pressure_r --field water_pressure --sample 5000

  # text 格式输出
  python3 impl/profiler.py --db "$DB_URL" --table st_pressure_r --format text

输出: JSON 格式 profile（默认）或可读 text。
"""

import argparse
import json
import os
import sys
from datetime import datetime

try:
    import pandas as pd
    import numpy as np
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("需要安装: pip install pandas numpy sqlalchemy pymysql", file=sys.stderr)
    sys.exit(1)


# ============================================================
# Path setup
# ============================================================

_HERE = os.path.dirname(os.path.abspath(__file__))            # .../impl
_SKILL_ROOT = os.path.dirname(_HERE)                            # .../powerelf-data-governance
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)
from lib.profiling import profile_table                          # noqa: E402


# ============================================================
# Schema / Sampling
# ============================================================

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


def get_schema_hints(engine, table):
    """通过 DESCRIBE <table> 获取列名 → 类型 hints。

    Returns:
        dict: {column_name: dtype_string, ...}
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"DESCRIBE `{table}`"))
            rows = result.fetchall()
    except Exception as e:
        print(f"[WARN] DESCRIBE {table} 失败: {e}", file=sys.stderr)
        return {}

    hints = {}
    for row in rows:
        # DESCRIBE 返回: Field, Type, Null, Key, Default, Extra
        col_name = row[0]
        col_type = row[1]
        hints[col_name] = col_type

    return hints


def load_sample(engine, table, field=None, sample_size=10000):
    """从数据库采样行列表。

    Args:
        engine: SQLAlchemy engine
        table: 表名
        field: 可选指定字段（None 表示全字段）
        sample_size: 最大采样行数

    Returns:
        list[dict]: 行字典列表
    """
    columns_clause = field if field else "*"

    try:
        sql = f"SELECT {columns_clause} FROM `{table}` LIMIT :sample_size"
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"sample_size": sample_size})
            rows = [dict(row._mapping) for row in result.fetchall()]
        return rows
    except Exception as e:
        print(f"[ERROR] 查询 {table} 失败: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================
# Output
# ============================================================

def output_text(profile):
    """将 profile dict 格式化为可读 text。"""
    lines = []
    lines.append(f"表画像: {profile.get('row_count', 0)} 行 (sample={profile.get('sample_size', 0)})")
    lines.append(f"完整性等级: {profile.get('completeness_tier', '?')}")
    lines.append(f"红旗: {', '.join(profile.get('flags', [])) or '无'}")
    lines.append("")

    for col in profile.get("columns", []):
        lines.append(f"列: {col['name']}  分类: {col['type']}  空值率: {col['null_rate']:.1%}")
        if "numeric_stats" in col:
            ns = col["numeric_stats"]
            lines.append(f"  min={ns.get('min')}  max={ns.get('max')}  mean={ns.get('mean')}  median={ns.get('median')}")
            lines.append(f"  std={ns.get('std')}  分布: {ns.get('distribution_hint')}")
            lines.append(f"  p1={ns.get('p1')}  p5={ns.get('p5')}  p25={ns.get('p25')}  p50={ns.get('p50')}  p75={ns.get('p75')}  p95={ns.get('p95')}  p99={ns.get('p99')}")
            lines.append(f"  zero_rate={ns.get('zero_rate')}  negative_rate={ns.get('negative_rate')}  distinct={ns.get('distinct')}")
        if "temporal_stats" in col:
            ts = col["temporal_stats"]
            lines.append(f"  min={ts.get('min')}  max={ts.get('max')}  span={ts.get('span')}")
            lines.append(f"  median_gap={ts.get('median_gap')}  max_gap={ts.get('max_gap')}  future_count={ts.get('future_count')}")
        flags = col.get("accuracy_flags", [])
        if flags:
            lines.append(f"  ⚠ 红旗: {', '.join(flags)}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# Main
# ============================================================

def run_profiling(db_url, table, field=None, sample_size=10000, output_format="json"):
    """Programmatic entry point (returns profile dict instead of printing).

    Args:
        db_url: database connection URL
        table: table name
        field: optional field name (None = all columns)
        sample_size: max rows to sample
        output_format: "json" or "text"

    Returns:
        dict: profile result
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table} (不在允许列表中)")
    if field is not None and field not in ALLOWED_FIELDS:
        raise ValueError(f"非法字段名: {field} (不在允许列表中)")

    engine = create_engine(db_url)

    # 1. 获取 schema hints
    schema_hints = get_schema_hints(engine, table)

    # 2. 验证 field 是否在表实际列中（防止 SQL 注入）
    if field is not None and field not in schema_hints:
        raise ValueError(f"非法字段名: {field} (表 {table} 中不存在)")

    # 3. 采样
    rows = load_sample(engine, table, field=field, sample_size=sample_size)

    if not rows:
        result = {
            "status": "NO_DATA",
            "table": table,
            "field": field,
            "message": f"表 {table} 无数据",
        }
    else:
        # 3. 画像
        result = profile_table(rows, schema_hints=schema_hints)
        result.setdefault("table", table)
        result.setdefault("field", field)
        result.setdefault("status", "OK")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="数据画像算子（列分类、统计量、完整性、准确性红旗）"
    )
    parser.add_argument("--db", required=True, help="数据库连接 URL")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--field", default=None, help="可选指定字段（默认画像全表）")
    parser.add_argument("--sample", type=int, default=10000, help="最大采样行数（默认 10000）")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="输出格式（默认 json）")
    args = parser.parse_args()

    result = run_profiling(
        db_url=args.db,
        table=args.table,
        field=args.field,
        sample_size=args.sample,
        output_format=args.format,
    )

    # 4. 输出
    if args.format == "text":
        print(output_text(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
