#!/usr/bin/env python3
"""
传感器数据巡检分析工具（inspection_analyzer）
职责：读取传感器/监测数据表，执行异常检测，输出巡检报告。

分析维度（15项）：
  水库水情、雨量、渗压、渗流、位移、闸门、泵站、水质、墒情、白蚁、
  巡检结果、设备状态、告警、MAD统计异常、多指标关联异常

用法:
  python3 inspection_analyzer.py --db "$DB_URL"
  python3 inspection_analyzer.py --db "..." --days 30
  python3 inspection_analyzer.py --db "..." --limit 10000
  python3 inspection_analyzer.py --db "..." --output report.md
  python3 inspection_analyzer.py --db "..." --json

注意：巡检质量评分、缺陷趋势预测、路线效率分析由 inspection_tool.py 负责。
"""

import argparse
import json
import logging
import sys
import os as _os
from datetime import datetime, timedelta

logger = logging.getLogger("inspection_analyzer")

# 导入 lib/anomaly（P2-T6 接线）
_sys_path_orig = sys.path[:]
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))
import anomaly as _anomaly
sys.path = _sys_path_orig

from registry import _validate_identifiers  # P1-5: 标识符白名单校验（防 SQL 注入）

try:
    import pandas as pd
    import numpy as np
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("需要安装: pip install pandas numpy sqlalchemy pymysql")
    sys.exit(1)


# ============================================================
# 0. 静态兜底阈值（Phase 4.8）与无数据四分法（Phase 4.1）
# ============================================================

# 静态兜底阈值集中字典。动态阈值单一来源仍是 ew_info_rules / sys_data_source_registry，
# 本字典只收 get_threshold/get_registry_threshold 查不到时的兜底值。
THRESHOLDS = {
    "rain_red_mm": 100,          # Why: SL 158-2010 暴雨红色预警单时段雨量经验线
    "rain_orange_mm": 80,        # Why: 橙色预警经验线
    "rain_yellow_mm": 50,        # Why: 黄色预警经验线（50mm/h 短时强降雨界）
    "rain_blue_mm": 30,          # Why: 蓝色预警经验线
    "rain_shortburst_mm": 30,    # Why: 短时强降雨关注线（气象行业惯例 30mm/h）
    "pressure_change_kpa": 5,    # Why: 渗压计相邻读数突变 >5kPa 超出正常水位响应幅度（专家经验）
    "percolation_change_pct": 20,  # Why: 渗流量突变 >20% 提示坝脚渗漏风险（历史误报率调优值）
    "gate_opening_jump_m": 1.0,  # Why: 单步开度变化 >1m 通常对应人工调度，需外因核验
    "gate_fluct_step_m": 0.3,    # Why: 6 点窗口内 ≥4 次 >0.3m 波动提示控制系统不稳定
    "pump_imbalance_ratio": 0.10,  # Why: GB/T 15543 三相不平衡度限值 10%
    "pump_freq_low_hz": 45,      # Why: 工频 50Hz ±10% 下界
    "pump_freq_high_hz": 55,     # Why: 工频 50Hz ±10% 上界
    "disp_speed_ii_mmd": 1.0,    # Why: 位移速率 II 级异常经验线（规范分级）
    "disp_speed_iii_mmd": 0.5,   # Why: 位移速率 III 级异常经验线
    "disp_delta_h_mm": 10,       # Why: 单次高程变化 >10mm 超 GNSS 常规噪声带
    "completion_rate_min": 0.7,  # Why: 巡检完成率 <70% 视为管理异常（考核线）
    "overtime_rate_max": 0.3,    # Why: 超时率 >30% 提示路线/时长配置不合理
    "omission_rate_max": 0.2,    # Why: 漏检率 >20% 视为无效巡检（考核线）
    "equip_offline_rate_max": 0.3,  # Why: 离线率 >30% 提示通信/供电系统性问题
    "idle_cv_min": 0.001,        # Why: 基础量变异系数低于此值视为平线，跳过相关性判定防伪相关
    "seasonal_lookback_years": 3,  # Why: 历年同期取近3个完整年同月（排除当年本月，防当前事件污染基线）
    "seasonal_z_threshold": 3.0,   # Why: 与 MAD 层 z=3~4 同口径，超即判非季节性
    "seasonal_min_samples": 10,    # Why: 同月历史样本下限，防小样本中位数失真
    "quality_green_pct": 99,     # Why: 完整性色阶 绿 >99%（kwp explore-data 四档）
    "quality_yellow_pct": 95,    # Why: 完整性色阶 黄 95-99%
    "quality_orange_pct": 80,    # Why: 完整性色阶 橙 80-95%，<80 红 → 维度 inconclusive
}

# 无数据四分法（互斥）：
#   NOT_APPLICABLE  该工程无此类设备/表历史为空，不算异常
#   NO_DATA         表存在但窗口内无记录（已查证为空）；子类"采集中断"由新鲜度探针判别
#   QUERY_FAILED    查询报错——严禁写 0 或空充数
#   DATA_LOSS_GUARD DB 有值但报告拿不到 = Skill 自身故障，最高优先级修复
QUERY_ERRORS = {}  # table -> code，每次 generate_report 开头重置


def _classify_query_error(e):
    msg = str(e).lower()
    if "doesn't exist" in msg or "1146" in msg:
        return "TABLE_MISSING"
    if "timeout" in msg or "timed out" in msg or "lost connection" in msg:
        return "QUERY_TIMEOUT"
    return "QUERY_FAILED"


def probe_table_latest(engine, table, time_field="tm"):
    """新鲜度探针：MAX(time_field)。区分 NOT_APPLICABLE（表恒空）与采集中断。"""
    try:
        _validate_identifiers(table, time_field, time_field)
        df = pd.read_sql(text(f"SELECT MAX({time_field}) AS latest FROM {table} WHERE deleted = 0"),
                         engine)
        if df.empty or pd.isna(df.iloc[0]["latest"]):
            return None
        return df.iloc[0]["latest"]
    except Exception:
        return None


def no_data_result(category, table=None, engine=None, time_field="tm"):
    """空数据分支统一出口：产出带四分法 status_code 的维度结果。"""
    code = "NO_DATA"
    note = ""
    if table and table in QUERY_ERRORS:
        code = "QUERY_FAILED" if QUERY_ERRORS[table] != "TABLE_MISSING" else "TABLE_MISSING"
        note = f"查询失败({QUERY_ERRORS[table]})，严禁以 0 或空充数"
    elif table and engine is not None:
        latest = probe_table_latest(engine, table, time_field)
        if latest is None:
            code = "NOT_APPLICABLE"
            note = "该表历史为空——本工程可能无此类设备，不算异常"
        else:
            note = f"表有历史数据（最新 {latest}），窗口内为空——疑似采集中断，设备可能离线"
    return {"category": category, "status": "无数据", "status_code": code,
            "status_note": note, "findings": []}


# ============================================================
# 1. 数据读取
# ============================================================

def load_thresholds(engine):
    """从数据库读取所有阈值配置（ew_info_rules + sys_data_source_registry.judge_rules）"""
    thresholds = {"rules": {}, "registry": {}}

    # 从 ew_info_rules 读取预警阈值
    try:
        rules = pd.read_sql(text("""
            SELECT id, name, ew_type, level_r, st_id, extend
            FROM ew_info_rules WHERE deleted = 0 AND status = '1'
        """), engine)
        for _, rule in rules.iterrows():
            try:
                extend = json.loads(rule['extend']) if isinstance(rule['extend'], str) else rule['extend']
                key = f"{rule['ew_type']}_{rule['level_r']}_{rule['st_id']}"
                thresholds["rules"][key] = {
                    "id": int(rule['id']),
                    "name": rule['name'],
                    "value": float(extend['content'][0]) if extend.get('content', [None])[0] else None,
                    "value_upper": float(extend['content'][1]) if extend.get('content', [None, None])[1] else None,
                    "condition": extend.get('condition', '>'),
                }
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                logger.warning("解析 ew_info_rules 失败 rule=%s: %s", rule.get('id'), e)
    except Exception as e:
        logger.warning("读取 ew_info_rules 失败: %s", e)

    # 从 sys_data_source_registry 读取 judge_rules
    try:
        registry = pd.read_sql(text("""
            SELECT name, source_table, judge_rules
            FROM sys_data_source_registry WHERE status = 1 AND deleted = 0
        """), engine)
        for _, row in registry.iterrows():
            try:
                jr = json.loads(row['judge_rules']) if isinstance(row['judge_rules'], str) else row['judge_rules']
                if jr:
                    thresholds["registry"][row['source_table']] = jr
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                logger.warning("解析 registry judge_rules 失败 table=%s: %s", row.get('source_table'), e)
    except Exception as e:
        logger.warning("读取 sys_data_source_registry 失败: %s", e)

    return thresholds


def get_threshold(thresholds, ew_type, level_r, st_id=None, default=None):
    """从 ew_info_rules 阈值中获取值"""
    key = f"{ew_type}_{level_r}_{st_id}"
    entry = thresholds.get("rules", {}).get(key)
    if entry and entry.get("value"):
        return entry["value"]
    # 尝试不带 st_id 的通配
    for k, v in thresholds.get("rules", {}).items():
        if k.startswith(f"{ew_type}_{level_r}_") and v.get("value"):
            return v["value"]
    return default


def get_registry_threshold(thresholds, source_table, path, default=None):
    """从 sys_data_source_registry.judge_rules 中获取值，path 如 'rate.max_change'"""
    jr = thresholds.get("registry", {}).get(source_table, {})
    keys = path.split(".")
    val = jr
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default


def read_sensor_data(engine, table, fields, st_id=None, days=30, time_field="tm", limit=20000):
    """读取传感器数据"""
    _validate_identifiers(table, fields, time_field)  # P1-5: 标识符白名单校验（防注入）
    where_parts = [f"{time_field} >= NOW()-INTERVAL :days DAY", "deleted = 0"]  # P1-1: 铁律 deleted=0
    params = {"days": days, "limit": limit}
    if st_id:
        where_parts.append("st_id = :st_id")
        params["st_id"] = st_id
    where = " AND ".join(where_parts)
    sql = f"SELECT {fields} FROM {table} WHERE {where} ORDER BY {time_field} DESC LIMIT :limit"
    try:
        df = pd.read_sql(text(sql), engine, params=params)
        QUERY_ERRORS.pop(table, None)
        return df
    except Exception as e:
        QUERY_ERRORS[table] = _classify_query_error(e)  # 四分法：QUERY_FAILED ≠ NO_DATA
        logger.warning("read_sensor_data 失败 table=%s fields=%s: %s", table, fields, e)
        return pd.DataFrame()


def read_warning_rules(engine):
    """读取预警规则"""
    try:
        return pd.read_sql(text("""
            SELECT id, name, ew_type, level_r, st_id, extend
            FROM ew_info_rules WHERE deleted = 0
        """), engine)
    except Exception as e:
        logger.warning("read_warning_rules 失败: %s", e)
        return pd.DataFrame()


def read_stations(engine):
    """读取测站信息"""
    try:
        return pd.read_sql(text("""
            SELECT id, code, name, type, status, longitude, latitude
            FROM att_st_base WHERE deleted = 0
        """), engine)
    except Exception as e:
        logger.warning("read_stations 失败: %s", e)
        return pd.DataFrame()


