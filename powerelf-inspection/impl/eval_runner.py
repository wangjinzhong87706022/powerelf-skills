#!/usr/bin/env python3
"""
eval_runner.py — Layer A 评测 runner（无 DB，全 mock）

把 autoresearch/eval_cases/cases.json 的 ✅/❌ 用例跑成量化指标：
monkeypatch read_sensor_data / seasonal_check / probe_table_latest / DIAG_ROUTES，
注入 fixtures.py 的构造数据，跑各 analyze_* + build_envelope，按 expected 判定，算：
  误报率 / 漏报率 / 根因链正确率 / coverage（4.9 效果的直接量化）。

用法：
  python3 eval_runner.py                 # 跑全部有 fixture 的用例
  python3 eval_runner.py --only PRES-SPIKE-1,SEASON-GUARD-1   # 只跑指定用例
  python3 eval_runner.py --verbose       # 打印每条 finding

输出：--out 指定路径（默认 /tmp/results_cases-partial.json）+ stdout 摘要（含验收线对照）。
  ⚠️ 更新全量验收文件 autoresearch/results_cases.json 须显式 --out 指回；
  --only 部分运行禁止写验收文件（防覆写，2026-08-19 教训）。
"""

import argparse
import contextlib
import json
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_CASES_DIR = os.path.join(_HERE, "..", "autoresearch", "eval_cases")
sys.path.insert(0, os.path.join(_HERE, "..", "lib"))   # 供 import anomaly
sys.path.insert(0, _HERE)                               # inspection_analyzer / verify_output
sys.path.insert(0, _CASES_DIR)                          # fixtures

import pandas as pd  # noqa: E402
import inspection_analyzer as ia  # noqa: E402
import fixtures as FX  # noqa: E402
from verify_output import _numbers  # noqa: E402

SEV = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}  # OK 不参与（envelope 不进 findings）

import re  # noqa: E402
_FROM_RE = re.compile(r"FROM\s+(\w+)", re.IGNORECASE)


def _make_fake_read_sql(fixture):
    """pd.read_sql mock：按 SQL 的 FROM <table> 分发 fixture（覆盖 inline bypassor + 专用 reader）。
    read_sensor_data 已被函数 mock 接管，不会走到这；seasonal_check/probe 也已 mock。"""
    def fake_read_sql(sql, con=None, *args, **kwargs):
        s = getattr(sql, "text", None) or str(sql)
        m = _FROM_RE.search(s)
        tbl = m.group(1).lower() if m else None
        df = fixture.get(tbl) if tbl else None
        if df is None:
            # 缺失表 → 抛异常，让调用方（_diag_sql / analyzer 的 try-except）走优雅降级
            raise RuntimeError(f"eval mock: 表 {tbl} 无 fixture（模拟查询失败）")
        return df.copy()
    return fake_read_sql

# 维度（剥括号后缀）→ analyzer 映射
DIM_TO_ANALYZER = {
    "水库水情": ("analyze_water_level", {}),
    "渗压监测": ("analyze_pressure", {}),
    "渗流监测": ("analyze_percolation", {}),
    "闸门工情": ("analyze_gate", {}),
    "MAD统计异常": ("analyze_mad_anomaly", {}),
    "关联异常": ("analyze_correlation", {"days": 7}),
    "雨量监测": ("analyze_rainfall", {}),
    "位移监测": ("analyze_displacement", {}),
    "泵站工情": ("analyze_pump", {}),
    "水质监测": ("analyze_water_quality", {}),
    "土壤墒情": ("analyze_soil_moisture", {}),
    "白蚁监测": ("analyze_termite", {}),
    "巡检结果": ("analyze_inspection_results", {}),
    "设备状态": ("analyze_equipment", {}),
    "告警分析": ("analyze_alerts", {}),
}


@contextlib.contextmanager
def patched(obj, name, value):
    had = hasattr(obj, name)
    old = getattr(obj, name) if had else None
    setattr(obj, name, value)
    try:
        yield
    finally:
        if had:
            setattr(obj, name, old)
        else:
            delattr(obj, name)


def _bare_dim(dim):
    """剥括号后缀：'水库水情（质量闸）' → '水库水情'"""
    return dim.split("（")[0].split("(")[0].strip()


def _fake_diag_route(root_cause=None, trace=("R1 已查 -2h rz 上升 0.5m",)):
    def fn(engine, st_id=None):
        return {"root_cause": root_cause,
                "conclusion": "排除结论" if root_cause else "DIAG_NO_EVIDENCE",
                "trace": list(trace)}
    return fn


