#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归一化脚本：把本项目各阶段生成的评测问题清单汇总为统一 JSON。
产出：docs/eval-questions-master.json
格式：基于 evals-database-v2.json 的 {id, name, prompt, expected_output} 规范。

数据来源（按阶段）：
1. early-warning-v3/tests/test-data-scenarios.md   — Q1~Q103 场景覆盖矩阵（题面仅标题，全文未入库）
2. powerelf-data-governance/docs/questions.md      — 可问/不可问路由清单
3. powerelf-data-governance/docs/test-questions.md — 基于真实数据的测试题集（T1.1~T11.1）
4. skill-creator-workspace/data-governance-routing/evals.json               — 路由测试 v1（6 题）
5. skill-creator-workspace/data-governance-routing/evals-database-v2.json   — 路由测试 v2（45 题）
6. powerelf-inspection/autoresearch/eval_criteria.md      — 10 条二元 EVAL
7. powerelf-inspection/autoresearch/eval_cases/cases.json — 47 个成对用例
8. darwin-skill/test-prompts.json                         — 3 条优化流程测试
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "eval-questions-master.json"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def load_json(path):
    with (ROOT / path).open(encoding="utf-8") as f:
        return json.load(f)


# ---------- 1. early-warning-v3 场景矩阵（Q1~Q103，标题级） ----------
def parse_early_warning_matrix():
    md = read("early-warning-v3/tests/test-data-scenarios.md")
    evals, seen = [], set()
    # 行格式: | Q1: 未确认告警数量 | 场景1 | 4条未确认告警 |
    pat = re.compile(r"^\|\s*Q(\d+):\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")
    for line in md.splitlines():
        m = pat.match(line)
        if not m:
            continue
        qid = int(m.group(1))
        seen.add(qid)
        evals.append({
            "id": f"Q{qid:03d}",
            "name": f"Q{qid}: {m.group(2).strip()}",
            "prompt": m.group(2).strip(),
            "expected_output": f"场景：{m.group(3).strip()}；数据要求：{m.group(4).strip()}",
            "prompt_source": "title-only",  # 题面全文未入库，仅标题
        })
    # 全量 Q1~Q103 缺口（矩阵跳号）；补零与 placeholder_ids 的 Q0xx 格式统一
    gaps = [f"Q{q:03d}" for q in range(1, 104) if q not in seen]
    return evals, gaps


# ---------- 1b. early-warning-v3 缺号段占位题面（补写，非原文） ----------
# Q36–Q61（26 题）位于「预测预警 Q29–Q35」与「智能综合分析 Q62–Q69」之间；
# Q99–Q101（3 题）位于「边界场景 Q94–Q98」与「气象预警 Q102–Q103」之间。
# 按 SKILL.md lifecycle/scenarios 真实能力分类补写，prompt_source=placeholder-reconstructed。
PLACEHOLDER_EARLY_WARNING = {
    # --- 告警处置与建议（Q36–Q40） ---
    36: ("告警处置建议", "当前最紧急的未确认告警是哪些？给出优先处置建议。", "按级别/时效排序，输出处置动作建议"),
    37: ("处置优先级排序", "结合告警级别、持续时间和影响范围，对当前告警做处置优先级排序。", "多因子排序并说明依据"),
    38: ("值班关注清单", "今天值班需要重点关注的告警有哪些？", "输出今日关注清单（按测站/类型聚合）"),
    39: ("处置动作建议", "对 I 级红色告警给出初步处置动作建议（人工核实/转派/忽略）。", "给出动作 + 依据"),
    40: ("处置验证", "告警处置后如何验证已解除？", "验证标准：状态流转 + 无新增同类告警"),
    # --- 告警合并与去重（Q41–Q45） ---
    41: ("重复告警检测", "最近 7 天有哪些重复告警（同测站/同类型/短时间窗）？", "输出重复告警清单"),
    42: ("告警合并建议", "这些相似告警是否可以合并？给出合并建议。", "合并窗口/规则 + 合并后条目"),
    43: ("高频告警分析", "哪个告警触发最频繁？TOP 10 高频告警是哪些？", "按触发次数排序输出 TOP10"),
    44: ("告警风暴检测", "当前是否处于告警风暴状态？", "判定：短时告警数超阈值"),
    45: ("合并策略建议", "针对当前告警模式，建议怎样的合并/去重策略？", "窗口大小 + 阈值 + 白名单"),
    # --- 告警升级（Q46–Q50） ---
    46: ("升级决策建议", "这条告警是否满足升级条件？是否需要升级？", "升级判定 + 依据"),
    47: ("升级通知生成", "为这条升级告警生成升级通知模板。", "模板：测站/级别/处置时限/责任人"),
    48: ("升级策略分析", "当前升级规则是否合理？给出优化建议。", "规则命中率分析 + 建议"),
    49: ("升级历史查询", "最近 30 天有哪些告警被升级过？", "输出升级历史清单"),
    50: ("升级级别建议", "该告警应升级到哪一级、通知哪些人？", "级别 + 通知对象"),
    # --- 告警恢复与生命周期（Q51–Q56） ---
    51: ("告警恢复判定", "这条告警当前是否已恢复？", "判定：触发条件消失/手动恢复"),
    52: ("恢复处置建议", "告警恢复后还需要做什么？", "后续动作：复核/归档/复盘"),
    53: ("状态机查询", "该告警当前处于状态机的哪个状态？", "输出当前状态"),
    54: ("状态流转建议", "该告警下一步应流转到哪个状态？", "目标状态 + 触发条件"),
    55: ("恢复率统计", "最近一个月告警恢复成功率是多少？", "恢复数/总数 + 趋势"),
    56: ("生命周期分析", "这条告警从产生到恢复的完整轨迹是怎样的？", "时间线：产生→确认→处置→恢复"),
    # --- 审计与操作分析（Q57–Q61） ---
    57: ("操作历史查询", "最近一周谁处理了哪些告警？", "输出操作历史清单"),
    58: ("处理效率分析", "告警平均处理时长是多少？有没有超时未处理的？", "平均时长 + 超时清单"),
    59: ("操作人员绩效", "哪个操作人员处理告警最多/最快？", "按人员聚合统计"),
    60: ("异常操作检测", "最近有没有异常操作记录（越权/非工作时间操作）？", "异常操作清单"),
    61: ("审计汇总", "汇总本周告警处理情况（处理量/时效/升级/恢复）。", "周报式汇总"),
    # --- 组合边界（Q99–Q101） ---
    99: ("组合边界判定", "多条边界条件同时满足（如水位恰好到警戒线且雨量临界）时如何判定？", "边界组合下的综合判定"),
    100: ("跨域边界叠加", "水位边界 + 降雨边界叠加时，级别如何计算？", "取高原则 + 依据"),
    101: ("气象关联边界", "气象预警与本地告警在边界状态下如何联动？", "气象+本地综合处置建议"),
}