def read_inspections(engine, days=30):
    """读取巡检结果"""
    try:
        tasks = pd.read_sql(text("""
            SELECT id, name, status, exceed_time, bad_num, check_percent,
                   plan_time, begin_time, end_time, create_time
            FROM business_check_task
            WHERE deleted = 0 AND create_time >= NOW()-INTERVAL :days DAY
            ORDER BY create_time DESC
        """), engine, params={"days": days})
        return tasks
    except Exception as e:
        logger.warning("read_inspections 失败: %s", e)
        return pd.DataFrame()


def read_defects(engine, days=90):
    """读取巡检缺陷"""
    try:
        return pd.read_sql(text("""
            SELECT id, task_id, problem, status, check_time, create_time
            FROM business_check_error
            WHERE deleted = 0 AND create_time >= NOW()-INTERVAL :days DAY
            ORDER BY create_time DESC
        """), engine, params={"days": days})
    except Exception as e:
        logger.warning("read_defects 失败: %s", e)
        return pd.DataFrame()


def read_equipment(engine):
    """读取设备状态"""
    try:
        return pd.read_sql(text("""
            SELECT id, name, code, status, category
            FROM eq_equip_base WHERE deleted = 0
        """), engine)
    except Exception as e:
        logger.warning("read_equipment 失败: %s", e)
        return pd.DataFrame()


def read_alerts(engine, days=30):
    """读取告警记录"""
    try:
        return pd.read_sql(text("""
            SELECT id, ew_name, ew_type, level_r, value, gather_time, message_confirm
            FROM ew_info_message
            WHERE deleted = 0 AND create_time >= NOW()-INTERVAL :days DAY
            ORDER BY create_time DESC LIMIT 500
        """), engine, params={"days": days})
    except Exception as e:
        logger.warning("read_alerts 失败: %s", e)
        return pd.DataFrame()


# ============================================================
# 2. 分析函数
# ============================================================

def classify_timeseries(values):
    """时序异常三分通道（互斥）：根因先验不同，诊断路由分流。

    spike  瞬时尖峰：window_max 离群但 latest 已回落 → 最像单点毛刺/瞬时事件
    step   台阶变点：前后半段水平位移持续 → 最像传感器重标定或工况切换
    drift  缓变趋势：单向持续变化 → 最像渐进性物理过程（渗漏/沉降）
    none   无显著模式
    """
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n < 10:
        return {"pattern": "none", "latest": vals[-1] if vals else None,
                "window_max": max(vals) if vals else None}
    med = float(np.median(vals))
    mad = float(np.median([abs(v - med) for v in vals])) or 1e-9
    latest, wmax = vals[-1], max(vals)

    def z(v):
        return 0.6745 * (v - med) / mad

    half = n // 2
    med_a, med_b = float(np.median(vals[:half])), float(np.median(vals[half:]))
    diffs = [vals[i] - vals[i - 1] for i in range(1, n)]
    same_sign = max(sum(1 for d in diffs if d > 0), sum(1 for d in diffs if d < 0))

    if abs(z(wmax)) > 3.5 and abs(z(latest)) < 2.0:
        pattern = "spike"
    elif abs(z(med_b) - z(med_a)) > 3.0:
        pattern = "step"
    elif same_sign / max(len(diffs), 1) > 0.8:
        pattern = "drift"
    else:
        pattern = "none"
    return {"pattern": pattern, "latest": latest, "window_max": wmax}


_PATTERN_LABELS = {"spike": "瞬时尖峰(latest已回落)", "step": "台阶变点(疑传感器重标定/工况切换)",
                   "drift": "缓变趋势(疑渐进性物理过程)", "none": ""}


def _change_finding(values, prev, curr, *, st_id, unit, dim_label):
    """变化率 finding 定型（Phase 4.9 三分通道驱动）：变化已由调用方检出(prev→curr 超阈)后，
    按整窗 classify_timeseries 定型 spike/step/drift，决定 severity 与 pattern 字段。

      spike  → INFO  ：窗口峰值离群但 latest 已回落，最像单点毛刺/瞬时干扰；run_auto_diagnosis
                       按 pattern=spike 跳过(不烧诊断预算、防撞巧合降雨生伪根因)
      step   → WARNING：前后半段水平位移持续，疑传感器重标定/工况切换
      drift  → WARNING：单向持续变化，疑渐进性物理过程（渗漏/沉降）
    （真实异常多层共振：drift 趋势层 + MAD 层仍报 WARNING，故降级 spike 不漏报。）
    values 为该测站全窗口序列（供 classify 定型）；返回带 pattern 字段的 finding dict。"""
    ts = classify_timeseries(values.tolist() if hasattr(values, "tolist") else list(values))
    pat = ts["pattern"]
    level = "INFO" if pat == "spike" else "WARNING"
    label = _PATTERN_LABELS.get(pat, "")
    mag = abs(curr - prev)
    detail = (f"形态: {label or '无明显模式'}；当前{curr:.2f}{unit}/窗口峰值{ts['window_max']:.2f}{unit}"
              + ("；单点毛刺最像传感器瞬时干扰，已降级提示" if pat == "spike" else ""))
    return {
        "level": level,
        "pattern": pat,
        "message": f"{dim_label}{st_id}: 突变{mag:.2f}{unit} ({prev:.2f} → {curr:.2f})",
        "detail": detail,
    }


def seasonal_check(engine, table, value_col, st_id, current, time_field="tm"):
    """季节性护栏：与历年同期（近 N 完整年同月）基线比对，防汛期正常抬升被误报。

    昂贵诊断准入：只在异常已命中后调用，不作为例行动作。
    窗口=近 seasonal_lookback_years 个完整年的同月（YEAR <= YEAR(NOW())-1 排除当年本月，
    防当前事件本身污染基线）。返回 {"in_season": bool, "seasonal_median": float|None, "note": str}
    """
    try:
        _validate_identifiers(table, value_col, time_field)
        lookback = int(THRESHOLDS["seasonal_lookback_years"])
        df = pd.read_sql(text(f"""
            SELECT {value_col} AS v FROM {table}
            WHERE deleted = 0 AND st_id = :st_id
              AND MONTH({time_field}) = MONTH(NOW())
              AND YEAR({time_field}) BETWEEN YEAR(NOW()) - {lookback} AND YEAR(NOW()) - 1
            LIMIT 5000
        """), engine, params={"st_id": int(st_id)})
    except Exception as e:
        logger.warning("seasonal_check 查询失败 table=%s: %s", table, e)
        return {"in_season": False, "seasonal_median": None,
                "note": "历年同期基线查询失败，护栏未生效"}
    vals = pd.to_numeric(df["v"], errors="coerce").dropna()
    min_samples = int(THRESHOLDS["seasonal_min_samples"])
    if len(vals) < min_samples:
        return {"in_season": False, "seasonal_median": None,
                "note": f"历年同期样本不足(<{min_samples})，护栏未生效"}
    med = float(vals.median())
    mad = float((vals - med).abs().median()) or 1e-9
    z_threshold = float(THRESHOLDS["seasonal_z_threshold"])
    zscore = abs(0.6745 * (float(current) - med) / mad)
    if zscore <= z_threshold:
        return {"in_season": True, "seasonal_median": med,
                "note": f"与历年同期一致(同期中位数{med:.2f}, z={zscore:.1f})，季节性护栏放行"}
    return {"in_season": False, "seasonal_median": med,
            "note": f"偏离历年同期(同期中位数{med:.2f}, z={zscore:.1f})，非季节性"}


def _is_idle(values, idle_cv_min=None):
    """平线/空闲护栏（Phase 4.9）：基础量变异系数(CV)低于阈值视为死值/停测。

    用死值当'稳定'参照会造出伪相关（渗压升+水位'稳'≠矛盾，可能只是水位计卡滞）；
    也用于变化率判定前置——死值序列不应产生有意义的 spike/step/drift 分类。
    len<2 或均值≈0（CV 无相对意义）时返回 False（不判 idle，交回原判定）。
    idle_cv_min 缺省读 THRESHOLDS["idle_cv_min"]，可注入以利参数化测试。"""
    s = pd.Series(values).dropna().astype(float)
    if len(s) < 2 or abs(s.mean()) < 1e-9:
        return False
    cv = s.std() / abs(s.mean())
    return bool(cv < (idle_cv_min if idle_cv_min is not None else THRESHOLDS["idle_cv_min"]))


# 占位值候选（0 不在列——0 是有效读数，输出纪律 #5）
_PLACEHOLDER_VALUES = {-1.0, -99.0, -999.0, 999.0, 9999.0, 99999.0, 999999.0}


def check_data_quality(df, value_cols):
    """第 0 层数据质量闸（检测前置）：不达标维度整体标 inconclusive 而非硬跑出假异常。

    完整性色阶：>99 绿 / 95-99 黄 / 80-95 橙 / <80 红（红 → inconclusive）。
    占位值探测：-1/999999 等非物理值占比 >20% → 红。
    """
    issues = []
    if df.empty or not value_cols:
        return {"tier": "red", "completeness_pct": 0.0, "issues": ["空数据集"]}
    ratios = []
    for col in value_cols:
        if col not in df.columns:
            issues.append(f"列缺失: {col}")
            ratios.append(0.0)
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        ratio = float(vals.notna().mean()) * 100
        ratios.append(ratio)
        nonnull = vals.dropna()
        if len(nonnull) > 0:
            ph_ratio = float(nonnull.isin(list(_PLACEHOLDER_VALUES)).mean())
            if ph_ratio > 0.2:
                issues.append(f"{col}: 占位值占比 {ph_ratio:.0%}（-1/999999 类非物理值）")
    completeness = min(ratios) if ratios else 0.0
    if issues and any("占位值" in i for i in issues):
        tier = "red"
    elif completeness > THRESHOLDS["quality_green_pct"]:
        tier = "green"
    elif completeness >= THRESHOLDS["quality_yellow_pct"]:
        tier = "yellow"
    elif completeness >= THRESHOLDS["quality_orange_pct"]:
        tier = "orange"
    else:
        tier = "red"
        issues.append(f"完整性 {completeness:.1f}% < {THRESHOLDS['quality_orange_pct']}%")
    return {"tier": tier, "completeness_pct": round(completeness, 1), "issues": issues}


