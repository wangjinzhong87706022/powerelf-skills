#!/usr/bin/env python3
"""
interpolate.py — 四策略自适应插值算子（lib/interpolation 的 CLI 包装）

背景：插值题曾是 SKILL.md 唯一"暂无内置脚本允许自写"的豁免类，agent 自写
脚本反复 write_file/patch 到超时（DG-P11 实测 8×write_file + 598s）。本脚本
补上内置入口：一条命令完成 取数→找缺失→自适应选策略→填补→报告。

2026-08-23 能力扩展（routing-evals-v2 #23 根因修复）：原版只填补已存行里的
NULL 值，对"时间断档"（设备停报/恢复造成的整段缺失时间戳）返回 NO_GAP ——
而 #23 正是时间断档题，agent 读到 NO_GAP 后判定内置不可用、自写 12+ 文件
撞 898s 超时。现新增时间断档检测 + 重采样填补：按推断采样频率重建期望时间
轴，找出缺失时间戳，逐点插值填补并报告断档起止/时长。另增 --writeback 选项
（默认仍只报告，落库需显式确认，延续"不静默写库"原则）。

用法：
  python3 impl/interpolate.py --db "$DB_URL" --table st_rsvr_r --field rz \
      [--st-id 123] [--days 7] [--gap-hours 2] [--writeback]

输出：JSON 报告（所选策略、逐点填补值、缺失率、时间断档清单、范围合理性）。
默认不写回 DB——填补值如需落库，加 --writeback 显式确认后经 writeback 流程执行。
"""
import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from interpolation import interpolate, select_strategy  # noqa: E402

# 与 missing_detector 一致（单一事实源 _shared/lib/db.py::ALLOWED_TABLES）
ALLOWED_TABLES = frozenset({
    "st_rsvr_r", "st_river_r", "st_pptn_r",
    "st_pressure_r", "st_percolation_r",
    "dsm_dfr_srvrds_srhrds",
})

_STRATEGY_CN = {
    "linear": "线性", "quadratic": "二次", "spline": "样条", "moving_avg": "滑动平均",
}


def validate_field(field):
    """值字段名白名单式校验（防注入：只允许小写字母/数字/下划线且字母开头）。"""
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", field or ""):
        raise ValueError(f"非法字段名: {field!r}")
    return field


def detect_time_gaps(rows, gap_hours=2.0):
    """检测时间断档：找出相邻已存行间隔超过 gap_hours 的空窗。

    返回 gap 列表，每个 = {"start": tm, "end": tm, "gap_hours": float,
    "missing_slots": int（按推断频率估算的缺失时间点数）}。
    rows 需时间升序、元素为 (tm, value)。
    """
    gaps = []
    for i in range(1, len(rows)):
        dt_h = _hours_between(rows[i - 1][0], rows[i][0])
        if dt_h is not None and dt_h > gap_hours:
            freq = _infer_freq_hours(rows)
            missing_slots = max(0, int(round(dt_h / freq)) - 1) if freq else 0
            gaps.append({
                "start": rows[i - 1][0],
                "end": rows[i][0],
                "gap_hours": round(dt_h, 2),
                "missing_slots": missing_slots,
            })
    return gaps


def _hours_between(t1, t2):
    """两个时间戳之间的小时差；不可解析返回 None。"""
    import datetime
    d1 = _to_dt(t1)
    d2 = _to_dt(t2)
    if d1 is None or d2 is None:
        return None
    return (d2 - d1).total_seconds() / 3600.0


