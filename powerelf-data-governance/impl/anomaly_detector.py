#!/usr/bin/env python3
"""
异常检测算子（MAD / IQR / 百分位，基于 rules/anomaly-detection.md 与
_shared/algorithms/outlier-methods.md）
直接调用，Agent 不需要自己写 SQL 或理解算法细节。

用法:
  # MAD（默认，正态/缓变指标：水位/GNSS/渗压）
  python3 anomaly_detector.py --db "$DB_URL" \
    --table st_pressure_r --field water_pressure --threshold 4.0

  # IQR（偏态指标：雨量/流量）；--threshold 为 IQR 倍数 k（默认 1.5）
  python3 anomaly_detector.py --db "$DB_URL" --table st_pptn_r --field p --method iqr

  # 百分位（快速筛查）；--threshold 为尾部百分位 p（默认 1 -> p1/p99）
  python3 anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --method percentile

  python3 anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --threshold 3.0 --st-id 128

--threshold 语义随 --method:
  mad         修正 Z 阈值（默认按字段自动选择）
  iqr         IQR 倍数 k（默认 1.5；3.0 激进）
  percentile  尾部百分位 p（默认 1，即 p1/p99）

输出: JSON 格式检测结果，含 method、分析块(mad_analysis/iqr_analysis/percentile_analysis)、
      异常点列表、综合判定。不带 --method 时与历史版本完全兼容（仅多 method 字段）。
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
    print("需要安装: pip install pandas numpy sqlalchemy pymysql")
    sys.exit(1)


# 把 skill 根加入 sys.path 以便 from lib.outliers import ...
_HERE = os.path.dirname(os.path.abspath(__file__))            # .../impl
_SKILL_ROOT = os.path.dirname(_HERE)                            # .../powerelf-data-governance
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)
from lib.outliers import detect_iqr, detect_percentile


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

# 监测表白名单（应与 _shared/lib/db.py::ALLOWED_TABLES 单一事实源一致；
# 删除 schema.md 不存在的 10 个幽灵表名，补 GNSS 实表 dsm_dfr_srvrds_srhrds）
ALLOWED_TABLES = frozenset({
    "st_rsvr_r", "st_river_r", "st_pptn_r",
    "st_pressure_r", "st_percolation_r",
    "dsm_dfr_srvrds_srhrds",
})
ALLOWED_FIELDS = frozenset({
    "rz", "z", "p", "water_pressure", "ext_pressure",
    "percolation", "wgs84_delta_h", "inq", "otq",
    "temperature", "humidity", "wind_speed", "wind_direction",
    "strain", "tilt_x", "tilt_y", "displacement",
})
ALLOWED_TIME_FIELDS = frozenset({"tm", "time", "timestamp", "collect_time"})


def load_data(engine, table, field, st_id=None, days=30, time_field="tm",
              start=None, end=None):
    """从数据库加载传感器数据。

    时间窗口三种模式（优先级：start/end > days）：
      1. start+end：指定日期范围（含端点）， days 被忽略
      2. 仅 days：相对"今天"往前 N 天（历史行为，默认 30）
      3. start+days 或 end+days：start 起 days 天 / end 往前 days 天（混合）
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table} (不在允许列表中)")
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"非法字段名: {field} (不在允许列表中)")
    if time_field not in ALLOWED_TIME_FIELDS:
        raise ValueError(f"非法时间字段: {time_field}")

    where_parts = []
    params = {}

    if start is not None:
        where_parts.append(f"{time_field} >= :start")
        params["start"] = start
    if end is not None:
        where_parts.append(f"{time_field} <= :end")
        params["end"] = end
    if start is None and end is None:
        # 兜底：相对"今天"往前 days 天（历史行为）
        where_parts.append(f"{time_field} >= NOW()-INTERVAL :days DAY")
        params["days"] = days

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


