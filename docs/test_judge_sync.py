#!/usr/bin/env python3
"""
test_judge_sync.py — 判分器一致性回归测试（bug#9）

背景：harness 曾有两套判分器——hermes_eval_runner.py（全量跑用）与
rescore_eval.py（离线重判用）。修 bug 时只改一份，导致 20260814 全量跑
对 ~90 题用了错误 parse（47 inspection-cases 被当 DG 方法短语、45 routing-v2
落 manual_judge、DG-P25"日报"→daily_report 无别名必 D1=0）。

本测试锁定三件事：
  1. parse 奇偶性：runner 与 rescore 对同一 expected 产出一致结构
  2. 别名覆盖：parse 能产出的每个 method/task_type key 都有 ALIAS_D1 别名
     （ALIAS_D1 必须是模块级，否则无法测试）
  3. D1 语义金样：日报/inspection_struct POS+NEG/routing_en 用合成 trace 验证

运行：python3 docs/test_judge_sync.py（也可被 pytest 收集）
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import hermes_eval_runner as H  # noqa: E402
import rescore_eval as R  # noqa: E402

GREEN_SETS = (
    "data-governance-routing-list",
    "routing-evals-v1",
    "routing-evals-v2",
    "inspection-eval-criteria",
    "inspection-eval-cases",
)


def _green_evals():
    master = H.load_master_json(str(_HERE / "eval-questions-master.json"))
    for s in master["sets"]:
        if s["set_id"] in GREEN_SETS:
            for ev in s.get("evals", []):
                yield s["set_id"], ev


def _norm(p):
    """去掉 _kind 装饰键后比较实质断言结构。"""
    if not p:
        return None
    return {k: v for k, v in p.items() if k != "_kind"}


def _mk_trace(final, tools=1, dur=10.0, in_tok=1000, out_tok=500):
    return {
        "session_id": "test",
        "final_answer": final,
        "messages": [{"role": "assistant", "content": final}],
        "tool_call_count": tools,
        "message_count": 2,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "duration_sec": dur,
        "cache_read_tokens": 0,
        "reasoning_tokens": 0,
        "tool_chain": [{"tool": "terminal"}] * tools,
    }


# ---------------------------------------------------------------------------
# 1. parse 奇偶性
# ---------------------------------------------------------------------------

def test_parse_parity_runner_vs_rescore():
    diffs = []
    for sid, ev in _green_evals():
        exp = ev.get("expected_output") or ""
        a = _norm(H.parse_expected(sid, exp))
        b = _norm(R.parse_expected_v2(sid, exp))
        if a != b:
            diffs.append((ev["id"], a, b))
    assert not diffs, (
        f"{len(diffs)} 题 parse 不一致（全量跑与重判不可比）。样例：\n  "
        + "\n  ".join(f"{i}: runner={a} vs rescore={b}" for i, a, b in diffs[:6])
    )


# ---------------------------------------------------------------------------
# 2. 别名覆盖（ALIAS_D1 须模块级 + 全 key 覆盖）
# ---------------------------------------------------------------------------

def test_alias_d1_is_module_level():
    assert hasattr(H, "ALIAS_D1"), (
        "ALIAS_D1 必须是 hermes_eval_runner 模块级常量——当前困在 judge() 局部，"
        "别名覆盖无法被测试，也无法与 rescore 共享"
    )


def test_alias_covers_all_parse_outputs():
    if not hasattr(H, "ALIAS_D1"):
        raise AssertionError("前置失败：ALIAS_D1 非模块级（见 test_alias_d1_is_module_level）")
    missing = []
    for sid, ev in _green_evals():
        p = H.parse_expected(sid, ev.get("expected_output") or "")
        if not p:
            continue
        keys = list(p.get("methods") or [])
        if p.get("task_type"):
            keys.append(p["task_type"])
        for k in keys:
            if k not in H.ALIAS_D1:
                missing.append(f"{ev['id']}: '{k}'")
    assert not missing, (
        f"parse 产出但 ALIAS_D1 无别名的 key（中文回答必 D1=0，bug#7/#9 同类）："
        f"{sorted(set(missing))}"
    )


# ---------------------------------------------------------------------------
# 3. D1 语义金样（合成 trace；答案刻意不含"阈值"等 DG 代理词，防旧 bug 蒙混）
# ---------------------------------------------------------------------------

def test_d1_daily_report_keyword():
    """DG-P25 回归：expected='日报生成'，回答含"日报/报告" → D1=1.0。

    旧 bug：parse 产 daily_report 而 ALIAS_D1 无此键 → 回退英文字面量 → 必 0。"""
    ev = {"id": "T-DG-P25", "name": "", "prompt": "", "expected_output": "日报生成"}
    tr = _mk_trace("已生成数据质量日报，报告含完整性/准确性/及时性三项汇总。")
    v = H.judge(ev, tr, {"set_id": "data-governance-routing-list"}, set())
    assert v["dimensions"]["D1_functional"] == 1.0, (
        f"日报生成 D1={v['dimensions']['D1_functional']}（note={v.get('d1_note')}），"
        f"应 1.0"
    )


def test_d1_inspection_struct_pos():
    """inspection-eval-cases 结构化 expected：正确报出 CRITICAL+关键词 → D1=1.0。

    旧 bug：runner 无 min_level 分支，整串落 DG 方法短语 fallback，用'阈值'
    代理判分（答案不含'阈值'就 0 分，含就 1 分，与真实断言无关）。"""
    ev = {"id": "T-POS", "name": "", "prompt": "",
          "expected_output": "min_level=CRITICAL; message_contains=红色预警 | 理由: 100.1mm>100mm"}
    tr = _mk_trace("检出CRITICAL红色预警：单时段雨量100.1mm，建议立即巡查。")
    v = H.judge(ev, tr, {"set_id": "inspection-eval-cases"}, set())
    assert v["dimensions"]["D1_functional"] == 1.0, (
        f"inspection POS D1={v['dimensions']['D1_functional']}（note={v.get('d1_note')}），应 1.0"
    )


def test_d1_inspection_struct_neg_not_reported():
    """NEG：最终结论未把 X 当发现报出（否定语境）→ D1=1.0。"""
    ev = {"id": "T-NEG", "name": "", "prompt": "",
          "expected_output": "no_finding_contains=告警 | 理由: 无I/II级；积压阈值为严格>10，不应触发"}
    tr = _mk_trace("未发现告警异常，各项指标正常，无需处理。")
    v = H.judge(ev, tr, {"set_id": "inspection-eval-cases"}, set())
    assert v["dimensions"]["D1_functional"] == 1.0, (
        f"inspection NEG(未报出) D1={v['dimensions']['D1_functional']}（note={v.get('d1_note')}），应 1.0"
    )


def test_d1_inspection_struct_neg_violation():
    """NEG 反例：最终结论把 X 当发现报出且无否定语境 → D1 应显著低于 1。"""
    ev = {"id": "T-NEG2", "name": "", "prompt": "",
          "expected_output": "no_finding_contains=告警 | 理由: 无I/II级；积压阈值为严格>10，不应触发"}
    tr = _mk_trace("发现告警积压问题，建议立即处理。")
    v = H.judge(ev, tr, {"set_id": "inspection-eval-cases"}, set())
    assert v["dimensions"]["D1_functional"] < 1.0, (
        f"inspection NEG(违规报出) D1={v['dimensions']['D1_functional']}，应 <1.0"
    )


def test_d1_routing_en():
    """routing-evals-v2 英文 expected：回答含异常关键词+锚点 → D1 明显高于无关键词。"""
    ev = {"id": "T-RT", "name": "", "prompt": "",
          "expected_output": "Provider calls powerelf-data-governance to analyze rainfall 606001 anomaly"}
    good = _mk_trace("已调用 powerelf-data-governance 分析 606001 雨量(rainfall)异常。")
    bad = _mk_trace("这个问题我无法处理。")
    vg = H.judge(ev, good, {"set_id": "routing-evals-v2"}, set())
    vb = H.judge(ev, bad, {"set_id": "routing-evals-v2"}, set())
    assert vg["dimensions"]["D1_functional"] > vb["dimensions"]["D1_functional"], (
        f"routing_en 好坏答案 D1 无区分："
        f"{vg['dimensions']['D1_functional']} vs {vb['dimensions']['D1_functional']}"
        f"（note={vg.get('d1_note')}）"
    )


def test_parse_golden_values():
    """代表性 expected 的 parse 金样（锁结构，防再次漂移）。"""
    dg = H.parse_expected("data-governance-routing-list", "日报生成")
    assert _norm(dg) == {"methods": ["report"], "task_type": "report", "raw": "日报生成"}, dg

    dg2 = H.parse_expected("data-governance-routing-list", "四策略自适应插值")
    assert _norm(dg2) == {"methods": ["interpolation", "adaptive", "strategy"],
                          "task_type": "detection", "raw": "四策略自适应插值"}, dg2

    # bug#10：等级并入 grade 模式（原"较差等级设备筛选" parse=None → D1 manual_judge 0.5 地板）
    dg3 = H.parse_expected("data-governance-routing-list", "较差等级设备筛选")
    assert _norm(dg3) == {"methods": ["grade"], "task_type": "grade",
                          "raw": "较差等级设备筛选"}, dg3

    insp = H.parse_expected("inspection-eval-cases",
                            "min_level=CRITICAL; message_contains=红色预警 | 理由: 100.1mm>100mm")
    assert insp.get("min_level") == "CRITICAL" and insp.get("message_contains") == "红色预警", insp

    rt = H.parse_expected("routing-evals-v2",
                          "Provider calls powerelf-data-governance to analyze rainfall 606001 anomaly")
    assert "routing_en" == rt.get("_kind") and "rainfall" in rt.get("anomalies", []), rt


# ---------------------------------------------------------------------------
# 4. D2 别名覆盖（bug#11 回归锁）
# ---------------------------------------------------------------------------

def test_d2_method_keywords_distinguish():
    """bug#11 回归：D2 须用与 D1 同源的全量别名，而非局部 10-key 子集。

    旧 bug：expected='四策略自适应插值' parse 产 methods=[interpolation,adaptive,
    strategy]，但局部 ALIAS_D2 无这三键 → 回退英文字面量 → 中文回答必 D2=0。
    修复后 _d2_hit 复用模块级 ALIAS_D1，中文回答应命中 → D2 显著高于无关回答。"""
    ev = {"id": "T-D2", "name": "", "prompt": "", "expected_output": "四策略自适应插值"}
    good = _mk_trace("采用自适应插值策略，按样条/线性多策略补全缺失数据。")
    bad = _mk_trace("该问题无法处理，缺少上下文。")
    vg = H.judge(ev, good, {"set_id": "data-governance-routing-list"}, set())
    vb = H.judge(ev, bad, {"set_id": "data-governance-routing-list"}, set())
    assert vg["dimensions"]["D2_routing"] > vb["dimensions"]["D2_routing"], (
        f"bug#11 未修：插值策略类 D2 好坏答案无区分 "
        f"({vg['dimensions']['D2_routing']} vs {vb['dimensions']['D2_routing']})"
    )


def test_d2_covers_all_parse_keys():
    """parse 能产出的每个 method/task_type key，D2 评分路径都能查到别名
    （否则中文回答落 D2=0，D2 维度被系统性低估）。"""
    missing = []
    for sid, ev in _green_evals():
        p = H.parse_expected(sid, ev.get("expected_output") or "")
        if not p or "methods" not in p:
            continue
        keys = list(p.get("methods") or [])
        if p.get("task_type"):
            keys.append(p["task_type"])
        for k in keys:
            if k not in H.ALIAS_D1:
                missing.append(f"{ev['id']}: '{k}'")
    assert not missing, (
        f"parse 产出但 D2 无别名的 key（中文回答必 D2=0）：{sorted(set(missing))}"
    )


def test_d1_ok_keyword_chinese_alias():
    """EVAL9 回归：expected pass_keyword='OK'（表无异常），agent 写'正常/🟢'
    不写英文 OK → 旧版字面不命中 all() 整题 D1=0（实测答案实质全对却判 FAIL）。
    修复：ALIAS_D1['OK'] 含'正常'等中文同义词。"""
    ev = {"id": "T-OK", "name": "", "prompt": "",
          "expected_output": 'Pass: 输出包含"OK"和"CRITICAL"——3维度报OK | Fail: 误报'}
    tr = _mk_trace("3个维度🟢正常无异常，位移维度🔴CRITICAL真实异常。")
    v = H.judge(ev, tr, {"set_id": "inspection-eval-criteria"}, set())
    assert v["dimensions"]["D1_functional"] == 1.0, (
        f"OK关键词中文同义词未认 D1={v['dimensions']['D1_functional']}（note={v.get('d1_note')}）"
    )


def test_d1_traditional_variant_gate():
    """EVAL2 回归：expected='闸门'，agent 写繁体'閘門' → 旧版字面不命中 D1=0。
    修复：ALIAS_D1['闸门'] 含繁体'閘門'。"""
    ev = {"id": "T-GATE", "name": "", "prompt": "",
          "expected_output": 'Pass: 输出包含"闸门"和"突变" | Fail: 输出不包含闸门异常'}
    tr = _mk_trace("閘門ステーション90: 突变1.32m，建议巡查。")
    v = H.judge(ev, tr, {"set_id": "inspection-eval-criteria"}, set())
    assert v["dimensions"]["D1_functional"] == 1.0, (
        f"闸门繁体变体未认 D1={v['dimensions']['D1_functional']}（note={v.get('d1_note')}）"
    )


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
