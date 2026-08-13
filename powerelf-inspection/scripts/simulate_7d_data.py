#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""智能巡检近 7 天模拟数据生成器（写本地库 powerelf_srm_yml）。

设计目标（用户确认，方案A）：
1. 数据量符合真实情况：水位/雨量/渗压/渗流/闸门/泵站按每小时 1 条，GNSS 按每日 1 条，
   水质/墒情每日 1 条，白蚁每周 1 条，巡检任务每日若干，告警少量。
2. 大部分设备正常：基线取自历史统计（st_rsvr_r rz≈461m、渗压 430-460kPa、渗流≈0.6L/s、
   闸门开度≈1.2m、泵站 380V/50A/50Hz、水质 pH≈7.5 等），叠加小幅随机波动（防恒值，
   波动幅度低于各维度检出阈值，不触发误报）。
3. 问题设备 5 台（2 严重 + 2 中等 + 1 细微）：
   - 严重① 渗压计 eq_id=139：最后 6 点连续上升（458→473kPa）→ 连续上升 WARNING + MAD WARNING
   - 严重② GNSS eq_id=155：speed_gh=1.2mm/d > 1.0 → CRITICAL；delta_h=12mm > 10 → WARNING
   - 中等① 泵站 eq_id=131：三相电流 50/62/38A 不平衡 24% > 10% → WARNING
   - 中等② 闸门 eq_id=132：开度单步 1.2→2.5m 突变 > 1m（末端 step，不降级）→ WARNING
   - 细微  雨量 eq_id=127：单时段 p=35mm > 30 → 短时强降雨 WARNING + 蓝色预警 INFO

清理策略：DELETE 近 7 天窗口内各表全部行（当前窗口除 eq_code='MOCK' 恒值外无其他真实
数据，已与用户确认清理），再插入模拟数据。只读查询仍走 _shared/lib/db.py。

用法：
    source <repo>/_shared/bootstrap.sh   # 或确保 POWERELF_DB_* 已注入
    python3 powerelf-inspection/scripts/simulate_7d_data.py [--days 7] [--seed 42]
