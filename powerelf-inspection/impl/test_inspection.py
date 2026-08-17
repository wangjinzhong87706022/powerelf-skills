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
# P0：--db 缺省解析 + envelope artifacts（无需 DB）
# ============================================================

def test_resolve_db_url_passthrough():
    """--db 显式给出时原样返回，不走环境解析"""
    from inspection_analyzer import _resolve_db_url
    url = "mysql+pymysql://user:pw@127.0.0.1:3306/powerelf_srm_yml"
    assert _resolve_db_url(url) == url


def test_resolve_db_url_from_env(monkeypatch):
    """--db 缺省时经 _shared/lib/db.py 从环境变量解析（hermes 启动即加载 ~/.hermes/.env）"""
    from inspection_analyzer import _resolve_db_url
    monkeypatch.setenv("POWERELF_DB_HOST", "10.0.0.9")
    monkeypatch.setenv("POWERELF_DB_PORT", "3307")
    monkeypatch.setenv("POWERELF_DB_NAME", "powerelf_test_db")
    for var in ("SRM_DB_HOST", "SRM_DB_PORT", "SRM_DB_NAME"):
        monkeypatch.delenv(var, raising=False)
    url = _resolve_db_url(None)
    assert "10.0.0.9:3307" in url
    assert "powerelf_test_db" in url


def test_resolve_db_url_unresolvable(monkeypatch):
    """环境残缺且共享层抛错时，向上抛异常（main 层转 DB_URL_UNRESOLVED envelope）"""
    import importlib
    import inspection_analyzer as ia
    from inspection_analyzer import _resolve_db_url

    def _boom():
        raise RuntimeError("no db config anywhere")

    real = getattr(ia, "_shared_sqlalchemy_url", None)
    ia._shared_sqlalchemy_url = _boom
    try:
        with pytest.raises(Exception):
            _resolve_db_url(None)
    finally:
        if real is not None:
            ia._shared_sqlalchemy_url = real
        else:
            del ia._shared_sqlalchemy_url
    importlib.reload(ia)  # 恢复模块干净状态


@envelope_only
def test_envelope_carries_artifacts():
    """envelope 携带 artifacts（report_md + charts 绝对路径），--json 不再丢失报告产物"""
    art = {"report_md": "/tmp/powerelf-inspection/report_insp-x.md",
           "charts": ["/tmp/powerelf-inspection/reports/trend_st_rsvr_r.png"]}
    env = build_envelope(_SAMPLE_ANALYSES, "insp-test", "cmd", days=7, artifacts=art)
    assert env["artifacts"] == art
    # 未提供时不造空字段
    env2 = build_envelope(_SAMPLE_ANALYSES, "insp-test", "cmd", days=7)
    assert "artifacts" not in env2


def test_write_report_artifacts(tmp_path):
    """报告无条件落盘到 <skill>/report_<run_id>.md，并收集 reports/ 下本轮图表"""
    from inspection_analyzer import _write_report_artifacts
    (tmp_path / "reports").mkdir()
    chart = tmp_path / "reports" / "trend_st_rsvr_r.png"
    chart.write_bytes(b"\x89PNG fake")

    art = _write_report_artifacts("# 巡检报告\n正文", "insp-test", skill_root=str(tmp_path))

    assert art is not None
    report_path = tmp_path / "report_insp-test.md"
    assert report_path.exists()
    assert report_path.read_text(encoding="utf-8").startswith("# 巡检报告")
    assert art["report_md"] == str(report_path)
    assert str(chart) in art["charts"]


# ============================================================
# P1：设备清单 / 雨量去重 / 同站关联 / CSV 导出（无需 DB）
# ============================================================

def _equip_rows(n_offline_by_cat=None, abnormal=None, online=70):
    """构造 eq_equip_base 形状的行；n_offline_by_cat={"渗压计":3,...}"""
    rows, i = [], 0
    for cat, n in (n_offline_by_cat or {}).items():
        for _ in range(n):
            rows.append({"id": i, "name": f"E{i:03d}", "code": f"C{i:03d}",
                         "status": 0, "category": cat})
            i += 1
    for code, name in (abnormal or []):
        rows.append({"id": i, "name": name, "code": code, "status": 2, "category": "传感器"})
        i += 1
    for _ in range(online):
        rows.append({"id": i, "name": f"E{i:03d}", "code": f"C{i:03d}",
                     "status": 1, "category": "传感器"})
        i += 1
    return rows