# ---------- 2. data-governance docs/questions.md（可问/不可问清单） ----------
def parse_questions_md():
    md = read("powerelf-data-governance/docs/questions.md")
    evals = []
    idx_p = idx_n = 0  # 正例/负例各自独立计数，避免负例继承正例计数（曾导致 DG-N47..N53）
    mode = None  # pos / neg
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("## ✅"):
            mode = "pos"
            continue
        if s.startswith("## ❌"):
            mode = "neg"
            continue
        if mode is None or s.startswith(("#", ">", "|----", "|------")):
            continue
        # 兼容 2 列（正例：问题示例|说明）与 3 列（负例：问题|skill|原因）
        m2 = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", s)
        m3 = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", s)
        if mode == "pos":
            if not m2 or m2.group(1).startswith("问题示例"):
                continue
            idx_p += 1
            evals.append({
                "id": f"DG-P{idx_p:02d}",
                "name": f"可问-{m2.group(2).strip()}",
                "prompt": m2.group(1).strip(),
                "expected_output": m2.group(2).strip(),
            })
        else:
            if not m3 or m3.group(1).startswith("问题"):
                continue
            idx_n += 1
            evals.append({
                "id": f"DG-N{idx_n:02d}",
                "name": f"不可问-{m3.group(1).strip()[:24]}",
                "prompt": m3.group(1).strip(),
                "expected_output": f"应路由到 {m3.group(2).strip()}；原因：{m3.group(3).strip()}",
            })
    return evals


# ---------- 3. data-governance docs/test-questions.md（真实数据题集 T1.1~T11.1） ----------
def parse_test_questions_md():
    md = read("powerelf-data-governance/docs/test-questions.md")
    evals = []
    cur = None
    in_fence = False
    fence_buf = []
    heading_pat = re.compile(r"^###\s*(T\d+\.\d+)\s+(.+)$")

    def close_cur():
        nonlocal cur
        if cur:
            evals.append(cur)
            cur = None

    for line in md.splitlines():
        s = line.strip()
        m = heading_pat.match(s)
        if m:
            close_cur()
            cur = {"id": m.group(1), "name": f"{m.group(1)} {m.group(2)}", "prompt": "", "expected_output": ""}
            continue
        if s.startswith("```"):
            if in_fence:  # 关闭围栏：非代码块即问题原文（首次命中即取，不覆盖）
                if cur and not cur["prompt"]:
                    buf = [b for b in fence_buf if b.strip()]
                    first = buf[0].strip() if buf else ""
                    if first and not first.startswith(("python", "from ", "import ", "bash", "#!/")):
                        cur["prompt"] = "\n".join(buf).strip()
                fence_buf = []
            in_fence = not in_fence
            continue
        if in_fence:
            fence_buf.append(line)
            continue
        # 围栏外：预期/纯文本（T9.x 等无围栏 prompt 的题目）
        if cur and s.startswith("**预期**"):
            cur["expected_output"] = "见文档预期"
        elif cur and not cur["prompt"] and s and not s.startswith(("**", "-", "|", ">", "验证")):
            cur["prompt"] = s
    close_cur()
    return evals


