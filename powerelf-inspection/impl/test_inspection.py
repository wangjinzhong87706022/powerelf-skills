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
# envelope 输出契约单元测试（Phase 1，无需 DB）
# ============================================================

try:
    from inspection_analyzer import (
        build_envelope, make_error, envelope_exit_code, get_run_id,
    )
    HAS_ENVELOPE = True
except ImportError:
    HAS_ENVELOPE = False

envelope_only = pytest.mark.skipif(not HAS_ENVELOPE, reason="无法导入 envelope 层") if _HAS_PYTEST else (lambda f: f)

_SAMPLE_ANALYSES = [
    {"category": "水库水情", "findings": [
        {"level": "CRITICAL", "message": "测站1: 水位超汛限", "detail": "rz=105.2m"},
        {"level": "WARNING", "message": "测站2: 水位连续上升", "detail": "趋势"},
    ], "data_points": 100},
    {"category": "渗压监测", "findings": [
        {"level": "OK", "message": "渗压正常", "detail": "分析3个测站"},
    ], "data_points": 50},
    {"category": "白蚁监测", "status": "无数据", "findings": []},
]


@envelope_only
def test_envelope_structure():
    env = build_envelope(_SAMPLE_ANALYSES, "insp-test", "cmd", days=7)
    assert env["ok"] is True
    assert env["error"] is None
    assert env["run_id"] == "insp-test"
    agent = env["agent"]
    assert agent["status"] in ("critical", "warning", "ok", "no_data", "inconclusive")
    for f in agent["findings"]:
        assert set(f) >= {"id", "severity", "title", "detail", "category",
                          "data_source", "correlated_with"}
        assert f["severity"] in ("critical", "warning", "info")
        assert f["category"] in ("root_cause", "anomaly", "data_quality", "info")
        assert "@" in f["data_source"]  # 表.列 + 时间窗锚点


@envelope_only
def test_envelope_summary_matches_findings():
    """输出纪律 #4：summary 计数 ≡ findings 明细"""
    env = build_envelope(_SAMPLE_ANALYSES, "insp-test", "cmd", days=7)
    agent = env["agent"]
    critical_n = sum(1 for f in agent["findings"] if f["severity"] == "critical")
    warning_n = sum(1 for f in agent["findings"] if f["severity"] == "warning")
    assert f"CRITICAL {critical_n}" in agent["summary"]
    assert f"WARNING {warning_n}" in agent["summary"]
    assert agent["status"] == "critical"  # 有 CRITICAL 即 critical


@envelope_only
def test_envelope_ok_not_in_findings():
    """OK 级占位条目不进 findings"""
    env = build_envelope(_SAMPLE_ANALYSES, "insp-test", "cmd")
    assert not any("正常" in f["title"] and f["severity"] == "info"
                   and "渗压正常" in f["title"] for f in env["agent"]["findings"])
    titles = [f["title"] for f in env["agent"]["findings"]]
    assert all("渗压正常" not in t for t in titles)


@envelope_only
def test_envelope_no_data():
    env = build_envelope([{"category": "水库水情", "status": "无数据", "findings": []}],
                         "insp-test", "cmd")
    assert env["agent"]["status"] == "no_data"
    assert envelope_exit_code(env) == 0  # no_data 但 ok=True 不算 CRITICAL


@envelope_only
def test_envelope_inconclusive():
    """数据质量红档维度 → envelope inconclusive → 退出码 4；CRITICAL 优先级更高"""
    inconclusive_dim = {"category": "渗压监测", "status": "inconclusive",
                        "status_code": "INCONCLUSIVE",
                        "status_note": "数据质量红档: 完整性 60% < 80%", "findings": []}
    ok_dim = {"category": "渗流监测", "findings": [
        {"level": "OK", "message": "渗流正常", "detail": ""}]}
    env = build_envelope([inconclusive_dim, ok_dim], "insp-test", "cmd")
    assert env["agent"]["status"] == "inconclusive"
    assert envelope_exit_code(env) == 4
    assert any("先修数据" in s["label"] for s in env["agent"]["next_steps"])
    # CRITICAL 存在时优先报 critical
    env2 = build_envelope([inconclusive_dim] + _SAMPLE_ANALYSES, "insp-test", "cmd")
    assert env2["agent"]["status"] == "critical"
    assert envelope_exit_code(env2) == 2