def analyze_water_level(engine, days=30, thresholds=None):
    """分析水库水情"""
    findings = []
    thresholds = thresholds or {}

    # 读取最近数据
    df = read_sensor_data(engine, "st_rsvr_r", "st_id, rz, inq, otq, w, tm", days=days)
    if df.empty:
        return no_data_result("水库水情", "st_rsvr_r", engine)

    # 第 0 层数据质量闸（Phase 4.6）：红档不硬跑，整体 inconclusive
    quality = check_data_quality(df, ["rz"])
    if quality["tier"] == "red":
        return {"category": "水库水情", "status": "inconclusive",
                "status_code": "INCONCLUSIVE",
                "status_note": f"数据质量红档: {'; '.join(quality['issues'])}",
                "quality": quality, "findings": []}

    # 按测站分析
    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm')
        if len(st_data) < 2:
            continue

        latest = st_data.iloc[-1]
        rz = float(latest['rz']) if pd.notna(latest['rz']) else None
        inq = float(latest['inq']) if pd.notna(latest['inq']) else None
        otq = float(latest['otq']) if pd.notna(latest['otq']) else None

        if rz is None:
            continue

        # 趋势分析 + 季节性护栏（Phase 4.9：汛期正常抬升不应报异常）
        rz_values = st_data['rz'].dropna().astype(float)
        if len(rz_values) >= 6:
            if _anomaly.consecutive_monotonic(rz_values.tail(6).values.tolist(), "rise", 5)["is_trend"]:
                season = seasonal_check(engine, "st_rsvr_r", "rz", st_id, rz)
                findings.append({
                    "level": "INFO" if season["in_season"] else "WARNING",
                    "message": f"测站{st_id}: 水位连续上升6次 ({rz_values.iloc[-6]:.2f}m → {rz:.2f}m)",
                    "detail": f"持续上升趋势，需关注；{season['note']}"
                })
            elif _anomaly.consecutive_monotonic(rz_values.tail(6).values.tolist(), "fall", 5)["is_trend"]:
                findings.append({
                    "level": "INFO",
                    "message": f"测站{st_id}: 水位连续下降6次 ({rz_values.iloc[-6]:.2f}m → {rz:.2f}m)",
                    "detail": "持续下降趋势"
                })

        # 极值分析
        rz_max = rz_values.max()
        rz_min = rz_values.min()
        rz_mean = rz_values.mean()

        # 稳健 MAD（替换 2-sigma：水位偏态，参数法易误报/漏报；修 H4 + 接线 lib）
        # + 季节性护栏（Phase 4.9）：7 月汛期水位普涨不应报异常
        if len(rz_values) >= 10:
            _r = _anomaly.mad_anomaly(rz_values.values.tolist(), threshold=3.0, min_samples=10)
            if _r["is_anomaly"]:
                season = seasonal_check(engine, "st_rsvr_r", "rz", st_id, rz)
                findings.append({
                    "level": "INFO" if season["in_season"] else "WARNING",
                    "message": f"测站{st_id}: 当前水位{rz:.2f}m MAD统计异常 z={_r['score']:.1f} (中位数{_r['median']:.2f}m)",
                    "detail": f"偏离近{days}天分布（当前{rz:.2f}m/窗口峰值{rz_max:.2f}m）；{season['note']}"
                })

        # 入库/出库平衡
        if inq is not None and otq is not None:
            if inq > 0 and otq > 0:
                ratio = inq / otq
                if ratio > 2:
                    findings.append({
                        "level": "WARNING",
                        "message": f"测站{st_id}: 入库流量({inq:.1f}m³/s)远大于出库({otq:.1f}m³/s)，比值{ratio:.1f}",
                        "detail": "蓄水速度过快，需关注水位变化"
                    })
                elif ratio < 0.5 and inq > 0:
                    findings.append({
                        "level": "INFO",
                        "message": f"测站{st_id}: 出库流量({otq:.1f}m³/s)远大于入库({inq:.1f}m³/s)",
                        "detail": "放水状态"
                    })

    if not findings:
        findings.append({"level": "OK", "message": "水库水情正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "水库水情", "findings": findings, "data_points": len(df)}


def analyze_rainfall(engine, days=7, thresholds=None):
    """分析雨量数据（检查整个时间窗口内的极端雨量事件）"""
    findings = []
    thresholds = thresholds or {}
    df = read_sensor_data(engine, "st_pptn_r", "st_id, p, dr, dyp, tm", days=days)
    if df.empty:
        return no_data_result("雨量监测", "st_pptn_r", engine)

    # 暴雨检测阈值（从 ew_info_rules 读取）
    rain_red = get_threshold(thresholds, '2', '1', default=100)
    rain_orange = get_threshold(thresholds, '2', '2', default=80)
    rain_yellow = get_threshold(thresholds, '2', '3', default=50)
    rain_blue = get_threshold(thresholds, '2', '4', default=30)

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].copy()
        st_data['p'] = pd.to_numeric(st_data['p'], errors='coerce')
        st_data = st_data.dropna(subset=['p'])

        if st_data.empty:
            continue

        # 最大单时段雨量（整个时间窗口）
        max_p = st_data['p'].max()
        max_p_time = st_data.loc[st_data['p'].idxmax(), 'tm'] if max_p > 0 else None

        # 检查整个时间窗口内的极端雨量事件
        if max_p > rain_red:
            findings.append({
                "level": "CRITICAL",
                "message": f"测站{st_id}: 单时段最大雨量{max_p:.1f}mm (红色预警>{rain_red}mm) @ {max_p_time}",
                "detail": "红色预警级别，需启动防汛响应"
            })
        elif max_p > rain_orange:
            findings.append({
                "level": "CRITICAL",
                "message": f"测站{st_id}: 单时段最大雨量{max_p:.1f}mm (橙色预警>{rain_orange}mm) @ {max_p_time}",
                "detail": "橙色预警级别"
            })
        elif max_p > rain_yellow:
            findings.append({
                "level": "WARNING",
                "message": f"测站{st_id}: 单时段最大雨量{max_p:.1f}mm (黄色预警>{rain_yellow}mm) @ {max_p_time}",
                "detail": "黄色预警级别"
            })
        elif max_p > rain_blue:
            findings.append({
                "level": "INFO",
                "message": f"测站{st_id}: 单时段最大雨量{max_p:.1f}mm (蓝色预警>{rain_blue}mm) @ {max_p_time}",
                "detail": "蓝色预警级别"
            })

        # 短时强降雨（单时段>30mm）
        if max_p > 30:
                findings.append({
                    "level": "WARNING",
                    "message": f"测站{st_id}: 单时段最大雨量{max_p:.1f}mm",
                    "detail": "短时强降雨，需关注"
                })

    if not findings:
        findings.append({"level": "OK", "message": "雨量正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "雨量监测", "findings": findings, "data_points": len(df)}


def analyze_pressure(engine, days=30, thresholds=None):
    """分析渗压数据"""
    findings = []
    thresholds = thresholds or {}
    df = read_sensor_data(engine, "st_pressure_r",
                          "st_id, water_pressure, ext_pressure, ext_temperature, tm", days=days)
    if df.empty:
        return no_data_result("渗压监测", "st_pressure_r", engine)

    # 第 0 层数据质量闸（Phase 4.6）：红档不硬跑，整体 inconclusive
    quality = check_data_quality(df, ["water_pressure"])
    if quality["tier"] == "red":
        return {"category": "渗压监测", "status": "inconclusive",
                "status_code": "INCONCLUSIVE",
                "status_note": f"数据质量红档: {'; '.join(quality['issues'])}",
                "quality": quality, "findings": []}

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()
        st_data['water_pressure'] = pd.to_numeric(st_data['water_pressure'], errors='coerce')
        st_data = st_data.dropna(subset=['water_pressure'])

        if len(st_data) < 3:
            continue

        latest = st_data.iloc[-1]
        wp = float(latest['water_pressure'])

        # 趋势分析 - 连续上升 + 季节性护栏（Phase 4.9）
        wp_values = st_data['water_pressure'].values
        if len(wp_values) >= 7:
            if _anomaly.consecutive_monotonic(wp_values[-7:].tolist(), "rise", 6)["is_trend"]:
                season = seasonal_check(engine, "st_pressure_r", "water_pressure", st_id, wp)
                findings.append({
                    "level": "INFO" if season["in_season"] else "WARNING",
                    "message": f"渗压计{st_id}: 渗压连续上升 ({wp_values[-7]:.2f}kPa → {wp:.2f}kPa)",
                    "detail": f"持续上升趋势，可能存在渗漏，需现场检查；{season['note']}"
                })

        # 突变检测（阈值从注册表读取，兜底 THRESHOLDS）→ 三分通道定型（Phase 4.9：spike降级INFO）
        pressure_change_threshold = get_registry_threshold(
            thresholds, "st_pressure_r", "rate.max_change", THRESHOLDS["pressure_change_kpa"])
        if len(wp_values) >= 2:
            change = abs(wp_values[-1] - wp_values[-2])
            if change > pressure_change_threshold:
                findings.append(_change_finding(
                    wp_values, wp_values[-2], wp_values[-1],
                    st_id=st_id, unit="kPa", dim_label="渗压计"))

        # MAD异常检测（委托 lib/anomaly）+ 季节性护栏（Phase 4.9，命中后才查历年同期）
        if len(wp_values) >= 10:
            _r = _anomaly.mad_anomaly(wp_values.tolist(), threshold=4.0, min_samples=10)
            if _r["is_anomaly"]:
                season = seasonal_check(engine, "st_pressure_r", "water_pressure", st_id, wp)
                level = "INFO" if season["in_season"] else "WARNING"
                findings.append({
                    "level": level,
                    "message": f"渗压计{st_id}: 统计异常 z_score={_r['score']:.1f} (当前{wp:.2f}kPa, 中位数{_r['median']:.2f}kPa)",
                    "detail": f"偏离近{days}天分布，需人工确认；{season['note']}"
                })

    if not findings:
        findings.append({"level": "OK", "message": "渗压正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "渗压监测", "findings": findings, "data_points": len(df)}


def analyze_percolation(engine, days=30):
    """分析渗流数据（扫描整个时间窗口内的异常）"""
    findings = []
    df = read_sensor_data(engine, "st_percolation_r", "st_id, percolation, tm", days=days)
    if df.empty:
        return no_data_result("渗流监测", "st_percolation_r", engine)

    # 第 0 层数据质量闸（Phase 4.6）：红档不硬跑，整体 inconclusive
    quality = check_data_quality(df, ["percolation"])
    if quality["tier"] == "red":
        return {"category": "渗流监测", "status": "inconclusive",
                "status_code": "INCONCLUSIVE",
                "status_note": f"数据质量红档: {'; '.join(quality['issues'])}",
                "quality": quality, "findings": []}

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()
        st_data['percolation'] = pd.to_numeric(st_data['percolation'], errors='coerce')
        st_data = st_data.dropna(subset=['percolation'])

        perc_values = st_data['percolation'].values
        if len(perc_values) < 2:
            continue

        # 扫描所有相邻数据点的突变 → 三分通道定型（Phase 4.9）
        for i in range(1, len(perc_values)):
            prev = perc_values[i-1]
            curr = perc_values[i]
            if prev > 0:
                change_pct = abs(curr - prev) / prev * 100
                if change_pct > THRESHOLDS["percolation_change_pct"]:
                    findings.append(_change_finding(
                        perc_values, prev, curr,
                        st_id=st_id, unit="L/s", dim_label="渗流计"))
                    break  # 只报一次

        # 统计异常（委托 lib/anomaly.mad_anomaly）+ 季节性护栏（Phase 4.9）
        if len(perc_values) >= 10:
            _r = _anomaly.mad_anomaly(perc_values.tolist(), threshold=3.0, min_samples=10)
            if _r["is_anomaly"]:
                season = seasonal_check(engine, "st_percolation_r", "percolation", st_id, float(perc_values[-1]))
                findings.append({
                    "level": "INFO" if season["in_season"] else "WARNING",
                    "message": f"渗流计{st_id}: 渗流量{float(perc_values[-1]):.3f}L/s MAD统计异常 z={_r['score']:.1f} (中位数{_r['median']:.3f})",
                    "detail": f"偏离历史分布，需确认；{season['note']}"
                })

    if not findings:
        findings.append({"level": "OK", "message": "渗流正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "渗流监测", "findings": findings, "data_points": len(df)}


def analyze_displacement(engine, days=30, thresholds=None):
    """分析GNSS位移数据"""
    findings = []
    thresholds = thresholds or {}
    df = read_sensor_data(engine, "dsm_dfr_srvrds_srhrds",
                          "st_id, wgs84_delta_h, wgs84_delta_x, wgs84_delta_y, speed_gh, speed_gx, speed_gy, tm",
                          days=days)
    if df.empty:
        return no_data_result("位移监测", "dsm_dfr_srvrds_srhrds", engine)

    # 第 0 层数据质量闸（Phase 4.6）：红档不硬跑，整体 inconclusive
    quality = check_data_quality(df, ["wgs84_delta_h"])
    if quality["tier"] == "red":
        return {"category": "位移监测", "status": "inconclusive",
                "status_code": "INCONCLUSIVE",
                "status_note": f"数据质量红档: {'; '.join(quality['issues'])}",
                "quality": quality, "findings": []}

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()
        for col in ['wgs84_delta_h', 'speed_gh']:
            st_data[col] = pd.to_numeric(st_data[col], errors='coerce')
        st_data = st_data.dropna(subset=['speed_gh'])

        if len(st_data) < 2:
            continue

        latest = st_data.iloc[-1]
        speed = float(latest['speed_gh']) if pd.notna(latest['speed_gh']) else 0
        delta_h = float(latest['wgs84_delta_h']) if pd.notna(latest['wgs84_delta_h']) else 0

        # 速率异常（阈值从注册表读取）
        speed_critical = get_registry_threshold(thresholds, "dsm_dfr_srvrds_srhrds", "thresholds.II_speed", 1.0)
        speed_warning = get_registry_threshold(thresholds, "dsm_dfr_srvrds_srhrds", "thresholds.III_speed", 0.5)
        if speed > speed_critical:
            findings.append({
                "level": "CRITICAL",
                "message": f"GNSS测站{st_id}: 位移速率{speed:.3f}mm/d (超过{speed_critical}mm/d)",
                "detail": "II级异常，需立即关注大坝安全"
            })
        elif speed > speed_warning:
            findings.append({
                "level": "WARNING",
                "message": f"GNSS测站{st_id}: 位移速率{speed:.3f}mm/d (超过{speed_warning}mm/d)",
                "detail": "III级异常，需加密监测"
            })

        # 累计位移
        if abs(delta_h) > 10:
            findings.append({
                "level": "WARNING",
                "message": f"GNSS测站{st_id}: 本次高程变化{delta_h:.2f}mm (超过10mm)",
                "detail": "累计位移较大，需关注"
            })

        # 趋势分析
        speed_values = st_data['speed_gh'].dropna().values
        if len(speed_values) >= 5:
            if _anomaly.consecutive_monotonic(speed_values[-5:].tolist(), "rise", 4)["is_trend"]:
                findings.append({
                    "level": "WARNING",
                    "message": f"GNSS测站{st_id}: 位移速率持续上升 ({speed_values[-5]:.3f} → {speed:.3f} mm/d)",
                    "detail": "加速趋势，需密切关注"
                })

    if not findings:
        findings.append({"level": "OK", "message": "位移正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "位移监测", "findings": findings, "data_points": len(df)}


def analyze_inspection_results(engine, days=30):
    """分析巡检结果"""
    findings = []
    tasks = read_inspections(engine, days)
    if tasks.empty:
        return no_data_result("巡检结果", "business_check_task", engine, time_field="create_time")

    total = len(tasks)
    completed = len(tasks[tasks['status'] == '3'])
    overtime = len(tasks[tasks['exceed_time'] == '1'])
    in_progress = len(tasks[tasks['status'] == '2'])
    pending = len(tasks[tasks['status'] == '1'])

    completion_rate = completed / total if total > 0 else 0
    overtime_rate = overtime / total if total > 0 else 0

    # 完成率
    if completion_rate < 0.7:
        findings.append({
            "level": "WARNING",
            "message": f"巡检完成率偏低: {completion_rate:.1%} ({completed}/{total})",
            "detail": "超过30%的任务未完成"
        })

    # 超时率
    if overtime_rate > 0.3:
        findings.append({
            "level": "WARNING",
            "message": f"巡检超时率偏高: {overtime_rate:.1%} ({overtime}/{total})",
            "detail": "超过30%的任务超时，需优化路线或增加时间"
        })

    # 漏检率
    def parse_pct(p):
        try:
            return float(str(p).replace('%', '')) / 100
        except (ValueError, AttributeError):
            return 0

    completed_tasks = tasks[tasks['status'] == '3'].copy()
    if not completed_tasks.empty:
        completed_tasks['omission'] = completed_tasks['check_percent'].apply(parse_pct)
        high_omission = completed_tasks[completed_tasks['omission'] > 0.2]
        if len(high_omission) > 0:
            findings.append({
                "level": "WARNING",
                "message": f"有{len(high_omission)}个任务漏检率超过20%",
                "detail": f"最高漏检率: {high_omission['omission'].max():.1%}"
            })

    # 缺陷统计
    total_defects = tasks['bad_num'].sum()
    if total_defects > 0:
        findings.append({
            "level": "INFO",
            "message": f"近{days}天共发现{int(total_defects)}个缺陷",
            "detail": "需检查缺陷处理情况"
        })

    if not findings:
        findings.append({"level": "OK", "message": "巡检结果正常", "detail": f"完成率{completion_rate:.1%}, 超时率{overtime_rate:.1%}"})

    return {
        "category": "巡检结果",
        "findings": findings,
        "stats": {
            "total": total, "completed": completed, "overtime": overtime,
            "in_progress": in_progress, "pending": pending,
            "completion_rate": f"{completion_rate:.1%}",
            "overtime_rate": f"{overtime_rate:.1%}",
            "total_defects": int(total_defects)
        }
    }


def analyze_equipment(engine):
    """分析设备状态"""
    findings = []
    equip = read_equipment(engine)
    if equip.empty:
        return no_data_result("设备状态", "eq_equip_base")

    total = len(equip)
    offline = len(equip[equip['status'] == 0])
    abnormal = len(equip[equip['status'] == 2])
    online = len(equip[equip['status'] == 1])

    offline_rate = offline / total if total > 0 else 0

    if offline_rate > 0.3:
        findings.append({
            "level": "WARNING",
            "message": f"设备离线率偏高: {offline_rate:.1%} ({offline}/{total})",
            "detail": "超过30%设备离线，需检查通信或电源"
        })

    if abnormal > 0:
        findings.append({
            "level": "WARNING",
            "message": f"有{abnormal}台设备处于异常状态",
            "detail": "需检查异常设备"
        })

    # 按类型统计
    type_stats = equip.groupby('category').agg(
        total=('id', 'count'),
        offline=('status', lambda x: (x == 0).sum()),
        abnormal=('status', lambda x: (x == 2).sum())
    ).reset_index()

    if not findings:
        findings.append({"level": "OK", "message": "设备状态正常", "detail": f"在线{online}台, 离线{offline}台, 异常{abnormal}台"})

    return {
        "category": "设备状态",
        "findings": findings,
        "stats": {
            "total": total, "online": online, "offline": offline, "abnormal": abnormal,
            "by_type": type_stats.to_dict('records') if not type_stats.empty else []
        }
    }


def analyze_gate(engine, days=30):
    """分析闸门工情（扫描整个时间窗口内的异常）"""
    findings = []
    df = read_sensor_data(engine, "rei_gate_r", "st_id, gtophgt, gtopnum, gtq, status, tm", days=days)
    if df.empty:
        return no_data_result("闸门工情", "rei_gate_r", engine)

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()
        st_data['gtophgt'] = pd.to_numeric(st_data['gtophgt'], errors='coerce')
        st_data['gtq'] = pd.to_numeric(st_data['gtq'], errors='coerce')

        # 扫描所有数据点 → 三分通道定型（Phase 4.9）
        opening_values = st_data['gtophgt'].dropna().values
        for i in range(1, len(opening_values)):
            change = abs(opening_values[i] - opening_values[i-1])
            if change > THRESHOLDS["gate_opening_jump_m"]:
                findings.append(_change_finding(
                    opening_values, opening_values[i-1], opening_values[i],
                    st_id=st_id, unit="m", dim_label="闸门站"))

        # 开度频繁波动（滑动窗口检测）
        if len(opening_values) >= 6:
            for start in range(len(opening_values) - 5):
                window = opening_values[start:start+6]
                diffs = [abs(window[j] - window[j-1]) for j in range(1, len(window))]
                if sum(1 for d in diffs if d > 0.3) >= 4:
                    findings.append({
                        "level": "WARNING",
                        "message": f"闸门站{st_id}: 开度频繁波动(窗口{start}-{start+5})",
                        "detail": "可能存在控制系统不稳定"
                    })
                    break  # 只报一次

        # 流量异常（扫描所有数据点）
        for _, row in st_data.iterrows():
            opening = float(row['gtophgt']) if pd.notna(row['gtophgt']) else 0
            flow = float(row['gtq']) if pd.notna(row['gtq']) else 0
            if opening > 0 and flow == 0:
                findings.append({
                    "level": "WARNING",
                    "message": f"闸门站{st_id}: 开度{opening:.2f}m但流量为0 @ {row.get('tm', '')}",
                    "detail": "闸门可能卡阻或流量计故障"
                })
                break  # 只报一次

    if not findings:
        findings.append({"level": "OK", "message": "闸门工情正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "闸门工情", "findings": findings, "data_points": len(df)}


def analyze_pump(engine, days=30, thresholds=None):
    """分析泵站工情（扫描整个时间窗口内的异常）"""
    findings = []
    thresholds = thresholds or {}
    df = read_sensor_data(engine, "rei_pump_r",
                          "st_id, uab, ubc, uca, ia, ib, ic, p, freq, status, tm", days=days)
    if df.empty:
        return no_data_result("泵站工情", "rei_pump_r", engine)

    imbalance_threshold = get_registry_threshold(thresholds, "rei_pump_r", "imbalance_threshold", 0.10)

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()

        for _, row in st_data.iterrows():
            # 三相不平衡检测
            for phase_label, cols in [("电压", ['uab', 'ubc', 'uca']), ("电流", ['ia', 'ib', 'ic'])]:
                values = []
                for col in cols:
                    v = pd.to_numeric(row.get(col), errors='coerce')
                    if pd.notna(v):
                        values.append(float(v))

                if len(values) == 3 and all(v > 0 for v in values):
                    avg = sum(values) / 3
                    max_dev = max(abs(v - avg) for v in values)
                    imbalance = max_dev / avg if avg > 0 else 0

                    if imbalance > imbalance_threshold:
                        findings.append({
                            "level": "WARNING",
                            "message": f"泵站{st_id}: {phase_label}三相不平衡{imbalance:.1%} ({'/'.join(f'{v:.1f}' for v in values)}) @ {row.get('tm', '')}",
                            "detail": f"不平衡>{imbalance_threshold:.0%}，需检查电气设备"
                        })

            # 频率异常
            freq = pd.to_numeric(row.get('freq'), errors='coerce')
            if pd.notna(freq):
                freq = float(freq)
                if freq < 45 or freq > 55:
                    findings.append({
                        "level": "WARNING",
                        "message": f"泵站{st_id}: 频率{freq:.1f}Hz偏离正常范围(45-55Hz) @ {row.get('tm', '')}",
                        "detail": "频率异常，需检查变频器或电网"
                    })

    # 去重（同一测站同一类型只报一次）
    seen = set()
    unique_findings = []
    for f in findings:
        key = f['message'][:30]  # 用前30字符去重
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)
    findings = unique_findings

    if not findings:
        findings.append({"level": "OK", "message": "泵站工情正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "泵站工情", "findings": findings, "data_points": len(df)}


def analyze_water_quality(engine, days=90):
    """分析水质数据"""
    findings = []
    try:
        df = pd.read_sql(text("""
            SELECT stcd, spt, ph, dox, nh3n, tn, tp, turb, wtmp
            FROM wq_pcp_d WHERE spt >= NOW()-INTERVAL :days DAY
            ORDER BY spt DESC LIMIT 500
        """), engine, params={"days": days})
    except Exception as e:
        QUERY_ERRORS["wq_pcp_d"] = _classify_query_error(e)
        logger.warning("read_water_quality 失败: %s", e)
        return no_data_result("水质监测", "wq_pcp_d", engine, time_field="spt")

    if df.empty:
        return no_data_result("水质监测", "wq_pcp_d", engine, time_field="spt")

    for col, label, low, high in [
        ('ph', 'pH', 6, 9),
        ('dox', '溶解氧', 5, None),
        ('nh3n', '氨氮', None, 1.5),
        ('tn', '总氮', None, 2.0),
        ('tp', '总磷', None, 0.4),
    ]:
        if col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors='coerce').dropna()
        if values.empty:
            continue

        latest = float(values.iloc[0])
        if low is not None and latest < low:
            findings.append({
                "level": "WARNING",
                "message": f"{label}偏低: {latest:.2f} (标准>{low})",
                "detail": f"水质{label}低于标准下限"
            })
        elif high is not None and latest > high:
            findings.append({
                "level": "WARNING",
                "message": f"{label}偏高: {latest:.2f} (标准<{high})",
                "detail": f"水质{label}超过标准上限"
            })

    if not findings:
        findings.append({"level": "OK", "message": "水质正常", "detail": f"分析{len(df)}条数据"})

    return {"category": "水质监测", "findings": findings, "data_points": len(df)}


def analyze_soil_moisture(engine, days=30):
    """分析土壤墒情"""
    findings = []
    try:
        df = pd.read_sql(text("""
            SELECT st_id, tm, soil_water10cm, soil_water20cm, soil_water30cm,
                   soil_water60cm, soil_water100cm, soil_moist_evaluation
            FROM st_soil_moisture_r
            WHERE tm >= NOW()-INTERVAL :days DAY
            ORDER BY tm DESC LIMIT 500
        """), engine, params={"days": days})
    except Exception as e:
        QUERY_ERRORS["st_soil_moisture_r"] = _classify_query_error(e)
        logger.warning("read_soil_moisture 失败: %s", e)
        return no_data_result("土壤墒情", "st_soil_moisture_r", engine)

    if df.empty:
        return no_data_result("土壤墒情", "st_soil_moisture_r", engine)

    # 检查评价字段
    if 'soil_moist_evaluation' in df.columns:
        evals = df['soil_moist_evaluation'].dropna()
        drought_keywords = ['干旱', '不足', '重度']
        for eval_val in evals:
            if any(kw in str(eval_val) for kw in drought_keywords):
                findings.append({
                    "level": "WARNING",
                    "message": f"墒情评价: {eval_val}",
                    "detail": "土壤含水量不足，需关注"
                })
                break

    # 检查深层含水量异常低
    for col, depth in [('soil_water100cm', '100cm')]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors='coerce').dropna()
            if not values.empty:
                latest = float(values.iloc[0])
                if latest < 10:
                    findings.append({
                        "level": "INFO",
                        "message": f"{depth}深层含水量偏低: {latest:.1f}%",
                        "detail": "深层土壤干燥，需关注坝体稳定性"
                    })

    if not findings:
        findings.append({"level": "OK", "message": "土壤墒情正常", "detail": f"分析{len(df)}条数据"})

    return {"category": "土壤墒情", "findings": findings, "data_points": len(df)}


def analyze_termite(engine, days=180):
    """分析白蚁监测"""
    findings = []
    try:
        df = pd.read_sql(text("""
            SELECT st_id, tm, termite_species, pest_density, damage_level,
                   damage_range, check_result
            FROM st_termite_monitor_r
            WHERE tm >= NOW()-INTERVAL :days DAY
            ORDER BY tm DESC LIMIT 500
        """), engine, params={"days": days})
    except Exception as e:
        QUERY_ERRORS["st_termite_monitor_r"] = _classify_query_error(e)
        logger.warning("read_termite 失败: %s", e)
        return no_data_result("白蚁监测", "st_termite_monitor_r", engine)

    if df.empty:
        return no_data_result("白蚁监测", "st_termite_monitor_r", engine)

    # 检查是否有白蚁发现（"未发现"含子串"发现"，须排除，否则漏检记录被误判为发现）
    if 'check_result' in df.columns:
        cr = df['check_result'].astype(str)
        found = df[cr.str.contains('发现', na=False) & ~cr.str.contains('未发现', na=False)]
        if not found.empty:
            findings.append({
                "level": "WARNING",
                "message": f"白蚁监测发现白蚁: {len(found)}条记录",
                "detail": "需安排白蚁治理"
            })

    # 检查危害等级
    if 'damage_level' in df.columns:
        for level in ['重度', '中度']:
            count = df[df['damage_level'].str.contains(level, na=False)].shape[0]
            if count > 0:
                findings.append({
                    "level": "WARNING" if level == "中度" else "CRITICAL",
                    "message": f"白蚁危害等级: {level} ({count}条记录)",
                    "detail": f"{level}危害，需立即治理"
                })
                break

    # 检查虫口密度
    if 'pest_density' in df.columns:
        densities = pd.to_numeric(df['pest_density'], errors='coerce').dropna()
        if not densities.empty:
            max_density = int(densities.max())
            if max_density >= 3:
                findings.append({
                    "level": "WARNING",
                    "message": f"虫口密度等级: {max_density}/4",
                    "detail": "密度较高，需加强监测和治理"
                })

    if not findings:
        findings.append({"level": "OK", "message": "白蚁监测正常", "detail": f"分析{len(df)}条数据"})

    return {"category": "白蚁监测", "findings": findings, "data_points": len(df)}


def analyze_alerts(engine, days=30):
    """分析告警情况"""
    findings = []
    alerts = read_alerts(engine, days)
    if alerts.empty:
        return no_data_result("告警分析", "ew_info_message", engine, time_field="create_time")

    total = len(alerts)
    unconfirmed = len(alerts[alerts['message_confirm'] == '0']) if 'message_confirm' in alerts.columns else 0

    # 按等级统计
    level_counts = alerts['level_r'].value_counts().to_dict()
    level_1 = level_counts.get('1', 0)
    level_2 = level_counts.get('2', 0)

    if level_1 > 0:
        findings.append({
            "level": "CRITICAL",
            "message": f"I级告警{level_1}条",
            "detail": "特别严重，需立即处理"
        })

    if level_2 > 0:
        findings.append({
            "level": "WARNING",
            "message": f"II级告警{level_2}条",
            "detail": "严重，需尽快处理"
        })

    if unconfirmed > 10:
        findings.append({
            "level": "WARNING",
            "message": f"未确认告警{unconfirmed}条",
            "detail": "告警积压，需及时确认处理"
        })

    if not findings:
        findings.append({"level": "OK", "message": "告警情况正常", "detail": f"近{days}天共{total}条告警"})

    return {
        "category": "告警分析",
        "findings": findings,
        "stats": {
            "total": total, "unconfirmed": unconfirmed,
            "level_1": level_1, "level_2": level_2,
            "level_3": level_counts.get('3', 0), "level_4": level_counts.get('4', 0)
        }
    }


def analyze_mad_anomaly(engine, days=30, thresholds=None):
    """第4层：MAD统计异常检测（跨传感器统一检测）"""
    findings = []
    thresholds = thresholds or {}

    sensor_configs = [
        ("st_rsvr_r", "st_id, rz, tm", "rz", "水位", 3.0),
        ("st_pressure_r", "st_id, water_pressure, tm", "water_pressure", "渗压", 4.0),
        ("st_percolation_r", "st_id, percolation, tm", "percolation", "渗流", 3.0),
        ("dsm_dfr_srvrds_srhrds", "st_id, wgs84_delta_h, tm", "wgs84_delta_h", "位移", 3.5),
    ]

    for table, fields, value_col, label, default_z in sensor_configs:
        df = read_sensor_data(engine, table, fields, days=days)
        if df.empty:
            continue

        for st_id in df['st_id'].unique():
            st_data = df[df['st_id'] == st_id].copy()
            st_data[value_col] = pd.to_numeric(st_data[value_col], errors='coerce')
            values = st_data[value_col].dropna().values

            if len(values) < 20:
                continue

            # MAD检测（委托 lib/anomaly）
            _r = _anomaly.mad_anomaly(values.tolist(), threshold=default_z, min_samples=20)
            if not _r["is_anomaly"]:
                continue

            latest = float(values[-1])

            # MAD阈值从注册表读取
            mad_threshold = get_registry_threshold(thresholds, table, "mad_threshold", default_z)

            # 使用lib返回的score（已计算z_score）
            if _r["score"] > mad_threshold:
                # 季节性护栏（Phase 4.9）：水位/渗压/渗流防汛期正常抬升；位移无季节性不加
                if table in ("st_rsvr_r", "st_pressure_r", "st_percolation_r"):
                    season = seasonal_check(engine, table, value_col, st_id, latest)
                else:
                    season = {"in_season": False, "note": ""}
                findings.append({
                    "level": "INFO" if season["in_season"] else "WARNING",
                    "message": f"{label}测站{st_id}: MAD统计异常 z={_r['score']:.1f} (阈值{mad_threshold}, 当前{latest:.2f}, 中位数{_r['median']:.2f})",
                    "detail": (f"偏离历史分布，基于{len(values)}个数据点的MAD检测"
                               + (f"；{season['note']}" if season["note"] else ""))
                })

    if not findings:
        findings.append({"level": "OK", "message": "MAD统计异常检测正常", "detail": "所有传感器数据在历史分布范围内"})

    return {"category": "MAD统计异常", "findings": findings}


def analyze_correlation(engine, days=7, thresholds=None):
    """第5层：多指标关联异常检测"""
    findings = []
    thresholds = thresholds or {}

    # 读取多指标数据
    water = read_sensor_data(engine, "st_rsvr_r", "st_id, rz, inq, otq, tm", days=days)
    pressure = read_sensor_data(engine, "st_pressure_r", "st_id, water_pressure, tm", days=days)
    rainfall = read_sensor_data(engine, "st_pptn_r", "st_id, p, tm", days=days)

    if water.empty:
        return no_data_result("关联异常", "st_rsvr_r", engine)

    # 关联分析1: 水位上升但入库流量下降
    for st_id in water['st_id'].unique():
        st_water = water[water['st_id'] == st_id].sort_values('tm').copy()
        st_water['rz'] = pd.to_numeric(st_water['rz'], errors='coerce')
        st_water['inq'] = pd.to_numeric(st_water['inq'], errors='coerce')

        if len(st_water) < 6:
            continue

        rz_trend = st_water['rz'].tail(6).values
        inq_trend = st_water['inq'].tail(6).values

        # 平线护栏（Phase 4.9）：水位或流量任一死值停测，则"上升/下降"趋势不可信
        if _is_idle(rz_trend) or _is_idle(inq_trend):
            continue

        rz_rising = all(rz_trend[i] > rz_trend[i-1] for i in range(1, len(rz_trend)))
        # 仅在有非零流量可比时才判定下降；全零/无可比项不算下降（修 C3 空真）
        comparable = [i for i in range(1, len(inq_trend)) if inq_trend[i-1] > 0]
        inq_falling = bool(comparable) and all(
            inq_trend[i] < inq_trend[i-1] for i in comparable
        )

        if rz_rising and inq_falling:
            findings.append({
                "level": "WARNING",
                "message": f"关联异常: 测站{st_id}水位持续上升但入库流量持续下降",
                "detail": "可能是闸门故障或数据错误，需人工确认"
            })

    # 关联分析2: 渗压与水位不相关
    if not pressure.empty and not water.empty:
        for st_id in pressure['st_id'].unique():
            st_pressure = pressure[pressure['st_id'] == st_id].sort_values('tm').copy()
            st_pressure['water_pressure'] = pd.to_numeric(st_pressure['water_pressure'], errors='coerce')

            if len(st_pressure) < 6:
                continue

            wp_trend = st_pressure['water_pressure'].tail(6).values
            wp_rising = all(wp_trend[i] > wp_trend[i-1] for i in range(1, len(wp_trend)))

            if wp_rising:
                # 检查水位是否稳定
                for w_st_id in water['st_id'].unique():
                    st_water = water[water['st_id'] == w_st_id].sort_values('tm').copy()
                    st_water['rz'] = pd.to_numeric(st_water['rz'], errors='coerce')
                    if len(st_water) < 6:
                        continue
                    rz_trend = st_water['rz'].tail(6).values
                    rz_change = abs(rz_trend[-1] - rz_trend[0])
                    if rz_change < 0.1 and not _is_idle(rz_trend):  # 水位基本稳定（且非死值平线）
                        findings.append({
                            "level": "WARNING",
                            "message": f"关联异常: 渗压计{st_id}持续上升但水位稳定",
                            "detail": "可能是防渗体损坏或渗压计故障，需现场检查"
                        })

    # 关联分析3: 降雨量大但水位不涨
    if not rainfall.empty and not water.empty:
        for st_id in rainfall['st_id'].unique():
            st_rain = rainfall[rainfall['st_id'] == st_id].copy()
            st_rain['p'] = pd.to_numeric(st_rain['p'], errors='coerce')
            total_rain = st_rain['p'].sum()

            if total_rain > 50:  # 累计雨量>50mm
                for w_st_id in water['st_id'].unique():
                    st_water = water[water['st_id'] == w_st_id].sort_values('tm').copy()
                    st_water['rz'] = pd.to_numeric(st_water['rz'], errors='coerce')
                    if len(st_water) < 2:
                        continue
                    rz_change = abs(st_water['rz'].iloc[-1] - st_water['rz'].iloc[0])
                    if rz_change < 0.05 and not _is_idle(st_water['rz'].values):  # 水位不涨（且非死值平线）
                        findings.append({
                            "level": "INFO",
                            "message": f"关联异常: 雨量站{st_id}累计{total_rain:.0f}mm但水位变化仅{rz_change:.2f}m",
                            "detail": "需检查是否有泄洪操作或雨量站是否准确"
                        })

    if not findings:
        findings.append({"level": "OK", "message": "多指标关联分析正常", "detail": "未发现指标间矛盾"})

    return {"category": "关联异常", "findings": findings}


# ============================================================
# 2.5 巡检→诊断自动衔接（Phase 2）
# ============================================================
# 纪律：只读 SELECT；证据充分即停；尝试轨迹入 detail；瞬时错误重试至多 1 次；
# 每轮巡检最多 MAX_DIAG_CHAINS 条诊断链（防爆炸）；失败标准化 code 不中断报告。

MAX_DIAG_CHAINS = 3

# 分层时间窗（对齐 smart-lock-diagnosis 三级窗）：纵向扩窗
_DIAG_WINDOWS = [("-2h", 2), ("-12h", 12), ("-3d", 72)]


def _diag_sql(engine, sql, params=None):
    """诊断查询：只读；瞬时错误重试至多一次，再失败返回 (None, code)。"""
    last_code = None
    for _ in range(2):
        try:
            return pd.read_sql(text(sql), engine, params=params or {}), None
        except Exception as e:
            last_code = _classify_query_error(e)
            if last_code == "TABLE_MISSING":
                break  # 表缺失重试无意义
    return None, f"DIAG_QUERY_FAILED({last_code})"


def _diagnose_pressure_outlier(engine, st_id=None):
    """渗压离群诊断链。根因先验：上游水位~50% > 降雨~25% > 闸门操作~15% > 传感器漂移~10%。"""
    trace = []
    for label, hours in _DIAG_WINDOWS:
        # ① 上游水位同期变化（先验 ~50%）
        df, code = _diag_sql(engine,
            "SELECT MAX(rz)-MIN(rz) AS delta FROM st_rsvr_r "
            "WHERE deleted=0 AND tm >= NOW()-INTERVAL :h HOUR", {"h": hours})
        if code:
            trace.append(f"{label} 水位: {code}")
        else:
            delta = df['delta'].iloc[0] if not df.empty else None
            if delta is not None and float(delta) >= 0.2:
                trace.append(f"{label} 水位变幅 {float(delta):.2f}m")
                return {"root_cause": "上游水位抬升→渗压响应（水位-渗压因果链）", "trace": trace}
            trace.append(f"{label} 水位变幅不足")
        # ② 同期降雨事件（~25%）
        df, code = _diag_sql(engine,
            "SELECT COALESCE(SUM(p),0) AS total FROM st_pptn_r "
            "WHERE deleted=0 AND tm >= NOW()-INTERVAL :h HOUR", {"h": hours})
        if code:
            trace.append(f"{label} 降雨: {code}")
        else:
            total = float(df['total'].iloc[0] or 0)
            if total >= 10:
                trace.append(f"{label} 累计降雨 {total:.1f}mm")
                return {"root_cause": "同期降雨入渗→渗压抬升", "trace": trace}
            trace.append(f"{label} 降雨 {total:.1f}mm 不足")
        # ③ 同期闸门操作（~15%）
        df, code = _diag_sql(engine,
            "SELECT COUNT(DISTINCT gtophgt) AS n FROM rei_gate_r "
            "WHERE deleted=0 AND tm >= NOW()-INTERVAL :h HOUR", {"h": hours})
        if code:
            trace.append(f"{label} 闸门: {code}")
        else:
            n = int(df['n'].iloc[0] or 0)
            if n > 1:
                trace.append(f"{label} 闸门开度变化 {n} 档")
                return {"root_cause": "同期闸门调度→渗流场扰动", "trace": trace}
            trace.append(f"{label} 闸门无操作")
    # 横向 fallback：同坝段其他渗压计是否同步离群（区分单点故障与面上异常）
    df, code = _diag_sql(engine,
        "SELECT COUNT(DISTINCT st_id) AS n FROM st_pressure_r "
        "WHERE deleted=0 AND tm >= NOW()-INTERVAL 72 HOUR")
    if not code and df is not None and int(df['n'].iloc[0] or 0) > 1:
        trace.append("横向: 同期多渗压计在测，建议比对是否同步离群")
    return {"root_cause": None,
            "conclusion": "外因（水位/降雨/闸门）均排除，疑似传感器漂移或真实渗漏，需人工现场确认",
            "trace": trace}


def _diagnose_water_level_rate(engine, st_id=None):
    """水位变化率超限诊断链。先验：闸门调度 > 泵站启停 > 上游降雨。产出：区分调度行为与异常水情。"""
    trace = []
    for label, hours in _DIAG_WINDOWS:
        df, code = _diag_sql(engine,
            "SELECT COUNT(DISTINCT gtophgt) AS n FROM rei_gate_r "
            "WHERE deleted=0 AND tm >= NOW()-INTERVAL :h HOUR", {"h": hours})
        if code:
            trace.append(f"{label} 闸门: {code}")
        elif int(df['n'].iloc[0] or 0) > 1:
            trace.append(f"{label} 闸门开度变化")
            return {"root_cause": "闸门调度行为（非异常水情）", "trace": trace}
        else:
            trace.append(f"{label} 闸门无操作")
        df, code = _diag_sql(engine,
            "SELECT COUNT(*) AS n FROM rei_pump_r "
            "WHERE deleted=0 AND tm >= NOW()-INTERVAL :h HOUR", {"h": hours})
        if code:
            trace.append(f"{label} 泵站: {code}")
        elif int(df['n'].iloc[0] or 0) > 0:
            trace.append(f"{label} 泵站有运行记录")
            return {"root_cause": "泵站启停引起的水位变化（调度行为）", "trace": trace}
        else:
            trace.append(f"{label} 泵站无记录")
        df, code = _diag_sql(engine,
            "SELECT COALESCE(SUM(p),0) AS total FROM st_pptn_r "
            "WHERE deleted=0 AND tm >= NOW()-INTERVAL :h HOUR", {"h": hours})
        if code:
            trace.append(f"{label} 降雨: {code}")
        else:
            total = float(df['total'].iloc[0] or 0)
            if total >= 10:
                trace.append(f"{label} 累计降雨 {total:.1f}mm")
                return {"root_cause": "上游降雨产流→水位上涨", "trace": trace}
            trace.append(f"{label} 降雨不足")
    return {"root_cause": None,
            "conclusion": "无调度/降雨外因，异常水情不能排除，需人工核查",
            "trace": trace}


def _diagnose_gate_closed_flow(engine, st_id=None):
    """闸门关闭但有流量诊断链。① 状态时序跳变（传感器抖动）→ ② 断面流量交叉验证。"""
    trace = []
    df, code = _diag_sql(engine,
        "SELECT COUNT(DISTINCT gtophgt) AS n FROM rei_gate_r "
        "WHERE deleted=0 AND tm >= NOW()-INTERVAL 12 HOUR"
        + (" AND st_id = :st" if st_id else ""),
        {"st": st_id} if st_id else {})
    if code:
        trace.append(f"闸门时序: {code}")
    elif int(df['n'].iloc[0] or 0) > 3:
        trace.append(f"12h 内开度值跳变 {int(df['n'].iloc[0])} 档")
        return {"root_cause": "闸门状态码跳变，疑似开度传感器故障", "trace": trace}
    else:
        trace.append("闸门开度时序平稳")
    df, code = _diag_sql(engine,
        "SELECT COUNT(*) AS n FROM st_river_r "
        "WHERE deleted=0 AND tm >= NOW()-INTERVAL 12 HOUR AND q > 0")
    if code:
        trace.append(f"断面流量: {code}")
    elif int(df['n'].iloc[0] or 0) > 0:
        trace.append("同期断面流量计有过流记录")
        return {"root_cause": "断面流量交叉验证过流成立，疑似闸门真实漏水", "trace": trace}
    else:
        trace.append("断面流量计无过流记录（或无此监测）")
    return {"root_cause": None,
            "conclusion": "流量信号未获交叉证实，疑似流量传感器故障，需现场核查",
            "trace": trace}


# 诊断路由表（首批 3 条，详见 references/diagnosis-routing.md；扩展复用本模式）
DIAG_ROUTES = [
    ("pressure_outlier",
     lambda cat, msg: "渗压" in msg and ("MAD" in msg or "统计异常" in msg or "突变" in msg or "上升" in msg),
     _diagnose_pressure_outlier),
    ("water_level_rate",
     lambda cat, msg: cat in ("水库水情", "MAD统计异常", "关联异常") and "水位" in msg,
     _diagnose_water_level_rate),
    ("gate_closed_flow",
     lambda cat, msg: cat in ("闸门工情", "关联异常") and "闸门" in msg and "流量" in msg,
     _diagnose_gate_closed_flow),
]


def _match_diag_route(category, message):
    for name, matcher, fn in DIAG_ROUTES:
        if matcher(category, message):
            return name, fn
    return None


def run_auto_diagnosis(engine, analyses):
    """高风险自动诊断（Phase 2）：CRITICAL/WARNING findings → 路由表 → 分层 fallback → 结果回填。

    触发条件：CRITICAL 恒候选；WARNING 需命中诊断路由（路由命中本身即高风险信号——
    渗压/水位/闸门维度只发 WARNING，若仅收 CRITICAL 则三条路由生产不可达）。
    CRITICAL 优先占 MAX_DIAG_CHAINS 配额。命中 root_cause 的 finding 打
    diagnosis_root_cause 标（envelope 中 category 升级为 root_cause）；未命中也把
    "已查窗口与结果"写入 detail——让"已检为空"与"忘了检"可区分。返回执行的诊断链数。"""
    import re
    candidates = []
    for a in analyses:
        cat = a.get("category", "")
        for f in a.get("findings", []):
            level = f.get("level")
            if level not in ("CRITICAL", "WARNING"):
                continue
            # 三分通道分流（Phase 4.9）：spike=瞬时毛刺，不烧诊断预算、防撞巧合降雨生伪根因。
            # （spike 已降级为 INFO 会被上一行 level 过滤；此守卫为显式防御 + 防未来回归）
            if f.get("pattern") == "spike":
                continue
            hit = _match_diag_route(cat, f.get("message", ""))
            if not hit:
                continue
            candidates.append((0 if level == "CRITICAL" else 1, hit, f))
    candidates.sort(key=lambda c: c[0])

    chains = 0
    for _, (name, fn), f in candidates:
        if chains >= MAX_DIAG_CHAINS:
            break
        msg = f.get("message", "")
        m = re.search(r"(?:测站|渗压计|渗流计|雨量站|站)(\d+)", msg)
        st_id = int(m.group(1)) if m else None
        try:
            result = fn(engine, st_id)
        except Exception as e:
            f["detail"] = f.get("detail", "") + f" ｜诊断链 {name} 执行失败: DIAG_QUERY_FAILED"
            logger.warning("诊断链 %s 失败: %s", name, e)
            chains += 1
            continue
        chains += 1
        trace_txt = "；".join(result.get("trace", [])[-6:])
        if result.get("root_cause"):
            f["diagnosis_root_cause"] = result["root_cause"]
            f["detail"] = f.get("detail", "") + f" ｜诊断: {result['root_cause']}（证据链: {trace_txt}）"
        else:
            f["detail"] = f.get("detail", "") + f" ｜诊断: {result.get('conclusion', 'DIAG_NO_EVIDENCE')}（已查: {trace_txt}）"
    return chains


# ============================================================
# 3. 报告生成
# ============================================================

# 报告模板外置（Phase 4.3）：{placeholder} 渲染，读取失败回退内置默认
_TEMPLATE_PATH = _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "..", "references", "report-template.md")

_FALLBACK_TEMPLATE = """# 智能巡检报告

**生成时间**: {generated_at}　**run_id**: {run_id}　**分析周期**: 近{days}天　**分析维度**: {dim_count}项

| 🔴 CRITICAL | 🟡 WARNING | 🟢 OK |
|---|---|---|
| {critical} | {warnings} | {ok_count} |

{sections}

## 巡检建议

{recommendations}

## Data Notes

{data_notes}

---
*报告由智能巡检系统自动生成（内置模板回退）*

{qa_checklist}
"""


def _render_report_markdown(context):
    """模板渲染：外置模板优先，读取/占位符失败回退内置默认（模板坏不毁报告）。"""
    try:
        with open(_TEMPLATE_PATH, encoding="utf-8") as fh:
            tpl = fh.read()
        return tpl.format(**context)
    except (OSError, KeyError, IndexError, ValueError) as e:
        logger.warning("外置模板渲染失败，回退内置默认: %s", e)
        return _FALLBACK_TEMPLATE.format(**context)


def generate_report(engine, days=30, limit=5000, auto_diagnosis=True):
    """生成巡检报告"""
    analyses = []
    QUERY_ERRORS.clear()  # 四分法前提：每轮重置，避免上轮失败污染本轮 no_data 归因

    # 加载阈值配置
    thresholds = load_thresholds(engine)

    # 执行各项分析（传感器分析传入阈值）
    analyses.append(analyze_water_level(engine, days, thresholds))
    analyses.append(analyze_rainfall(engine, min(days, 14), thresholds))
    analyses.append(analyze_pressure(engine, days, thresholds))
    analyses.append(analyze_percolation(engine, days))
    analyses.append(analyze_displacement(engine, days, thresholds))
    analyses.append(analyze_gate(engine, days))
    analyses.append(analyze_pump(engine, days, thresholds))
    analyses.append(analyze_water_quality(engine, days))
    analyses.append(analyze_soil_moisture(engine, days))
    analyses.append(analyze_termite(engine, days))
    analyses.append(analyze_inspection_results(engine, days))
    analyses.append(analyze_equipment(engine))
    analyses.append(analyze_alerts(engine, days))
    analyses.append(analyze_mad_anomaly(engine, days, thresholds))
    analyses.append(analyze_correlation(engine, min(days, 7), thresholds))

    # 高风险自动诊断（Phase 2）：CRITICAL → 路由表 → 根因链回填；失败不毁报告
    if auto_diagnosis:
        try:
            run_auto_diagnosis(engine, analyses)
        except Exception as e:
            logger.warning("自动诊断环节失败（不影响报告主体）: %s", e)

    # 统计
    total_findings = sum(len(a.get('findings', [])) for a in analyses)
    critical = sum(1 for a in analyses for f in a.get('findings', []) if f.get('level') == 'CRITICAL')
    warnings = sum(1 for a in analyses for f in a.get('findings', []) if f.get('level') == 'WARNING')
    ok_count = sum(1 for a in analyses for f in a.get('findings', []) if f.get('level') == 'OK')

    # 生成报告（模板渲染，Phase 4.3）
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    sections = ""
    for analysis in analyses:
        category = analysis.get('category', '未知')
        findings = analysis.get('findings', [])
        stats = analysis.get('stats', None)

        sections += f"## {category}\n\n"

        if stats:
            if category == '巡检结果':
                sections += f"- 总任务: {stats.get('total', 0)}, 已完成: {stats.get('completed', 0)}, 超时: {stats.get('overtime', 0)}\n"
                sections += f"- 完成率: {stats.get('completion_rate', 'N/A')}, 超时率: {stats.get('overtime_rate', 'N/A')}\n"
                sections += f"- 缺陷总数: {stats.get('total_defects', 0)}\n\n"
            elif category == '设备状态':
                sections += f"- 总设备: {stats.get('total', 0)}, 在线: {stats.get('online', 0)}, 离线: {stats.get('offline', 0)}, 异常: {stats.get('abnormal', 0)}\n\n"
            elif category == '告警分析':
                sections += f"- 告警总数: {stats.get('total', 0)}, 未确认: {stats.get('unconfirmed', 0)}\n"
                sections += f"- I级: {stats.get('level_1', 0)}, II级: {stats.get('level_2', 0)}, III级: {stats.get('level_3', 0)}, IV级: {stats.get('level_4', 0)}\n\n"

        for f in findings:
            level = f.get('level', 'INFO')
            icon = {'CRITICAL': '🔴', 'WARNING': '🟡', 'INFO': '🔵', 'OK': '🟢'}.get(level, '⚪')
            sections += f"- {icon} **{f.get('message', '')}**\n"
            if f.get('detail'):
                sections += f"  - {f['detail']}\n"

        sections += "\n"

    recommendations = ""
    if critical > 0:
        recommendations += "1. **紧急**: 有CRITICAL级发现，需立即组织现场检查\n"
    if warnings > 0:
        recommendations += "2. **关注**: 有WARNING级发现，建议本周内安排巡检\n"
    if critical == 0 and warnings == 0:
        recommendations += "- 各项指标正常，建议按常规计划巡检\n"

    # Data Notes 表（Phase 4.3）：本次所有 NOT_APPLICABLE/NO_DATA/QUERY_FAILED/inconclusive 项
    note_rows = []
    for a in analyses:
        st = a.get("status")
        if st in ("无数据", "数据不足"):
            note_rows.append(f"| {a.get('category')} | {a.get('status_code', 'NO_DATA')} | {a.get('status_note', '')} |")
        elif st == "inconclusive":
            note_rows.append(f"| {a.get('category')} | INCONCLUSIVE | {a.get('status_note', '数据完整性红档，不足以下结论')} |")
    if note_rows:
        data_notes = "| 维度 | 状态码 | 说明 |\n|---|---|---|\n" + "\n".join(note_rows)
    else:
        data_notes = "本次全部维度均有数据且质量达标。"

    # QA 闸（P2-T8）
    qa_checklist = ""
    try:
        import sys as _sys
        _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))
        from report import _QA_CHECKLIST
        qa_checklist = _QA_CHECKLIST.format(confidence_tier="With caveats")
    except Exception:
        pass  # QA 闸导入失败不影响报告主体

    report = _render_report_markdown({
        "generated_at": now,
        "run_id": get_run_id(),
        "days": days,
        "dim_count": len(analyses),
        "critical": critical,
        "warnings": warnings,
        "ok_count": ok_count,
        "sections": sections.rstrip() + "\n",
        "recommendations": recommendations.rstrip(),
        "data_notes": data_notes,
        "qa_checklist": qa_checklist,
    })

    return report, analyses


# ============================================================
# 4. envelope 输出契约（Phase 1，对齐 SysOM 诊断 envelope）
# ============================================================

# 封闭错误码枚举——下游按 code 分支，不解析 message
ERROR_FIX_HINTS = {
    "DB_CONNECT_FAILED": "检查 POWERELF_DB_* 环境变量与网络连通性（source ../_shared/bootstrap.sh）",
    "TABLE_MISSING": "确认目标库为 powerelf_srm_yml 且已执行建表脚本；勿重试本维度",
    "QUERY_TIMEOUT": "缩小 --days 窗口或降低 --limit；确认索引 (st_id, tm) 存在",
    "BAD_ARGS": "检查 CLI 参数：--days/--limit 必须为正整数，--db 为合法连接串",
}


def make_error(code, message):
    """错误对象定型 {code, message, fix_hint}。code 必须取自封闭枚举。"""
    if code not in ERROR_FIX_HINTS:
        code = "BAD_ARGS"
    return {"code": code, "message": str(message)[:500], "fix_hint": ERROR_FIX_HINTS[code]}


def get_run_id():
    """run_id 审计链：env SKILL_SESSION_ID 优先（格式校验），否则生成 insp-<uuid> 并回写 env。"""
    import re
    import uuid
    sid = _os.environ.get("SKILL_SESSION_ID", "")
    if sid and re.fullmatch(r"[A-Za-z0-9_.\-]{8,64}", sid):
        return sid
    sid = f"insp-{uuid.uuid4()}"
    _os.environ["SKILL_SESSION_ID"] = sid
    return sid


# 维度 → 数据源锚点（表.列），防结论漂移；时间窗在 build_envelope 内拼接
CATEGORY_DATA_SOURCES = {
    "水库水情": "st_rsvr_r.rz/inq/otq",
    "雨量监测": "st_pptn_r.p",
    "渗压监测": "st_pressure_r.water_pressure",
    "渗流监测": "st_percolation_r.percolation",
    "位移监测": "dsm_dfr_srvrds_srhrds.speed_gh/wgs84_delta_h",
    "闸门工情": "rei_gate_r.gtophgt/gtq",
    "泵站工情": "rei_pump_r.uab/ubc/uca/ia/ib/ic/freq",
    "水质监测": "wq_pcp_d.ph/dox/nh3n/tn/tp",
    "土壤墒情": "st_soil_moisture_r.soil_water*",
    "白蚁监测": "st_termite_monitor_r.check_result/damage_level",
    "巡检结果": "business_check_task.status/exceed_time/check_percent",
    "设备状态": "eq_equip_base.status",
    "告警分析": "ew_info_message.level_r/message_confirm",
    "MAD统计异常": "st_rsvr_r/st_pressure_r/st_percolation_r/dsm_dfr_srvrds_srhrds (MAD)",
    "关联异常": "st_rsvr_r+st_pressure_r+st_pptn_r (关联)",
}

_SEVERITY_MAP = {"CRITICAL": "critical", "WARNING": "warning", "INFO": "info"}


def build_envelope(analyses, run_id, command, days=30, error=None):
    """把 15 个 analyze_* 的平铺 findings 归一为 envelope 契约。

    契约：{ok, run_id, command, error, agent:{status, summary, findings[], next_steps[]}}
    findings 核心 4 字段 severity/title/detail/category + 附注 data_source/correlated_with。
    OK 级条目是"本维度正常"占位，不进 findings（envelope 用 status/summary 表达正常）。
    """
    if error is not None:
        return {
            "ok": False, "run_id": run_id, "command": command, "error": error,
            "agent": {"status": "no_data", "summary": f"巡检未能执行：{error['code']}",
                      "findings": [], "next_steps": [
                          {"kind": "manual", "label": "修复环境", "command": None,
                           "reason": error["fix_hint"]}]},
        }

    findings = []
    no_data_cats = []
    no_data_notes = []
    inconclusive_cats = []
    analyzed_cats = 0
    for a in analyses:
        cat = a.get("category", "未知")
        if a.get("status") in ("无数据", "数据不足"):
            no_data_cats.append(cat)
            note = a.get("status_note")
            no_data_notes.append(f"{cat}[{a.get('status_code', 'NO_DATA')}]"
                                 + (f": {note}" if note else ""))
            continue
        if a.get("status") == "inconclusive":
            inconclusive_cats.append(cat)
            continue
        analyzed_cats += 1
        anchor = CATEGORY_DATA_SOURCES.get(cat, cat)
        for f in a.get("findings", []):
            level = f.get("level", "INFO")
            if level == "OK":
                continue
            fid = f"F{len(findings)+1:03d}"
            if f.get("diagnosis_root_cause"):
                fcat = "root_cause"  # 诊断链命中 → stop-ready，不再追加分析轮次
            elif level == "INFO":
                fcat = "info"
            else:
                fcat = "anomaly"
            ef = {
                "id": fid,
                "severity": _SEVERITY_MAP.get(level, "info"),
                "title": f"[{cat}] {f.get('message', '')}",
                "detail": f.get("detail", ""),
                "category": fcat,
                "data_source": f"{anchor} @ [-{days}d, now]",
                "correlated_with": [],
            }
            if f.get("pattern"):  # Phase 4.9：三分通道标签（仅 change-rate 类 finding 有）
                ef["pattern"] = f["pattern"]
            findings.append(ef)

    critical_n = sum(1 for f in findings if f["severity"] == "critical")
    warning_n = sum(1 for f in findings if f["severity"] == "warning")
    info_n = sum(1 for f in findings if f["severity"] == "info")

    if analyzed_cats == 0 and not inconclusive_cats:
        status = "no_data"
    elif critical_n > 0:
        status = "critical"
    elif warning_n > 0:
        status = "warning"
    elif inconclusive_cats:
        # 数据质量红档维度存在且无明确异常结论 → inconclusive（退出码 4）
        status = "inconclusive"
    else:
        status = "ok"

    # summary 计数 ≡ findings 明细（输出纪律 #4）
    total_dims = len(analyses)
    if status == "no_data":
        summary = f"{total_dims} 项巡检维度均无数据，无法给出结论"
    else:
        parts = [f"{total_dims} 项巡检（{analyzed_cats} 项有数据）",
                 f"异常 {critical_n + warning_n} 项（CRITICAL {critical_n} / WARNING {warning_n} / INFO {info_n}）"]
        if inconclusive_cats:
            parts.append(f"数据质量不足以下结论 {len(inconclusive_cats)} 项：{'、'.join(inconclusive_cats)}")
        if critical_n > 0:
            top = next(f for f in findings if f["severity"] == "critical")
            parts.append(f"最严重：{top['title']}")
        summary = "，".join(parts)

    next_steps = []
    if critical_n > 0:
        next_steps.append({
            "kind": "manual", "label": "现场核查",
            "command": None,
            "reason": "存在 CRITICAL 级发现，按边界规则需人工确认后处置"})
    if warning_n > 0:
        next_steps.append({
            "kind": "manual", "label": "本周安排巡检复核",
            "command": None,
            "reason": f"{warning_n} 项 WARNING 需在例行巡检中确认"})
    if inconclusive_cats:
        next_steps.append({
            "kind": "manual", "label": "先修数据再下结论",
            "command": None,
            "reason": f"数据完整性<80%（红档）维度：{'、'.join(inconclusive_cats)}，"
                      "先经 powerelf-data-governance 排查采集/传输，再复跑巡检"})
    if no_data_cats:
        next_steps.append({
            "kind": "manual", "label": "核查无数据维度",
            "command": None,
            "reason": "；".join(no_data_notes) + "（区分设备离线与本工程无此类设备）"})

    return {
        "ok": True, "run_id": run_id, "command": command, "error": None,
        "agent": {"status": status, "summary": summary,
                  "findings": findings, "next_steps": next_steps},
    }


def envelope_exit_code(envelope):
    """退出码语义：0 无异常 / 2 检出 CRITICAL / 3 DB 连接失败 / 4 inconclusive / 5 关键表缺失。"""
    if not envelope.get("ok"):
        code = (envelope.get("error") or {}).get("code")
        if code == "DB_CONNECT_FAILED":
            return 3
        if code == "TABLE_MISSING":
            return 5
        return 3
    status = envelope["agent"]["status"]
    if status == "critical":
        return 2
    if status == "inconclusive":
        return 4
    return 0


def append_run_ledger(run_id, command, exit_code, envelope, duration_s):
    """state 台账（Phase 4.2）：每次运行追加一行 JSONL 到 state/inspection_runs.jsonl，
    供趋势回看与评测取数。写入失败只告警，不影响主流程。"""
    try:
        state_dir = _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)), "..", "state")
        _os.makedirs(state_dir, exist_ok=True)
        agent = envelope.get("agent", {})
        fnds = agent.get("findings", [])
        row = {
            "run_id": run_id,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "command": command,
            "exit_code": exit_code,
            "status": agent.get("status"),
            "critical": sum(1 for f in fnds if f.get("severity") == "critical"),
            "warning": sum(1 for f in fnds if f.get("severity") == "warning"),
            "error_code": (envelope.get("error") or {}).get("code"),
            "duration_s": round(duration_s, 2),
        }
        with open(_os.path.join(state_dir, "inspection_runs.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("state 台账写入失败（不影响主流程）: %s", e)


# ============================================================
# 5. CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="智能巡检分析工具")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--days", type=int, default=30, help="分析天数")
    parser.add_argument("--limit", type=int, default=5000, help="每表最大查询行数")
    parser.add_argument("--output", help="输出报告文件路径")
    parser.add_argument("--json", action="store_true", help="输出 envelope JSON（Phase 1 契约）")
    parser.add_argument("--legacy-json", action="store_true",
                        help="输出旧版裸 analyses 数组（过渡一个版本后移除）")
    parser.add_argument("--no-auto-diagnosis", action="store_true",
                        help="关闭 CRITICAL 异常的自动诊断链（Phase 2 唯一 opt-out）")

    args = parser.parse_args()

    _started = datetime.now()
    run_id = get_run_id()
    command = f"inspection_analyzer --days {args.days}"

    def _finish(envelope):
        code = envelope_exit_code(envelope)
        append_run_ledger(run_id, command, code, envelope,
                          (datetime.now() - _started).total_seconds())
        sys.exit(code)

    if args.days <= 0 or args.limit <= 0:
        envelope = build_envelope([], run_id, command,
                                  error=make_error("BAD_ARGS", f"days={args.days} limit={args.limit}"))
        print(json.dumps(envelope, ensure_ascii=False, indent=2, default=str))
        _finish(envelope)

    try:
        # 双超时（Phase 4.7）：connect 10s + read 120s，防单查询挂死整轮巡检
        engine = create_engine(args.db, connect_args={
            "connect_timeout": 10, "read_timeout": 120})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        envelope = build_envelope([], run_id, command,
                                  error=make_error("DB_CONNECT_FAILED", e))
        print(json.dumps(envelope, ensure_ascii=False, indent=2, default=str))
        _finish(envelope)

    report, analyses = generate_report(engine, args.days, args.limit,
                                       auto_diagnosis=not args.no_auto_diagnosis)
    envelope = build_envelope(analyses, run_id, command, days=args.days)

    if args.legacy_json:
        body = json.dumps(analyses, ensure_ascii=False, indent=2, default=str)
    elif args.json:
        body = json.dumps(envelope, ensure_ascii=False, indent=2, default=str)
    else:
        body = report

    print(body)

    if args.output:
        # 写盘失败不毁输出：正文已走 stdout，仅记录错误（Phase 4.5）
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(body)
            print(f"\n报告已保存到: {args.output}", file=sys.stderr)
        except OSError as e:
            logger.error("report_file_write_error: %s", e)
            print(f"\n[report_file_write_error] 写盘失败（正文已输出至 stdout）: {e}", file=sys.stderr)

    _finish(envelope)


if __name__ == "__main__":
    main()
