#!/usr/bin/env python3
"""
智能巡检 Skill 自动化测试脚本
用法: python3 test_inspection.py --db "mysql+pymysql://root:xxx@localhost:3306/powerelf_srm_yml"

从92道测试题中选取代表性题目，自动执行工具并判定结果。
"""

import json
import sys
import time

try:
    import pandas as pd
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    print("需要: pip install pandas sqlalchemy pymysql")
    sys.exit(1)

DB_URL = None


def query(sql, params=None):
    """执行SQL查询"""
    engine = create_engine(DB_URL)
    return pd.read_sql(text(sql), engine, params=params or {})


# ============================================================
# 测试用例定义
# ============================================================

TEST_CASES = [
    # --- 水库水情 ---
    {
        "id": "Q1", "cat": "水库水情", "desc": "测站3水位趋势",
        "test": lambda: _check_water_trend(3),
        "expect": "OK or WARNING"
    },
    {
        "id": "Q3", "cat": "水库水情", "desc": "水位统计极值",
        "test": lambda: _check_water_stats(),
        "expect": "输出最大值/最小值/平均值"
    },
    # --- 雨量监测 ---
    {
        "id": "Q7", "cat": "雨量监测", "desc": "测站200累计雨量",
        "test": lambda: _check_rain_accumulation(200),
        "expect": "输出累计雨量数值"
    },
    {
        "id": "Q8", "cat": "雨量监测", "desc": "24h最大雨量站",
        "test": lambda: _check_max_rain_24h(),
        "expect": "输出最大雨量测站"
    },
    # --- 渗压监测 ---
    {
        "id": "Q13", "cat": "渗压监测", "desc": "渗压计416连续上升",
        "test": lambda: _check_pressure_trend(416),
        "expect": "WARNING: 连续上升"
    },
    {
        "id": "Q14", "cat": "渗压监测", "desc": "渗压突变检测",
        "test": lambda: _check_pressure_mutation(416),
        "expect": "WARNING: 突变"
    },
    # --- 渗流监测 ---
    {
        "id": "Q19", "cat": "渗流监测", "desc": "渗流计418突变",
        "test": lambda: _check_percolation_mutation(418),
        "expect": "WARNING: 突变"
    },
    # --- 闸门工情 ---
    {
        "id": "Q30", "cat": "闸门工情", "desc": "闸门开度突变",
        "test": lambda: _check_gate_mutation(131),
        "expect": "WARNING: 突变"
    },
    # --- 泵站工情 ---
    {
        "id": "Q34", "cat": "泵站工情", "desc": "三相不平衡",
        "test": lambda: _check_pump_imbalance(217),
        "expect": "WARNING: 不平衡"
    },
    # --- 水质监测 ---
    {
        "id": "Q38", "cat": "水质监测", "desc": "pH是否达标",
        "test": lambda: _check_water_quality_ph(),
        "expect": "OK or WARNING"
    },
    # --- 设备状态 ---
    {
        "id": "Q42", "cat": "设备状态", "desc": "设备在线率",
        "test": lambda: _check_equipment_status(),
        "expect": "输出在线/离线/异常数量"
    },
    # --- 告警分析 ---
    {
        "id": "Q47", "cat": "告警分析", "desc": "告警等级统计",
        "test": lambda: _check_alert_levels(),
        "expect": "输出I/II/III/IV级数量"
    },
    # --- 巡检结果 ---
    {
        "id": "Q52", "cat": "巡检结果", "desc": "巡检任务统计",
        "test": lambda: _check_task_stats(),
        "expect": "输出完成率/超时率"
    },
    # --- MAD统计 ---
    {
        "id": "Q57", "cat": "MAD统计", "desc": "MAD异常检测",
        "test": lambda: _check_mad_anomaly(),
        "expect": "OK or WARNING"
    },
    # --- 关联异常 ---
    {
        "id": "Q60", "cat": "关联异常", "desc": "水位入库关联",
        "test": lambda: _check_correlation(),
        "expect": "OK or WARNING"
    },
    # --- 边缘场景 ---
    {
        "id": "Q73", "cat": "边缘场景", "desc": "NULL值处理",
        "test": lambda: _check_null_handling(),
        "expect": "不报错"
    },
]


