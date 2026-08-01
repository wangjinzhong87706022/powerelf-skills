#!/usr/bin/env python3
"""
eval_cases/fixtures.py — Layer A 评测的输入数据工厂（无 DB）

每个 case_id 对应一个工厂函数，返回 {table: pd.DataFrame}，供 eval_runner monkeypatch
read_sensor_data 时按 table 返回。cases.json 的 rows_desc 仅供人类阅读，本文件才是机器输入。

fixture 约束（探查实证）：
  - 列须含 analyze_* SELECT 的字段（至少 st_id, value_col, tm）；tm 用 pd.Timestamp（可排序）。
  - 不要 deleted 列（过滤在 read_sensor_data 的 SQL 内，mock 后跳过）。
  - value 列非空率 >80%（否则 check_data_quality 判红档 inconclusive）。
  - analyze_pressure 的变化检测只看末对 wp[-1] vs wp[-2]——spike 用例须把尖峰放倒数第二、末点回落。

只覆盖走 read_sensor_data 的维度（4.9 全覆盖 + 回归）。水质/墒情/白蚁/巡检/设备/告警走 inline
pd.read_sql 或专用 reader，机制不同，留 extension（见 eval_runner 的 skipped 报告）。
"""

import pandas as pd

# 固定时间锚（避免 Date.now 类不确定）：2026-07-31 00:00 为窗口末端，向前 periods 个小时
_ANCHOR = pd.Timestamp("2026-07-31 00:00:00")


def _hours(n, freq="1h"):
    """升序 n 个时间戳（analyze_* 内部会 sort_values，升序降序均可，给升序最直观）。"""
    return list(pd.date_range(end=_ANCHOR, periods=n, freq=freq))


def _df(**cols):
    return pd.DataFrame(cols)


# ============================================================
# 渗压监测 st_pressure_r（变化率三分通道 + MAD + 诊断链）
# 字段：st_id, water_pressure, ext_pressure, ext_temperature, tm
# ============================================================

def _pressure_df(wp_series, st_id=9003):
    n = len(wp_series)
    return _df(st_id=[st_id] * n, water_pressure=wp_series,
               ext_pressure=[25.0] * n, ext_temperature=[20.0] * n, tm=_hours(n))


def PRES_POS_1():
    """应报 WARNING：末对上跳 5.1kPa 未回落 → classify 'none' → WARNING（非 spike）"""
    return {"st_pressure_r": _pressure_df([50.0] * 9 + [55.1])}


def PRES_NEG_1():
    """不应报：末对变化 4.9kPa < 阈值 5"""
    return {"st_pressure_r": _pressure_df([50.0] * 9 + [54.9])}


def PRES_SPIKE_1():
    """应报 INFO：尖峰在倒数第二、末点回落 → 末对是 85→50 的回落步(检出) + classify spike → INFO"""
    return {"st_pressure_r": _pressure_df([50.0] * 9 + [85.0, 50.0])}


def DIAG_HIT_1():
    """渗压突变 5.5kPa（WARNING 命中诊断路由 R1）→ run_auto_diagnosis 回填 root_cause"""
    return {"st_pressure_r": _pressure_df([50.0] * 9 + [55.5])}


def DIAG_MISS_1():
    """渗压突变 5.5kPa，但外因全空 → 诊断未命中 root_cause，detail 须含'已查'(空证据可区分)"""
    return {"st_pressure_r": _pressure_df([50.0] * 9 + [55.5])}


# ============================================================
# 渗流监测 st_percolation_r（变化率扫描全对 + MAD）
# 字段：st_id, percolation, tm
# ============================================================

def _percolation_df(perc_series, st_id=9004):
    n = len(perc_series)
    return _df(st_id=[st_id] * n, percolation=perc_series, tm=_hours(n))


def PERC_POS_1():
    """应报：相邻 1.000→1.201（+20.1%>20%）；末点未回落 → WARNING"""
    return {"st_percolation_r": _percolation_df([1.0] * 9 + [1.201])}


def PERC_NEG_1():
    """不应报：变化 +19.5% < 20%"""
    return {"st_percolation_r": _percolation_df([1.0] * 9 + [1.195])}


def PERC_SPIKE_1():
    """应报 INFO：渗流单点尖峰回落 → spike"""
    return {"st_percolation_r": _percolation_df([1.0] * 9 + [3.0, 1.0])}


# ============================================================
# 闸门工情 rei_gate_r（变化率扫描全对，报全部）
# 字段：st_id, gtophgt, gtopnum, gtq, status, tm
# ============================================================