def comprehensive_judge(mad_result, change_rate_result, threshold, method_label="MAD"):
    """综合判定（离群检测 + 变化率交叉验证）。

    method_label 仅影响 message 文案（MAD/IQR/百分位）；默认 "MAD" 时输出与历史版本逐字一致。
    判定逻辑只依赖 anomaly_count，与具体检测方法无关。
    """
    has_mad_anomaly = mad_result["anomaly_count"] > 0
    has_rate_anomaly = len(change_rate_result) > 0

    if has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "CRITICAL",
            "confidence": "high",
            "message": f"{method_label}异常 + 变化率超标，确认异常",
        }
    elif has_mad_anomaly and not has_rate_anomaly:
        return {
            "level": "WARNING",
            "confidence": "medium",
            "message": f"{method_label}异常但变化率正常，可能异常，检查是否为正常波动峰值",
        }
    elif not has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "INFO",
            "confidence": "low",
            "message": f"{method_label}正常但变化率超标，可疑，标记待人工确认",
        }
    else:
        return {
            "level": "OK",
            "confidence": "high",
            "message": f"{method_label}正常且变化率正常，数据在历史分布范围内",
        }


def detect_by_method(method, values, threshold):
    """按 method 分派离群检测，返回统一结构（可脱离 DB 单测）。

    Args:
        method: "mad" | "iqr" | "percentile"
        values: 数值序列
        threshold: 用户传入的阈值（语义随 method）；None 表示用方法默认。

    Returns:
        dict:
          method        实际方法
          threshold     解析后实际使用的阈值
          result        检测结果 dict（含 anomaly_count/anomaly_indices）
          analysis      供输出 JSON 的分析摘要 dict
          analysis_key  输出 JSON 中分析块的字段名(mad_analysis/iqr_analysis/percentile_analysis)
          score_label   异常点详情里附带的分值字段名(mad="z_score"，其余 None)
          score_source  result 中分值列表的字段名(mad="z_scores"，其余 None)
          method_label  综合判定的文案标签(MAD/IQR/百分位)
    """
    if method == "mad":
        t = 4.0 if threshold is None else threshold
        result = detect_anomalies(values, t)
        total = result["total_points"]
        analysis = {
            "median": result["median"],
            "mad": result["mad"],
            "anomaly_count": result["anomaly_count"],
            "anomaly_rate": f"{result['anomaly_count']/total*100:.1f}%" if total else "0.0%",
        }
        return {"method": "mad", "threshold": t, "result": result,
                "analysis": analysis, "analysis_key": "mad_analysis",
                "score_label": "z_score", "score_source": "z_scores",
                "method_label": "MAD"}

    elif method == "iqr":
        k = threshold
        if k is None or k <= 0:
            k = 1.5
        result = detect_iqr(values, k=k)
        total = result["total_points"]
        analysis = {
            "q1": result["q1"], "q3": result["q3"], "iqr": result["iqr"],
            "lower_bound": result["lower_bound"], "upper_bound": result["upper_bound"],
            "anomaly_count": result["anomaly_count"],
            "anomaly_rate": f"{result['anomaly_count']/total*100:.1f}%" if total else "0.0%",
        }
        return {"method": "iqr", "threshold": k, "result": result,
                "analysis": analysis, "analysis_key": "iqr_analysis",
                "score_label": None, "score_source": None,
                "method_label": "IQR"}

    elif method == "percentile":
        p = threshold
        if p is None or p <= 0 or p >= 50:
            p = 1
        result = detect_percentile(values, low=p, high=100 - p)
        total = result["total_points"]
        analysis = {
            "low_bound": result["low_bound"], "high_bound": result["high_bound"],
            "anomaly_count": result["anomaly_count"],
            "anomaly_rate": f"{result['anomaly_count']/total*100:.1f}%" if total else "0.0%",
        }
        return {"method": "percentile", "threshold": p, "result": result,
                "analysis": analysis, "analysis_key": "percentile_analysis",
                "score_label": None, "score_source": None,
                "method_label": "百分位"}

    raise ValueError(f"未知检测方法: {method}（可选: mad / iqr / percentile）")


