#!/usr/bin/env python3
"""
智能巡检集成测试（pytest 版）

用法（有 DB）:
  pytest test_inspection.py --db "$DB_URL" -v

用法（无 DB — 全 skip）:
  pytest test_inspection.py -v

从旧版 92 题手工测试集成迁移，转为 pytest + analyzer 接线式测试。
"""

import sys, os as _os

# 加入 lib 路径供 pytest 导入 analyzer
_lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib")
sys.path.insert(0, _lib)

# DB 可用性守卫
_DB = _os.environ.get("DB_URL") or ""
_HAS_PYTEST = True
try:
    import pytest
except ImportError:
    _HAS_PYTEST = False
    pytest = None  # type: ignore

_RUN = bool(_HAS_PYTEST and _DB)
skip_no_db = pytest.mark.skipif(not _RUN, reason="无 DB_URL 或 pytest，跳过集成测试")

# 导入 analyzer（所有测试通过 analyzer 接口）
try:
    from sqlalchemy import create_engine
    from inspection_analyzer import (
        read_sensor_data,
        analyze_water_level,
        analyze_rainfall,
        analyze_pressure,
        analyze_percolation,
        analyze_displacement,
        analyze_gate,
        analyze_pump,
        analyze_water_quality,
        analyze_equipment,
        analyze_alerts,
        analyze_inspection_results,
        analyze_mad_anomaly,
        analyze_correlation,
    )
    HAS_ANALYZER = True
except ImportError:
    HAS_ANALYZER = False


def _engine():
    return create_engine(_DB)


TEST_CASES = [
    # --- 水库水情 ---
    pytest.param("Q1", "水库水情", "水位分析", "analyze_water_level", id="Q1"),
    # --- 雨量监测 ---
    pytest.param("Q7", "雨量监测", "雨量分析", "analyze_rainfall", id="Q7"),
    # --- 渗压监测 ---
    pytest.param("Q13", "渗压监测", "渗压趋势/MAD", "analyze_pressure", id="Q13"),
    # --- 渗流监测 ---
    pytest.param("Q19", "渗流监测", "渗流分析", "analyze_percolation", id="Q19"),
    # --- 闸门工情 ---
    pytest.param("Q30", "闸门工情", "闸门分析", "analyze_gate", id="Q30"),
    # --- 泵站工情 ---
    pytest.param("Q34", "泵站工情", "泵站分析", "analyze_pump", id="Q34"),
    # --- 水质监测 ---
    pytest.param("Q38", "水质监测", "水质分析", "analyze_water_quality", id="Q38"),
    # --- 设备状态 ---
    pytest.param("Q42", "设备状态", "设备分析", "analyze_equipment", id="Q42"),
    # --- 告警分析 ---
    pytest.param("Q47", "告警分析", "告警分析", "analyze_alerts", id="Q47"),
    # --- 巡检结果 ---
    pytest.param("Q52", "巡检结果", "巡检分析", "analyze_inspection_results", id="Q52"),
    # --- MAD 统计 ---
    pytest.param("Q57", "MAD 统计", "MAD 异常", "analyze_mad_anomaly", id="Q57"),
    # --- 关联异常 ---
    pytest.param("Q60", "关联异常", "关联分析", "analyze_correlation", id="Q60"),
]


def _call_analyzer(name):
    """Call the given analyzer function and return its findings."""
    eng = _engine()
    fn = globals()[name]
    result = fn(eng)
    return result.get("findings", result if isinstance(result, list) else [])


# ============================================================
# 参数化集成测试
# ============================================================

@pytest.mark.skipif(not HAS_ANALYZER, reason="无法导入 inspection_analyzer")
@skip_no_db
@pytest.mark.parametrize("qid, cat, desc, analyzer_name", TEST_CASES)
def test_analyzer_runs(qid, cat, desc, analyzer_name):
    """运行 analyzer 函数，断言返回 findings 且无异常抛出"""
    eng = _engine()
    fn = globals()[analyzer_name]
    try:
        result = fn(eng)
    except Exception as e:
        pytest.fail(f"{qid} [{cat}] {desc} 抛异常: {e}")

    assert isinstance(result, dict), f"{qid}: 返回类型应为 dict, 实际 {type(result)}"
    assert "findings" in result or "category" in result, f"{qid}: 缺少 findings/category"


# ============================================================
# 传感器数据读取测试（轻量，主要测试通路不通）
# ============================================================

@skip_no_db
def test_read_water_level():
    df = read_sensor_data(_engine(), "st_rsvr_r", "st_id, rz, tm", days=7)
    if df.empty:
        pytest.skip("无水位数据")
    assert "rz" in df.columns


@skip_no_db
def test_read_rainfall():
    df = read_sensor_data(_engine(), "st_pptn_r", "st_id, p, tm", days=7)
    if df.empty:
        pytest.skip("无雨量数据")
    assert "p" in df.columns


@skip_no_db
def test_read_pressure():
    df = read_sensor_data(_engine(), "st_pressure_r", "st_id, water_pressure, tm", days=30)
    if df.empty:
        pytest.skip("无渗压数据")
    assert "water_pressure" in df.columns


@skip_no_db
def test_read_gate():
    df = read_sensor_data(_engine(), "rei_gate_r", "st_id, gtophgt, tm", days=30)
    if df.empty:
        pytest.skip("无闸门数据")
    assert "gtophgt" in df.columns


@skip_no_db
def test_read_pump():
    df = read_sensor_data(_engine(), "rei_pump_r", "st_id, ia, ib, ic, tm", days=30)
    if df.empty:
        pytest.skip("无泵站数据")
    assert "ia" in df.columns


@skip_no_db
def test_read_alerts():
    from inspection_analyzer import read_alerts
    df = read_alerts(_engine(), days=30)
    if df.empty:
        pytest.skip("无告警数据")
    assert "ew_name" in df.columns or "id" in df.columns


@skip_no_db
def test_read_inspections():
    from inspection_analyzer import read_inspections
    df = read_inspections(_engine(), days=30)
    if df.empty:
        pytest.skip("无巡检任务数据")
    assert "id" in df.columns


# ============================================================
# 全维度集成测试（高耗时，标记慢）
# ============================================================

@skip_no_db
@pytest.mark.slow
def test_all_15_dimensions():
    """运行全部 15 维度，验证无异常退出"""
    from inspection_analyzer import generate_report as gen_report
    try:
        report, analyses = gen_report(_engine(), days=7)
        assert isinstance(analyses, list)
        assert len(analyses) >= 1
    except Exception as e:
        pytest.fail(f"全量分析抛异常: {e}")


# ============================================================
# 入口（兼容旧版直接调用）
# ============================================================

def run_tests():
    """兼容旧版 CLI 入口"""
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="DB URL")
    parser.add_argument("-v", "--verbose", action="store_true")
    args, remaining = parser.parse_known_args()
    if args.db:
        _os.environ["DB_URL"] = args.db
    argv = [__file__] + remaining
    if args.verbose:
        argv.append("-v")
    sys.exit(pytest.main(argv))