def _gate_df(gtophgt, gtq=None, status=None, st_id=9006):
    n = len(gtophgt)
    return _df(st_id=[st_id] * n, gtophgt=gtophgt, gtopnum=[1] * n,
               gtq=gtq if gtq is not None else [0.0] * n,
               status=status if status is not None else [1] * n, tm=_hours(n))


def GATE_POS_1():
    """应报：开度突变 2.5m（>1m）；末点未回落 → WARNING"""
    return {"rei_gate_r": _gate_df([1.0] * 9 + [3.5])}


def GATE_NEG_1():
    """不应报：开度变化恰 1.0m（阈值 1.0，>才报，=不报）"""
    return {"rei_gate_r": _gate_df([1.0] * 9 + [2.0])}


# ============================================================
# 水库水情 st_rsvr_r（趋势 + MAD + 季节护栏 + 入出库比 + 质量闸 + 空数据）
# 字段：st_id, rz, inq, otq, w, tm
# ============================================================

def _rsvr_df(rz, inq=None, otq=None, st_id=9001):
    n = len(rz)
    return _df(st_id=[st_id] * n, rz=rz,
               inq=inq if inq is not None else [10.0] * n,
               otq=otq if otq is not None else [10.0] * n,
               w=[100.0] * n, tm=_hours(n))


def WL_POS_1():
    """应报：水位连续上升 6 次（consecutive_monotonic rise,5）。
    注：占位 st_id 无历史同期数据，seasonal_check 返回 in_season=False → 保持 WARNING。"""
    return {"st_rsvr_r": _rsvr_df([100.0, 100.1, 100.2, 100.3, 100.4, 100.5])}


def WL_NEG_1():
    """不应报连续上升：仅 4 次后末点持平"""
    return {"st_rsvr_r": _rsvr_df([100.0, 100.1, 100.2, 100.3, 100.4, 100.4])}


def SEASON_GUARD_1():
    """季节护栏：7 月汛期 MAD 离群高水位。seasonal_check mock 返回 in_season=True → 降级 INFO。
    rz 历史须有抖动（mad>0），末点 108 离群。"""
    import numpy as np
    rng = np.random.RandomState(7)
    rz = [100.0 + float(rng.uniform(-0.5, 0.5)) for _ in range(29)] + [108.0]
    return {"st_rsvr_r": _rsvr_df(rz)}


def MAD_POS_1():
    """应报 MAD：30 点稳定 50±0.05（须真实抖动 mad>0），末点 60.0（z 远超阈值）。"""
    import numpy as np
    rng = np.random.RandomState(42)
    base = [50.0 + float(rng.uniform(-0.05, 0.05)) for _ in range(29)]
    return {"st_pressure_r": _pressure_df(base + [60.0])}


def MAD_NEG_1():
    """不应报 MAD：同形态离群但仅 19 点（< min_samples 20）"""
    return {"st_pressure_r": _pressure_df([50.0] * 18 + [60.0])}


def QG_RED_1():
    """质量闸红档：rz 列非空率 <80% → red → INCONCLUSIVE。
    注：check_data_quality 的'完整性'= value 列非空比率（非时间稀疏度），故注入 NaN 触发。"""
    import numpy as np
    rz = [100.0, 100.1] + [float("nan")] * 8  # 非空率 20% <80% → 红
    return {"st_rsvr_r": _rsvr_df(rz, st_id=9012)}


def EMPTY_NA_1():
    """空数据 NOT_APPLICABLE：表历史为空。st_river_r 无对应 analyzer，借 st_percolation_r
    走 analyze_percolation 的 no_data_result 分支 + probe_table_latest mock 返回 None。"""
    return {"st_percolation_r": pd.DataFrame(columns=["st_id", "percolation", "tm"])}


def EMPTY_ND_1():
    """空数据 NO_DATA：窗口内为空但表有历史（probe 返回时间戳）→ 疑似采集中断"""
    return {"st_percolation_r": pd.DataFrame(columns=["st_id", "percolation", "tm"])}


# ============================================================
# 关联异常（多表：st_rsvr_r + st_pressure_r + st_pptn_r）
# ============================================================