# ---------- 6. inspection eval_criteria.md（10 条二元 EVAL） ----------
def parse_eval_criteria():
    md = read("powerelf-inspection/autoresearch/eval_criteria.md")
    evals, cur = [], None
    for line in md.splitlines():
        s = line.strip()
        m = re.match(r"^###\s*EVAL\s*(\d+):\s*(.+)$", s)
        if m:
            if cur:
                evals.append(cur)
            cur = {"id": f"EVAL{m.group(1)}", "name": f"EVAL{m.group(1)}: {m.group(2)}", "prompt": "", "pass": "", "fail": ""}
            continue
        if not cur:
            continue
        if s.startswith("Question:"):
            cur["prompt"] = s[len("Question:"):].strip()
        elif s.startswith("Pass:"):
            cur["pass"] = s[len("Pass:"):].strip()
        elif s.startswith("Fail:"):
            cur["fail"] = s[len("Fail:"):].strip()
    if cur:
        evals.append(cur)
    for e in evals:
        e["expected_output"] = f"Pass: {e['pass']} | Fail: {e['fail']}"
        del e["pass"], e["fail"]
    return evals


# ---------- 7. inspection eval_cases/cases.json（47 个成对用例） ----------
def parse_cases():
    data = load_json("powerelf-inspection/autoresearch/eval_cases/cases.json")
    evals = []
    for c in data.get("cases", []):
        exp = c.get("expected", {})
        exp_str = "; ".join(f"{k}={v}" for k, v in exp.items()) if exp else ""
        evals.append({
            "id": c["id"],
            "name": f"{c.get('dimension','')}-{c.get('kind','')}",
            "prompt": c.get("fixture", {}).get("rows_desc", "") or c.get("fixture", {}).get("table", ""),
            "expected_output": f"{exp_str} | 理由: {c.get('reason','')}",
        })
    return evals