def test_equip_offline_detail_lists_critical_types(monkeypatch):
    """F009：离线率 WARNING 的 detail 必须列出关键类型离线清单（渗压/水位优先+编码+总数）"""
    import pandas as pd
    rows = _equip_rows(n_offline_by_cat={"渗压计": 3, "水位": 2, "视频": 36}, online=63)
    monkeypatch.setattr(_ia, "read_equipment", lambda eng: pd.DataFrame(rows))
    result = _ia.analyze_equipment(None)
    off = [f for f in result["findings"] if "离线率" in f["message"]]
    assert len(off) == 1
    detail = off[0]["detail"]
    assert "渗压计" in detail and "3台" in detail, f"渗压计清单缺失: {detail}"
    assert "水位" in detail and "2台" in detail
    assert "C000" in detail  # 具体编码可定位
    assert "视频" in detail and "共41台" in detail  # 类型未截断时总数兜底
    # 关键类型排在非关键类型前
    assert detail.index("渗压计") < detail.index("视频")


def test_equip_offline_detail_truncates_many_types(monkeypatch):
    """离线类型超过上限时截断展示但保留总数"""
    import pandas as pd
    rows = _equip_rows(n_offline_by_cat={"渗压计": 2, "视频": 10, "通信": 10, "电源": 10, "广播": 10},
                       online=58)
    monkeypatch.setattr(_ia, "read_equipment", lambda eng: pd.DataFrame(rows))
    result = _ia.analyze_equipment(None)
    off = [f for f in result["findings"] if "离线率" in f["message"]]
    assert len(off) == 1
    detail = off[0]["detail"]
    assert "渗压计2台" in detail          # 关键类型永远展示
    assert "…" in detail and "等42台" in detail  # 截断 + 总数兜底
    # 5 类离线只展示 4 类：至少一个非关键类型被截断（用"类型N台"模式匹配，避开前缀文案干扰）
    import re as _re
    shown = sum(1 for t in ("视频", "通信", "电源", "广播") if _re.search(rf"{t}\d+台", detail))
    assert shown == 3, f"应截断1个非关键类型，实际展示{shown}个: {detail}"


def test_equip_offline_classifies_by_name_keyword(monkeypatch):
    """真库 category 是数字码（"0"）：类型应从设备名关键词提取，防 '054台' 歧义拼接"""
    import pandas as pd
    rows = []
    for i, nm in enumerate(["振弦渗压计E01", "振弦渗压计E02", "振弦渗压计E03",
                            "西坝咀雨量计", "E900"]):
        rows.append({"id": i, "name": nm, "code": f"C{i:03d}", "status": 0, "category": "0"})
    for i in range(10):
        rows.append({"id": 100 + i, "name": f"E{i:03d}", "code": f"X{i:03d}",
                     "status": 1, "category": "0"})
    monkeypatch.setattr(_ia, "read_equipment", lambda eng: pd.DataFrame(rows))
    result = _ia.analyze_equipment(None)
    off = [f for f in result["findings"] if "离线率" in f["message"]][0]
    detail = off["detail"]
    assert "渗压计3台" in detail and "C000" in detail   # 名称关键词分类
    assert "雨量计1台" in detail
    assert "054台" not in detail                        # 数字码不再与台数粘连
    assert "类型0" in detail                            # 无关键词者退回 category 数字码
    assert detail.index("渗压计") < detail.index("类型0")  # 关键类型排前


def test_rain_station_id_renders_int(monkeypatch):
    """st_pptn_r.st_id 为 float(85.0) 时 title 必须渲染 '测站85' 而非 '测站85.0'"""
    monkeypatch.setattr(_ia, "read_sensor_data",
                        lambda eng, table, cols, days: _rain_df(35, st_id=85.0))
    findings = _ia.analyze_rainfall(None, days=7)["findings"]
    rain = [f for f in findings if "雨量" in f["message"]]
    assert len(rain) == 1
    assert "测站85:" in rain[0]["message"]
    assert "85.0" not in rain[0]["message"]


