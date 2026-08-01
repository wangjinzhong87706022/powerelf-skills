#!/usr/bin/env python3
"""
eval_runner.py — chatbi Layer A 评测 runner

跑两类语料过 sql_lint：
  1. cases.json：~12 条 ✅/❌ SQL 用例（手写，靶向各检查项）。
  2. few_shots.md：20 条真实示例 SQL（回归基线——修 bug 前应报 fail，修后全绿）。

输出 autoresearch/results_cases.json + stdout 摘要。

用法：
  python3 eval_runner.py                  # 跑 cases + few_shots
  python3 eval_runner.py --no-fewshots    # 只跑 cases
"""

import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CASES_DIR = os.path.join(_HERE, "..", "autoresearch", "eval_cases")
sys.path.insert(0, _HERE)

import sql_lint as L  # noqa: E402


def judge_case(case, findings):
    """按 expected 判定。findings = lint() 返回的 [(severity, msg)]。"""
    exp = case["expected"]
    fails = [m for s, m in findings if s == "fail"]
    if exp.get("clean"):
        return (not fails), ("干净" if not fails else f"误报 fail: {fails}")
    kw = exp.get("fails_with")
    if kw:
        if any(kw in m for m in fails):
            return True, f"命中 '{kw}'"
        return False, f"未命中 fail '{kw}'（findings: {finds_summary(findings)})"
    return False, "expected 无 clean/fails_with"


def finds_summary(findings):
    return ", ".join(f"{s}:{m[:25]}" for s, m in findings) or "∅"


def extract_fewshots(path):
    """从 few_shots.md 抽 ```sql ... ``` 块，返回 [(标题, sql), ...]。"""
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8").read()
    # 标题在 SQL 块前一个 ## 行
    blocks = re.findall(r"## (.+?)\n[\s\S]*?```sql\n([\s\S]*?)```", text)
    return [(t.strip(), sql.strip()) for t, sql in blocks]


def main():
    ap = argparse.ArgumentParser(description="chatbi Layer A 评测 runner")
    ap.add_argument("--cases", default=os.path.join(_CASES_DIR, "cases.json"))
    ap.add_argument("--fewshots", default=os.path.join(_HERE, "..", "references", "few_shots.md"))
    ap.add_argument("--no-fewshots", action="store_true")
    ap.add_argument("--out", default=os.path.join(_HERE, "..", "autoresearch", "results_cases.json"))
    args = ap.parse_args()

    cases = json.load(open(args.cases))["cases"]
    results = []

    # ---- cases ----
    for case in cases:
        finds = L.lint(case["sql"])
        passed, reason = judge_case(case, finds)
        results.append({"suite": "cases", "id": case["id"], "status": "passed" if passed else "failed",
                        "reason": reason, "findings": [{"sev": s, "msg": m} for s, m in finds]})

    # ---- few_shots 基线 ----
    fs_results = []
    if not args.no_fewshots:
        for title, sql in extract_fewshots(args.fewshots):
            finds = L.lint(sql)
            fails = [m for s, m in finds if s == "fail"]
            fs_results.append({"suite": "few_shots", "id": title, "status": "failed" if fails else "passed",
                               "findings": [{"sev": s, "msg": m} for s, m in finds]})
    results.extend(fs_results)

    # ---- 摘要 ----
    def split(suite):
        rs = [r for r in results if r["suite"] == suite]
        return rs, [r for r in rs if r["status"] == "passed"], [r for r in rs if r["status"] == "failed"]

    case_rs, case_ok, case_fail = split("cases")
    fs_rs, fs_ok, fs_fail = split("few_shots")

    # 误报（clean 用例却 fail）/ 漏报（应 fail 却干净）
    clean_cases = [c for c in cases if c["expected"].get("clean")]
    should_fail = [c for c in cases if c["expected"].get("fails_with")]
    # 误报：clean 用例却被 fail；漏报：should_fail 用例 linter 没抓到（status=failed）
    fp = [r["id"] for r in case_rs if r["id"] in {c["id"] for c in clean_cases} and r["status"] == "failed"]
    fn = [c["id"] for c in should_fail
          if next((r for r in case_rs if r["id"] == c["id"]), {}).get("status") == "failed"]

    out = {
        "experiment": "chatbi-sql-lint",
        "cases": {"pass": len(case_ok), "total": len(case_rs), "误报": len(fp), "漏报": len(fn)},
        "few_shots": {"clean": len(fs_ok), "total": len(fs_rs), "with_bug": len(fs_fail)},
        "results": results,
    }
    json.dump(out, open(args.out, "w"), ensure_ascii=False, indent=2)

    print(f"\n{'='*60}\nchatbi Layer A（SQL 语义 lint）\n{'='*60}")
    print(f"cases:    {len(case_ok)}/{len(case_rs)} 通过   误报={len(fp)} 漏报={len(fn)}")
    print(f"few_shots: {len(fs_ok)}/{len(fs_rs)} 干净   {len(fs_fail)} 条含 bug")
    if case_fail:
        print("\n--- cases 失败 ---")
        for r in case_fail:
            print(f"  ✗ {r['id']:14} {r['reason']}")
    if fs_fail:
        print("\n--- few_shots 含 bug（修 bug 前 baseline）---")
        for r in fs_fail:
            msgs = "; ".join(f["msg"][:40] for f in r["findings"] if f["sev"] == "fail")
            print(f"  ✗ {r['id'][:28]:30} {msgs}")
    print(f"\n结果写入 {args.out}")


if __name__ == "__main__":
    main()