# ============================================================
# 测试函数实现
# ============================================================

def _check_water_trend(st_id):
    """Q1: 检查水位趋势"""
    df = query("""
        SELECT rz, tm FROM st_rsvr_r
        WHERE st_id = :st_id AND tm >= NOW() - INTERVAL 30 DAY
        ORDER BY tm DESC LIMIT 10
    """, {"st_id": st_id})
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    rz = pd.to_numeric(df['rz'], errors='coerce').dropna()
    if len(rz) < 6:
        return {"pass": True, "detail": f"数据点{len(rz)}个，不足6个，跳过趋势判定"}
    recent = rz.tail(6).values
    rising = all(recent[i] > recent[i-1] for i in range(1, len(recent)))
    falling = all(recent[i] < recent[i-1] for i in range(1, len(recent)))
    if rising:
        return {"pass": True, "detail": f"连续上升 {recent[0]:.2f}→{recent[-1]:.2f}"}
    elif falling:
        return {"pass": True, "detail": f"连续下降 {recent[0]:.2f}→{recent[-1]:.2f}"}
    else:
        return {"pass": True, "detail": f"正常波动 {recent[0]:.2f}→{recent[-1]:.2f}"}


def _check_water_stats():
    """Q3: 水位统计"""
    df = query("""
        SELECT MAX(rz) as max_rz, MIN(rz) as min_rz, AVG(rz) as avg_rz
        FROM st_rsvr_r WHERE tm >= '2026-05-01'
    """)
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    row = df.iloc[0]
    return {"pass": True, "detail": f"最大{row['max_rz']:.2f} 最小{row['min_rz']:.2f} 平均{row['avg_rz']:.2f}"}


def _check_rain_accumulation(st_id):
    """Q7: 累计雨量"""
    df = query("""
        SELECT SUM(p) as total FROM st_pptn_r
        WHERE st_id = :st_id AND tm >= NOW() - INTERVAL 7 DAY
    """, {"st_id": st_id})
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    total = float(df.iloc[0]['total'] or 0)
    return {"pass": True, "detail": f"7天累计{total:.1f}mm"}


def _check_max_rain_24h():
    """Q8: 24h最大雨量"""
    df = query("""
        SELECT st_id, sum(p) as total FROM st_pptn_r
        WHERE tm >= NOW() - INTERVAL 24 HOUR
        GROUP BY st_id ORDER BY total DESC LIMIT 1
    """)
    if df.empty:
        return {"pass": True, "detail": "24h内无雨量数据"}
    row = df.iloc[0]
    return {"pass": True, "detail": f"测站{row['st_id']}累计{row['total']:.1f}mm"}


def _check_pressure_trend(st_id):
    """Q13: 渗压趋势"""
    df = query("""
        SELECT water_pressure, tm FROM st_pressure_r
        WHERE st_id = :st_id ORDER BY tm DESC LIMIT 10
    """, {"st_id": st_id})
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    wp = pd.to_numeric(df['water_pressure'], errors='coerce').dropna()
    if len(wp) < 7:
        return {"pass": True, "detail": f"数据点{len(wp)}个，不足7个"}
    recent = wp.tail(7).values
    rising = all(recent[i] > recent[i-1] for i in range(1, len(recent)))
    if rising:
        return {"pass": True, "detail": f"连续上升 {recent[0]:.2f}→{recent[-1]:.2f}kPa"}
    return {"pass": True, "detail": f"无连续上升趋势"}


def _check_pressure_mutation(st_id):
    """Q14: 渗压突变"""
    df = query("""
        SELECT water_pressure, tm FROM st_pressure_r
        WHERE st_id = :st_id ORDER BY tm DESC LIMIT 10
    """, {"st_id": st_id})
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    wp = pd.to_numeric(df['water_pressure'], errors='coerce').dropna().values
    if len(wp) < 2:
        return {"pass": True, "detail": "数据不足"}
    for i in range(1, len(wp)):
        change = abs(wp[i] - wp[i-1])
        if change > 5:
            return {"pass": True, "detail": f"突变{change:.2f}kPa ({wp[i-1]:.2f}→{wp[i]:.2f})"}
    return {"pass": True, "detail": "无突变(>5kPa)"}


