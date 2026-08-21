#!/usr/bin/env python3
"""
rescore_eval.py — 离线重打分：从已有 state.db session 重判，不重跑 hermes。

设计原则（第一版踩坑后的修正；bug#9 后进一步收敛）：
  • 效率维度 D3/D4/D5 用原报告 eval 时捕获的「不可变事实」
    （tool_call_count / input_tokens / output_tokens / duration_sec），
    不从 state.db 重提取——否则 ended_at=NULL 走 time.time() 兜底，
    duration 膨胀到百万秒，D5 全部判 0（第一版的致命 bug）。
  • bug#9：parse / 判分别名 / D1 增强（inspection_struct、routing_en、
    pass_keywords 别名兜底）/ clarify 地板，已全部并入 H.judge 单一事实源
    （此前两套判分器各持一份、修 bug 只改一份 → 20260814 全量跑 95 题口径
    不一致）。本文件只做：不可变事实重构 + 双口径语料（corpus /
    final_strict）+ 报告对比输出。一致性由 docs/test_judge_sync.py 锁定。

用法：python3 docs/rescore_eval.py [YYYYMMDD-HHMMSS]
输出：docs/rescore-<ts>.json + 控制台新旧 delta
"""
import json
import re
import sys
import datetime as _dt
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import hermes_eval_runner as H  # noqa: E402

TS = "20260812-182946"
MASTER = _HERE / "eval-questions-master.json"


def _resolve_report(ts):
    """报告可能在 output/{ts}/ 或 docs/ 下，优先 output/。"""
    for cand in (_HERE.parent / "output" / ts / f"hermes-eval-results-{ts}.json",
                 _HERE / f"hermes-eval-results-{ts}.json"):
        if cand.exists():
            return cand
    return _HERE / f"hermes-eval-results-{ts}.json"  # 兜底（报错时给清晰路径）


ORIG_REPORT = _resolve_report(TS)

# 允许命令行指定要重判的轮次时间戳：python3 rescore_eval.py 20260814-103000
# 或直接指定结果文件路径（run 目录名与结果文件名可能差 1 秒，ts 寻址落空时用）：
#   python3 rescore_eval.py output/hermes-eval-20260814-182333/hermes-eval-results-20260814-182334.json
if len(sys.argv) > 1:
    _arg = sys.argv[1]
    if re.match(r"\d{8}-\d{6}", _arg):
        TS = _arg
        ORIG_REPORT = _resolve_report(TS)
    elif _arg.endswith(".json"):
        ORIG_REPORT = Path(_arg).resolve()
        _m = re.search(r"(\d{8}-\d{6})", ORIG_REPORT.name)
        TS = _m.group(1) if _m else ORIG_REPORT.stem

# ===========================================================================
# 修复 ①：D6 表名提取（ASCII-only，排除比较散文）
# ===========================================================================

_TABLE_PATTERNS = [
    r'\bst_[a-z0-9_]+_r\b',   # \b 防止在文件名(如 august_2026_anomaly_report)里子串误匹配出假表
    r'\bdsm_[a-z0-9_]+\b',
    r'\beq_[a-z][a-z0-9_]*\b',   # eq_ 后须字母开头（排除 eq_139_vs_140 这类）
    r'\brei_[a-z0-9_]+_r\b',
    r'\bsl_[a-z0-9_]+_r\b',
]


def extract_table_names_v2(text):
    if not text:
        return []
    found = set()
    for pat in _TABLE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            tok = m.group(0).lower()
            if "vs" in tok:          # 排除比较散文 eq_139_vs_140_may
                continue
            found.add(tok)
    return sorted(found)


# ===========================================================================
# 修复 ②（bug#9 起整体并入 hermes_eval_runner，此处仅保留兼容委托）
#
# 历史：parse_expected_v2 曾是本文件的扩展版 parse（routing-v2 英文 /
# inspection 结构化 / DG 方法短语），与 H.parse_expected 各持一份 → 修 bug
# 只改一份 → 20260814 全量跑 95 题 parse 不一致（47 inspection 被"阈值"代理
# 误判、45 routing-v2 落 manual_judge、DG 方法短语大面积 None 吃 0.5 地板）。
# 现为单一事实源，奇偶性由 docs/test_judge_sync.py 锁定。
# ===========================================================================

def parse_expected_v2(set_id, s):
    """委托 H.parse_expected（bug#9 统一后单一事实源），保留函数名兼容旧引用。"""
    return H.parse_expected(set_id, s)



# ===========================================================================
# judge_v2：委托 H.judge + 局部增强
# ===========================================================================

def judge_v2(ev, trace, set_obj, schema_tables, orig_summary):
    """bug#9 统一后：parse/别名/D1 增强/clarify 地板已全部并入 H.judge。
    本函数仅负责两件事：
      ① 用 eval 时捕获的不可变事实重构 trace——不从 state.db 重提取
        duration/tokens（否则 ended_at=NULL 走 time.time() 兜底，duration
        膨胀到百万秒，D5 全 0，第一版的致命 bug）；
      ② 双口径语料：corpus（final+clarify+assistant 全历史）供 D1/D7/D6，
        final_strict（仅最终回答）供 no_finding_contains 误报检查。"""
    msgs = trace.get("messages", []) or []
    clarify_text = "".join((m.get("content") or "") for m in msgs
                           if m.get("role") == "tool" and m.get("tool_name") == "clarify")
    assistant_text = "".join((m.get("content") or "") for m in msgs
                             if m.get("role") == "assistant")
    answer_corpus = (trace.get("final_answer") or "") + "\n" + clarify_text + "\n" + assistant_text

    tj = {
        "session_id": trace["session_id"],
        "final_answer": answer_corpus,
        "answer_corpus": answer_corpus,
        "final_answer_strict": trace.get("final_answer") or "",
        "messages": msgs,
        "tool_call_count": orig_summary.get("tool_call_count", trace["tool_call_count"]),
        "input_tokens": orig_summary.get("input_tokens", trace["input_tokens"]),
        "output_tokens": orig_summary.get("output_tokens", trace["output_tokens"]),
        "duration_sec": orig_summary.get("duration_sec", trace["duration_sec"]),
        "message_count": trace.get("message_count", 0),
        "cache_read_tokens": trace.get("cache_read_tokens", 0),
        "reasoning_tokens": trace.get("reasoning_tokens", 0),
        "tool_chain": orig_summary.get("tool_chain", trace.get("tool_chain", [])),
    }
    base = H.judge(ev, tj, set_obj, schema_tables)
    base["clarified"] = bool(clarify_text)
    return base