def run_detection(engine, table, field, threshold=None, st_id=None, days=30, method="mad",
                  start=None, end=None, detail="compact"):
    """执行离群检测流程（MAD / IQR / 百分位）。

    时间窗口：start/end（指定日期范围，优先级高于 days）或 days（相对今天往前 N 天）。
    detail：compact=最多 10 条明细（历史行为）；full=全部异常点明细。
    method="mad" 时与历史版本完全兼容（仅输出多一个 method 字段）。
    """

    # 阈值解析：mad 走分指标默认；iqr/percentile 由 detect_by_method 兜底
    if method == "mad" and threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(field, 4.0)
    # 越界告警（告警但继续，detect_by_method 会回退默认）
    if method == "iqr" and threshold is not None and threshold <= 0:
        print(f"[WARN] iqr 倍数 k={threshold} 非法(需>0)，回退到 1.5", file=sys.stderr)
    if method == "percentile" and threshold is not None and (threshold <= 0 or threshold >= 50):
        print(f"[WARN] percentile 尾部 p={threshold} 越界(需 0<p<50)，回退到 1", file=sys.stderr)

    # 加载数据
    df = load_data(engine, table, field, st_id, days, start=start, end=end)
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

    # 方法分派（纯函数，可单测）
    dispatch = detect_by_method(method, values, threshold)
    anom_result = dispatch["result"]
    analysis_key = dispatch["analysis_key"]
    analysis = dispatch["analysis"]
    score_label = dispatch["score_label"]
    score_source = dispatch["score_source"]
    method_label = dispatch["method_label"]
    resolved_threshold = dispatch["threshold"]

    # 变化率检测（对所有方法适用，互补）
    change_rate_result = detect_change_rate(values, field)

    # 综合判定（仅依赖 anomaly_count，方法无关）
    judgment = comprehensive_judge(anom_result, change_rate_result, resolved_threshold, method_label)

    # 构建异常点详情
    tm_cols = [c for c in df.columns if c != field]
    tm_col = tm_cols[0] if tm_cols else None
    anomaly_details = []
    for idx in anom_result["anomaly_indices"]:
        original_idx = clean_series.index[idx]
        detail = {
            "index": int(original_idx),
            "value": round(float(values[idx]), 4),
        }
        if score_label and score_source and score_source in anom_result:
            detail[score_label] = anom_result[score_source][idx]
        if tm_col and original_idx in df.index:
            detail["time"] = str(df.loc[original_idx, tm_col])
        # ③ 补 st_id 设备列：从 df 同行取 st_id（若表有此列），让 CSV 自带设备维度
        if "st_id" in df.columns and original_idx in df.index:
            detail["st_id"] = df.loc[original_idx, "st_id"]
        else:
            detail["st_id"] = st_id if st_id else ""
        anomaly_details.append(detail)

    # 解释集（mad 路径与历史版本逐字一致；iqr/percentile 用方法感知文案）
    if method == "mad":
        explanation = (
            f"对 {table}.{field} 做 MAD 异常检测: "
            f"数据点{anom_result['total_points']}个, "
            f"中位数{anom_result['median']}, "
            f"MAD={anom_result['mad']}, "
            f"阈值={resolved_threshold}, "
            f"发现{anom_result['anomaly_count']}个异常点。"
            f"综合判定: {judgment['message']} (置信度{judgment['confidence']})"
        )
    else:
        explanation = (
            f"对 {table}.{field} 做 {method_label} 离群检测: "
            f"数据点{anom_result['total_points']}个, "
            f"阈值={resolved_threshold}, "
            f"发现{anom_result['anomaly_count']}个离群点。"
            f"综合判定: {judgment['message']} (置信度{judgment['confidence']})"
        )

    # 按天聚合（daily_summary）：按 tm 列的日期部分聚合记录数/零值数/最大值/累计值
    daily_summary = _build_daily_summary(df, field, tm_col)

    return {
        "status": "OK",
        "table": table,
        "field": field,
        "st_id": st_id,
        "days": days,
        "start": start,
        "end": end,
        "threshold": resolved_threshold,
        "data_points": anom_result["total_points"],
        analysis_key: analysis,
        "change_rate_analysis": {
            "exceed_count": len(change_rate_result),
            "threshold": CHANGE_RATE_THRESHOLDS.get(field, 0.10),
            "exceed_details": change_rate_result[:5],  # 最多5条
        },
        "daily_summary": daily_summary,
        "judgment": judgment,
        "anomaly_details": anomaly_details if detail == "full" else anomaly_details[:10],  # compact=最多10条；full=全部
        "explanation": explanation,
        "method": method,
    }