def _to_dt(t):
    """尽力把 tm 解析成 datetime；失败返回 None。"""
    import datetime
    if isinstance(t, datetime.datetime):
        return t
    if isinstance(t, datetime.date):
        return datetime.datetime(t.year, t.month, t.day)
    if isinstance(t, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(t, fmt)
            except ValueError:
                continue
    return None


def _infer_freq_hours(rows):
    """从相邻间隔推断采样频率（小时），取众数；样本不足返回 None。"""
    from collections import Counter
    dts = []
    for i in range(1, len(rows)):
        dt_h = _hours_between(rows[i - 1][0], rows[i][0])
        if dt_h is not None and dt_h > 0:
            dts.append(round(dt_h, 3))
    if not dts:
        return None
    freq = Counter(dts).most_common(1)[0][0]
    return freq if freq > 0 else None


def resample_with_gaps(rows, gap_hours=2.0):
    """重建期望时间轴，把时间断档展开成 (tm, None) 占位行。

    返回 (resampled_rows, time_gaps)：
    - resampled_rows：按推断频率在断档处插入 None 占位的时间升序 (tm, value) 序列；
      既有 NULL 值也保留为 None。无断档时原样返回。
    - time_gaps：detect_time_gaps 的结果（断档清单）。
    """
    if len(rows) < 2:
        return list(rows), []
    gaps = detect_time_gaps(rows, gap_hours)
    if not gaps:
        return list(rows), gaps

    freq = _infer_freq_hours(rows)
    if not freq:
        return list(rows), gaps

    import datetime
    out = [rows[0]]
    for i in range(1, len(rows)):
        prev_tm = _to_dt(rows[i - 1][0])
        cur_tm = _to_dt(rows[i][0])
        if prev_tm is None or cur_tm is None:
            out.append(rows[i])
            continue
        dt_h = (cur_tm - prev_tm).total_seconds() / 3600.0
        if dt_h > gap_hours:
            # 在断档内按频率插入占位行
            step = datetime.timedelta(hours=freq)
            t = prev_tm + step
            while t < cur_tm:
                out.append((t.strftime("%Y-%m-%d %H:%M:%S"), None))
                t = t + step
        out.append(rows[i])
    return out, gaps


def build_report(rows, table, field, st_id=None, gap_hours=2.0):
    """纯函数：rows=[(tm, value)] 时间升序、value None=待填补 → 插值报告 dict。

    两阶段填补（2026-08-23 能力扩展）：
    1. 时间断档检测：把间隔 > gap_hours 的空窗按推断频率展开成 (tm, None) 占位；
    2. 自适应插值：对原 NULL 值 + 断档占位统一跑四策略填补。
    这样既覆盖"已存行里有 NULL"也覆盖"整段缺失时间戳"（#23 场景）。
    """
    # 第一阶段：时间断档重采样（无断档时原样返回）
    rows, time_gaps = resample_with_gaps(rows, gap_hours)

    values = [None if v is None else float(v) for _, v in rows]
    indices = [i for i, v in enumerate(values) if v is None]
    base = {
        "table": table, "field": field, "st_id": st_id,
        "total_points": len(values), "missing_points": len(indices),
        "missing_rate": f"{len(indices) / len(values):.2%}" if values else "0.00%",
        "time_gaps": time_gaps,
        "time_gap_count": len(time_gaps),
    }
    if not values:
        return {**base, "status": "NO_DATA", "strategy": None, "filled": [],
                "explanation": "窗口内无数据"}
    if not indices:
        return {**base, "status": "NO_GAP", "strategy": None, "filled": [],
                "explanation": "无缺失值（含时间断档检测），无需插值"}
    if len(indices) == len(values):
        return {**base, "status": "NO_VALID_DATA", "strategy": None, "filled": [],
                "explanation": "全部缺失，无有效数据可插值"}

    strategy = select_strategy(values, indices)
    filled_vals = interpolate(values, indices, strategy="auto")

    valid = [v for v in values if v is not None]
    lo, hi = min(valid), max(valid)
    in_range = sum(1 for i in indices if lo <= filled_vals[i] <= hi)
    filled = [{"tm": rows[i][0], "value": filled_vals[i]} for i in indices]

    gap_desc = ""
    if time_gaps:
        total_gap_slots = sum(g["missing_slots"] for g in time_gaps)
        gap_desc = (
            f"；检出 {len(time_gaps)} 处时间断档（合计约 {total_gap_slots} 个缺失时间点，"
            f"最长 {max(g['gap_hours'] for g in time_gaps):.1f}h），已按推断频率重采样为占位并一并填补"
        )

    return {
        **base,
        "status": "OK",
        "strategy": strategy,
        "filled": filled[:50],
        "filled_truncated": max(0, len(filled) - 50),
        "filled_in_range_pct": f"{in_range / len(indices):.2%}",
        "explanation": (
            f"表 {table}.{field} 共 {len(values)} 点，缺失 {len(indices)} 点"
            f"（{base['missing_rate']}），四策略自适应选择【{_STRATEGY_CN.get(strategy, strategy)}插值】"
            f"已全部填补，{in_range}/{len(indices)} 个填补值在有效值范围内{gap_desc}"
        ),
    }


def load_series(engine, table, field, st_id=None, days=7):
    """从 DB 加载 (tm, value) 序列；value 为 NULL/NaN → None。"""
    import pandas as pd  # 延迟导入：纯函数测试不依赖 pandas/DB
    from sqlalchemy import text

    if table not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    validate_field(field)

    where = ["tm >= NOW()-INTERVAL :days DAY"]
    params = {"days": days}
    if st_id:
        where.append("st_id = :st_id")
        params["st_id"] = st_id
    sql = f"SELECT tm, {field} FROM {table} WHERE {' AND '.join(where)} ORDER BY tm ASC"
    df = pd.read_sql(text(sql), engine, params=params)

    rows = []
    for _, r in df.iterrows():
        v = r[field]
        rows.append((r["tm"], None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)))
    return rows