# ===========================================================================
# 主流程
# ===========================================================================

def main():
    orig = json.load(open(ORIG_REPORT, encoding="utf-8"))
    master = H.load_master_json(str(MASTER))
    set_obj_by_id = {s["set_id"]: s for s in master["sets"]}
    ev_idx = {(s["set_id"], ev["id"]): ev for s in master["sets"] for ev in s.get("evals", [])}
    schema = H.load_schema_tables()

    new_results = []
    missing = 0
    for r in orig["results"]:
        ev = ev_idx.get((r["set"], r["id"]))
        if not ev:
            continue
        # 优先用 eval 时已存的权威 session_id（避免 routing-v1/v2 数字 id 撞 source_tag
        # 导致 find_session_by_source 抓到另一题的 session）；缺失再反查。
        sid = (r.get("trace_summary") or {}).get("session_id") \
            or H.find_session_by_source(f"eval-{TS}-{r['id']}")
        if not sid:
            missing += 1
            new_results.append(r)
            continue
        trace = H.extract_trace(sid)
        if trace is None:
            missing += 1
            new_results.append(r)
            continue
        set_obj = set_obj_by_id.get(r["set"], {"set_id": r["set"]})
        nr = judge_v2(ev, trace, set_obj, schema, r.get("trace_summary", {}))
        if ev.get("known_issue"):
            nr["known_issue"] = ev["known_issue"]
        new_results.append(nr)

    def _overall(res):
        s = [x["score"] for x in res]
        return round(sum(s) / len(s), 3) if s else 0.0

    def _dims(res):
        out = {}
        for dn in H.DIMENSION_WEIGHTS:
            vals = [x["dimensions"][dn] for x in res]
            out[dn] = {"avg": round(sum(vals) / len(vals), 3),
                       "fail": sum(1 for v in vals if v < 0.4)}
        return out

    old_o, new_o = _overall(orig["results"]), _overall(new_results)
    old_d, new_d = _dims(orig["results"]), _dims(new_results)
    ovc = Counter(r["verdict"] for r in orig["results"])
    nvc = Counter(r["verdict"] for r in new_results)
    n_clar = sum(1 for r in new_results if r.get("clarified"))

    print("=" * 66)
    print(f"重打分完成：{len(new_results)} 题（session 缺失 {missing} 保留原值）")
    print(f"总体得分：{old_o}  →  {new_o}   （Δ {new_o - old_o:+.3f}）")
    print(f"结论：PASS {ovc.get('PASS',0)}→{nvc.get('PASS',0)}  "
          f"PARTIAL {ovc.get('PARTIAL',0)}→{nvc.get('PARTIAL',0)}  "
          f"FAIL {ovc.get('FAIL',0)}→{nvc.get('FAIL',0)}")
    print(f"触发 clarify 题：{n_clar}（已给 D1 地板 + 评分含 clarify 分析文本）")
    known = [r for r in new_results if r.get("known_issue")]
    real_fail = [r for r in new_results if r["verdict"] == "FAIL" and not r.get("known_issue")]
    if known:
        print(f"已知评测题缺陷（不计真 skill FAIL）：{len(known)} → {[r['id'] for r in known]}")
        print(f"→ 真 skill FAIL：{len(real_fail)} → {[r['id'] for r in real_fail]}")
    print("\n维度              旧avg  新avg   Δavg    旧失败 新失败")
    for dn in H.DIMENSION_WEIGHTS:
        o, n = old_d[dn], new_d[dn]
        print(f"  {dn:16s} {o['avg']:.3f}  {n['avg']:.3f}  {n['avg']-o['avg']:+.3f}   "
              f"{o['fail']:5d}  {n['fail']:5d}")

    manual = sum(1 for r in new_results if str(r.get("d1_note", "")).startswith("manual"))
    print(f"\nD1 仍 manual_judge：{manual}/164（原 97）")

    oh = sum(len(r.get("hallucinated_tables", [])) for r in orig["results"])
    nh = sum(len(r.get("hallucinated_tables", [])) for r in new_results)
    print(f"D6 标记幻觉表名总数：{oh} → {nh}")

    report = {
        "rescore_of": TS,
        "rescored_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "overall_old": old_o, "overall_new": new_o,
        "verdict_old": orig["overall_verdict"],
        "verdict_new": "PASS" if new_o >= 0.7 else ("PARTIAL" if new_o >= 0.4 else "FAIL"),
        "per_dimension": {"old": old_d, "new": new_d},
        "results": new_results,
    }
    out = _HERE / f"rescore-{TS}.json"
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n已写入：{out}")


if __name__ == "__main__":
    main()
