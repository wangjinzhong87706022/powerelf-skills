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
# 回归维度（read_sensor_data）：水位入出库比 / 雨量 / 位移 / 闸门流量 / 泵站
# ============================================================

def WL_POS_2():
    """应报：末条 inq=21, otq=10，比值 2.1>2 → WARNING 入库流量"""
    rz = [100.0, 100.01, 100.02, 100.01, 100.02, 100.03]
    return {"st_rsvr_r": _rsvr_df(rz, inq=[10.0] * 5 + [21.0], otq=[10.0] * 6)}


def WL_NEG_2():
    """不应报：末条 inq=20, otq=10，比值恰 2.0（严格大于才报）"""
    rz = [100.0, 100.01, 100.02, 100.01, 100.02, 100.03]
    return {"st_rsvr_r": _rsvr_df(rz, inq=[10.0] * 5 + [20.0], otq=[10.0] * 6)}


def _rain_df(p_series, st_id=9002):
    n = len(p_series)
    return _df(st_id=[st_id] * n, p=p_series, dr=[0.0] * n, dyp=[0.0] * n, tm=_hours(n))


def RAIN_POS_1():
    """应报 CRITICAL：单时段 p=100.1mm > 红色阈值 100"""
    return {"st_pptn_r": _rain_df([100.1])}


def RAIN_NEG_1():
    """不应报：p=29.9mm < 蓝色阈值 30"""
    return {"st_pptn_r": _rain_df([29.9])}


def _gnss_df(speed_gh, st_id=9005):
    n = len(speed_gh)
    return _df(st_id=[st_id] * n, wgs84_delta_h=[0.0] * n, wgs84_delta_x=[0.0] * n,
               wgs84_delta_y=[0.0] * n, speed_gh=speed_gh, speed_gx=[0.0] * n,
               speed_gy=[0.0] * n, tm=_hours(n))


def GNSS_POS_1():
    """应报：speed_gh 5 点 4 次连续加速 → WARNING"""
    return {"dsm_dfr_srvrds_srhrds": _gnss_df([1.0, 2.0, 3.0, 4.0, 5.0])}


def GNSS_NEG_1():
    """不应报：5 点仅 3 次连续加速（阈值 4）"""
    return {"dsm_dfr_srvrds_srhrds": _gnss_df([1.0, 2.0, 3.0, 3.0, 4.0])}


def GATE_POS_2():
    """应报：开度 2.5m>0 且流量 0 → WARNING 流量为0"""
    return {"rei_gate_r": _gate_df([2.5, 2.5], gtq=[0.0, 0.0])}


def GATE_NEG_2():
    """不应报：全窗口开度 0 流量 0（闸门关闭，0 是合法观测，不报卡阻也不归 no_data）"""
    return {"rei_gate_r": _gate_df([0.0, 0.0], gtq=[0.0, 0.0])}


def _pump_df(freq=None, uab=None, ubc=None, uca=None, st_id=9007):
    n = len(freq) if freq else len(uab)
    return _df(st_id=[st_id] * n,
               uab=uab if uab else [400.0] * n, ubc=ubc if ubc else [400.0] * n,
               uca=uca if uca else [400.0] * n, ia=[10.0] * n, ib=[10.0] * n, ic=[10.0] * n,
               p=[5.0] * n, freq=freq if freq else [50.0] * n, status=[1] * n, tm=_hours(n))


def PUMP_POS_1():
    """应报：freq=44.9 < 下界 45 → WARNING 频率"""
    return {"rei_pump_r": _pump_df(freq=[44.9])}


def PUMP_NEG_1():
    """不应报：freq=45.0 恰等于下界（严格小于才报）"""
    return {"rei_pump_r": _pump_df(freq=[45.0])}


def PUMP_POS_2():
    """应报：uab=400,ubc=400,uca=464 不平衡>10% → WARNING 三相不平衡"""
    return {"rei_pump_r": _pump_df(uab=[400.0], ubc=[400.0], uca=[464.0])}