@envelope_only
def test_envelope_error():
    err = make_error("DB_CONNECT_FAILED", "Connection refused")
    assert set(err) == {"code", "message", "fix_hint"}
    env = build_envelope([], "insp-test", "cmd", error=err)
    assert env["ok"] is False
    assert env["error"]["code"] == "DB_CONNECT_FAILED"
    assert envelope_exit_code(env) == 3


@envelope_only
def test_envelope_exit_codes():
    env_crit = build_envelope(_SAMPLE_ANALYSES, "r", "c")
    assert envelope_exit_code(env_crit) == 2
    env_ok = build_envelope([{"category": "渗压监测", "findings": [
        {"level": "OK", "message": "正常", "detail": ""}]}], "r", "c")
    assert envelope_exit_code(env_ok) == 0
    env_missing = build_envelope([], "r", "c", error=make_error("TABLE_MISSING", "x"))
    assert envelope_exit_code(env_missing) == 5


@envelope_only
def test_make_error_unknown_code_falls_back():
    err = make_error("NOT_A_CODE", "msg")
    assert err["code"] == "BAD_ARGS"


@envelope_only
def test_run_id_format():
    _os.environ.pop("SKILL_SESSION_ID", None)
    rid = get_run_id()
    assert rid.startswith("insp-")
    assert _os.environ["SKILL_SESSION_ID"] == rid  # 回写 env 保证同进程一致
    assert get_run_id() == rid  # 二次调用复用


# ============================================================
# 自动诊断路由单元测试（Phase 2，无需 DB）
# ============================================================

try:
    import inspection_analyzer as _ia
    HAS_DIAG = hasattr(_ia, "run_auto_diagnosis")
except ImportError:
    HAS_DIAG = False

diag_only = pytest.mark.skipif(not HAS_DIAG, reason="无法导入诊断层") if _HAS_PYTEST else (lambda f: f)


def _fake_route(name, root_cause=None):
    def fn(engine, st_id=None):
        return {"root_cause": root_cause,
                "conclusion": "排除结论", "trace": [f"{name} 已查 -2h/-12h/-3d 均空"]}
    return fn


@diag_only
def test_diag_route_match():
    assert _ia._match_diag_route("渗压监测", "渗压计3: 统计异常 z_score=5.0")[0] == "pressure_outlier"
    assert _ia._match_diag_route("水库水情", "测站1: 水位连续上升")[0] == "water_level_rate"
    assert _ia._match_diag_route("闸门工情", "闸门关闭但有流量")[0] == "gate_closed_flow"
    assert _ia._match_diag_route("白蚁监测", "蚁情高危") is None


@diag_only
def test_diag_root_cause_backfill(monkeypatch):
    """命中根因 → diagnosis_root_cause 标 + detail 证据链；envelope category 升级 root_cause"""
    monkeypatch.setattr(_ia, "DIAG_ROUTES", [
        ("pressure_outlier", lambda c, m: "渗压" in m, _fake_route("R1", "上游水位抬升→渗压响应"))])
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "CRITICAL", "message": "渗压计3: 统计异常", "detail": "z=5.0"}]}]
    n = _ia.run_auto_diagnosis(None, analyses)
    assert n == 1
    f = analyses[0]["findings"][0]
    assert f["diagnosis_root_cause"] == "上游水位抬升→渗压响应"
    assert "证据链" in f["detail"]
    env = build_envelope(analyses, "r", "c")
    assert env["agent"]["findings"][0]["category"] == "root_cause"