def test_equip_abnormal_detail_lists_devices(monkeypatch):
    """F010：异常设备 WARNING 的 detail 必须列出设备编码+名称（可定位到台）"""
    import pandas as pd
    rows = _equip_rows(abnormal=[("C099", "GNSS测站99"), ("C100", "渗压计100")], online=98)
    monkeypatch.setattr(_ia, "read_equipment", lambda eng: pd.DataFrame(rows))
    result = _ia.analyze_equipment(None)
    abn = [f for f in result["findings"] if "异常状态" in f["message"]]
    assert len(abn) == 1
    detail = abn[0]["detail"]
    assert "C099" in detail and "GNSS测站99" in detail
    assert "C100" in detail and "渗压计100" in detail


def _rain_df(max_p, st_id=85):
    import pandas as pd
    return pd.DataFrame([
        {"st_id": st_id, "p": 0.0, "dr": 1.0, "dyp": 0.0, "tm": "2026-08-15 08:00"},
        {"st_id": st_id, "p": float(max_p), "dr": 1.0, "dyp": float(max_p), "tm": "2026-08-15 12:00"},
        {"st_id": st_id, "p": 0.0, "dr": 1.0, "dyp": float(max_p), "tm": "2026-08-15 13:00"},
    ])


def test_rain_blue_band_single_warning(monkeypatch):
    """F001/F002 去重：30-50mm 蓝色带同一事件只出 1 条 WARNING（不再 INFO+WARNING 双报）"""
    monkeypatch.setattr(_ia, "read_sensor_data", lambda eng, table, cols, days: _rain_df(35))
    findings = _ia.analyze_rainfall(None, days=7)["findings"]
    rain = [f for f in findings if "雨量" in f["message"]]
    assert len(rain) == 1, f"蓝色带应只有1条，实际: {rain}"
    assert rain[0]["level"] == "WARNING"
    assert "蓝色" in rain[0]["message"] or "蓝色" in rain[0]["detail"]


def test_rain_yellow_band_no_duplicate(monkeypatch):
    """分级已表达严重度（黄色 WARNING）时不再追加硬编码'短时强降雨'重复条目"""
    monkeypatch.setattr(_ia, "read_sensor_data", lambda eng, table, cols, days: _rain_df(60))
    findings = _ia.analyze_rainfall(None, days=7)["findings"]
    rain = [f for f in findings if "雨量" in f["message"]]
    assert len(rain) == 1, f"黄色带应只有1条，实际: {rain}"
    assert rain[0]["level"] == "WARNING" and "黄色" in rain[0]["message"]


def test_rain_red_critical_single(monkeypatch):
    """红色 CRITICAL 单条，不叠加强降雨 WARNING"""
    monkeypatch.setattr(_ia, "read_sensor_data", lambda eng, table, cols, days: _rain_df(120))
    findings = _ia.analyze_rainfall(None, days=7)["findings"]
    rain = [f for f in findings if "雨量" in f["message"]]
    assert len(rain) == 1 and rain[0]["level"] == "CRITICAL" and "红色" in rain[0]["message"]


@envelope_only
def test_envelope_correlates_same_station():
    """F003/F004 聚合：同维度同测站的多条 findings 互填 correlated_with"""
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "WARNING", "message": "渗压计93: 突变17.08kPa", "detail": ""},
        {"level": "WARNING", "message": "渗压计93: 统计异常 z_score=57.6", "detail": ""},
        {"level": "WARNING", "message": "渗压计94: 突变3.00kPa", "detail": ""},
    ]}]
    env = build_envelope(analyses, "insp-t", "cmd", days=7)
    fs = env["agent"]["findings"]
    assert fs[0]["correlated_with"] == [fs[1]["id"]] and fs[1]["correlated_with"] == [fs[0]["id"]]
    assert fs[2]["correlated_with"] == []  # 不同测站不关联