# ============================================================
# inline pd.read_sql 维度：水质 / 墒情 / 白蚁
# ============================================================

def _wq_df(ph, stcd=9008):
    n = len(ph)
    return _df(stcd=[stcd] * n, spt=_hours(n), ph=ph, dox=[7.0] * n, nh3n=[0.5] * n,
               tn=[1.0] * n, tp=[0.1] * n, turb=[5.0] * n, wtmp=[20.0] * n)


def WQ_POS_1():
    """应报：最新一条 ph=5.99<6 → WARNING pH偏低。
    analyzer 取 values.iloc[0] 为 latest（SQL DESC），故异常值置首行。"""
    return {"wq_pcp_d": _wq_df([5.99, 7.5, 7.4])}


def WQ_NEG_1():
    """不应报：ph=6.00（恰等于下界，不报）"""
    return {"wq_pcp_d": _wq_df([6.00, 7.5, 7.4])}


def _soil_df(eval_series, water100=None, st_id=9009):
    n = len(eval_series)
    return _df(st_id=[st_id] * n, tm=_hours(n), soil_water10cm=[20.0] * n,
               soil_water20cm=[20.0] * n, soil_water30cm=[20.0] * n,
               soil_water60cm=[20.0] * n,
               soil_water100cm=water100 if water100 else [25.0] * n,
               soil_moist_evaluation=eval_series)


def SOIL_POS_1():
    """应报：soil_moist_evaluation='重度干旱'"""
    return {"st_soil_moisture_r": _soil_df(["重度干旱"])}


def SOIL_NEG_1():
    """不应报：'适宜'"""
    return {"st_soil_moisture_r": _soil_df(["适宜"], water100=[25.0])}


def _termite_df(damage=None, pest=None, check_result="未发现", st_id=9010):
    n = len(damage) if damage else len(pest)
    return _df(st_id=[st_id] * n, tm=_hours(n), termite_species=["黑翅土白蚁"] * n,
               pest_density=pest if pest else [None] * n,
               damage_level=damage if damage else [None] * n,
               damage_range=[""] * n, check_result=[check_result] * n)


def TERM_POS_1():
    """应报 CRITICAL：damage_level='重度'"""
    return {"st_termite_monitor_r": _termite_df(damage=["重度"])}


def TERM_POS_2():
    """应报 WARNING：pest_density=3（damage_level NULL）"""
    return {"st_termite_monitor_r": _termite_df(pest=[3])}


def TERM_NEG_1():
    """不应报：pest_density=2（阈值 3，差 1）"""
    return {"st_termite_monitor_r": _termite_df(pest=[2])}


# ============================================================
# 专用 reader 维度：巡检结果 / 设备状态 / 告警分析（均走 pd.read_sql）
# ============================================================

def _insp_df(status_list):
    n = len(status_list)
    return _df(id=list(range(1, n + 1)), name=[f"task{i}" for i in range(1, n + 1)],
               status=status_list, exceed_time=[0] * n, bad_num=[0] * n,
               check_percent=[100.0] * n, plan_time=_hours(n), begin_time=_hours(n),
               end_time=_hours(n), create_time=_hours(n))


def INSP_POS_1():
    """应报：100 任务 69 完成(69%<70%) → WARNING 完成率偏低"""
    return {"business_check_task": _insp_df(["3"] * 69 + ["1"] * 31)}


def INSP_NEG_1():
    """不应报：70 完成(70%，恰阈值)"""
    return {"business_check_task": _insp_df(["3"] * 70 + ["1"] * 30)}


def _equip_df(status_list):
    n = len(status_list)
    return _df(id=list(range(1, n + 1)), name=[f"dev{i}" for i in range(1, n + 1)],
               code=[f"C{i}" for i in range(1, n + 1)], status=status_list,
               category=["闸门"] * n)


def EQUIP_POS_1():
    """应报：100 台 31 离线(31%>30%) → WARNING 离线率偏高（无 status=2 异常）"""
    return {"eq_equip_base": _equip_df([0] * 31 + [1] * 69)}