# ---------- 组装 ----------
def build():
    # 1. early-warning（矩阵题 + 缺号段占位题，合并后按 Q 号排序）
    ew, ew_gaps = parse_early_warning_matrix()
    for qid in PLACEHOLDER_EARLY_WARNING:
        name, prompt, expected = PLACEHOLDER_EARLY_WARNING[qid]
        ew.append({
            "id": f"Q{qid:03d}",
            "name": f"Q{qid}: {name}",
            "prompt": prompt,
            "expected_output": f"{expected}（占位：非原文，按相邻分类补写）",
            "prompt_source": "placeholder-reconstructed",
        })
    ew.sort(key=lambda e: e["id"])
    ew_placeholder_ids = [e["id"] for e in ew if e.get("prompt_source") == "placeholder-reconstructed"]
    # 2. questions.md
    dg_route = parse_questions_md()
    # 3. test-questions.md
    dg_test = parse_test_questions_md()
    # 4. routing v1
    r1 = load_json("skill-creator-workspace/data-governance-routing/evals.json")
    # 5. routing v2
    r2 = load_json("skill-creator-workspace/data-governance-routing/evals-database-v2.json")
    # 6. eval_criteria
    insp_eval = parse_eval_criteria()
    # 7. cases
    insp_cases = parse_cases()
    # 8. darwin
    darwin = load_json("darwin-skill/test-prompts.json")

    sets = [
        {
            "set_id": "early-warning-v3-matrix",
            "phase": "阶段1 预警分析 early-warning-v3",
            "source_files": ["early-warning-v3/tests/test-data-scenarios.md",
                             "early-warning-v3/tests/test-data-complete.sql",
                             "early-warning-v3/tests/test-data-high-risk.sql",
                             "early-warning-v3/tests/test-data-missing-data.sql"],
            "description": "Q1~Q103 场景覆盖矩阵（15 个测试场景）。⚠️ 矩阵跳号：Q36–Q61、Q99–Q101 原文无题面，已按相邻分类补写 29 个占位题面（prompt_source=placeholder-reconstructed，非原文）。",
            "gap_note": "Q36–Q61（26 题，位于『预测预警 Q29–Q35』与『智能综合分析 Q62–Q69』之间）、Q99–Q101（3 题，位于『边界场景 Q94–Q98』与『气象预警 Q102–Q103』之间）在仓库与 git 历史中均无原文题面；本次按 SKILL.md lifecycle/scenarios 真实能力（告警处置/合并去重/升级/恢复与状态机/审计/组合边界）补写占位题面，如需复原原文需回溯原始 hermes 测试会话。",
            "placeholder_count": len(ew_placeholder_ids),
            "placeholder_ids": ew_placeholder_ids,
            "gaps": ew_gaps,
            "evals": ew,
        },
        {
            "set_id": "data-governance-routing-list",
            "phase": "阶段2 数据治理 powerelf-data-governance",
            "source_files": ["powerelf-data-governance/docs/questions.md"],
            "description": "可问/不可问路由清单：46 个正例（覆盖 11 个能力模块）+ 7 条负例（应路由到其他 skill）。",
            "gaps": [],
            "evals": dg_route,
        },
        {
            "set_id": "data-governance-realdata-tests",
            "phase": "阶段2 数据治理 powerelf-data-governance",
            "source_files": ["powerelf-data-governance/docs/test-questions.md"],
            "description": "基于真实库数据（基准日 2026-07-08）的验证题集 T1.1~T11.1，含预期与验证命令。",
            "gaps": [],
            "evals": dg_test,
        },
        {
            "set_id": "routing-evals-v1",
            "phase": "阶段3 路由 skill 评测 v1",
            "source_files": ["skill-creator-workspace/data-governance-routing/evals.json"],
            "description": "路由意图测试 v1（6 题），断言应路由到 powerelf-data-governance。",
            "gaps": [],
            "evals": [{"id": str(e["id"]), "name": e["name"], "prompt": e["prompt"], "expected_output": e["expected_output"]} for e in r1["evals"]],
        },
        {
            "set_id": "routing-evals-v2",
            "phase": "阶段3 路由 skill 评测 v2（45 题）",
            "source_files": ["skill-creator-workspace/data-governance-routing/evals-database-v2.json"],
            "description": "基于真实数据模式的路由测试 v2：MAD/缺失/离线/卡滞/评分/插值/回写/报告/相关性/极端事件/上下文等 45 题，配套 iteration-1/eval-0..44 元数据。",
            "gaps": [],
            "evals": [{"id": str(e["id"]), "name": e["name"], "prompt": e["prompt"], "expected_output": e["expected_output"]} for e in r2["evals"]],
        },
        {
            "set_id": "inspection-eval-criteria",
            "phase": "阶段4 智能巡检 powerelf-inspection",
            "source_files": ["powerelf-inspection/autoresearch/eval_criteria.md"],
            "description": "10 条二元 EVAL（v2 升级版）：8 检出 + 1 无误报 + 1 边界规则完整性。",
            "gaps": [],
            "evals": insp_eval,
        },
        {
            "set_id": "inspection-eval-cases",
            "phase": "阶段4 智能巡检 powerelf-inspection",
            "source_files": ["powerelf-inspection/autoresearch/eval_cases/cases.json"],
            "description": "47 个成对用例：15 维度正/反例（差 1 翻转）+ 质量闸/季节护栏/诊断链/空数据三态。",
            "gaps": [],
            "evals": insp_cases,
        },
        {
            "set_id": "darwin-test-prompts",
            "phase": "阶段5 skill 优化器 darwin-skill",
            "source_files": ["darwin-skill/test-prompts.json"],
            "description": "3 条优化流程引导测试（典型/全量/歧义失败场景）。",
            "gaps": [],
            "evals": [{"id": str(e["id"]), "name": e["scenario"], "prompt": e["prompt"], "expected_output": e["expected"]} for e in darwin],
        },
    ]

    total = sum(len(s["evals"]) for s in sets)
    master = {
        "master_version": "1.0",
        "generated_at": "2026-08-10",
        "base_format": "evals-database-v2.json 规范: {id, name, prompt, expected_output}",
        "summary": {
            "total_questions": total,
            "per_set": {s["set_id"]: len(s["evals"]) for s in sets},
            "known_gaps": {"early-warning-v3-matrix": ew_gaps},
        },
        "sets": sets,
    }
    OUT.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK → {OUT}")
    print(f"总问题数: {total}")
    for s in sets:
        print(f"  {s['set_id']:<34} {len(s['evals']):>4} 题")
    print(f"early-warning 缺口: {len(ew_gaps)} 个 → {ew_gaps[:5]} ... " if ew_gaps else "无缺口")


if __name__ == "__main__":
    build()