@envelope_only
def test_export_findings_csv(tmp_path):
    """内置 CSV 导出：UTF-8 BOM、表头含复核结论空列、行数=findings、测站列提取"""
    from inspection_analyzer import export_findings_csv
    analyses = [{"category": "渗压监测", "findings": [
        {"level": "WARNING", "message": "渗压计93: 突变17.08kPa", "detail": "d1"},
        {"level": "INFO", "message": "测站85: 单时段最大雨量35.0mm", "detail": "d2"},
    ]}]
    env = build_envelope(analyses, "insp-t", "cmd", days=7)
    p = tmp_path / "findings.csv"
    out = export_findings_csv(env, str(p))
    assert out == str(p) and p.exists()
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # Excel 友好
    text = raw.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0].startswith("编号,严重程度,监测维度")
    assert lines[0].endswith("测站,复核结论")
    assert len(lines) == 3  # 表头 + 2 findings
    assert "渗压监测" in lines[1] and ",93," in lines[1]
    assert ",85," in lines[2]  # 测站85 提取
    assert lines[1].endswith(",")  # 复核结论空列


# ============================================================
# P2：SMART 行动建议 / verify_output 报告章节闸 / 绝对路径（无需 DB）
# ============================================================

@envelope_only
def test_envelope_next_steps_smart():
    """P2-1：next_steps 每条带 owner/deadline/acceptance（SMART：责任方/时限/验收）"""
    env = build_envelope(_SAMPLE_ANALYSES, "insp-t", "cmd", days=7)  # 含 critical+warning
    steps = env["agent"]["next_steps"]
    assert steps, "有 CRITICAL/WARNING 必有 next_steps"
    for s in steps:
        for k in ("owner", "deadline", "acceptance"):
            assert s.get(k), f"next_step[{s.get('label')}] 缺 SMART 字段 {k}: {s}"
    crit = next(s for s in steps if s["label"] == "现场核查")
    assert "2小时" in crit["deadline"] or "2 小时" in crit["deadline"]


def test_smart_recommendations_table():
    """P2-1：报告巡检建议 SMART 表（责任方/时限/验收列），CRITICAL→2小时紧急"""
    from inspection_analyzer import smart_recommendations
    md = smart_recommendations(critical=1, warnings=2)
    for kw in ("责任方", "时限", "验收"):
        assert kw in md, f"建议表缺 {kw} 列"
    assert "2小时" in md or "2 小时" in md
    assert "本周" in md  # WARNING 时限
    md_calm = smart_recommendations(critical=0, warnings=0)
    assert "常规" in md_calm and "责任方" in md_calm


def test_verify_report_artifacts_sections(tmp_path):
    """P2-2：verify_output 校验报告四章节齐全 + 图表文件存在 + 至少一张图嵌入"""
    import verify_output as vo
    good = tmp_path / "report_good.md"
    good.write_text(
        "# 智能巡检报告\n## 巡检图表\n![趋势](reports/a.png)\n"
        "## 设备状态（三口径分层）\n| 当前快照 |\n## Data Notes\nx\n"
        "## 附录：数据覆盖清单（近7天各表行数）\n| 表 |\n", encoding="utf-8")
    chart = tmp_path / "a.png"
    chart.write_bytes(b"\x89PNG fake")
    env = {"agent": {"findings": []},
           "artifacts": {"report_md": str(good), "charts": [str(chart)]}}
    problems = []
    vo.check_report_artifacts(env, problems)
    assert problems == [], f"章节齐全不应报错: {problems}"

    bad = tmp_path / "report_bad.md"
    bad.write_text("# 智能巡检报告\n只有正文，章节缺失", encoding="utf-8")
    env_bad = {"agent": {"findings": []},
               "artifacts": {"report_md": str(bad),
                             "charts": [str(tmp_path / "missing.png")]}}
    problems2 = []
    vo.check_report_artifacts(env_bad, problems2)
    assert any("巡检图表" in p for p in problems2)
    assert any("三口径" in p for p in problems2)
    assert any("覆盖清单" in p for p in problems2)
    assert any("missing.png" in p for p in problems2)
    # 无 artifacts 的 envelope 不报错（向后兼容）
    problems3 = []
    vo.check_report_artifacts({"agent": {"findings": []}}, problems3)
    assert problems3 == []