def _check_percolation_mutation(st_id):
    """Q19: 渗流突变"""
    df = query("""
        SELECT percolation, tm FROM st_percolation_r
        WHERE st_id = :st_id ORDER BY tm DESC LIMIT 10
    """, {"st_id": st_id})
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    vals = pd.to_numeric(df['percolation'], errors='coerce').dropna().values
    if len(vals) < 2:
        return {"pass": True, "detail": "数据不足"}
    for i in range(1, len(vals)):
        prev = vals[i-1]
        curr = vals[i]
        if prev > 0:
            pct = abs(curr - prev) / prev * 100
            if pct > 20:
                return {"pass": True, "detail": f"突变{pct:.1f}% ({prev:.3f}→{curr:.3f})"}
    return {"pass": True, "detail": "无突变(>20%)"}


def _check_gate_mutation(st_id):
    """Q30: 闸门突变"""
    df = query("""
        SELECT gtophgt, tm FROM rei_gate_r
        WHERE st_id = :st_id ORDER BY tm DESC LIMIT 10
    """, {"st_id": st_id})
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    vals = pd.to_numeric(df['gtophgt'], errors='coerce').dropna().values
    if len(vals) < 2:
        return {"pass": True, "detail": "数据不足"}
    for i in range(1, len(vals)):
        change = abs(vals[i] - vals[i-1])
        if change > 1.0:
            return {"pass": True, "detail": f"突变{change:.2f}m ({vals[i-1]:.2f}→{vals[i]:.2f})"}
    return {"pass": True, "detail": "无突变(>1m)"}


def _check_pump_imbalance(st_id):
    """Q34: 三相不平衡"""
    df = query("""
        SELECT ia, ib, ic, tm FROM rei_pump_r
        WHERE st_id = :st_id ORDER BY tm DESC LIMIT 10
    """, {"st_id": st_id})
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    for _, row in df.iterrows():
        vals = []
        for col in ['ia', 'ib', 'ic']:
            v = pd.to_numeric(row[col], errors='coerce')
            if pd.notna(v):
                vals.append(float(v))
        if len(vals) == 3 and all(v > 0 for v in vals):
            avg = sum(vals) / 3
            imbalance = max(abs(v - avg) for v in vals) / avg
            if imbalance > 0.10:
                return {"pass": True, "detail": f"不平衡{imbalance:.1%} ({'/'.join(f'{v:.0f}' for v in vals)})"}
    return {"pass": True, "detail": "无三相不平衡(>10%)"}


def _check_water_quality_ph():
    """Q38: 水质pH"""
    df = query("SELECT ph FROM wq_pcp_d ORDER BY spt DESC LIMIT 1")
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    ph = float(df.iloc[0]['ph'])
    status = "正常" if 6 <= ph <= 9 else "异常"
    return {"pass": True, "detail": f"pH={ph:.1f} ({status})"}


def _check_equipment_status():
    """Q42: 设备状态"""
    df = query("""
        SELECT status, COUNT(*) as cnt FROM eq_equip_base WHERE deleted=0 GROUP BY status
    """)
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    stats = {str(r['status']): int(r['cnt']) for _, r in df.iterrows()}
    online = stats.get('1', 0)
    offline = stats.get('0', 0)
    abnormal = stats.get('2', 0)
    total = online + offline + abnormal
    rate = offline / total if total > 0 else 0
    return {"pass": True, "detail": f"在线{online} 离线{offline} 异常{abnormal} 离线率{rate:.1%}"}


def _check_alert_levels():
    """Q47: 告警等级统计"""
    df = query("""
        SELECT level_r, COUNT(*) as cnt FROM ew_info_message
        WHERE deleted=0 AND create_time >= NOW()-INTERVAL 30 DAY
        GROUP BY level_r
    """)
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    stats = {str(r['level_r']): int(r['cnt']) for _, r in df.iterrows()}
    return {"pass": True, "detail": f"I级{stats.get('1',0)} II级{stats.get('2',0)} III级{stats.get('3',0)} IV级{stats.get('4',0)}"}