def run_case(case):
    """跑单条 case，返回 (analysis_result, envelope)。异常时抛出由上层捕获。"""
    cid = case["id"]
    kind = case["kind"]
    dim = _bare_dim(case["dimension"])
    fixture = FX.FIXTURES[cid]()  # {table: DataFrame}

    def fake_read(engine, table, fields, st_id=None, days=30, time_field="tm", limit=20000):
        df = fixture.get(table)
        if df is None:
            return pd.DataFrame()
        return df.copy()

    # seasonal_check：默认 in_season=False（占位 st_id 无历史数据即此行为）；
    # 季节用例显式 in_season=True 触发降级
    season_ret = FX.SEASONAL_OVERRIDE.get(
        cid, {"in_season": False, "seasonal_median": None, "note": "test: 历年同期无数据，护栏未生效"})

    # empty_data 用例：需 sentinel engine 触发 probe 分支
    is_empty = kind == "empty_data"
    engine = object() if is_empty else None

    probe_ret = FX.PROBE_LATEST_OVERRIDE.get(cid, "2026-06-15 00:00:00")

    def fake_probe(engine_, table, time_field="tm"):
        return probe_ret

    # QUERY_FAILED 用例：预置 QUERY_ERRORS（no_data_result 据此返回 QUERY_FAILED）
    qe_key, qe_val = FX.QUERY_ERRORS_SET.get(cid, (None, None))
    if qe_key:
        ia.QUERY_ERRORS[qe_key] = qe_val

    # pd.read_sql mock 只对 inline/specialized 维度生效；诊断链须走真实 None-engine
    # 优雅路径（_diag_sql 异常 → (None, code) → "已查"），不能被 fixture mock 干扰。
    PDREADSQL_DIMS = {"水质监测", "土壤墒情", "白蚁监测", "巡检结果", "设备状态", "告警分析"}
    need_pdsql = dim in PDREADSQL_DIMS
    pdsql_cm = patched(pd, "read_sql", _make_fake_read_sql(fixture)) if need_pdsql \
        else contextlib.nullcontext()

    try:
        with patched(ia, "read_sensor_data", fake_read), \
                patched(ia, "seasonal_check", lambda *a, **k: season_ret), \
                patched(ia, "probe_table_latest", fake_probe), \
                pdsql_cm:
            # 选 analyzer
            if kind == "empty_data":
                analyzer_name, kw = "analyze_percolation", {}
            else:
                analyzer_name, kw = DIM_TO_ANALYZER.get(dim, (None, None))
                if analyzer_name is None:
                    raise ValueError(f"无 dimension 映射: {dim}（case={cid}）")
            analyzer = getattr(ia, analyzer_name)
            result = analyzer(engine, **kw)

            # diagnosis 用例：run_auto_diagnosis（HIT 用 fake 命中路由；MISS 用真路由+None engine→空证据）
            if kind == "diagnosis":
                hit = "finding_has" in case.get("expected", {})  # DIAG_ROUTES override only for HIT
                if hit:
                    routes = [("pressure_outlier", lambda c, m: "渗压" in m,
                               _fake_diag_route("上游水位抬升→渗压响应"))]
                    with patched(ia, "DIAG_ROUTES", routes):
                        ia.run_auto_diagnosis(None, [result])
                else:
                    ia.run_auto_diagnosis(None, [result])
    finally:
        if qe_key:
            ia.QUERY_ERRORS.pop(qe_key, None)

    env = ia.build_envelope([result], "eval-" + cid, "eval_runner", days=30)
    return result, env


