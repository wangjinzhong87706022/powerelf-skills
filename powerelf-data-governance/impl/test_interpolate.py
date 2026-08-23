"""Tests for interpolate.py — 四策略自适应插值算子（impl CLI 的纯函数核心）。

DG-P11 回归锁：插值题此前"暂无内置脚本"导致 agent 8×write_file 开发螺旋，
本脚本把 lib/interpolation 包成一条命令（同 missing_detector 惯例）。
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import interpolate as interp


# ---------- build_report：无缺失 / 全缺失 ----------

def test_no_gap():
    rows = [("2026-08-16 00:00", 1.0), ("2026-08-16 01:00", 1.2)]
    r = interp.build_report(rows, "st_rsvr_r", "rz", st_id=123)
    assert r["status"] == "NO_GAP"
    assert r["missing_points"] == 0
    assert r["filled"] == []


def test_all_missing():
    rows = [("2026-08-16 00:00", None), ("2026-08-16 01:00", None)]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    assert r["status"] == "NO_VALID_DATA"
    assert r["filled"] == []


# ---------- build_report：短缺失 → 线性策略，值正确 ----------

def test_short_gap_uses_linear_and_fills_correctly():
    # 缺失点 < 3 → select_strategy 返回 linear；线性插值 0.0..2.0 中点 = 1.0
    rows = [("t0", 0.0), ("t1", None), ("t2", 2.0)]
    r = interp.build_report(rows, "st_rsvr_r", "rz", st_id=9)
    assert r["status"] == "OK"
    assert r["strategy"] == "linear"
    assert r["missing_points"] == 1
    assert abs(r["filled"][0]["value"] - 1.0) < 1e-6
    assert r["filled"][0]["tm"] == "t1"


def test_two_gap_linear_values():
    rows = [("t0", 0.0), ("t1", None), ("t2", None), ("t3", 3.0)]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    assert r["strategy"] == "linear"
    vals = [f["value"] for f in r["filled"]]
    assert abs(vals[0] - 1.0) < 1e-6 and abs(vals[1] - 2.0) < 1e-6


# ---------- 报告自述关键词（DG-P01 同款纪律：结论必须自述方法）----------

def test_explanation_names_adaptive_strategy():
    rows = [("t0", 0.0), ("t1", None), ("t2", 2.0)]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    for kw in ("自适应", "策略", "插值"):
        assert kw in r["explanation"], f"explanation 缺关键词[{kw}]: {r['explanation']}"


# ---------- 统计与合理性 ----------

def test_missing_rate():
    rows = [("t0", 1.0), ("t1", None), ("t2", 2.0), ("t3", None), ("t4", 3.0)]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    assert r["total_points"] == 5
    assert r["missing_points"] == 2
    assert r["missing_rate"] == "40.00%"


def test_filled_in_range_pct():
    # 填补值应落在有效值 min/max 范围内（线性插值天然满足；报告该指标防二次/样条跑飞）
    rows = [("t0", 10.0), ("t1", None), ("t2", 20.0)]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    assert r["filled_in_range_pct"] == "100.00%"


# ---------- 时间断档检测（#23 能力扩展回归锁）----------

def test_time_gap_detected_and_filled():
    """#23 场景：已存行无 NULL，但存在整段时间断档（设备停报）。
    原版返回 NO_GAP → agent 自写 12 文件撞超时；现应检出断档并填补。"""
    # 每小时一行，03→06 之间缺 04/05 两个时间点（3h 空窗 > 2h 阈值）
    rows = [
        ("2026-08-16 00:00", 100.0),
        ("2026-08-16 01:00", 101.0),
        ("2026-08-16 02:00", 102.0),
        ("2026-08-16 03:00", 103.0),
        ("2026-08-16 06:00", 106.0),  # 断档 3h
        ("2026-08-16 07:00", 107.0),
    ]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    assert r["status"] == "OK", f"应检出断档并填补，实际 {r['status']}"
    assert r["time_gap_count"] == 1, f"应检出 1 处断档，实际 {r['time_gap_count']}"
    assert r["time_gaps"][0]["gap_hours"] == 3.0
    # 断档应被重采样为占位并填补（04=104.0, 05=105.0 线性插值）
    filled_tms = {f["tm"] for f in r["filled"]}
    assert "2026-08-16 04:00:00" in filled_tms, f"断档占位 04:00 未填补: {filled_tms}"
    assert "2026-08-16 05:00:00" in filled_tms, f"断档占位 05:00 未填补: {filled_tms}"
    by_tm = {f["tm"]: f["value"] for f in r["filled"]}
    assert abs(by_tm["2026-08-16 04:00:00"] - 104.0) < 1e-6
    assert abs(by_tm["2026-08-16 05:00:00"] - 105.0) < 1e-6


def test_no_false_gap_on_regular_cadence():
    """正常等间隔数据不应误报断档（频率推断=1h，间隔≤2h 不算断档）。"""
    rows = [(f"2026-08-16 {h:02d}:00", 100.0 + h) for h in range(10)]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    assert r["status"] == "NO_GAP"
    assert r["time_gap_count"] == 0


def test_time_gap_explanation_names_strategy():
    """断档填补报告仍须自述方法名（DG-P01 纪律）。"""
    rows = [
        ("2026-08-16 00:00", 100.0),
        ("2026-08-16 01:00", 101.0),
        ("2026-08-16 05:00", 105.0),  # 4h 断档
    ]
    r = interp.build_report(rows, "st_rsvr_r", "rz")
    assert r["status"] == "OK"
    assert "断档" in r["explanation"], r["explanation"]
    assert "插值" in r["explanation"], r["explanation"]


def test_gap_hours_threshold_respected():
    """--gap-hours 阈值可调：4h 空窗在阈值 5h 下不算断档。"""
    rows = [
        ("2026-08-16 00:00", 100.0),
        ("2026-08-16 01:00", 101.0),
        ("2026-08-16 05:00", 105.0),  # 4h 空窗
    ]
    r = interp.build_report(rows, "st_rsvr_r", "rz", gap_hours=5.0)
    assert r["status"] == "NO_GAP", f"阈值 5h 下 4h 空窗不应算断档: {r['status']}"


# ---------- 输入防御 ----------

def test_field_validation_rejects_injection():
    for bad in ("rz; DROP TABLE x", "rz--", "1rz", ""):
        try:
            interp.validate_field(bad)
            raise AssertionError(f"应拒绝非法字段名: {bad!r}")
        except ValueError:
            pass
    assert interp.validate_field("rz") == "rz"
    assert interp.validate_field("water_pressure") == "water_pressure"
