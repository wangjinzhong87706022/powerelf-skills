#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""智能巡检报告图表生成（T8）。

生成 4 类 PNG 供巡检报告嵌入：
  1. 趋势图     — 水位/渗压/渗流/位移 近 N 天时序曲线（latest 标注）
  2. 异常分布图 — 各维度异常数柱状图 + severity 构成
  3. 离线全景图 — 离线分级双口径（设备数 vs 记录数）条形图
  4. 关联分析图 — 水位-渗压双轴联动曲线

依赖：matplotlib(agg) + pandas + sqlalchemy（沿用 generate_report 的 engine）。
中文：优先 AR PL UKai CN（实测可用），缺失时回退文泉驿/黑体。
Why: 评审 T8 — 报告当前为纯 Markdown 无图表，可读性弱；matplotlib 3.11.1 已装。
"""
import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # 无 DISPLAY 环境可出图
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

# ---- 中文字体（实测：AR PL UKai CN 可用；否则回退列表）----
_CN_FONT_CANDIDATES = ["AR PL UKai CN", "WenQuanYi Zen Hei", "Noto Sans CJK SC",
                       "SimHei", "Microsoft YaHei", "AR PL UMing CN"]


def _setup_cn_font():
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in _CN_FONT_CANDIDATES:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False  # 负号正常显示


_setup_cn_font()

# ---- 趋势图：4 个核心监测维度 ----
_TREND_DIMS = [
    ("水库水位", "st_rsvr_r", "rz", "m", "#1f77b4"),
    ("渗压", "st_pressure_r", "water_pressure", "kPa", "#d62728"),
    ("渗流", "st_percolation_r", "percolation", "L/s", "#2ca02c"),
    ("GNSS位移速率", "dsm_dfr_srvrds_srhrds", "speed_gh", "mm/d", "#ff7f0e"),
]


def _read_series(engine, table, value_col, days):
    """只读近 days 天时序（deleted=0）。返回 DataFrame[value, tm] 或空。"""
    try:
        sql = (f"SELECT {value_col} AS value, tm FROM {table} "
               f"WHERE deleted = 0 AND tm >= NOW()-INTERVAL :days DAY "
               f"ORDER BY tm ASC")
        return pd.read_sql(text(sql), engine, params={"days": days})
    except Exception:
        return pd.DataFrame()


def _safe_path(out_dir, name):
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, name)


def chart_trends(engine, days, out_dir):
    """4 张趋势图；返回 [{path, title}]。"""
    out = []
    for label, table, col, unit, color in _TREND_DIMS:
        df = _read_series(engine, table, col, days)
        if df.empty:
            continue
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        if df.empty:
            continue
        path = _safe_path(out_dir, f"trend_{table}.png")
        fig, ax = plt.subplots(figsize=(9, 3.2), dpi=110)
        ax.plot(df["tm"], df["value"], color=color, linewidth=1.2)
        ax.set_title(f"{label} 近{days}天趋势（单位:{unit}）", fontsize=11)
        ax.set_xlabel("时间")
        ax.set_ylabel(unit)
        ax.grid(alpha=0.3)
        latest = df.iloc[-1]
        ax.annotate(f"{latest['value']:.2f}{unit} @ {latest['tm']:%m-%d %H:%M}",
                    xy=(latest["tm"], latest["value"]),
                    xytext=(-8, 8), textcoords="offset points", fontsize=8,
                    color="darkred")
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        out.append({"path": path, "title": f"{label} 趋势"})
    return out


def chart_severity(analyses, out_dir):
    """异常分布：各维度异常数柱状图 + severity 构成。返回单张图路径。"""
    path = _safe_path(out_dir, "anomaly_distribution.png")
    rows = []
    for a in analyses:
        for f in (a.get("findings") or []):
            rows.append({"dim": a.get("category", "?"), "level": f.get("level", "INFO")})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    level_order = ["CRITICAL", "WARNING", "INFO", "OK"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.4), dpi=110)

    # 左：按维度×级别计数堆叠柱状图
    pivot = df.pivot_table(index="dim", columns="level", aggfunc="size", fill_value=0)
    keep = [lv for lv in level_order if lv in pivot.columns]
    pivot = pivot[keep] if keep else pivot
    pivot.plot(kind="bar", ax=ax1, stacked=True, colormap="RdYlGn_r")
    ax1.set_title("各维度异常分布")
    ax1.set_xlabel("")
    ax1.set_ylabel("异常数")
    ax1.tick_params(axis="x", rotation=30)

    # 右：severity 构成饼图（仅非 OK）
    non_ok = df[df["level"] != "OK"]
    if non_ok.empty:
        ax2.text(0.5, 0.5, "无异常", ha="center", va="center", fontsize=14)
    else:
        counts = non_ok["level"].value_counts()
        colors = {"CRITICAL": "#d62728", "WARNING": "#ff7f0e", "INFO": "#1f77b4"}
        ax2.pie(counts.values, labels=counts.index, autopct="%1.0f%%",
                colors=[colors.get(l, "#7f7f7f") for l in counts.index])
    ax2.set_title("异常严重度构成")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_offline(engine, out_dir):
    """离线全景：按 duration 分级的 设备数 vs 记录数 双口径条形图。返回路径或 None。"""
    path = _safe_path(out_dir, "offline_overview.png")
    try:
        rows = pd.read_sql(text(
            "SELECT "
            "  CASE WHEN total_offline_duration > 86400 THEN 'CRITICAL>24h' "
            "       WHEN total_offline_duration > 14400 THEN 'ERROR 4-24h' "
            "       WHEN total_offline_duration > 3600 THEN 'WARNING 1-4h' "
            "       ELSE 'INFO <1h' END AS bucket, "
            "  COUNT(*) AS records, COUNT(DISTINCT equipment_code) AS devices "
            "FROM eq_equip_offline_record GROUP BY bucket ORDER BY bucket"
        ), engine)
    except Exception:
        return None
    if rows.empty:
        return None
    order = ["CRITICAL>24h", "ERROR 4-24h", "WARNING 1-4h", "INFO <1h"]
    rows["bucket"] = pd.Categorical(rows["bucket"], categories=order, ordered=True)
    rows = rows.sort_values("bucket")

    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=110)
    x = range(len(rows))
    w = 0.38
    ax.bar([i - w / 2 for i in x], rows["records"], width=w, label="记录数", color="#d62728")
    ax.bar([i + w / 2 for i in x], rows["devices"], width=w, label="设备数", color="#1f77b4")
    ax.set_xticks(list(x))
    ax.set_xticklabels(rows["bucket"], rotation=15)
    ax.set_ylabel("数量")
    ax.set_title("离线分级：记录数 vs 设备数（双口径）")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_correlation(engine, days, out_dir):
    """水位-渗压双轴联动曲线（对应渗压-水位因果链结论）。返回路径或 None。"""
    path = _safe_path(out_dir, "correlation_wl_pressure.png")
    wl = _read_series(engine, "st_rsvr_r", "rz", days)
    pr = _read_series(engine, "st_pressure_r", "water_pressure", days)
    if wl.empty or pr.empty:
        return None
    wl = wl.set_index("tm")["value"].astype(float)
    pr = pr.set_index("tm")["value"].astype(float)
    # 同一时刻多测站记录 → 取均值，保证索引唯一（否则 loc 展开后 x/y 维度不一致）
    wl = wl.groupby(level=0).mean()
    pr = pr.groupby(level=0).mean()
    # 对齐到小时（两表均小时级），取交集
    idx = wl.index.intersection(pr.index)
    if len(idx) < 2:
        return None
    fig, ax1 = plt.subplots(figsize=(9, 3.4), dpi=110)
    ax1.plot(idx, wl.loc[idx], color="#1f77b4", label="水位(m)", linewidth=1.2)
    ax1.set_ylabel("水位 (m)", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax2 = ax1.twinx()
    ax2.plot(idx, pr.loc[idx], color="#d62728", label="渗压(kPa)", linewidth=1.2)
    ax2.set_ylabel("渗压 (kPa)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")
    ax1.set_title(f"水位-渗压联动（近{days}天）")
    ax1.grid(alpha=0.3)
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [l.get_label() for l in lines], loc="best")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def render_charts(engine, days, analyses, out_dir):
    """统一入口：返回 {section_key: [ {path, title} ]}，供 generate_report 接线。"""
    result = {}
    trends = chart_trends(engine, days, out_dir)
    if trends:
        result["trends"] = trends
    sev = chart_severity(analyses, out_dir)
    if sev:
        result["severity"] = [{"path": sev, "title": "异常分布"}]
    off = chart_offline(engine, out_dir)
    if off:
        result["offline"] = [{"path": off, "title": "离线全景（双口径）"}]
    corr = chart_correlation(engine, days, out_dir)
    if corr:
        result["correlation"] = [{"path": corr, "title": "水位-渗压联动"}]
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                    "_shared", "lib"))
    from db import get_sqlalchemy_url
    from sqlalchemy import create_engine
    engine = create_engine(get_sqlalchemy_url())
    charts = render_charts(engine, days=7, analyses=[], out_dir="/tmp/inspection-charts")
    for key, items in charts.items():
        print(f"{key}: {[i['path'] for i in items]}")