def _build_daily_summary(df, field, tm_col):
    """按天聚合：按 tm 列的日期部分聚合记录数/零值数/最大值/累计值。

    返回 list[dict]，每条：{date, records, zeros, max_value, sum_value}。
    无 tm_col 或 df 空 → 返回 []。
    """
    if tm_col is None or df.empty:
        return []
    # 取 tm 列 + field 列，按日期部分聚合
    tmp = df[[tm_col, field]].copy()
    # 日期部分：tm 可能是 datetime 或字符串，取前 10 字符即 YYYY-MM-DD
    tmp["day"] = tmp[tm_col].astype(str).str[:10]
    # 数值化（排除 Decimal/字符串混合）
    tmp["val"] = pd.to_numeric(tmp[field], errors="coerce")
    grouped = tmp.groupby("day")
    summary = []
    for day, g in grouped:
        vals = g["val"].dropna()
        summary.append({
            "date": day,
            "records": int(len(g)),
            "zeros": int((g["val"] == 0).sum()),
            "max_value": round(float(vals.max()), 4) if not vals.empty else None,
            "sum_value": round(float(vals.sum()), 4) if not vals.empty else None,
        })
    return summary


def export_csv(result, out_path):
    """把 run_detection 的结果导出为 CSV（含 anomaly_details 全量明细 + st_id 设备列）。

    列：index, time, value, modified_z/iqr_dev/percentile, judgment, method, table, field, st_id, 复核结论。
    UTF-8 BOM 编码（Excel 友好），含空白的"复核结论"列供人工填写。
    ③ 修复：加 st_id 设备列，让 hermes 一次拿全异常+设备维度无需再查关联表。
    """
    import csv
    details = result.get("anomaly_details", [])
    # 列头：固定列 + 动态评分列（ModifiedZ / iqr_dev / percentile）+ st_id
    base_cols = ["index", "time", "value", "judgment", "method", "table", "field", "st_id", "复核结论"]
    score_cols = []
    if details:
        for k in details[0].keys():
            if k not in ("index", "time", "value", "st_id"):
                score_cols.append(k)
    header = base_cols[:3] + score_cols + base_cols[3:]

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for d in details:
            row = [d.get("index", ""), d.get("time", ""), d.get("value", "")]
            for k in score_cols:
                row.append(d.get(k, ""))
            row.extend([
                result.get("judgment", {}).get("message", ""),
                result.get("method", ""),
                result.get("table", ""),
                result.get("field", ""),
                d.get("st_id", ""),  # ③ 补 st_id 设备列
                "",  # 复核结论空列
            ])
            w.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="异常检测算子（MAD / IQR / 百分位）")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--field", required=True, help="检测字段名")
    parser.add_argument("--method", choices=["mad", "iqr", "percentile"], default="mad",
                        help="离群检测方法: mad(默认,修正Z) / iqr(四分位距) / percentile(百分位)")
    parser.add_argument("--threshold", type=float, default=None,
                        help="阈值，语义随 --method: mad=修正Z(默认按字段) / iqr=IQR倍数k(默认1.5) / percentile=尾部百分位p(默认1→p1/p99)")
    parser.add_argument("--st-id", type=int, default=None, help="测站ID")
    parser.add_argument("--days", type=int, default=30, help="检测天数（相对今天往前 N 天，与 --start/--end 互斥）")
    parser.add_argument("--start", type=str, default=None,
                        help="起始日期（YYYY-MM-DD），指定日期范围模式，优先级高于 --days")
    parser.add_argument("--end", type=str, default=None,
                        help="结束日期（YYYY-MM-DD），指定日期范围模式，优先级高于 --days")
    parser.add_argument("--detail", choices=["compact", "full"], default="compact",
                        help="明细输出模式: compact=最多10条(默认) / full=全部异常点")
    parser.add_argument("--format", choices=["json", "csv"], default="json",
                        help="输出格式: json(默认,stdout) / csv(导出明细到 --output 文件)")
    parser.add_argument("--output", type=str, default=None,
                        help="CSV 导出路径（仅 --format csv 时生效，默认 /tmp/anomaly_<table>_<field>.csv）")
    args = parser.parse_args()

    engine = create_engine(args.db)
    result = run_detection(engine, args.table, args.field, args.threshold,
                           args.st_id, args.days, args.method,
                           start=args.start, end=args.end, detail=args.detail)

    # 输出格式分派
    if args.format == "csv":
        out_path = args.output or f"/tmp/anomaly_{args.table}_{args.field}.csv"
        export_csv(result, out_path)
        print(f"CSV 已导出：{out_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