def test_write_report_artifacts_absolute(tmp_path):
    """P2-3：artifacts 产物路径必须是绝对路径（agent 直接引用，无需拼接）"""
    from inspection_analyzer import _write_report_artifacts
    import os
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "t.png").write_bytes(b"\x89PNG")
    art = _write_report_artifacts("# r", "insp-t", skill_root=str(tmp_path))
    assert os.path.isabs(art["report_md"])
    assert art["charts"] and all(os.path.isabs(p) for p in art["charts"])


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
# 设备状态边界测试（Phase 5，无需 DB）
# ============================================================

equip_only = pytest.mark.skipif(not (HAS_ANALYZER and HAS_ENVELOPE),
                                reason="无法导入 analyzer/envelope 层")


@equip_only
def test_equip_offline_rate_boundary_exact_30pct(monkeypatch):
    """边界：100台设备，30台离线(status=0)，离线率恰30% → 不触发 > 0.3 的WARNING"""
    import pandas as pd
    # 30台 status=0(离线), 70台 status=1(在线), 0台 status=2(异常)
    rows = []
    for i in range(30):
        rows.append({"id": i, "name": f"E{i:03d}", "code": f"C{i:03d}", "status": 0, "category": "传感器"})
    for i in range(70):
        rows.append({"id": 30 + i, "name": f"E{30+i:03d}", "code": f"C{30+i:03d}", "status": 1, "category": "传感器"})
    monkeypatch.setattr(_ia, "read_equipment", lambda eng: pd.DataFrame(rows))

    result = _ia.analyze_equipment(None)
    findings = result["findings"]

    # 离线率 == 0.3 不触发 > 0.3 的 WARNING
    offline_warnings = [f for f in findings if "离线率" in f["message"]]
    assert len(offline_warnings) == 0, f"离线率恰 30% 不应触发 WARNING, 实际: {offline_warnings}"

    # abnormal == 0 不触发异常设备分支
    abnormal_warnings = [f for f in findings if "异常状态" in f["message"]]
    assert len(abnormal_warnings) == 0, "0台异常不应触发 WARNING"

    # 应返回 OK 级 finding
    assert any(f["level"] == "OK" for f in findings), "无异常时应返回 OK 级 finding"
    assert result["stats"]["total"] == 100
    assert result["stats"]["offline"] == 30
    assert result["stats"]["abnormal"] == 0


@equip_only
def test_equip_offline_rate_over_30pct(monkeypatch):
    """离线率 > 30% → 触发 WARNING"""
    import pandas as pd
    rows = []
    for i in range(31):
        rows.append({"id": i, "name": f"E{i:03d}", "code": f"C{i:03d}", "status": 0, "category": "传感器"})
    for i in range(69):
        rows.append({"id": 31 + i, "name": f"E{31+i:03d}", "code": f"C{31+i:03d}", "status": 1, "category": "传感器"})
    monkeypatch.setattr(_ia, "read_equipment", lambda eng: pd.DataFrame(rows))

    result = _ia.analyze_equipment(None)
    findings = result["findings"]

    offline_warnings = [f for f in findings if "离线率" in f["message"]]
    assert len(offline_warnings) == 1, "离线率 31% 应触发 WARNING"
    assert offline_warnings[0]["level"] == "WARNING"


@equip_only
def test_equip_abnormal_any_triggers_warning(monkeypatch):
    """0台离线，但1台异常(status=2) → 触发异常设备 WARNING"""
    import pandas as pd
    rows = []
    for i in range(99):
        rows.append({"id": i, "name": f"E{i:03d}", "code": f"C{i:03d}", "status": 1, "category": "传感器"})
    rows.append({"id": 99, "name": "E099", "code": "C099", "status": 2, "category": "传感器"})
    monkeypatch.setattr(_ia, "read_equipment", lambda eng: pd.DataFrame(rows))

    result = _ia.analyze_equipment(None)
    findings = result["findings"]

    abnormal_warnings = [f for f in findings if "异常状态" in f["message"]]
    assert len(abnormal_warnings) == 1, "1台异常应触发 WARNING"
    assert abnormal_warnings[0]["level"] == "WARNING"


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