def EQUIP_NEG_1():
    """不应报：30 离线(30%，恰阈值)"""
    return {"eq_equip_base": _equip_df([0] * 30 + [1] * 70)}


def _alert_df(level_list):
    n = len(level_list)
    return _df(id=list(range(1, n + 1)), ew_name=[f"告警{i}" for i in range(1, n + 1)],
               ew_type=["1"] * n, level_r=level_list, value=[0.0] * n,
               gather_time=_hours(n), message_confirm=[0] * n)


def ALERT_POS_1():
    """应报 CRITICAL：1 条 level_r='1' 未确认 → I级告警"""
    return {"ew_info_message": _alert_df(["1"])}


def ALERT_NEG_1():
    """不应报：10 条 level_r='4'（无 I/II 级）"""
    return {"ew_info_message": _alert_df(["4"] * 10)}


# ============================================================
# 质量闸（占位值）+ 空数据（查询失败）
# ============================================================

def QG_PLACEHOLDER_1():
    """质量闸占位值：rz 混入 -99/999 各 3 个（占位 60%>20% → 红 + 占位值 issue），
    另含合法 0.00 读数（0 ∉ _PLACEHOLDER_VALUES，不计占位）。"""
    rz = [100.0, 0.0, -99.0, 999.0, -99.0, 999.0, -99.0, 999.0, 100.0, 0.0]
    return {"st_rsvr_r": _rsvr_df(rz, st_id=9012)}


def EMPTY_QF_1():
    """空数据 QUERY_FAILED：mock read_sensor_data 抛异常 → QUERY_ERRORS 置位。
    实际通过 eval_runner 的 QUERY_ERRORS_SET 预置实现，fixture 给空 DF 占位。"""
    return {"st_percolation_r": pd.DataFrame(columns=["st_id", "percolation", "tm"])}


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
    "QG-PLACEHOLDER-1": QG_PLACEHOLDER_1,
    "EMPTY-NA-1": EMPTY_NA_1,
    "EMPTY-ND-1": EMPTY_ND_1,
    "EMPTY-QF-1": EMPTY_QF_1,
    "CORR-POS-1": CORR_POS_1,
    "CORR-NEG-1": CORR_NEG_1,
    "CORR-POS-2": CORR_POS_2,
    "CORR-NEG-2": CORR_NEG_2,
    "WL-POS-2": WL_POS_2,
    "WL-NEG-2": WL_NEG_2,
    "RAIN-POS-1": RAIN_POS_1,
    "RAIN-NEG-1": RAIN_NEG_1,
    "GNSS-POS-1": GNSS_POS_1,
    "GNSS-NEG-1": GNSS_NEG_1,
    "GATE-POS-2": GATE_POS_2,
    "GATE-NEG-2": GATE_NEG_2,
    "PUMP-POS-1": PUMP_POS_1,
    "PUMP-NEG-1": PUMP_NEG_1,
    "PUMP-POS-2": PUMP_POS_2,
    "WQ-POS-1": WQ_POS_1,
    "WQ-NEG-1": WQ_NEG_1,
    "SOIL-POS-1": SOIL_POS_1,
    "SOIL-NEG-1": SOIL_NEG_1,
    "TERM-POS-1": TERM_POS_1,
    "TERM-POS-2": TERM_POS_2,
    "TERM-NEG-1": TERM_NEG_1,
    "INSP-POS-1": INSP_POS_1,
    "INSP-NEG-1": INSP_NEG_1,
    "EQUIP-POS-1": EQUIP_POS_1,
    "EQUIP-NEG-1": EQUIP_NEG_1,
    "ALERT-POS-1": ALERT_POS_1,
    "ALERT-NEG-1": ALERT_NEG_1,
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

# QUERY_FAILED：预置 ia.QUERY_ERRORS[table]=code，使 no_data_result 走 QUERY_FAILED 分支
QUERY_ERRORS_SET = {
    "EMPTY-QF-1": ("st_percolation_r", "QUERY_TIMEOUT"),
}