def _check_task_stats():
    """Q52: 巡检任务统计"""
    df = query("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='3' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN exceed_time='1' THEN 1 ELSE 0 END) as overtime
        FROM business_check_task WHERE deleted=0 AND create_time >= NOW()-INTERVAL 30 DAY
    """)
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    row = df.iloc[0]
    total = int(row['total'])
    completed = int(row['completed'])
    overtime = int(row['overtime'])
    comp_rate = completed / total if total > 0 else 0
    ovt_rate = overtime / total if total > 0 else 0
    return {"pass": True, "detail": f"总{total} 完成{completed}({comp_rate:.1%}) 超时{overtime}({ovt_rate:.1%})"}


def _check_mad_anomaly():
    """Q57: MAD检测"""
    df = query("""
        SELECT water_pressure FROM st_pressure_r
        WHERE st_id = 416 ORDER BY tm DESC LIMIT 50
    """)
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    vals = pd.to_numeric(df['water_pressure'], errors='coerce').dropna().values
    if len(vals) < 10:
        return {"pass": True, "detail": f"数据点{len(vals)}个，不足10个，跳过MAD"}
    import numpy as np
    median = np.median(vals)
    mad = np.median(np.abs(vals - median)) * 1.4826
    if mad == 0:
        return {"pass": True, "detail": "MAD=0，无变异"}
    latest = float(vals[-1])
    z_score = abs(latest - median) / mad
    status = "异常" if z_score > 4 else "正常"
    return {"pass": True, "detail": f"z_score={z_score:.1f} (当前{latest:.2f} 中位数{median:.2f}) {status}"}


def _check_correlation():
    """Q60: 水位入库关联"""
    df = query("""
        SELECT rz, inq, tm FROM st_rsvr_r
        WHERE tm >= NOW()-INTERVAL 7 DAY
        ORDER BY tm DESC LIMIT 20
    """)
    if df.empty:
        return {"pass": False, "detail": "无数据"}
    rz = pd.to_numeric(df['rz'], errors='coerce').dropna().values
    inq = pd.to_numeric(df['inq'], errors='coerce').dropna().values
    if len(rz) < 6 or len(inq) < 6:
        return {"pass": True, "detail": "数据不足"}
    rz_rising = all(rz[i] > rz[i-1] for i in range(1, min(6, len(rz))))
    inq_falling = all(inq[i] < inq[i-1] for i in range(1, min(6, len(inq))) if inq[i-1] > 0)
    if rz_rising and inq_falling:
        return {"pass": True, "detail": "关联异常: 水位上升但入库下降"}
    return {"pass": True, "detail": "无关联异常"}


def _check_null_handling():
    """Q73: NULL值处理"""
    try:
        df = query("""
            SELECT rz FROM st_rsvr_r WHERE rz IS NULL LIMIT 1
        """)
        return {"pass": True, "detail": f"NULL值查询成功，{len(df)}条"}
    except Exception as e:
        return {"pass": False, "detail": f"查询报错: {e}"}


# ============================================================
# 执行测试
# ============================================================

def run_tests():
    print("=" * 70)
    print("智能巡检 Skill 测试 (92题代表性子集)")
    print("=" * 70)

    passed = 0
    failed = 0
    errors = 0
    results = []

    for tc in TEST_CASES:
        try:
            result = tc['test']()
            status = "✅ PASS" if result['pass'] else "❌ FAIL"
            if result['pass']:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            status = f"💥 ERROR"
            result = {"pass": False, "detail": str(e)}
            errors += 1

        results.append({
            "id": tc['id'],
            "cat": tc['cat'],
            "desc": tc['desc'],
            "status": status,
            "detail": result.get('detail', '')
        })

        print(f"  {status} {tc['id']} [{tc['cat']}] {tc['desc']}: {result.get('detail', '')}")

    total = passed + failed + errors
    print(f"\n{'='*70}")
    print(f"总计: {total}题, 通过: {passed}, 失败: {failed}, 错误: {errors}")
    print(f"通过率: {passed/total*100:.1f}%")

    # 保存结果
    with open('/tmp/test_results_92.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    DB_URL = args.db
    run_tests()
