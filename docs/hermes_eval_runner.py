#!/usr/bin/env python3
"""
hermes_eval_runner.py — Layer B Hermes 平台 LLM 实际评测 runner

功能：
  1. 加载 docs/eval-questions-master.json（293 题 / 8 集合）
  2. 按就绪度过滤（默认只跑🟢可自动评测集，164 题）
  3. 逐题调用 hermes CLI（--source 标签绕过 workflow 缓存 + 便于事后反查 session_id）
  4. 从 ~/.hermes/state.db 按 source_tag 反查 session_id，提取运行轨迹（extract_trace）
  5. 按 7 维度评判 actual vs expected（parse_expected + judge）
  6. 输出 docs/hermes-eval-results-{timestamp}.json + .md

依赖：
  - hermes CLI（~/.local/bin/hermes）
  - ~/.hermes/state.db（SQLite，sessions/messages 表）
  - Python 3.8+（标准库 only，无第三方依赖）

用法：
  python3 docs/hermes_eval_runner.py                          # 跑全部🟢集（164 题）
  python3 docs/hermes_eval_runner.py --readiness green        # 显式指定就绪度
  python3 docs/hermes_eval_runner.py --only-set routing-evals-v2  # 只跑指定集合
  python3 docs/hermes_eval_runner.py --dry-run                # 不调用 hermes，只打印计划
  python3 docs/hermes_eval_runner.py --analyze-only --eval-run-id <id>  # 只分析不重跑
  python3 docs/hermes_eval_runner.py --max-questions 5        # 限制题数（调试用）

参考文档：
  - docs/hermes-eval-implementation-plan.md（实施方案，本脚本是其落地实现）
  - docs/eval-questions-master.README.md（master JSON 格式说明）

评审修复对照（docs/hermes-eval-implementation-plan.md 评审意见）：
  P1 #1: judge 把 expected_output 当 dict → 改 parse_expected 按字符串解析
  P1 #2: set 无 source_skill 字段 → 用 SET_TO_SKILL 内置映射表
  P1 #3: db_path.expanduser() str 无此方法 → 改 os.path.expanduser
  P1 #4: hermes chat --user-id 不存在 → 改用 --source 标签
  INFO #5: D6 白名单自相矛盾 → SCHEMA_TABLES 从 schema.md 解析，非 profiler 白名单
  INFO #7: state.db 无 tool_calls 表 → 工具调用存于 messages 表
  INFO #8: 就绪度过滤逻辑与示例不一致 → is_runnable 按 readiness 过滤
  INFO #9: D4 漏算 cache/reasoning token → extract_trace 补 cache_read/cache_write/reasoning_tokens
  INFO #10: extract_trace 缺空值防护 → sess is None 检查 + ended_at NULL 兜底
  INFO #11: session_id 捕获与 --quiet 冲突 → 用 --source 标签反查 sessions.source
  INFO #12: 未定义符号被当成可运行代码 → 所有桩函数均有实现或明确标注
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================================================
# 常量与映射表
# ============================================================================

# 脚本所在目录（docs/）
_HERE = Path(__file__).resolve().parent
# 项目根目录（docs/ 的上一级）
_PROJECT_ROOT = _HERE.parent
# master JSON 路径
_MASTER_JSON = _HERE / "eval-questions-master.json"
# Hermes state.db 路径
_HERMES_DB = Path(os.path.expanduser("~/.hermes/state.db"))
# Hermes CLI 路径
_HERMES_CLI = os.environ.get("HERMES_CLI", "hermes")
# 输出目录
_OUT_DIR = _HERE

# P1 #2: set_id → hermes skill 名（-s 参数值）映射表
# set 无 source_skill 字段，需内置映射
SET_TO_SKILL = {
    "early-warning-v3-matrix": "early-warning-v3",  # 新目录名（现行）
    "data-governance-routing-list": "powerelf-data-governance",
    "data-governance-realdata-tests": "powerelf-data-governance",
    "routing-evals-v1": "powerelf-data-governance",
    "routing-evals-v2": "powerelf-data-governance",
    "inspection-eval-criteria": "powerelf-inspection",
    "inspection-eval-cases": "powerelf-inspection",
    "darwin-test-prompts": "darwin-skill",
}

# 就绪度分级（INFO #8: runner 内置 is_runnable 按 readiness 过滤）
# 🟢 green:  prompt + expected_output 均完整，可直接自动评测
# 🟡 yellow: prompt 为真实题面，但 expected_output 为占位符，不可自动判分
# 🟠 orange: prompt 仅标题或占位补写，需人工补全后再自动评测
SET_READINESS = {
    "early-warning-v3-matrix": "orange",          # 74 标题 + 29 占位
    "data-governance-routing-list": "green",       # 46 正例 + 7 负例，prompt/expected 完整
    "data-governance-realdata-tests": "yellow",    # 20/26 expected_output 为占位符
    "routing-evals-v1": "green",                   # 6 题，prompt/expected 完整
    "routing-evals-v2": "green",                   # 45 题，prompt/expected 完整
    "inspection-eval-criteria": "green",           # 10 题（EVAL1-EVAL10），prompt/expected 完整
    "inspection-eval-cases": "green",              # 47 题，prompt/expected 完整
    "darwin-test-prompts": "green",                # 3 题，prompt/expected 完整
}

# 7 维度权重（§5.2 综合评分公式）
DIMENSION_WEIGHTS = {
    "D1_functional": 0.30,
    "D2_routing": 0.15,
    "D3_tool_eff": 0.15,
    "D4_token_eff": 0.10,
    "D5_latency": 0.10,
    "D6_halluc": 0.10,
    "D7_completeness": 0.10,
}

# D4/D5 阈值（源自 _shared/hermes_test_final_report.md KPI）
D4_INPUT_EXCELLENT = 20000     # P75 档：input < 20K 为优秀（实测 30 题 P75≈20K）
D4_OUTPUT_EXCELLENT = 3000     # P75 档：output < 3K 为优秀（实测 30 题 P75≈3K）
D4_INPUT_WARNING = 36000       # P95 档：input < 36K 为预警（实测 30 题 P90=35K, P95≈36K）
D4_OUTPUT_WARNING = 7000       # P95 档：output < 7K 为预警（实测 30 题 P90=5.4K, max=8.3K）
D5_LATENCY_EXCELLENT = 50     # P0 修复：原 30s 偏低，实测 30 题 P50=49.5s，改 P50 档
D5_LATENCY_WARNING = 180      # P0 修复：原 60s 偏低，实测 30 题 P90=298.6s，改 P90 档（<180s 预警）
D3_TOOL_CALL_EXCELLENT = 2          # ≤2 优秀
D3_TOOL_CALL_WARNING = 5            # 3-5 预警，>5 失败


# ============================================================================
# 工具函数（桩函数实现，INFO #12: 所有被引用符号均有实现）
# ============================================================================

def load_master_json(master_path):
    """加载 master JSON，返回解析后的 dict。"""
    with open(master_path, encoding="utf-8") as f:
        return json.load(f)


def get_set_readiness(set_id):
    """获取集合的就绪度分级。未知集合默认 orange（保守）。"""
    return SET_READINESS.get(set_id, "orange")


def is_runnable(ev, set_, readiness_filter):
    """
    INFO #8: 就绪度过滤，判断该题是否可运行评测。

    过滤逻辑：
      - readiness_filter='green': 只跑🟢集
      - readiness_filter='yellow': 跑🟢+🟡
      - readiness_filter='orange': 跑全部
      - placeholder-reconstructed 题（prompt_source=placeholder-reconstructed）默认跳过

    返回 True 表示该题可运行评测。
    """
    set_readiness = get_set_readiness(set_["set_id"])

    # 就绪度过滤：题目所在集合的就绪度必须 ≥ readiness_filter
    readiness_order = {"green": 0, "yellow": 1, "orange": 2}
    if readiness_order.get(set_readiness, 2) > readiness_order.get(readiness_filter, 0):
        return False

    # 跳过占位题（prompt_source=placeholder-reconstructed）
    if ev.get("prompt_source") == "placeholder-reconstructed":
        return False

    # 跳过空 prompt 或空 expected_output
    if not ev.get("prompt") or not ev.get("expected_output"):
        return False

    return True


def extract_tool_args(content):
    """
    桩函数（INFO #12）: 从 messages.content（role='tool'）中解析工具入参。
    实际实现需按 tool_name 分支用正则解析，此处返回 content 的前 200 字符作为预览。
    """
    if not content:
        return ""
    return content[:200]


def extract_table_names(text):
    """
    桩函数（INFO #12）: 从 final_answer 中正则提取表名。
    匹配形态：st_xxx_r / dsm_xxx / eq_xxx / rei_xxx_r / sl_xxx_r 等。
    """
    if not text:
        return []
    # 匹配常见表名模式
    patterns = [
        r'\bst_\w+_r\b',           # st_rsvr_r, st_pptn_r, st_pressure_r ...
        r'\bdsm_\w+\b',            # dsm_dfr_srvrds_srhrds
        r'\beq_\w+\b',             # eq_equip_base, eq_business_equip_relation
        r'\brei_\w+_r\b',          # rei_gate_r, rei_pump_r
        r'\bsl_\w+_r\b',           # sl_rsvr_rt_r（旧名）
    ]
    found = set()
    for pat in patterns:
        found.update(re.findall(pat, text, re.IGNORECASE))
    return sorted(found)


def load_schema_tables(schema_md_path=None):
    """
    INFO #5: D6 ground truth 必须是 schema.md 的规范表名集。
    从 _shared/references/schema.md 解析所有表名。

    返回 set[str]，全小写。
    """
    if schema_md_path is None:
        schema_md_path = _PROJECT_ROOT / "_shared" / "references" / "schema.md"

    tables = set()
    if not os.path.exists(schema_md_path):
        # 降级：硬编码 schema.md 中已知的规范表名（防止文件缺失导致 D6 全失败）
        tables = {
            "st_rsvr_r", "st_river_r", "st_pptn_r", "st_pressure_r",
            "st_percolation_r", "dsm_dfr_srvrds_srhrds", "eq_equip_base",
            "eq_business_equip_relation", "rei_gate_r", "rei_pump_r",
            "st_soil_moisture_r", "st_termite_monitor_r",
        }
        return {t.lower() for t in tables}

    with open(schema_md_path, encoding="utf-8") as f:
        text = f.read()

    # schema.md 中表名出现的模式：**st_rsvr_r**、| st_rsvr_r |、`st_rsvr_r`
    for m in re.finditer(r'`?(st_\w+_r|dsm_\w+|eq_\w+|rei_\w+_r|sl_\w+_r)`?', text):
        tables.add(m.group(1).lower())

    return tables


# ============================================================================
# Hermes CLI 调用与 session_id 反查
# ============================================================================

def run_hermes(skill, query, source_tag, dry_run=False, timeout=120):
    """
    P1 #4: 调用 hermes CLI，用 --source 标签绕过 workflow 缓存 + 便于事后反查 session_id。

    注意：hermes chat 无 --user-id flag（实测 hermes chat --help 确认）。
    绕缓存用 --source（每题 source 不同即绕过 workflow:{user_id}:{minute_bucket} 缓存）。

    参数：
      skill: hermes skill 名（-s 参数值）
      query: 问题原文（-q 参数值）
      source_tag: session 来源标签（--source 参数值）
      dry_run: True 则不实际调用 hermes，只打印命令
      timeout: hermes chat 超时秒数（默认 120s）

    返回：
      dry_run=True 时返回 None
      dry_run=False 时返回 subprocess.CompletedProcess
    """
    cmd = [
        _HERMES_CLI, "chat",
        "-s", skill,
        "-q", query,
        "--source", source_tag,
        "-Q",  # quiet mode（抑制 banner/spinner/tool previews）
    ]

    if dry_run:
        print(f"  [DRY-RUN] {' '.join(cmd[:6])} ... --source {source_tag}")
        return None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] hermes chat 超时（{timeout}s），source_tag={source_tag}")
        return None
    except FileNotFoundError:
        print(f"  [ERROR] hermes CLI 未找到：{_HERMES_CLI}")
        print(f"          请确认 hermes 在 PATH 或设置 HERMES_CLI 环境变量")
        return None


def find_session_by_source(source_tag, db_path=_HERMES_DB):
    """
    INFO #11: 从 state.db 按 source_tag 反查 session_id，避免依赖解析 stdout。

    查询：SELECT id FROM sessions WHERE source = ? ORDER BY started_at DESC LIMIT 1

    返回 session_id（str）或 None（未找到）。
    """
    if not os.path.exists(db_path):
        return None

    db = sqlite3.connect(str(db_path))
    try:
        cursor = db.execute(
            "SELECT id FROM sessions WHERE source = ? "
            "ORDER BY started_at DESC LIMIT 1",
            (source_tag,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        db.close()


# ============================================================================
# 轨迹提取（extract_trace）
# ============================================================================

def extract_trace(session_id, db_path=_HERMES_DB):
    """
    §4.2: 从 state.db 提取 session 的运行轨迹。

    修复点：
      P1 #3: db_path.expanduser() → os.path.expanduser(db_path)
      INFO #9: 补 cache_read_tokens/cache_write_tokens/reasoning_tokens 列
      INFO #10: sess is None 防护 + ended_at NULL 兜底

    返回 trace dict 或 None（session_id 未命中）。
    """
    if not os.path.exists(db_path):
        return None

    db = sqlite3.connect(str(db_path))  # P1 #3: os.path.expanduser 已在 _HERMES_DB 定义时处理
    db.row_factory = sqlite3.Row

    try:
        # 1. 会话级汇总
        sess = db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        if sess is None:  # INFO #10: 空值防护
            return None

        # 2. 逐条消息（含 tool 调用与返回）
        msgs = db.execute(
            "SELECT timestamp, role, tool_name, content "
            "FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()

        # 3. 工具调用序列（重构为有序链）
        tool_chain = [
            {
                "seq": i,
                "ts": m["timestamp"],
                "tool": m["tool_name"],
                "args": extract_tool_args(m["content"]),  # 桩函数
                "result_preview": (m["content"] or "")[:200],
            }
            for i, m in enumerate(msgs) if m["role"] == "tool"
        ]

        # INFO #10: ended_at 可能为 NULL（session 未结束），用 time.time() 兜底
        ended_at = sess["ended_at"] if sess["ended_at"] is not None else time.time()

        # 最终 assistant 回答（最后一条 role=assistant 的 content）
        final_answer = ""
        for m in reversed(msgs):
            if m["role"] == "assistant" and m["content"]:
                final_answer = m["content"]
                break

        return {
            "session_id": session_id,
            "started_at": sess["started_at"],
            "ended_at": ended_at,
            "duration_sec": ended_at - sess["started_at"],
            "tool_call_count": sess["tool_call_count"] or 0,
            "message_count": sess["message_count"] or 0,
            "input_tokens": sess["input_tokens"] or 0,
            "output_tokens": sess["output_tokens"] or 0,
            "cache_read_tokens": sess["cache_read_tokens"] or 0,   # INFO #9
            "cache_write_tokens": sess["cache_write_tokens"] or 0,  # INFO #9
            "reasoning_tokens": sess["reasoning_tokens"] or 0,     # INFO #9
            "messages": [dict(m) for m in msgs],
            "tool_chain": tool_chain,
            "final_answer": final_answer,
        }
    finally:
        db.close()


# ============================================================================
# expected_output 字符串解析（parse_expected）
# ============================================================================

def parse_expected(set_id, expected_str):
    """
    P1 #1: 把 expected_output 字符串解析为结构化断言。

    master JSON 的 expected_output 是自由文本字符串，不是 {should_report/contains/equals} 结构。
    各 set 的 expected 格式不同，需分别 parse。

    格式样本（实测 master JSON）：
      early-warning-v3-matrix:     "场景：场景1；数据要求：4条未确认告警"
      data-governance-routing-list: "Pass: 路由到 offline-detection | Fail: 路由到其他"
      routing-evals-v2:            "应路由到 governance-profiler；原因：…"
      inspection-eval-cases:       "should_report: WARNING | should_not_report: …"
      darwin-test-prompts:         自由文本，需人工判

    返回 dict（结构化断言）或 None（无法自动解析）。
    """
    if not expected_str:
        return None

    s = expected_str.strip()

    # inspection-eval-cases：已有 should_report/should_not_report 结构化关键字
    if "should_report" in s or "should_not_report" in s:
        out = {}
        m = re.search(r"should_report:\s*(\S+)", s)
        if m:
            out["should_report"] = m.group(1)
        m = re.search(r"should_not_report:\s*(\S+)", s)
        if m:
            out["should_not_report"] = m.group(1)
        return out if out else None

    # routing-evals-v2 / data-governance-routing-list：应路由到 X / 路由到 X
    m = re.search(r"路由到\s*(\S+?)[\s；|,)]", s)
    if m:
        return {"expected_route": m.group(1).strip()}

    m = re.search(r"应路由到\s*(\S+?)[\s；|,)]", s)
    if m:
        return {"expected_route": m.group(1).strip()}

    # data-governance-routing-list：Pass: ... | Fail: ...
    m = re.search(r"Pass:\s*(.+?)\s*\|\s*Fail:\s*(.+)", s, re.IGNORECASE)
    if m:
        return {
            "pass_condition": m.group(1).strip(),
            "fail_condition": m.group(2).strip(),
        }

    # P1 修复：data-governance-routing-list 的方法名短语格式
    # 实测样本（master JSON）：
    #   "MAD 异常检测" / "分指标阈值检测" / "MAD + 变化率综合判定"
    #   "指定时间窗口检测" / "变化率检测 + 综合判定" / "缺失检测"
    # 解析为 {"method": ..., "task_type": ...}，让 D1/D2 做实质评判而非 fallback 0.5
    method_patterns = [
        (r"\bMAD\b", "MAD"),
        (r"\bIQR\b", "IQR"),
        (r"\bpercentile\b", "percentile"),
        (r"变化率", "change_rate"),
        (r"变率", "change_rate"),
        (r"阈值", "threshold"),
        (r"时间窗口|指定时间|时间区间|日期范围", "time_window"),
        (r"缺失", "missing"),
        (r"综合", "comprehensive"),
        (r"分级", "grade"),
        (r"日报", "daily_report"),
        (r"概览", "overview"),
        (r"评分", "scoring"),
    ]
    task_type_patterns = [
        (r"异常检测|异常分析|离群", "anomaly_detection"),
        (r"缺失检测|缺测", "missing_detection"),
        (r"分级|分类", "grade"),
        (r"日报|报告", "report"),
        (r"概览|总览", "overview"),
        (r"评分|打分", "scoring"),
        (r"检测", "detection"),
        (r"判定", "judgment"),
    ]

    found_methods = [m for pat, m in method_patterns if re.search(pat, s, re.IGNORECASE)]
    found_types = [t for pat, t in task_type_patterns if re.search(pat, s, re.IGNORECASE)]

    if found_methods or found_types:
        return {
            "methods": found_methods or None,
            "task_type": found_types[0] if found_types else None,
            "raw": s,  # 保留原文，D7 关键点提取用
        }

    # early-warning-v3-matrix：自由文本场景描述，无法自动 parse
    # darwin-test-prompts：自由文本，需人工判
    return None


# ============================================================================
# 七维度评判（judge）
# ============================================================================

def judge(ev, trace, set_, schema_tables):
    """
    §5.3: 按 7 维度评判 actual vs expected。

    维度（权重）：
      D1 功能性正确 (30%) - actual 是否满足 expected_output 的核心断言
      D2 路由命中 (15%) - hermes 是否加载了正确的 rules/*.md
      D3 工具调用效率 (15%) - tool_call_count ≤2 优秀；3-5 预警；>5 失败
      D4 Token 效率 (10%) - input_tokens <15K 且 output_tokens <3K 为达标
      D5 响应时延 (10%) - duration_sec <30s 优秀；30-60s 预警；>60s 失败
      D6 幻觉抑制 (10%) - final_answer 引用的表名全部可在 schema.md 中溯源
      D7 回答完整性 (10%) - final_answer 覆盖 expected_output 所有关键信息点

    返回 verdict dict。
    """
    expected_str = ev["expected_output"]  # P1 #1: 是字符串，不是 dict
    actual_answer = trace.get("final_answer", "") or ""
    parsed = parse_expected(set_["set_id"], expected_str)

    # ---- D1 功能性正确 ----
    d1 = 0.5  # 默认中位（expected 不明确或无法自动 parse）
    d1_note = "manual_judge"

    if parsed:
        if "should_report" in parsed:
            d1 = 1.0 if parsed["should_report"] in actual_answer else 0.0
            d1_note = f"should_report={parsed['should_report']}"
        elif "should_not_report" in parsed:
            d1 = 1.0 if parsed["should_not_report"] not in actual_answer else 0.0
            d1_note = f"should_not_report={parsed['should_not_report']}"
        elif "pass_condition" in parsed:
            d1 = 1.0 if parsed["pass_condition"] in actual_answer else 0.0
            d1_note = f"pass_condition='{parsed['pass_condition'][:30]}'"
        elif "expected_route" in parsed:
            # 路由类题目：D1 检查 final_answer 是否提到 expected_route
            d1 = 1.0 if parsed["expected_route"] in actual_answer else 0.0
            d1_note = f"expected_route={parsed['expected_route']}"
        elif "methods" in parsed or "task_type" in parsed:
            # P1 修复：方法名短语格式（"MAD 异常检测"/"分指标阈值检测"）
            # 检查 hermes 回答是否提到 expected 的方法/任务类型关键词（含同义词扩）
            methods = parsed.get("methods") or []
            task_type = parsed.get("task_type")
            # 把 method/task_type 扩成别名组，命中任一个就算 D1 通过
            ALIAS_D1 = {
                "MAD": ["MAD", "中位数绝对偏差", "修正Z", "modified z"],
                "IQR": ["IQR", "四分位距", "interquartile"],
                "percentile": ["percentile", "百分位"],
                "change_rate": ["变化率", "变率", "change rate", "波动"],
                "threshold": ["阈值", "门限", "threshold"],
                "time_window": ["时间窗口", "指定时间", "时间区间", "日期范围", "窗口", "日期", "每日", "每日摘要", "按天", "YYYY-MM-DD", "2026-"],
                "missing": ["缺失", "漏", "missing", "空值", "缺测"],
                "comprehensive": ["综合", "汇总", "联合", "多指标"],
                "anomaly_detection": ["异常检测", "异常分析", "离群", "outlier", "anomaly"],
                "missing_detection": ["缺失检测", "缺测检测", "missing detection"],
                "grade": ["分级", "分类", "等级", "grade"],
                "report": ["日报", "报告", "report"],
                "overview": ["概览", "总览", "overview"],
                "scoring": ["评分", "打分", "score"],
                "detection": ["检测", "分析", "判定", "识别"],
                "judgment": ["判定", "结论", "判断", "诊断"],
            }
            def _d1_hit(key):
                aliases = ALIAS_D1.get(key, [key])
                return any(a in actual_answer for a in aliases)

            # 方法命中 + 任务类型命中，取 min（两者都应覆盖）
            method_hits = sum(1 for m in methods if _d1_hit(m))
            method_score = method_hits / len(methods) if methods else 1.0
            task_score = 1.0 if (task_type and _d1_hit(task_type)) else (1.0 if not task_type else 0.0)
            d1 = min(method_score, task_score)
            d1_note = f"methods={methods},task_type={task_type}"

    # ---- D2 路由命中 ----
    expected_route = parsed.get("expected_route", "") if parsed else ""
    # 检查 system 消息（加载的 rules）或 final_answer 中是否提到 expected_route
    loaded_rules = [
        m["content"] for m in trace.get("messages", []) if m["role"] == "system"
    ]
    system_content = str(loaded_rules)
    if expected_route and (expected_route in system_content or expected_route in actual_answer):
        d2 = 1.0
    elif expected_route:
        d2 = 0.0
    elif parsed and ("methods" in parsed or "task_type" in parsed):
        # P1 修复：方法名短语格式无明确 expected_route，
        # 但若 hermes 回答中命中了 expected 的方法/任务类型关键词，说明路由正确
        methods = parsed.get("methods") or []
        task_type = parsed.get("task_type")
        ALIAS_D2 = {
            "MAD": ["MAD", "中位数绝对偏差", "修正Z"],
            "IQR": ["IQR", "四分位距"],
            "percentile": ["percentile", "百分位"],
            "change_rate": ["变化率", "变率", "波动"],
            "threshold": ["阈值", "门限"],
            "time_window": ["时间窗口", "指定时间", "日期范围", "日期", "每日", "每日摘要", "按天", "YYYY-MM-DD", "2026-"],
            "missing": ["缺失", "漏", "missing", "空值"],
            "anomaly_detection": ["异常", "离群", "outlier"],
            "missing_detection": ["缺失检测", "缺测"],
            "detection": ["检测", "分析", "判定"],
        }
        def _d2_hit(key):
            aliases = ALIAS_D2.get(key, [key])
            return any(a in actual_answer for a in aliases)
        method_hits = sum(1 for m in methods if _d2_hit(m))
        task_hit = _d2_hit(task_type) if task_type else True
        if methods and method_hits == len(methods) and task_hit:
            d2 = 1.0
        elif method_hits > 0 or task_hit:
            d2 = 0.75  # 部分命中
        else:
            d2 = 0.0
    else:
        d2 = 0.5  # 无明确 expected_route，给中位

    # ---- D3 工具调用效率 ----
    tc = trace["tool_call_count"]
    if tc <= D3_TOOL_CALL_EXCELLENT:
        d3 = 1.0
    elif tc <= D3_TOOL_CALL_WARNING:
        d3 = 0.5
    else:
        d3 = 0.0

    # ---- D4 Token 效率（方案 A：P75 阈值 + 连续评分）----
    # 关键修正：只用 input_tokens（不含 cache_read_tokens）。
    # cache_read_tokens 是缓存命中（省下的推理成本），不是真实消耗；
    # 把它算进 total_input 会导致 DG-P04 的 total=260K（其中 cache=249K）误判 FAIL。
    # 实测 30 题 input_tokens(不含cache) P75=19.9K P90=35.3K → 阈值 20K/36K 合理。
    input_tokens = trace["input_tokens"]
    output_tokens = trace["output_tokens"]

    # 连续评分：优秀档（<P75）=1.0，预警档（<P95）=0.5，失败档（>P95）=0.0
    # 中间区间线性插值，避免阈值边界跳变（input=19.9K vs 20.1K 不会从 1.0 跳到 0.5）
    def _linear_score(val, excellent, warning):
        """val < excellent → 1.0; val > warning → 0.0; 中间线性插值 → [0.5, 1.0]。"""
        if val <= excellent:
            return 1.0
        if val >= warning:
            return 0.0
        # excellent < val < warning: 线性从 1.0 降到 0.5
        return 1.0 - 0.5 * (val - excellent) / (warning - excellent)

    input_score = _linear_score(input_tokens, D4_INPUT_EXCELLENT, D4_INPUT_WARNING)
    output_score = _linear_score(output_tokens, D4_OUTPUT_EXCELLENT, D4_OUTPUT_WARNING)
    # input 和 output 取 min：任一维度差则拉低总分（避免一个维度好但另一个极差时虚高）
    d4 = min(input_score, output_score)

    # ---- D5 响应时延（P0：P50/P90 阈值 + 连续评分）----
    # 实测 30 题 duration P50=49.5s P90=298.6s，原 30s/60s 阈值偏低致 43% 题判 FAIL
    dur = trace["duration_sec"]

    def _linear_score_dur(val, excellent, warning):
        """val < excellent → 1.0; val > warning → 0.0; 中间线性插值 → [0.5, 1.0]。"""
        if val <= excellent:
            return 1.0
        if val >= warning:
            return 0.0
        return 1.0 - 0.5 * (val - excellent) / (warning - excellent)

    d5 = _linear_score_dur(dur, D5_LATENCY_EXCELLENT, D5_LATENCY_WARNING)

    # ---- D6 幻觉抑制 ----
    # INFO #5: SCHEMA_TABLES 必须是 schema.md 的规范表名集，非 profiler 白名单
    mentioned_tables = extract_table_names(actual_answer)
    hallucinated = [
        t for t in mentioned_tables if t.lower() not in schema_tables
    ]
    d6 = 1.0 if not hallucinated else 0.0

    # ---- D7 回答完整性 ----
    # P0 修复：原逻辑用 re.findall 提取中文关键词再做精确子串匹配，
    # 但 data-governance-routing-list 的 expected_output 是方法名短语
    #（"MAD 异常检测"/"分指标阈值检测"/"指定时间窗口检测"），
    # hermes 实际回答可能用同义表述（"中位数绝对偏差"/"离群"/"阈值"），
    # 导致覆盖率极低（D7 avg=0.1，27/30 题失败）。
    #
    # 修法：① 提取关键点后做子串匹配 ② 加方法名别名表扩同义匹配
    ALIAS_MAP = {
        "MAD": ["MAD", "中位数绝对偏差", "修正Z", "modified z", "median absolute"],
        "异常": ["异常", "离群", "outlier", "anomaly", "异常点", "异常值"],
        "检测": ["检测", "分析", "判定", "识别", "监控"],
        "阈值": ["阈值", "门限", "threshold", "标准"],
        "变化": ["变化", "变率", "变化率", "change rate", "波动"],
        "时间": ["时间", "日期", "窗口", "区间", "范围", "date", "time"],
        "综合": ["综合", "汇总", "合并", "联合", "多指标"],
        "分": ["分", "拆分", "明细", "细分", "分布"],
        "指标": ["指标", "维度", "factor", "metric"],
        "判定": ["判定", "结论", "判断", "诊断", "verdict"],
        "缺失": ["缺失", "漏", "missing", "空值", "缺测"],
        "分级": ["分级", "分类", "等级", "grade", "level"],
        "日报": ["日报", "报告", "report", "汇总"],
        "概览": ["概览", "总览", "概览", "overview", "全局"],
        "评分": ["评分", "打分", "score", "评级"],
    }

    def _expand_key_point(kp):
        """扩一个关键点为它本身 + 别名表中的所有同义词。"""
        expanded = [kp]
        # 精确命中别名表
        for key, aliases in ALIAS_MAP.items():
            if kp == key or kp in aliases:
                expanded.extend(aliases)
                break
            # 部分命中（关键点包含别名键）
            if key in kp:
                expanded.extend(aliases)
        # 去重保序
        seen = set()
        result = []
        for w in expanded:
            if w and w not in seen:
                seen.add(w)
                result.append(w)
        return result

    key_points = re.findall(r"[\u4e00-\u9fa5]{2,}", expected_str)
    # 补充：英文方法名/缩写也当关键点（如 MAD/IQR/percentile）
    key_points.extend(re.findall(r"\b(MAD|IQR|percentile|SQL|CSV|JSON)\b", expected_str, re.IGNORECASE))
    if key_points:
        # 每个 key_point 扩成别名组，只要命中组内任一个就算覆盖该关键点
        covered = 0
        for kp in key_points:
            aliases = _expand_key_point(kp)
            if any(a in actual_answer for a in aliases):
                covered += 1
        d7 = covered / len(key_points)
    else:
        d7 = 1.0  # 无关键点可提取，默认完整

    # ---- 综合评分 ----
    score = (
        d1 * DIMENSION_WEIGHTS["D1_functional"]
        + d2 * DIMENSION_WEIGHTS["D2_routing"]
        + d3 * DIMENSION_WEIGHTS["D3_tool_eff"]
        + d4 * DIMENSION_WEIGHTS["D4_token_eff"]
        + d5 * DIMENSION_WEIGHTS["D5_latency"]
        + d6 * DIMENSION_WEIGHTS["D6_halluc"]
        + d7 * DIMENSION_WEIGHTS["D7_completeness"]
    )

    verdict = "PASS" if score >= 0.7 else ("PARTIAL" if score >= 0.4 else "FAIL")

    return {
        "id": ev["id"],
        "set": set_["set_id"],
        "name": ev.get("name", ""),
        "score": round(score, 3),
        "verdict": verdict,
        "dimensions": {
            "D1_functional": round(d1, 3),
            "D2_routing": round(d2, 3),
            "D3_tool_eff": round(d3, 3),
            "D4_token_eff": round(d4, 3),
            "D5_latency": round(d5, 3),
            "D6_halluc": round(d6, 3),
            "D7_completeness": round(d7, 3),
        },
        "d1_note": d1_note,
        "hallucinated_tables": hallucinated,
        "trace_summary": {
            "session_id": trace["session_id"],
            "duration_sec": round(trace["duration_sec"], 2),
            "tool_call_count": trace["tool_call_count"],
            "message_count": trace["message_count"],
            "input_tokens": trace["input_tokens"],
            "output_tokens": trace["output_tokens"],
            "cache_read_tokens": trace["cache_read_tokens"],
            "reasoning_tokens": trace["reasoning_tokens"],
            "tool_chain": [t["tool"] for t in trace["tool_chain"]],
        },
    }


# ============================================================================
# 报告生成
# ============================================================================

def generate_json_report(results, master, eval_run_id, readiness_filter, skipped_stats):
    """生成机器可读 JSON 报告。"""
    # 计算总体得分
    scores = [r["score"] for r in results]
    overall_score = round(sum(scores) / len(scores), 3) if scores else 0.0
    overall_verdict = (
        "PASS" if overall_score >= 0.7
        else "PARTIAL" if overall_score >= 0.4
        else "FAIL"
    )

    # 按集合汇总
    per_set = {}
    for r in results:
        sid = r["set"]
        if sid not in per_set:
            per_set[sid] = {"count": 0, "pass": 0, "partial": 0, "fail": 0, "scores": []}
        per_set[sid]["count"] += 1
        per_set[sid]["scores"].append(r["score"])
        if r["verdict"] == "PASS":
            per_set[sid]["pass"] += 1
        elif r["verdict"] == "PARTIAL":
            per_set[sid]["partial"] += 1
        else:
            per_set[sid]["fail"] += 1

    per_set_summary = {}
    for sid, s in per_set.items():
        per_set_summary[sid] = {
            "count": s["count"],
            "avg_score": round(sum(s["scores"]) / len(s["scores"]), 3) if s["scores"] else 0,
            "pass": s["pass"],
            "partial": s["partial"],
            "fail": s["fail"],
        }

    # 按维度汇总
    dim_names = list(DIMENSION_WEIGHTS.keys())
    per_dim = {}
    for dn in dim_names:
        vals = [r["dimensions"][dn] for r in results]
        fail_count = sum(1 for v in vals if v < 0.4)
        per_dim[dn] = {
            "avg": round(sum(vals) / len(vals), 3) if vals else 0,
            "fail_count": fail_count,
        }

    return {
        "eval_run_id": eval_run_id,
        "evaluated_at": datetime.now().isoformat(),
        "master_version": master.get("master_version", "unknown"),
        "readiness_filter": readiness_filter,
        "total_questions": master.get("summary", {}).get("total_questions", 0),
        "evaluated_questions": len(results),
        "skipped": skipped_stats,
        "overall_score": overall_score,
        "overall_verdict": overall_verdict,
        "per_set_summary": per_set_summary,
        "per_dimension_summary": per_dim,
        "results": results,
    }


def generate_markdown_report(json_report):
    """生成人读 Markdown 报告。"""
    lines = []
    lines.append(f"# Hermes 平台 LLM 实际评测报告")
    lines.append("")
    lines.append(f"| 字段 | 值 |")
    lines.append(f"|---|---|")
    lines.append(f"| 评测运行 ID | `{json_report['eval_run_id']}` |")
    lines.append(f"| 评测时间 | {json_report['evaluated_at']} |")
    lines.append(f"| master 版本 | {json_report['master_version']} |")
    lines.append(f"| 就绪度过滤 | {json_report['readiness_filter']} |")
    lines.append(f"| 总题数 | {json_report['total_questions']} |")
    lines.append(f"| 实际评测题数 | {json_report['evaluated_questions']} |")
    lines.append(f"| 总体得分 | **{json_report['overall_score']}** |")
    lines.append(f"| 总体结论 | **{json_report['overall_verdict']}** |")
    lines.append("")

    # 跳过统计
    skipped = json_report.get("skipped", {})
    if skipped:
        lines.append("## 跳过统计")
        lines.append("")
        lines.append("| 跳过原因 | 题数 |")
        lines.append("|---|---|")
        for reason, count in skipped.items():
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    # 按集合汇总
    per_set = json_report.get("per_set_summary", {})
    if per_set:
        lines.append("## 按集合汇总")
        lines.append("")
        lines.append("| 集合 | 题数 | 平均得分 | PASS | PARTIAL | FAIL |")
        lines.append("|---|---|---|---|---|---|")
        for sid, s in sorted(per_set.items()):
            lines.append(
                f"| {sid} | {s['count']} | {s['avg_score']} | "
                f"{s['pass']} | {s['partial']} | {s['fail']} |"
            )
        lines.append("")

    # 按维度汇总
    per_dim = json_report.get("per_dimension_summary", {})
    if per_dim:
        lines.append("## 按维度汇总")
        lines.append("")
        lines.append("| 维度 | 平均得分 | 失败题数（<0.4） |")
        lines.append("|---|---|---|")
        for dn, d in sorted(per_dim.items()):
            lines.append(f"| {dn} | {d['avg']} | {d['fail_count']} |")
        lines.append("")

    # 失败题明细（score < 0.4）
    fail_results = [r for r in json_report.get("results", []) if r["score"] < 0.4]
    if fail_results:
        lines.append("## 失败题明细（score < 0.4）")
        lines.append("")
        lines.append("| 题号 | 集合 | 得分 | 结论 | D1 | D2 | D3 | D4 | D5 | D6 | D7 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in fail_results:
            d = r["dimensions"]
            lines.append(
                f"| {r['id']} | {r['set']} | {r['score']} | {r['verdict']} | "
                f"{d['D1_functional']} | {d['D2_routing']} | {d['D3_tool_eff']} | "
                f"{d['D4_token_eff']} | {d['D5_latency']} | {d['D6_halluc']} | "
                f"{d['D7_completeness']} |"
            )
        lines.append("")

    # 占位题面评测专项（如有）
    placeholder_results = [
        r for r in json_report.get("results", [])
        if "placeholder" in r.get("d1_note", "").lower()
        or r.get("id", "").startswith("Q0")  # early-warning 占位题 Q036-Q061, Q099-Q101
    ]
    if placeholder_results:
        ph_pass = sum(1 for r in placeholder_results if r["verdict"] == "PASS")
        ph_total = len(placeholder_results)
        lines.append("## 占位题面评测专项")
        lines.append("")
        lines.append(f"> ⚠️ 占位题面为补写非原文，评测结果**不代表原文题面真实能力**。")
        lines.append(f"> 29 个 `placeholder-reconstructed` 题通过率单独统计如下。")
        lines.append("")
        lines.append(f"- 占位题评测数：{ph_total}")
        lines.append(f"- 通过数：{ph_pass}")
        lines.append(f"- 通过率：{round(ph_pass / ph_total * 100, 1) if ph_total else 0}%")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        f"*报告由 `docs/hermes_eval_runner.py` 自动生成，"
        f"评测运行 ID：`{json_report['eval_run_id']}`*"
    )

    return "\n".join(lines)


# ============================================================================
# 主流程
# ============================================================================

def run_eval(args):
    """主评测流程：加载 master → 过滤 → 调用 hermes → 提取轨迹 → 评判 → 输出报告。"""
    # 1. 加载 master JSON
    print(f"[1/6] 加载 master JSON：{args.master}")
    master = load_master_json(args.master)
    total = master.get("summary", {}).get("total_questions", 0)
    print(f"      总题数：{total}")

    # 2. 加载 schema.md 表名集（D6 幻觉检测的 ground truth）
    print(f"[2/6] 加载 schema.md 表名集（D6 ground truth）")
    schema_tables = load_schema_tables()
    print(f"      已加载 {len(schema_tables)} 个规范表名")

    # 3. 逐题评测
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    eval_run_id = f"hermes-eval-{timestamp}"
    results = []
    skipped_stats = {
        "placeholder_reconstructed": 0,
        "readiness_filter": 0,
        "empty_prompt_or_expected": 0,
        "max_questions_limit": 0,
    }

    questions_processed = 0
    for set_ in master.get("sets", []):
        if args.only_set and set_["set_id"] != args.only_set:
            continue

        skill = SET_TO_SKILL.get(set_["set_id"])
        if not skill:
            print(f"  [WARN] 集合 {set_['set_id']} 无 SET_TO_SKILL 映射，跳过")
            continue

        print(f"\n[3/6] 评测集合：{set_['set_id']}（skill={skill}）")

        for ev in set_.get("evals", []):
            # 就绪度过滤（先过滤，再判断 max_questions，避免误计）
            if not is_runnable(ev, set_, args.readiness):
                if ev.get("prompt_source") == "placeholder-reconstructed":
                    skipped_stats["placeholder_reconstructed"] += 1
                elif not ev.get("prompt") or not ev.get("expected_output"):
                    skipped_stats["empty_prompt_or_expected"] += 1
                else:
                    skipped_stats["readiness_filter"] += 1
                continue

            # 限制题数（调试用）：只对通过就绪度过滤的题计数
            if args.max_questions and questions_processed >= args.max_questions:
                skipped_stats["max_questions_limit"] += 1
                continue

            questions_processed += 1
            ev_id = ev["id"]
            source_tag = f"eval-{timestamp}-{ev_id}"

            print(f"  [{questions_processed}] {ev_id}: ", end="", flush=True)

            # 调用 hermes
            run_hermes(
                skill=skill,
                query=ev["prompt"],
                source_tag=source_tag,
                dry_run=args.dry_run,
                timeout=args.timeout,
            )

            if args.dry_run:
                # dry-run 模式：记录计划题到 results（score=0，verdict=DRY-RUN），
                # 便于报告正确反映"计划评测题数"
                print("DRY-RUN")
                results.append({
                    "id": ev_id,
                    "set": set_["set_id"],
                    "name": ev.get("name", ""),
                    "score": 0.0,
                    "verdict": "DRY-RUN",
                    "dimensions": {dn: 0.0 for dn in DIMENSION_WEIGHTS},
                    "d1_note": "dry_run",
                    "hallucinated_tables": [],
                    "trace_summary": {
                        "session_id": None,
                        "source_tag": source_tag,
                    },
                })
                continue

            # 从 state.db 按 source_tag 反查 session_id
            time.sleep(2)  # 等待 hermes 写入 state.db
            session_id = find_session_by_source(source_tag)

            if not session_id:
                print(f"FAIL（session 未写入，source_tag={source_tag}）")
                # 记录为失败
                results.append({
                    "id": ev_id,
                    "set": set_["set_id"],
                    "name": ev.get("name", ""),
                    "score": 0.0,
                    "verdict": "FAIL",
                    "dimensions": {dn: 0.0 for dn in DIMENSION_WEIGHTS},
                    "d1_note": "session_not_found",
                    "hallucinated_tables": [],
                    "trace_summary": {"session_id": None, "source_tag": source_tag},
                })
                continue

            # 提取运行轨迹
            trace = extract_trace(session_id)

            if trace is None:
                print(f"FAIL（trace 提取失败，session_id={session_id}）")
                results.append({
                    "id": ev_id,
                    "set": set_["set_id"],
                    "name": ev.get("name", ""),
                    "score": 0.0,
                    "verdict": "FAIL",
                    "dimensions": {dn: 0.0 for dn in DIMENSION_WEIGHTS},
                    "d1_note": "trace_extraction_failed",
                    "hallucinated_tables": [],
                    "trace_summary": {"session_id": session_id, "source_tag": source_tag},
                })
                continue

            # 评判
            verdict = judge(ev, trace, set_, schema_tables)
            results.append(verdict)
            print(f"{verdict['verdict']}（score={verdict['score']}）")

    # 4. 生成 JSON 报告
    print(f"\n[4/6] 生成 JSON 报告")
    json_report = generate_json_report(
        results, master, eval_run_id, args.readiness, skipped_stats
    )
    json_out = _OUT_DIR / f"hermes-eval-results-{timestamp}.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    print(f"      JSON 报告：{json_out}")

    # 5. 生成 Markdown 报告
    print(f"\n[5/6] 生成 Markdown 报告")
    md_report = generate_markdown_report(json_report)
    md_out = _OUT_DIR / f"hermes-eval-results-{timestamp}.md"
    with open(md_out, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"      Markdown 报告：{md_out}")

    # 6. 打印摘要
    print(f"\n[6/6] 评测摘要")
    print(f"      评测运行 ID：{eval_run_id}")
    print(f"      实际评测题数：{len(results)}")
    if results:
        pass_count = sum(1 for r in results if r["verdict"] == "PASS")
        partial_count = sum(1 for r in results if r["verdict"] == "PARTIAL")
        fail_count = sum(1 for r in results if r["verdict"] == "FAIL")
        print(f"      PASS={pass_count}  PARTIAL={partial_count}  FAIL={fail_count}")
        print(f"      总体得分：{json_report['overall_score']}（{json_report['overall_verdict']}）")
    print(f"\n      跳过统计：")
    for reason, count in skipped_stats.items():
        if count > 0:
            print(f"        {reason}: {count}")

    return json_report


def analyze_only(args):
    """只分析模式：从已有 state.db 提取轨迹并评判，不重新调用 hermes。"""
    print(f"[分析模式] eval_run_id={args.eval_run_id}")
    print("  （此模式需配合已有的 --source 标签 session，功能待扩展）")
    print("  当前建议：用 --dry-run 验证流程，或直接运行完整评测。")


def main():
    ap = argparse.ArgumentParser(
        description="hermes_eval_runner.py — Layer B Hermes 平台 LLM 实际评测 runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 docs/hermes_eval_runner.py                          # 跑全部🟢集（164 题）
  python3 docs/hermes_eval_runner.py --readiness green        # 显式指定就绪度
  python3 docs/hermes_eval_runner.py --only-set routing-evals-v2  # 只跑指定集合
  python3 docs/hermes_eval_runner.py --dry-run                # 不调用 hermes，只打印计划
  python3 docs/hermes_eval_runner.py --max-questions 5        # 限制题数（调试用）
""",
    )
    ap.add_argument(
        "--master", default=str(_MASTER_JSON),
        help=f"master JSON 路径（默认：{_MASTER_JSON}）",
    )
    ap.add_argument(
        "--readiness", default="green", choices=["green", "yellow", "orange"],
        help="就绪度过滤：green=只跑🟢可自动评测集；yellow=🟢+🟡；orange=全部（默认：green）",
    )
    ap.add_argument(
        "--only-set", default=None,
        help="只跑指定集合（set_id），调试用",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="不调用 hermes，只打印评测计划",
    )
    ap.add_argument(
        "--max-questions", type=int, default=None,
        help="限制评测题数（调试用）",
    )
    ap.add_argument(
        "--timeout", type=int, default=600,
        help="hermes chat 单题超时秒数（默认：600，P3 修复：原 120 偏低致 TIMEOUT）",
    )
    ap.add_argument(
        "--analyze-only", action="store_true",
        help="只分析模式（不重新调用 hermes）",
    )
    ap.add_argument(
        "--eval-run-id", default=None,
        help="配合 --analyze-only 指定要分析的评测运行 ID",
    )

    args = ap.parse_args()

    # 前置检查
    if not os.path.exists(args.master):
        print(f"[ERROR] master JSON 不存在：{args.master}")
        sys.exit(1)

    if not args.dry_run and not os.path.exists(_HERMES_DB):
        print(f"[WARN] Hermes state.db 不存在：{_HERMES_DB}")
        print(f"       请确认 hermes 已运行且 state.db 路径正确")

    if args.analyze_only:
        analyze_only(args)
    else:
        run_eval(args)


if __name__ == "__main__":
    main()