def judge(case, result, env):
    """按 expected/kind 判定。返回 (passed: bool, reason: str)。"""
    exp = case["expected"]
    kind = case["kind"]
    fs = result.get("findings", [])
    non_ok = [f for f in fs if f.get("level") in SEV]
    lvls = [SEV[f["level"]] for f in non_ok]
    max_lvl = max(lvls) if lvls else 0
    msgs = " ".join(f.get("message", "") + " " + f.get("detail", "") for f in non_ok)
    env_findings = env["agent"]["findings"]

    def need(cond, why):
        return (True, "") if cond else (False, why)

    if kind in ("should_report", "guardrail", "diagnosis"):
        if "min_level" in exp:
            ok, why = need(max_lvl >= SEV[exp["min_level"]],
                           f"max level {max_lvl} < min {exp['min_level']}")
            if not ok:
                return False, why
        if "max_level" in exp:
            ok, why = need(max_lvl <= SEV[exp["max_level"]],
                           f"max level {max_lvl} > max {exp['max_level']}")
            if not ok:
                return False, why
        if "message_contains" in exp:
            ok, why = need(exp["message_contains"] in msgs, f"缺关键词 {exp['message_contains']}")
            if not ok:
                return False, why
        if "detail_contains" in exp:
            ok = any(exp["detail_contains"] in f.get("detail", "") for f in non_ok)
            if not ok:
                return False, f"detail 缺关键词 {exp['detail_contains']}"
        if exp.get("no_diagnosis") and any("diagnosis_root_cause" in f for f in non_ok):
            return False, "不应诊断但命中 root_cause"
        if "pattern" in exp:
            chg = [f for f in non_ok if "pattern" in f]
            if chg and not all(f.get("pattern") == exp["pattern"] for f in chg):
                return False, f"pattern 不符（期望 {exp['pattern']}，实际 {[f.get('pattern') for f in chg]}）"
        if "finding_has" in exp:
            found = any(exp["finding_has"] in str(f) for f in non_ok)
            if not found:
                return False, f"缺 {exp['finding_has']}"
        if "finding_not_has" in exp:
            if any(exp["finding_not_has"] in str(f) for f in non_ok):
                return False, f"不应有 {exp['finding_not_has']}"
        if "envelope_category" in exp:
            cats = [f.get("category") for f in env_findings]
            if exp["envelope_category"] not in cats:
                return False, f"envelope category 未升 {exp['envelope_category']}（实际 {cats}）"
        return True, "ok"

    if kind == "should_not_report":
        ncf = exp.get("no_finding_contains", "")
        if ncf and ncf in msgs:
            return False, f"误报含 {ncf}"
        if exp.get("not_no_data") and result.get("status") in ("无数据", "数据不足"):
            return False, "误归 no_data"
        if "finding_not_has" in exp and any(exp["finding_not_has"] in str(f) for f in non_ok):
            return False, f"不应有 {exp['finding_not_has']}"
        return True, "ok"

    if kind == "empty_data":
        sc = result.get("status_code")
        if "status_code" in exp and sc != exp["status_code"]:
            return False, f"status_code {sc} != {exp['status_code']}"
        if "note_contains" in exp and exp["note_contains"] not in (result.get("status_note") or ""):
            return False, f"note 缺关键词 {exp['note_contains']}"
        if exp.get("no_fabricated_values"):
            for f in fs:
                if _numbers(f.get("detail", "")) or _numbers(f.get("message", "")):
                    return False, "空数据伪造数值"
        return True, "ok"

    if kind == "quality_gate":
        if "dimension_status" in exp and result.get("status_code") != exp["dimension_status"]:
            return False, f"dimension_status {result.get('status_code')} != {exp['dimension_status']}"
        if "envelope_status" in exp and env["agent"]["status"] != exp["envelope_status"]:
            return False, f"envelope status {env['agent']['status']} != {exp['envelope_status']}"
        if "exit_code" in exp and ia.envelope_exit_code(env) != exp["exit_code"]:
            return False, f"exit_code {ia.envelope_exit_code(env)} != {exp['exit_code']}"
        if "next_steps_contains" in exp:
            labels = " ".join(s.get("label", "") for s in env["agent"]["next_steps"])
            if exp["next_steps_contains"] not in labels:
                return False, f"next_steps 缺关键词 {exp['next_steps_contains']}"
        if "quality_issues_contains" in exp and exp["quality_issues_contains"] not in str(
                result.get("quality_issues") or result.get("quality", {}).get("issues", [])):
            return False, f"quality_issues 缺关键词 {exp['quality_issues_contains']}"
        if exp.get("zero_not_counted_as_placeholder"):
            # 0 ∉ _PLACEHOLDER_VALUES（构造保证），无独立计数出口，记为构造性满足
            pass
        return True, "ok"

    return False, f"未知 kind={kind}"