"""
import argparse
import math
import os
import random
import sys
from datetime import datetime, timedelta

# ---- 定位 repo 根，加载 _shared/lib/db.py ----
_REPO = os.environ.get("POWERELF_SKILLS_ROOT") or os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "_shared", "lib"))
from db import get_connection  # noqa: E402

# ---- 设备-业务映射（eq_business_equip_relation 实测；st_id 与 eq_code 取自 eq_equip_base）----
# (table, eq_id, st_id, eq_code)  —— 覆盖每张业务表在库中的真实设备
DEVICE_MAP = {
    "st_rsvr_r":      [(129, 87, "MOCK"), (157, 99, "MOCK"), (193, 128, "MOCK"),
                       (194, 129, "MOCK"), (250, 200, "MOCK"), (260, 210, "MOCK"), (270, 220, "MOCK")],
    "st_pptn_r":      [(127, 85, "MOCK"), (128, 86, "MOCK"), (129, 87, "MOCK"),
                       (158, 85, "MOCK"), (185, 115, "MOCK"), (186, 116, "MOCK"),
                       (192, 127, "MOCK"), (262, 212, "MOCK")],
    "st_pressure_r":  [(134, 91, "MOCK"), (135, 92, "MOCK"), (136, 91, "MOCK"),
                       (137, 92, "MOCK"), (138, 92, "MOCK"), (139, 93, "MOCK"),
                       (140, 93, "MOCK"), (141, 93, "MOCK"), (142, 93, "MOCK"),
                       (143, 93, "MOCK"), (144, 94, "MOCK"), (145, 94, "MOCK"),
                       (146, 94, "MOCK"), (147, 94, "MOCK"), (148, 94, "MOCK"),
                       (149, 95, "MOCK"), (150, 95, "MOCK"), (151, 96, "MOCK"),
                       (152, 96, "MOCK"), (153, 96, "MOCK"), (154, 96, "MOCK"),
                       (261, 211, "MOCK"), (268, 218, "MOCK")],
    "st_percolation_r": [(188, 98, "MOCK"), (269, 219, "MOCK")],
    "dsm_dfr_srvrds_srhrds": [(155, 97, "MOCK"), (187, 118, "MOCK"), (263, 213, "MOCK"),
                              (264, 214, "MOCK"), (265, 215, "MOCK")],
    "rei_gate_r":     [(132, 90, "MOCK"), (133, 90, "MOCK"), (159, 100, "MOCK"),
                       (196, 131, "MOCK"), (197, 131, "MOCK"), (266, 216, "MOCK")],
    "rei_pump_r":     [(131, 89, "MOCK"), (195, 130, "MOCK"), (267, 217, "MOCK")],
}

# 问题设备（方案A）
PROBLEM = {
    "st_pressure_r": {139},          # 严重① 渗压计持续上升
    "dsm_dfr_srvrds_srhrds": {155},  # 严重② GNSS 位移速率超限
    "rei_pump_r": {131},             # 中等① 泵站三相电流不平衡
    "rei_gate_r": {132},             # 中等② 闸门开度突变
    "st_pptn_r": {127},              # 细微  雨量短时强降雨
}

# ---- 正常基线（历史统计）与波动幅度 ----
# 波动用 正弦(短周期, 幅值小) + 随机噪声；保证连续单调 ≤4 点、单步变化低于检出阈值
NORMAL = {
    "st_rsvr_r":       {"rz": (461.5, 0.08), "inq": (45.0, 2.0), "otq": (44.0, 2.0), "w": (8400.0, 30.0)},
    "st_pptn_r":       {"p": (0.0, 0.0)},          # 正常无雨
    "st_pressure_r":   {"water_pressure": (445.0, 0.6), "ext_pressure": (51.0, 0.3), "ext_temperature": (19.5, 0.2)},
    "st_percolation_r": {"percolation": (0.6, 0.04)},
    "dsm_dfr_srvrds_srhrds": {"speed_gh": (0.10, 0.03), "delta_h": (0.0, 1.5)},
    "rei_gate_r":      {"gtophgt": (1.20, 0.08), "gtq": (15.0, 0.8)},
    "rei_pump_r":      {"u": 380.0, "i": 50.0, "freq": (50.0, 0.1)},
    "wq_pcp_d":        {"ph": (7.5, 0.15), "dox": (7.0, 0.3), "nh3n": (0.8, 0.05), "tn": (1.5, 0.05), "tp": (0.2, 0.02)},
    "st_soil_moisture_r": {"s10": (20.0, 0.5), "s20": (24.0, 0.5), "s30": (27.0, 0.5),
                           "s60": (30.0, 0.5), "s100": (32.0, 0.5)},
}

def wave(base, amp, i, rng):
    """基线 + 小幅波动：短周期正弦（周期 24 点）+ 噪声；合成波动 ~1.5×amp。"""
    sine = amp * 0.7 * math.sin(2 * math.pi * i / 24.0)
    noise = rng.gauss(0, amp * 0.4)
    return base + sine + noise

def _exec(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    return cur.rowcount

def _delete_window(conn, table, days):
    """清理近 days 天窗口内数据（先按 eq_code='MOCK' 精删，兜底删整窗）。"""
    n = 0
    try:
        n = _exec(conn, f"DELETE FROM {table} WHERE deleted=0 AND tm >= NOW()-INTERVAL {days} DAY")
    except Exception:
        n = 0
    # 若无 tm 列（wq_pcp_d 用 spt / business_check_task、ew_info_message 用 create_time）
    for col in ("tm", "spt", "create_time"):
        if n == 0:
            try:
                n = _exec(conn, f"DELETE FROM {table} WHERE deleted=0 AND {col} >= NOW()-INTERVAL {days} DAY")
            except Exception:
                n = 0
    return n

# ============================================================
# 各表生成器：返回 [(sql, rows)]
# ============================================================

def gen_st_rsvr_r(rng, now, days):
    rows = []
    for eq_id, st_id, code in DEVICE_MAP["st_rsvr_r"]:
        base = NORMAL["st_rsvr_r"]
        for i in range(days * 24):
            tm = now - timedelta(hours=(days * 24 - 1 - i))
            # 短周期(6点)正弦 + 噪声，围绕基线 461.5m 无累积漂移；
            # 半周期仅 3 点，末端 1 点轻微回落，连续单调 ≤4 点，不触发趋势层
            rz = 461.5 + 0.05 * math.sin(2 * math.pi * i / 6) + rng.gauss(0, 0.02)
            if i >= days * 24 - 1:
                rz -= 0.03
            rz = max(459.0, min(464.0, rz))
            inq = max(0, wave(base["inq"][0], base["inq"][1], i, rng))
            otq = max(0, wave(base["otq"][0], base["otq"][1], i, rng))
            w = max(0, wave(base["w"][0], base["w"][1], i, rng))
            rows.append((st_id, eq_id, code, tm, round(rz, 3), round(inq, 3),
                         round(otq, 3), round(w, 3)))
    sql = ("INSERT INTO st_rsvr_r (st_id, eq_id, eq_code, tm, rz, inq, otq, w, deleted, tenant_id) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_st_pptn_r(rng, now, days):
    rows = []
    for eq_id, st_id, code in DEVICE_MAP["st_pptn_r"]:
        for i in range(days * 24):
            tm = now - timedelta(hours=(days * 24 - 1 - i))
            if eq_id in PROBLEM["st_pptn_r"] and i == days * 24 - 5:  # 细微：单时段强降雨 35mm
                p, dr, dyp = 35.0, 60.0, 35.0
            else:
                p, dr, dyp = 0.0, 0.0, 0.0
            rows.append((st_id, eq_id, code, tm, p, dr, dyp))
    sql = ("INSERT INTO st_pptn_r (st_id, eq_id, eq_code, tm, p, dr, dyp, deleted, tenant_id) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_st_pressure_r(rng, now, days):
    rows = []
    for eq_id, st_id, code in DEVICE_MAP["st_pressure_r"]:
        base = NORMAL["st_pressure_r"]
        # 按 st_id 派生统一基线（同测站多渗压计量级一致，防同组混基线误报突变/MAD）
        dev_base = 430.0 + ((st_id * 7) % 30) * 1.2
        wp = dev_base
        for i in range(days * 24):
            tm = now - timedelta(hours=(days * 24 - 1 - i))
            if eq_id in PROBLEM["st_pressure_r"] and i >= days * 24 - 7:
                # 严重①：最后 7 点连续上升，每点 +2.4kPa（458→473），触发连续上升 + MAD
                wp += 2.4
            else:
                wp = dev_base + rng.gauss(0, base["water_pressure"][1] * 0.5)
            ext_p = wave(base["ext_pressure"][0], base["ext_pressure"][1], i, rng)
            ext_t = wave(base["ext_temperature"][0], base["ext_temperature"][1], i, rng)
            rows.append((st_id, eq_id, code, tm, round(wp, 5), round(ext_p, 5), round(ext_t, 5)))
    sql = ("INSERT INTO st_pressure_r (st_id, eq_id, eq_code, tm, water_pressure, ext_pressure, "
           "ext_temperature, section_id, sort, deleted, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,1,0,0,1)")
    return sql, rows

def gen_st_percolation_r(rng, now, days):
    rows = []
    for eq_id, st_id, code in DEVICE_MAP["st_percolation_r"]:
        base = NORMAL["st_percolation_r"]
        for i in range(days * 24):
            tm = now - timedelta(hours=(days * 24 - 1 - i))
            v = max(0.1, wave(base["percolation"][0], base["percolation"][1], i, rng))
            rows.append((st_id, eq_id, code, tm, round(v, 5)))
    sql = ("INSERT INTO st_percolation_r (st_id, eq_id, eq_code, tm, percolation, deleted, tenant_id) "
           "VALUES (%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_dsm(rng, now, days):
    rows = []
    for eq_id, st_id, code in DEVICE_MAP["dsm_dfr_srvrds_srhrds"]:
        base = NORMAL["dsm_dfr_srvrds_srhrds"]
        for i in range(days):
            tm = now - timedelta(days=(days - 1 - i))
            if eq_id in PROBLEM["dsm_dfr_srvrds_srhrds"] and i == days - 1:
                # 严重②：位移速率超 II 级（>1.0mm/d）+ 累计位移超 10mm
                speed, dh = 1.2, 12.0
            else:
                # 纯噪声（±0.02 内）防 5 点窗口连续上升；末端 2 天回落防尾窗误报
                speed = max(0.0, 0.10 + rng.gauss(0, 0.01))
                if i >= days - 2:
                    speed = max(0.0, speed - 0.02 * (i - (days - 2) + 1))
                dh = rng.gauss(base["delta_h"][0], base["delta_h"][1])
            dx = rng.gauss(0, 1.0)
            dy = rng.gauss(0, 1.0)
            rows.append((st_id, eq_id, tm, round(dh, 4), round(dx, 4), round(dy, 4),
                         round(speed, 4), round(speed, 4), round(speed, 4)))
    sql = ("INSERT INTO dsm_dfr_srvrds_srhrds (st_id, eq_id, tm, wgs84_delta_h, wgs84_delta_x, "
           "wgs84_delta_y, speed_gh, speed_gx, speed_gy, deleted, tenant_id) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_rei_gate_r(rng, now, days):
    rows = []
    for eq_id, st_id, code in DEVICE_MAP["rei_gate_r"]:
        base = NORMAL["rei_gate_r"]
        for i in range(days * 24):
            tm = now - timedelta(hours=(days * 24 - 1 - i))
            if eq_id in PROBLEM["rei_gate_r"] and i == days * 24 - 1:
                # 中等②：末端单步 1.2→2.5m 突变（step 通道，不降级）
                opening = 2.5
            else:
                # 短周期(8点)正弦 + 噪声，围绕 1.20m，无累积漂移
                opening = 1.20 + 0.05 * math.sin(2 * math.pi * i / 8) + rng.gauss(0, 0.03)
                opening = max(0.3, min(3.5, opening))
            gtq = max(0.0, opening * 12.5 + rng.gauss(0, base["gtq"][1]))
            slcd = str(code).ljust(18, "0")[:18]
            rows.append((st_id, eq_id, code, tm, round(opening, 2), 1,
                         round(gtq, 3), 1, slcd, code[:20]))
    sql = ("INSERT INTO rei_gate_r (st_id, eq_id, eq_code, tm, gtophgt, gtopnum, gtq, status, "
           "slcd, stcd, deleted, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_rei_pump_r(rng, now, days):
    rows = []
    for eq_id, st_id, code in DEVICE_MAP["rei_pump_r"]:
        base = NORMAL["rei_pump_r"]
        for i in range(days * 24):
            tm = now - timedelta(hours=(days * 24 - 1 - i))
            if eq_id in PROBLEM["rei_pump_r"] and i == days * 24 - 3:
                # 中等①：三相电流 50/62/38A，不平衡 24% > 10%
                ia, ib, ic = 50.0, 62.0, 38.0
            else:
                ia = base["i"] + rng.gauss(0, 0.5)
                ib = base["i"] + rng.gauss(0, 0.5)
                ic = base["i"] + rng.gauss(0, 0.5)
            u = base["u"] + rng.gauss(0, 1.0)
            freq = max(45.0, min(55.0, wave(base["freq"][0], base["freq"][1], i, rng)))
            p = round(ia * u * 1.732 / 1000.0, 1)
            idstcd = str(code).ljust(18, "0")[:18]
            rows.append((st_id, eq_id, code, tm, f"{u:.1f}", f"{u:.1f}", f"{u:.1f}",
                         f"{ia:.1f}", f"{ib:.1f}", f"{ic:.1f}", str(p), str(round(freq, 1)),
                         1, idstcd))
    sql = ("INSERT INTO rei_pump_r (st_id, eq_id, eq_code, tm, uab, ubc, uca, ia, ib, ic, p, freq, "
           "status, idstcd, deleted, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_wq_pcp_d(rng, now, days):
    """水质：每日 2 条（08:00/16:00），按 stcd（历史 3 站：scsz1#/spsz1#/skswz0001）"""
    rows = []
    stcds = ["scsz1#", "spsz1#", "skswz0001"]
    base = NORMAL["wq_pcp_d"]
    for stcd in stcds:
        for i in range(days):
            for hh in (8, 16):
                spt = (now - timedelta(days=(days - 1 - i))).replace(hour=hh, minute=0, second=0, microsecond=0)
                ph = wave(base["ph"][0], base["ph"][1], i, rng)
                dox = wave(base["dox"][0], base["dox"][1], i, rng)
                nh3n = max(0.0, wave(base["nh3n"][0], base["nh3n"][1], i, rng))
                tn = max(0.0, wave(base["tn"][0], base["tn"][1], i, rng))
                tp = max(0.0, wave(base["tp"][0], base["tp"][1], i, rng))
                rows.append((stcd, spt, round(ph, 2), round(dox, 1), round(nh3n, 2),
                             round(tn, 2), round(tp, 2)))
    sql = ("INSERT INTO wq_pcp_d (stcd, spt, ph, dox, nh3n, tn, tp, deleted, tenant_id) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_st_soil_moisture_r(rng, now, days):
    """墒情：每小时 1 条（真实采集频率），1 站（st_id='101', eq_id='EQ101'）"""
    rows = []
    base = NORMAL["st_soil_moisture_r"]
    for i in range(days * 24):
        tm = now - timedelta(hours=(days * 24 - 1 - i))
        s10 = max(5.0, wave(base["s10"][0], base["s10"][1], i, rng))
        s20 = max(5.0, wave(base["s20"][0], base["s20"][1], i, rng))
        s30 = max(5.0, wave(base["s30"][0], base["s30"][1], i, rng))
        s60 = max(5.0, wave(base["s60"][0], base["s60"][1], i, rng))
        s100 = max(5.0, wave(base["s100"][0], base["s100"][1], i, rng))
        rows.append(("101", "EQ101", tm, round(s10, 2), round(s20, 2), round(s30, 2),
                     round(s60, 2), round(s100, 2), "适宜"))
    sql = ("INSERT INTO st_soil_moisture_r (st_id, eq_id, tm, soil_water10cm, soil_water20cm, "
           "soil_water30cm, soil_water60cm, soil_water100cm, soil_moist_evaluation, deleted, tenant_id) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,1)")
    return sql, rows

def gen_st_termite_r(rng, now, days):
    """白蚁：每周 1 条，补全历史 7 站（201-207），全部正常（未发现/无危害/密度0）"""
    rows = []
    for sid in ("201", "202", "203", "204", "205", "206", "207"):
        tm = now - timedelta(days=3)
        rows.append((sid, f"EQ{sid}", f"PT{sid}", tm, "未发现白蚁", "无危害", 0))
    sql = ("INSERT INTO st_termite_monitor_r (st_id, eq_id, point_id, tm, check_result, damage_level, "
           "pest_density, termite_species, deleted, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,'',0,1)")
    return sql, rows

def gen_business_check_task(rng, now, days):
    """巡检任务：每日 4 条，全部完成、不超时、无缺陷（完成率 100%）"""
    rows = []
    serial_base = now.strftime("%Y%m%d")
    for i in range(days):
        for j in range(4):
            plan = now - timedelta(days=(days - 1 - i), hours=(8 + j * 3))
            begin = plan + timedelta(hours=1)
            end = begin + timedelta(hours=2)
            serial = f"XJ{serial_base}{i:02d}{j:02d}"
            # check_percent 用历史最常见值 '0.00%'（parse_pct=0 < 0.2，不触发漏检率误报）
            rows.append((1, serial, f"日常巡检-{i}-{j}", plan, begin, end, "3", "0",
                         "0.00%", 0))
    sql = ("INSERT INTO business_check_task (dept_id, serial, name, plan_time, begin_time, end_time, "
           "status, exceed_time, check_percent, bad_num, project_id, deleted, tenant_id) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,1)")
    return sql, rows

def gen_ew_info_message(rng, now, days):
    """告警：每日 2 条 III/IV 级且已确认（无 I/II 级、无未确认积压）"""
    rows = []
    for i in range(days):
        for j, lvl in enumerate(("3", "4")):
            tm = now - timedelta(days=(days - 1 - i), hours=(10 + j * 4))
            rows.append((f"水位监测告警-{i}-{j}", lvl, tm, 1))
    sql = ("INSERT INTO ew_info_message (ew_name, level_r, gather_time, message_confirm, type, dot_id, "
           "ew_rules_id, deleted, tenant_id) VALUES (%s,%s,%s,%s,'0',0,0,0,1)")
    return sql, rows

# ============================================================

def main():
    ap = argparse.ArgumentParser(description="生成智能巡检近 N 天模拟数据（写本地库）")
    ap.add_argument("--days", type=int, default=7, help="模拟窗口天数（默认 7）")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="只打印计划不写库")
    args = ap.parse_args()
    days = max(3, min(args.days, 30))
    rng = random.Random(args.seed)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)

    gens = [
        gen_st_rsvr_r, gen_st_pptn_r, gen_st_pressure_r, gen_st_percolation_r,
        gen_dsm, gen_rei_gate_r, gen_rei_pump_r, gen_wq_pcp_d,
        gen_st_soil_moisture_r, gen_st_termite_r, gen_business_check_task,
        gen_ew_info_message,
    ]

    plan = []
    for g in gens:
        sql, rows = g(rng, now, days)
        table = sql.split("INTO ")[1].split(" ")[0]
        plan.append((table, sql, rows))

    total = sum(len(r) for _, _, r in plan)
    print(f"[simulate] 计划：{days} 天窗口，{len(plan)} 张表，共 {total} 行")
    for table, _, rows in plan:
        print(f"  - {table}: {len(rows)} 行")

    if args.dry_run:
        print("[simulate] dry-run 模式，未写库")
        return 0

    conn = get_connection()
    try:
        for table, sql, rows in plan:
            n_del = _delete_window(conn, table, days)
            cur = conn.cursor()
            # 分批插入（每批 500），避免长事务
            for i in range(0, len(rows), 500):
                cur.executemany(sql, rows[i:i + 500])
            print(f"[simulate] {table}: 清理 {n_del} 行, 插入 {len(rows)} 行")
        conn.commit()
        print("[simulate] ✅ 全部写入完成并提交")
    except Exception as e:
        conn.rollback()
        print(f"[simulate] ❌ 失败已回滚: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