def CORR_POS_1():
    """关联3应报 INFO：累计雨量 60mm 但水位变化<0.05m（水位须非平线 CV≥idle_cv_min）"""
    rain = {"st_id": [9002] * 6, "p": [10.0] * 6, "dr": [0.0] * 6, "dyp": [0.0] * 6,
            "tm": _hours(6)}
    water = _rsvr_df([100.0, 100.5, 100.1, 100.6, 100.2, 100.04])  # 抖动足 CV>0.001，首末差0.04<0.05
    pressure = _pressure_df([50.0] * 6)
    return {"st_pptn_r": _df(**rain), "st_rsvr_r": water, "st_pressure_r": pressure}


def CORR_NEG_1():
    """关联3不应报：水位死值平线（恒等 100.000）→ idle 护栏抑制"""
    rain = {"st_id": [9002] * 6, "p": [10.0] * 6, "dr": [0.0] * 6, "dyp": [0.0] * 6,
            "tm": _hours(6)}
    water = _rsvr_df([100.0] * 6)  # 全程恒等 → CV=0 < idle_cv_min
    pressure = _pressure_df([50.0] * 6)
    return {"st_pptn_r": _df(**rain), "st_rsvr_r": water, "st_pressure_r": pressure}


def CORR_POS_2():
    """关联2应报 WARNING：渗压持续上升 + 水位稳定（rz 变化<0.1 且非平线）"""
    water = _rsvr_df([100.0, 100.5, 100.2, 100.6, 100.3, 100.04])  # 首末差0.04<0.1，CV>0.001 非平线
    pressure = _pressure_df([50.0, 52.0, 54.0, 56.0, 58.0, 60.0])      # 严格递增
    rain = {"st_id": [9002] * 2, "p": [0.0, 0.0], "tm": _hours(2)}
    return {"st_rsvr_r": water, "st_pressure_r": pressure, "st_pptn_r": _df(**rain)}


def CORR_NEG_2():
    """关联2不应报：渗压升但水位死值平线 → idle 抑制"""
    water = _rsvr_df([100.0] * 6)  # 死值平线
    pressure = _pressure_df([50.0, 52.0, 54.0, 56.0, 58.0, 60.0])
    rain = {"st_id": [9002] * 2, "p": [0.0, 0.0], "tm": _hours(2)}
    return {"st_rsvr_r": water, "st_pressure_r": pressure, "st_pptn_r": _df(**rain)}


# ============================================================
# case_id → 工厂映射
# ============================================================
FIXTURES = {
    "PRES-POS-1": PRES_POS_1,
    "PRES-NEG-1": PRES_NEG_1,
    "PRES-SPIKE-1": PRES_SPIKE_1,
    "DIAG-HIT-1": DIAG_HIT_1,
    "DIAG-MISS-1": DIAG_MISS_1,
    "PERC-POS-1": PERC_POS_1,
    "PERC-NEG-1": PERC_NEG_1,
    "PERC-SPIKE-1": PERC_SPIKE_1,
    "GATE-POS-1": GATE_POS_1,
    "GATE-NEG-1": GATE_NEG_1,
    "WL-POS-1": WL_POS_1,
    "WL-NEG-1": WL_NEG_1,
    "SEASON-GUARD-1": SEASON_GUARD_1,
    "MAD-POS-1": MAD_POS_1,
    "MAD-NEG-1": MAD_NEG_1,
    "QG-RED-1": QG_RED_1,
    "EMPTY-NA-1": EMPTY_NA_1,
    "EMPTY-ND-1": EMPTY_ND_1,
    "CORR-POS-1": CORR_POS_1,
    "CORR-NEG-1": CORR_NEG_1,
    "CORR-POS-2": CORR_POS_2,
    "CORR-NEG-2": CORR_NEG_2,
}


# ============================================================
# 特殊 mock 配置（超出纯 fixture 的 case 级控制）
# ============================================================

# seasonal_check 返回值（季节用例需 in_season=True 触发降级；其余用例默认不 mock=生产行为，
# 但占位 st_id 无历史数据会返回 in_season=False，故只对季节用例显式 mock）
SEASONAL_OVERRIDE = {
    "SEASON-GUARD-1": {"in_season": True, "seasonal_median": 100.0,
                       "note": "test: 与历年同期一致(同期中位数100.00, z=0.8)，季节性护栏放行"},
}

# 空 data 四分法：probe_table_latest 返回（None→NOT_APPLICABLE；时间戳→NO_DATA 有历史）
PROBE_LATEST_OVERRIDE = {
    "EMPTY-NA-1": None,       # 表历史为空 → NOT_APPLICABLE
    "EMPTY-ND-1": "2026-06-15 00:00:00",  # 有历史窗口内空 → NO_DATA(采集中断)
}