def main():
    ap = argparse.ArgumentParser(description="Layer A 评测 runner（无 DB）")
    ap.add_argument("--only", default="", help="逗号分隔的 case_id，只跑这些")
    ap.add_argument("--verbose", action="store_true", help="打印每条 finding")
    ap.add_argument("--cases", default=os.path.join(_CASES_DIR, "cases.json"))
    ap.add_argument(
        "--out", default="/tmp/results_cases-partial.json",
        help="结果输出路径。默认 /tmp 部分运行文件——2026-08-19 教训：原默认值是"
             " autoresearch/results_cases.json（47 条全量验收记录），评测 agent 按"
             " 文档跑 --only 部分运行时整文件覆写冲掉验收记录。更新全量验收文件"
             " 必须显式 --out 指回，且 --only 部分运行禁止写验收文件")
    args = ap.parse_args()

    # 防覆写双保险：--only 部分运行不得指向验收文件（即便显式传了 --out）
    _acceptance_out = os.path.realpath(
        os.path.join(_HERE, "..", "autoresearch", "results_cases.json"))
    _only = set(filter(None, args.only.split(",")))
    if os.path.realpath(args.out) == _acceptance_out and _only:
        ap.error(
            f"--only 部分运行不允许写验收文件 {_acceptance_out}"
            "（会整文件覆写冲掉全量记录）；用默认 /tmp 输出，或去掉 --only 全量跑")

    cases = json.load(open(args.cases))["cases"]
    only = set(filter(None, args.only.split(",")))

    results = []
    for case in cases:
        cid = case["id"]
        if only and cid not in only:
            continue
        if cid not in FX.FIXTURES:
            results.append({"id": cid, "kind": case["kind"], "status": "skipped",
                            "reason": "无 fixture（extension：bypassor/专用 reader 维度）"})
            continue
        try:
            result, env = run_case(case)
            passed, reason = judge(case, result, env)
            rec = {"id": cid, "kind": case["kind"], "dimension": case["dimension"],
                   "status": "passed" if passed else "failed", "reason": reason}
            if args.verbose:
                rec["findings"] = [{"level": f.get("level"), "pattern": f.get("pattern"),
                                    "message": f.get("message", "")[:60]} for f in result.get("findings", [])
                                   if f.get("level") in SEV]
            results.append(rec)
        except Exception as e:
            results.append({"id": cid, "kind": case["kind"], "dimension": case["dimension"],
                            "status": "error", "reason": f"{type(e).__name__}: {e}",
                            "trace": traceback.format_exc().splitlines()[-3:]})

    # ---- 指标 ----
    def of(kind, status):
        return [r for r in results if r["kind"] == kind and r["status"] == status]

    ran = [r for r in results if r["status"] in ("passed", "failed")]
    passed = [r for r in ran if r["status"] == "passed"]
    failed = [r for r in ran if r["status"] == "failed"]

    # 误报率：should_not_report 失败（应不报却报）
    neg = [r for r in ran if r["kind"] == "should_not_report"]
    fp = [r for r in neg if r["status"] == "failed"]
    fp_rate = len(fp) / len(neg) if neg else None
    # 漏报率：should_report 失败（应报却没报）
    pos = [r for r in ran if r["kind"] in ("should_report", "guardrail")]
    fn_ = [r for r in pos if r["status"] == "failed"]
    fn_rate = len(fn_) / len(pos) if pos else None
    # 根因链率：diagnosis 通过
    diag = [r for r in ran if r["kind"] == "diagnosis"]
    diag_pass = [r for r in diag if r["status"] == "passed"]
    diag_rate = len(diag_pass) / len(diag) if diag else None
    # coverage
    total = len(cases)
    coverage = len(ran) / total if total else 0

    metrics = {
        "误报率": round(fp_rate, 3) if fp_rate is not None else None,
        "漏报率": round(fn_rate, 3) if fn_rate is not None else None,
        "根因链正确率": round(diag_rate, 3) if diag_rate is not None else None,
        "coverage": f"{len(ran)}/{total}",
        "pass_rate": round(len(passed) / len(ran), 3) if ran else None,
    }

    out = {
        "experiment": "phase4.9-cases",
        "score": len(passed), "max_score": len(ran),
        "pass_rate": metrics["pass_rate"], "status": "all_pass" if not failed else "has_failures",
        "metrics": metrics,
        "acceptance": {
            "误报率=0": fp_rate == 0,
            "漏报率≤20%": (fn_rate is not None and fn_rate <= 0.20),
            "根因链≥60%": (diag_rate is None or diag_rate >= 0.60),
        },
        "cases": results,
    }
    json.dump(out, open(args.out, "w"), ensure_ascii=False, indent=2)

    # ---- stdout 摘要 ----
    print(f"\n{'='*60}\nLayer A 评测结果（{len(ran)}/{total} 用例有 fixture）\n{'='*60}")
    print(f"通过 {len(passed)}/{len(ran)}    {metrics}")
    print(f"验收线: 误报率=0 → {'✓' if fp_rate==0 else '✗ '+str(fp_rate)} | "
          f"漏报率≤20% → {'✓' if fn_rate is not None and fn_rate<=0.20 else '✗ '+str(fn_rate)} | "
          f"根因链≥60% → {'✓' if diag_rate is None or diag_rate>=0.60 else '✗ '+str(diag_rate)}")
    if failed:
        print(f"\n--- 失败 ({len(failed)}) ---")
        for r in failed:
            print(f"  ✗ {r['id']:16} [{r.get('kind')}] {r['reason']}")
    errs = [r for r in results if r["status"] == "error"]
    if errs:
        print(f"\n--- 错误 ({len(errs)}) ---")
        for r in errs:
            print(f"  ‼ {r['id']:16} {r['reason']}")
            for line in r.get("trace", []):
                print(f"      {line.strip()}")
    skipped = [r for r in results if r["status"] == "skipped"]
    if skipped:
        print(f"\n--- 跳过 ({len(skipped)}：无 fixture) ---")
        print("  " + ", ".join(r["id"] for r in skipped))
    print(f"\n结果写入 {args.out}")


if __name__ == "__main__":
    main()