@diag_only
def test_diag_no_evidence_trace(monkeypatch):
    """未命中也要把'已查窗口与结果'写入 detail（已检为空 ≠ 忘了检）"""
    monkeypatch.setattr(_ia, "DIAG_ROUTES", [
        ("pressure_outlier", lambda c, m: "渗压" in m, _fake_route("R1"))])
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "CRITICAL", "message": "渗压计3: 统计异常", "detail": ""}]}]
    _ia.run_auto_diagnosis(None, analyses)
    f = analyses[0]["findings"][0]
    assert "diagnosis_root_cause" not in f
    assert "已查" in f["detail"]


@diag_only
def test_diag_chain_limit(monkeypatch):
    """限流：每轮巡检最多 MAX_DIAG_CHAINS=3 条诊断链"""
    monkeypatch.setattr(_ia, "DIAG_ROUTES", [
        ("any", lambda c, m: True, _fake_route("R", "根因"))])
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "CRITICAL", "message": f"渗压计{i}: 异常", "detail": ""} for i in range(5)]}]
    assert _ia.run_auto_diagnosis(None, analyses) == 3


@diag_only
def test_diag_warning_with_route_triggers(monkeypatch):
    """WARNING 命中路由即触发（渗压/水位/闸门只发 WARNING，仅收 CRITICAL 则路由不可达）"""
    monkeypatch.setattr(_ia, "DIAG_ROUTES", [
        ("any", lambda c, m: True, _fake_route("R", "根因"))])
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "WARNING", "message": "渗压计3: 突变5.1kPa", "detail": ""}]}]
    assert _ia.run_auto_diagnosis(None, analyses) == 1
    assert analyses[0]["findings"][0]["diagnosis_root_cause"] == "根因"


@diag_only
def test_diag_skips_info_and_ok(monkeypatch):
    monkeypatch.setattr(_ia, "DIAG_ROUTES", [
        ("any", lambda c, m: True, _fake_route("R", "根因"))])
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "INFO", "message": "渗压计3: 缓慢变化", "detail": ""},
        {"level": "OK", "message": "渗压正常", "detail": ""}]}]
    assert _ia.run_auto_diagnosis(None, analyses) == 0
    assert all("diagnosis_root_cause" not in f for f in analyses[0]["findings"])


@diag_only
def test_diag_critical_takes_quota_priority(monkeypatch):
    """CRITICAL 优先占 MAX_DIAG_CHAINS 配额，WARNING 排后"""
    monkeypatch.setattr(_ia, "DIAG_ROUTES", [
        ("any", lambda c, m: True, _fake_route("R", "根因"))])
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "WARNING", "message": "渗压计1: 轻微异常", "detail": ""},
        {"level": "WARNING", "message": "渗压计2: 轻微异常", "detail": ""},
        {"level": "CRITICAL", "message": "渗压计7: 严重异常", "detail": ""},
        {"level": "CRITICAL", "message": "渗压计8: 严重异常", "detail": ""},
        {"level": "CRITICAL", "message": "渗压计9: 严重异常", "detail": ""}]}]
    assert _ia.run_auto_diagnosis(None, analyses) == 3
    fs = analyses[0]["findings"]
    assert all("diagnosis_root_cause" in f for f in fs if f["level"] == "CRITICAL")
    assert all("diagnosis_root_cause" not in f for f in fs if f["level"] == "WARNING")


# ============================================================
# 三分通道 + 护栏单元测试（Phase 4.9，无需 DB）
# ============================================================

has_4_9 = (_HAS_PYTEST and HAS_DIAG
           and hasattr(_ia, "classify_timeseries") and hasattr(_ia, "_is_idle")
           and hasattr(_ia, "_change_finding"))
unit4_9_only = pytest.mark.skipif(not has_4_9, reason="缺 Phase 4.9 构件") if _HAS_PYTEST else (lambda f: f)


@unit4_9_only
def test_classify_spike():
    """尖峰：窗口峰值离群但 latest 已回落 → spike"""
    series = [10.0] * 5 + [50.0] + [10.0] * 6  # 中间一个尖峰，末点=10 已回落
    assert _ia.classify_timeseries(series)["pattern"] == "spike"