def main():
    parser = argparse.ArgumentParser(description="四策略自适应插值算子（含时间断档检测）")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--field", required=True, help="值字段名（如 rz / water_pressure / p）")
    parser.add_argument("--st-id", type=int, default=None, help="测站ID")
    parser.add_argument("--days", type=int, default=7, help="回看天数")
    parser.add_argument("--gap-hours", type=float, default=2.0,
                        help="时间断档阈值（小时），相邻已存行间隔超过此值视为空窗（默认 2）")
    parser.add_argument("--writeback", action="store_true",
                        help="把填补值写回 DB（默认只报告不写库，需显式确认）")
    args = parser.parse_args()

    from db import create_engine  # 延迟导入：db 模块读 ~/.hermes/.env

    engine = create_engine(args.db)
    rows = load_series(engine, args.table, args.field, args.st_id, args.days)
    result = build_report(rows, args.table, args.field, args.st_id, args.gap_hours)

    if args.writeback and result.get("status") == "OK" and result.get("filled"):
        _writeback(engine, args.table, args.field, args.st_id, result["filled"])
        result["writeback"] = f"已写回 {len(result['filled'])} 个填补值（creator=data-governance-interpolation）"

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def _writeback(engine, table, field, st_id, filled):
    """把填补值写回 DB（--writeback 时调用）。沿用既有 writeback 惯例：
    INSERT ... creator='data-governance-interpolation'，不覆盖既有行。"""
    from sqlalchemy import text
    cols = _table_columns(engine, table)
    if "creator" in cols:
        sql = (f"INSERT INTO {table} (tm, {field}, st_id, creator, deleted) "
               f"VALUES (:tm, :val, :st_id, 'data-governance-interpolation', 0)")
    else:
        sql = (f"INSERT INTO {table} (tm, {field}, st_id, deleted) "
               f"VALUES (:tm, :val, :st_id, 0)")
    params = [{"tm": f["tm"], "val": f["value"], "st_id": st_id} for f in filled]
    with engine.begin() as conn:
        conn.execute(text(sql), params)


def _table_columns(engine, table):
    """安全取表列名清单（用于判断有无 creator 列）。"""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            res = conn.execute(text(f"SHOW COLUMNS FROM {table}"))
            return [r[0] for r in res]
    except Exception:
        return []


if __name__ == "__main__":
    main()
