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
from datetime import datetime, timedelta

logger = logging.getLogger("inspection_analyzer")

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
    where_parts = [f"{time_field} >= NOW()-INTERVAL :days DAY"]
    params = {"days": days, "limit": limit}
    if st_id:
        where_parts.append("st_id = :st_id")
        params["st_id"] = st_id
    where = " AND ".join(where_parts)
    sql = f"SELECT {fields} FROM {table} WHERE {where} ORDER BY {time_field} DESC LIMIT :limit"
    try:
        return pd.read_sql(text(sql), engine, params=params)
    except Exception as e:
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

def analyze_water_level(engine, days=30, thresholds=None):
    """分析水库水情"""
    findings = []
    thresholds = thresholds or {}

    # 读取最近数据
    df = read_sensor_data(engine, "st_rsvr_r", "st_id, rz, inq, otq, w, tm", days=days)
    if df.empty:
        return {"category": "水库水情", "status": "无数据", "findings": []}

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

        # 趋势分析
        rz_values = st_data['rz'].dropna().astype(float)
        if len(rz_values) >= 6:
            recent_6 = rz_values.tail(6).values
            if all(recent_6[i] > recent_6[i-1] for i in range(1, len(recent_6))):
                findings.append({
                    "level": "WARNING",
                    "message": f"测站{st_id}: 水位连续上升6次 ({rz_values.iloc[-6]:.2f}m → {rz:.2f}m)",
                    "detail": "持续上升趋势，需关注"
                })
            elif all(recent_6[i] < recent_6[i-1] for i in range(1, len(recent_6))):
                findings.append({
                    "level": "INFO",
                    "message": f"测站{st_id}: 水位连续下降6次 ({rz_values.iloc[-6]:.2f}m → {rz:.2f}m)",
                    "detail": "持续下降趋势"
                })

        # 极值分析
        rz_max = rz_values.max()
        rz_min = rz_values.min()
        rz_mean = rz_values.mean()

        # 稳健 MAD（替换 2-sigma：水位偏态，参数法易误报/漏报；修 H4）
        if len(rz_values) >= 10:
            _rz = rz_values.values
            _median = float(np.median(_rz))
            _mad = float(np.median(np.abs(_rz - _median))) * 1.4826
            if _mad > 0:
                _z = abs(rz - _median) / _mad
                if _z > 3.0:
                    findings.append({
                        "level": "WARNING",
                        "message": f"测站{st_id}: 当前水位{rz:.2f}m MAD统计异常 z={_z:.1f} (中位数{_median:.2f}m)",
                        "detail": "偏离历史分布，需确认"
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
        return {"category": "雨量监测", "status": "无数据", "findings": []}

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
        return {"category": "渗压监测", "status": "无数据", "findings": []}

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()
        st_data['water_pressure'] = pd.to_numeric(st_data['water_pressure'], errors='coerce')
        st_data = st_data.dropna(subset=['water_pressure'])

        if len(st_data) < 3:
            continue

        latest = st_data.iloc[-1]
        wp = float(latest['water_pressure'])

        # 趋势分析 - 连续上升
        wp_values = st_data['water_pressure'].values
        if len(wp_values) >= 7:
            recent_7 = wp_values[-7:]
            if all(recent_7[i] > recent_7[i-1] for i in range(1, len(recent_7))):
                findings.append({
                    "level": "WARNING",
                    "message": f"渗压计{st_id}: 渗压连续7次上升 ({wp_values[-7]:.2f}kPa → {wp:.2f}kPa)",
                    "detail": "持续上升趋势，可能存在渗漏，需现场检查"
                })

        # 突变检测（阈值从注册表读取，默认5kPa）
        pressure_change_threshold = get_registry_threshold(thresholds, "st_pressure_r", "rate.max_change", 5)
        if len(wp_values) >= 2:
            change = abs(wp_values[-1] - wp_values[-2])
            if change > pressure_change_threshold:
                findings.append({
                    "level": "WARNING",
                    "message": f"渗压计{st_id}: 渗压突变{change:.2f}kPa ({wp_values[-2]:.2f} → {wp_values[-1]:.2f})",
                    "detail": f"变化幅度>{pressure_change_threshold}kPa，需确认是否有外部因素"
                })

        # MAD异常检测
        if len(wp_values) >= 10:
            median = np.median(wp_values)
            mad = np.median(np.abs(wp_values - median)) * 1.4826
            if mad > 0:
                z_score = abs(wp - median) / mad
                if z_score > 4:
                    findings.append({
                        "level": "WARNING",
                        "message": f"渗压计{st_id}: 统计异常 z_score={z_score:.1f} (当前{wp:.2f}kPa, 中位数{median:.2f}kPa)",
                        "detail": "偏离历史分布，需人工确认"
                    })

    if not findings:
        findings.append({"level": "OK", "message": "渗压正常", "detail": f"分析{len(df['st_id'].unique())}个测站"})

    return {"category": "渗压监测", "findings": findings, "data_points": len(df)}


def analyze_percolation(engine, days=30):
    """分析渗流数据（扫描整个时间窗口内的异常）"""
    findings = []
    df = read_sensor_data(engine, "st_percolation_r", "st_id, percolation, tm", days=days)
    if df.empty:
        return {"category": "渗流监测", "status": "无数据", "findings": []}

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()
        st_data['percolation'] = pd.to_numeric(st_data['percolation'], errors='coerce')
        st_data = st_data.dropna(subset=['percolation'])

        perc_values = st_data['percolation'].values
        if len(perc_values) < 2:
            continue

        # 扫描所有相邻数据点的突变
        for i in range(1, len(perc_values)):
            prev = perc_values[i-1]
            curr = perc_values[i]
            if prev > 0:
                change_pct = abs(curr - prev) / prev * 100
                if change_pct > 20:
                    findings.append({
                        "level": "WARNING",
                        "message": f"渗流计{st_id}: 渗流量突变{change_pct:.1f}% ({prev:.3f} → {curr:.3f} L/s)",
                        "detail": "变化幅度>20%，可能存在坝脚渗漏"
                    })
                    break  # 只报一次

        # 统计异常（稳健 MAD 替换 2-sigma）
        if len(perc_values) >= 10:
            _perc = perc_values.values
            _median = float(np.median(_perc))
            _mad = float(np.median(np.abs(_perc - _median))) * 1.4826
            if _mad > 0:
                latest = float(_perc[-1])
                _z = abs(latest - _median) / _mad
                if _z > 3.0:
                    findings.append({
                        "level": "WARNING",
                        "message": f"渗流计{st_id}: 渗流量{latest:.3f}L/s MAD统计异常 z={_z:.1f} (中位数{_median:.3f})",
                        "detail": "偏离历史分布，需确认"
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
        return {"category": "位移监测", "status": "无数据", "findings": []}

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
            recent_5 = speed_values[-5:]
            if all(recent_5[i] > recent_5[i-1] for i in range(1, len(recent_5))):
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
        return {"category": "巡检结果", "status": "无数据", "findings": []}

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
        return {"category": "设备状态", "status": "无数据", "findings": []}

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
        return {"category": "闸门工情", "status": "无数据", "findings": []}

    for st_id in df['st_id'].unique():
        st_data = df[df['st_id'] == st_id].sort_values('tm').copy()
        st_data['gtophgt'] = pd.to_numeric(st_data['gtophgt'], errors='coerce')
        st_data['gtq'] = pd.to_numeric(st_data['gtq'], errors='coerce')

        # 扫描所有数据点
        opening_values = st_data['gtophgt'].dropna().values
        for i in range(1, len(opening_values)):
            change = abs(opening_values[i] - opening_values[i-1])
            if change > 1.0:
                findings.append({
                    "level": "WARNING",
                    "message": f"闸门站{st_id}: 开度突变{change:.2f}m ({opening_values[i-1]:.2f} → {opening_values[i]:.2f})",
                    "detail": "开度变化>1m，需确认是否有调度操作"
                })

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
        return {"category": "泵站工情", "status": "无数据", "findings": []}

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
        logger.warning("read_water_quality 失败: %s", e)
        return {"category": "水质监测", "status": "无数据", "findings": []}

    if df.empty:
        return {"category": "水质监测", "status": "无数据", "findings": []}

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
        logger.warning("read_soil_moisture 失败: %s", e)
        return {"category": "土壤墒情", "status": "无数据", "findings": []}

    if df.empty:
        return {"category": "土壤墒情", "status": "无数据", "findings": []}

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
        logger.warning("read_termite 失败: %s", e)
        return {"category": "白蚁监测", "status": "无数据", "findings": []}

    if df.empty:
        return {"category": "白蚁监测", "status": "无数据", "findings": []}

    # 检查是否有白蚁发现
    if 'check_result' in df.columns:
        found = df[df['check_result'].str.contains('发现', na=False)]
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
        return {"category": "告警分析", "status": "无数据", "findings": []}

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

            median = np.median(values)
            mad = np.median(np.abs(values - median)) * 1.4826
            if mad == 0:
                continue

            latest = float(values[-1])
            z_score = abs(latest - median) / mad

            # MAD阈值从注册表读取
            mad_threshold = get_registry_threshold(thresholds, table, "mad_threshold", default_z)

            if z_score > mad_threshold:
                findings.append({
                    "level": "WARNING",
                    "message": f"{label}测站{st_id}: MAD统计异常 z={z_score:.1f} (阈值{mad_threshold}, 当前{latest:.2f}, 中位数{median:.2f})",
                    "detail": f"偏离历史分布，基于{len(values)}个数据点的MAD检测"
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
        return {"category": "关联异常", "status": "数据不足", "findings": []}

    # 关联分析1: 水位上升但入库流量下降
    for st_id in water['st_id'].unique():
        st_water = water[water['st_id'] == st_id].sort_values('tm').copy()
        st_water['rz'] = pd.to_numeric(st_water['rz'], errors='coerce')
        st_water['inq'] = pd.to_numeric(st_water['inq'], errors='coerce')

        if len(st_water) < 6:
            continue

        rz_trend = st_water['rz'].tail(6).values
        inq_trend = st_water['inq'].tail(6).values

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
                    if rz_change < 0.1:  # 水位基本稳定
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
                    if rz_change < 0.05:  # 水位变化<0.05m
                        findings.append({
                            "level": "INFO",
                            "message": f"关联异常: 雨量站{st_id}累计{total_rain:.0f}mm但水位变化仅{rz_change:.2f}m",
                            "detail": "需检查是否有泄洪操作或雨量站是否准确"
                        })

    if not findings:
        findings.append({"level": "OK", "message": "多指标关联分析正常", "detail": "未发现指标间矛盾"})

    return {"category": "关联异常", "findings": findings}


# ============================================================
# 3. 报告生成
# ============================================================

def generate_report(engine, days=30, limit=5000):
    """生成巡检报告"""
    analyses = []

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

    # 统计
    total_findings = sum(len(a.get('findings', [])) for a in analyses)
    critical = sum(1 for a in analyses for f in a.get('findings', []) if f.get('level') == 'CRITICAL')
    warnings = sum(1 for a in analyses for f in a.get('findings', []) if f.get('level') == 'WARNING')
    ok_count = sum(1 for a in analyses for f in a.get('findings', []) if f.get('level') == 'OK')

    # 生成报告
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    report = f"""# 智能巡检报告

**生成时间**: {now}
**分析周期**: 近{days}天
**分析维度**: {len(analyses)}项

---

## 巡检摘要

| 级别 | 数量 | 说明 |
|------|------|------|
| 🔴 CRITICAL | {critical} | 需立即处理 |
| 🟡 WARNING | {warnings} | 需关注 |
| 🟢 OK | {ok_count} | 正常 |

---

"""

    # 按严重程度排序输出
    for analysis in analyses:
        category = analysis.get('category', '未知')
        findings = analysis.get('findings', [])
        stats = analysis.get('stats', None)

        report += f"## {category}\n\n"

        if stats:
            if category == '巡检结果':
                report += f"- 总任务: {stats.get('total', 0)}, 已完成: {stats.get('completed', 0)}, 超时: {stats.get('overtime', 0)}\n"
                report += f"- 完成率: {stats.get('completion_rate', 'N/A')}, 超时率: {stats.get('overtime_rate', 'N/A')}\n"
                report += f"- 缺陷总数: {stats.get('total_defects', 0)}\n\n"
            elif category == '设备状态':
                report += f"- 总设备: {stats.get('total', 0)}, 在线: {stats.get('online', 0)}, 离线: {stats.get('offline', 0)}, 异常: {stats.get('abnormal', 0)}\n\n"
            elif category == '告警分析':
                report += f"- 告警总数: {stats.get('total', 0)}, 未确认: {stats.get('unconfirmed', 0)}\n"
                report += f"- I级: {stats.get('level_1', 0)}, II级: {stats.get('level_2', 0)}, III级: {stats.get('level_3', 0)}, IV级: {stats.get('level_4', 0)}\n\n"

        for f in findings:
            level = f.get('level', 'INFO')
            icon = {'CRITICAL': '🔴', 'WARNING': '🟡', 'INFO': '🔵', 'OK': '🟢'}.get(level, '⚪')
            report += f"- {icon} **{f.get('message', '')}**\n"
            if f.get('detail'):
                report += f"  - {f['detail']}\n"

        report += "\n"

    # 建议
    report += "## 巡检建议\n\n"

    if critical > 0:
        report += "1. **紧急**: 有CRITICAL级发现，需立即组织现场检查\n"
    if warnings > 0:
        report += "2. **关注**: 有WARNING级发现，建议本周内安排巡检\n"
    if critical == 0 and warnings == 0:
        report += "- 各项指标正常，建议按常规计划巡检\n"

    report += "\n---\n*报告由智能巡检系统自动生成*\n"

    return report, analyses


# ============================================================
# 4. CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="智能巡检分析工具")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--days", type=int, default=30, help="分析天数")
    parser.add_argument("--limit", type=int, default=5000, help="每表最大查询行数")
    parser.add_argument("--output", help="输出报告文件路径")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")

    args = parser.parse_args()

    engine = create_engine(args.db)

    report, analyses = generate_report(engine, args.days, args.limit)

    if args.json:
        print(json.dumps(analyses, ensure_ascii=False, indent=2, default=str))
    else:
        print(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            if args.json:
                json.dump(analyses, f, ensure_ascii=False, indent=2, default=str)
            else:
                f.write(report)
        print(f"\n报告已保存到: {args.output}")


if __name__ == "__main__":
    main()