@unit4_9_only
def test_classify_step():
    """台阶：前后半段水平位移（不平衡分布使 z 差放大）→ step"""
    series = [10.0] * 9 + [100.0] * 3  # 末点=100 未回落 → 非 spike；后半中位数远抬 → step
    assert _ia.classify_timeseries(series)["pattern"] == "step"


@unit4_9_only
def test_classify_drift():
    """缓变：单向持续（同号差分占比>0.8）→ drift"""
    series = [float(i) for i in range(12)]  # 严格递增
    assert _ia.classify_timeseries(series)["pattern"] == "drift"


@unit4_9_only
def test_classify_too_short_returns_none():
    assert _ia.classify_timeseries([1.0, 2.0, 3.0])["pattern"] == "none"


@unit4_9_only
def test_is_idle_flat_line():
    """死值平线（CV 极低）→ True"""
    assert _ia._is_idle([100.0, 100.0, 100.0, 100.001]) is True


@unit4_9_only
def test_is_idle_active_series():
    """有波动序列 → False"""
    assert _ia._is_idle([10.0, 20.0, 30.0, 40.0]) is False


@unit4_9_only
def test_is_idle_short_or_zero_mean():
    """len<2 或均值≈0（CV 无相对意义）→ False，交回原判定"""
    assert _ia._is_idle([5.0]) is False
    assert _ia._is_idle([0.0, 0.0, 0.0]) is False


@unit4_9_only
def test_is_idle_parametrized_threshold():
    """可注入 idle_cv_min（参数化测试用）"""
    assert _ia._is_idle([100.0, 100.0, 100.5], idle_cv_min=0.01) is True
    assert _ia._is_idle([100.0, 100.0, 100.5], idle_cv_min=0.0001) is False


@unit4_9_only
def test_change_finding_spike_downgrades_to_info():
    """spike → INFO（不触发诊断）+ 带 pattern 字段"""
    series = [10.0] * 5 + [50.0] + [10.0] * 6
    f = _ia._change_finding(series, 10.0, 50.0, st_id=1, unit="kPa", dim_label="渗压计")
    assert f["level"] == "INFO"
    assert f["pattern"] == "spike"


@unit4_9_only
def test_change_finding_drift_stays_warning():
    """drift → WARNING（疑渐进性物理过程）+ pattern=drift"""
    series = [float(i) for i in range(12)]
    f = _ia._change_finding(series, 10.0, 11.0, st_id=2, unit="m", dim_label="闸门站")
    assert f["level"] == "WARNING"
    assert f["pattern"] == "drift"


@diag_only
def test_diag_skips_spike_pattern(monkeypatch):
    """三分通道分流（Phase 4.9）：pattern=spike 不进诊断候选（防御性，即使标 WARNING）"""
    monkeypatch.setattr(_ia, "DIAG_ROUTES", [("any", lambda c, m: True, _fake_route("R", "根因"))])
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "WARNING", "pattern": "spike", "message": "渗压计3: 突变", "detail": ""},
        {"level": "WARNING", "pattern": "drift", "message": "渗压计4: 上升", "detail": ""}]}]
    assert _ia.run_auto_diagnosis(None, analyses) == 1  # 仅 drift 触发，spike 被跳过
    assert "diagnosis_root_cause" not in analyses[0]["findings"][0]  # spike 未诊断
    assert analyses[0]["findings"][1]["diagnosis_root_cause"] == "根因"


@unit4_9_only
def test_envelope_passes_pattern_through():
    """envelope 透传 pattern（仅 change-rate 类 finding）"""
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "WARNING", "pattern": "step", "message": "渗压计3: 突变", "detail": ""},
        {"level": "WARNING", "message": "测站4: 无pattern字段", "detail": ""}]}]
    env = build_envelope(analyses, "r", "c")
    fs = env["agent"]["findings"]
    assert fs[0].get("pattern") == "step"
    assert "pattern" not in fs[1]  # 无 pattern 的 finding 不强加该键


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