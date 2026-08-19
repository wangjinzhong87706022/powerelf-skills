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

# ============================================================================
# 代码冻结护栏（CODE-FREEZE GUARD）
#
# 背景（2026-08-19 EVAL1 实证）：评测会话中的 agent 在回答"工具是否检出？"时
# 就地 patch 了被测生产代码 inspection_analyzer.py（突变层只查末端两点 → 全窗口
# 扫描）。评测对象在评测中途漂移：该题 FAIL 是"agent 忙于修代码未及作答"，且
# 后续所有题都跑在被改过的代码上——结果不可信、不可复现。
#
# 护栏语义：
#   - 评测启动时对被测代码面（GUARDED）做内容哈希基线（允许评测前已有未提交
#     修改——基线记录的是内容而非"必须干净"）
#   - 每题 hermes 跑完后复检：内容哈希变化 / tracked 文件被删 / guarded 前缀下
#     新增 untracked 代码文件 → 该题 verdict 强制 CODE-MUTATED（score=0），
#     顶层记录 code_freeze_violations
#   - 只检测+告警，不自动回滚（自动 checkout 会丢人工未提交修改）
#
# GUARDED = 被 skill 实际加载执行的代码与规则文档（tracked 文件筛前缀）。
# 预期产物排除：report_insp-*.md 等运行报告、output/、/tmp。
# ============================================================================

_GUARDED_PREFIXES = (
    "powerelf-data-governance/",
    "powerelf-inspection/",
    "_shared/",
    "docs/eval-questions-master.json",  # 评测题面本身（判分 ground truth）
)
# untracked 新文件中不算污染的（运行产物，非被测代码）
_UNTRACKED_OK_SUFFIXES = (".md", ".csv", ".pdf", ".png", ".jpg", ".svg", ".log", ".tsv")
_UNTRACKED_OK_PREFIXES = ("report_", "output/")


def snapshot_guarded_state():
    """
    代码冻结基线。

    返回 {"hashes": {tracked guarded path: 内容哈希},
          "untracked": [评测启动前已存在的 guarded untracked 代码文件]}
    —— 评测前已有的人工未提交文件（含 untracked）属合法起点，不视为突变；
    突变 = 评测运行期间相对本基线的新变化。

    无法计算（非 git 仓库 / git 失败）返回 None（护栏降级关闭，run_eval 打印 WARN）。
    """
    try:
        ls = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "ls-files", "-z"],
            capture_output=True, text=True, timeout=15,
        )
        if ls.returncode != 0:
            return None
        tracked = [p for p in ls.stdout.split("\0") if p]
        guarded = [p for p in tracked
                   if any(p.startswith(pre) for pre in _GUARDED_PREFIXES)]

        hashes = {}
        if guarded:
            hs = subprocess.run(
                ["git", "-C", str(_PROJECT_ROOT), "hash-object", "--stdin-paths"],
                input="\n".join(guarded), capture_output=True, text=True, timeout=120,
            )
            if hs.returncode != 0:
                return None
            hlist = hs.stdout.split()
            if len(hlist) != len(guarded):
                return None
            hashes = dict(zip(guarded, hlist))

        untracked = _list_guarded_untracked()
        return {"hashes": hashes, "untracked": untracked}
    except Exception as e:
        print(f"  [WARN] 代码冻结基线快照失败（护栏关闭）：{e}")
        return None


def _list_guarded_untracked():
    """当前 GUARDED 前缀下的 untracked 代码文件（排除运行产物后缀/前缀）。"""
    st = subprocess.run(
        ["git", "-C", str(_PROJECT_ROOT), "status", "--porcelain", "-z"],
        capture_output=True, text=True, timeout=15,
    )
    if st.returncode != 0:
        return []
    out = []
    for entry in st.stdout.split("\0"):
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        if status == "??" and _is_guarded_code(path):
            out.append(path)
    return out


def _is_guarded_code(path):
    """untracked 路径是否属被测代码面（排除 report_*/output 等运行产物）。"""
    return (any(path.startswith(pre) for pre in _GUARDED_PREFIXES)
            and not path.endswith(_UNTRACKED_OK_SUFFIXES)
            and not any(path.startswith(pre) for pre in _UNTRACKED_OK_PREFIXES))


def detect_code_mutation(baseline):
    """
    对比当前状态与基线，返回突变文件列表（相对 baseline）：
      - tracked 文件内容哈希变化 / 消失（被删）
      - GUARDED 前缀下【新增】untracked 代码文件（基线里已有的不算）

    baseline 为 None（护栏关闭）时恒返回 []。
    """
    if baseline is None:
        return []
    mutated = []
    base_hashes = baseline["hashes"]
    base_untracked = set(baseline["untracked"])
    try:
        # 1. tracked 文件内容对比
        live = [p for p in base_hashes if os.path.exists(_PROJECT_ROOT / p)]
        if live:
            hs = subprocess.run(
                ["git", "-C", str(_PROJECT_ROOT), "hash-object", "--stdin-paths"],
                input="\n".join(live), capture_output=True, text=True, timeout=120,
            )
            if hs.returncode == 0:
                hashes = hs.stdout.split()
                for path, h in zip(live, hashes):
                    if base_hashes.get(path) != h:
                        mutated.append(f"M {path}")
            else:
                mutated.append("? hash-object failed")
        for path in base_hashes:
            if not os.path.exists(_PROJECT_ROOT / path):
                mutated.append(f"D {path}")
        # 2. 新增 untracked 代码文件（相对基线）
        for path in _list_guarded_untracked():
            if path not in base_untracked:
                mutated.append(f"A {path}")
    except Exception as e:
        mutated.append(f"? detect error: {e}")
    return mutated

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
    "darwin-test-prompts": "powerelf-inspection",
}

# ⚠️ Skill 黑名单：临时排除不需要评测的 skill 或负例测试
SKILL_BLACKLIST = {
    # 外部参考项目（不在当前环境）
    "water-resource",  # 外部参考项目 /opt/git/water-resources-skills/
    # 幻影 skill（文档中提到但实际未安装）
    "water-situation", # 幻影 skill
    "water-warning",   # 幻影 skill
    "gate-pump-operation", # 幻影 skill
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
D4_INPUT_EXCELLENT = 34000     # P75 档（全量161题 P75≈34.2K；旧30题标定20K偏紧）
D4_OUTPUT_EXCELLENT = 5600     # P75 档（全量161题 P75≈5.6K；旧3K偏紧）
D4_INPUT_WARNING = 65000       # P95 档（全量161题 P95≈65.3K；旧36K偏紧）
D4_OUTPUT_WARNING = 12000      # P95 档（全量161题 P95≈11.8K；旧7K偏紧）
D5_LATENCY_EXCELLENT = 85     # P50 档（全量161题 P50≈85.6s；旧50s 低于中位数）
D5_LATENCY_WARNING = 370      # P90 档（全量161题 P90≈371s；旧180s 偏紧）
# D3 工具效率：按任务复杂度归一化（不再用扁平 tool_call_count 阈值）
# 生产性调用（terminal=DB查询 / execute_code=分析）随任务复杂度增长，属合理成本，不计入效率惩罚；
# 只对"开销调用"（search_files/read_file/patch/write_file/todo/clarify 等探索编辑）评分。
# 阈值用全量(161题)开销分布标定：P50=1, P90=10。
D3_PRODUCTIVE_TOOLS = ("terminal", "execute_code")
D3_OVERHEAD_EXCELLENT = 1     # 开销调用 ≤1 → 1.0（实测 P50=1）
D3_OVERHEAD_WARNING = 10      # 开销调用 ≥10 → 0.0（实测 P90=10；>10 属真·探索冗余）


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

    # ⚠️ Skill 黑名单：排除不需要评测的 skill（如 water-resource 外部参考项目）
    # 通过 expected_output 或 prompt 中是否包含黑名单关键词判断
    prompt_lower = (ev.get("prompt", "") + ev.get("expected_output", "")).lower()
    if any(banned in prompt_lower for banned in SKILL_BLACKLIST):
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

    bug#9 对齐 rescore v2：① ASCII 字符类（Python3 \\w 含 Unicode，会匹配出
    中文"表名"）；② 排除 "vs" 比较散文（eq_139_vs_140_may 这类非表名）。
    """
    if not text:
        return []
    # 匹配常见表名模式
    patterns = [
        r'\bst_[a-z0-9_]+_r\b',    # st_rsvr_r, st_pptn_r, st_pressure_r ...
        r'\bdsm_[a-z0-9_]+\b',     # dsm_dfr_srvrds_srhrds
        r'\beq_[a-z][a-z0-9_]*\b', # eq_equip_base（eq_ 后须字母，排除 eq_139_vs_140）
        r'\brei_[a-z0-9_]+_r\b',   # rei_gate_r, rei_pump_r
        r'\bsl_[a-z0-9_]+_r\b',    # sl_rsvr_rt_r（旧名）
    ]
    found = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            tok = m.group(0).lower()
            if "vs" in tok:        # 排除比较散文 eq_139_vs_140_may
                continue
            found.add(tok)
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

def run_hermes(skill, query, source_tag, dry_run=False, timeout=900):
    """
    P1 #4: 调用 hermes CLI，用 --source 标签绕过 workflow 缓存 + 便于事后反查 session_id。

    注意：hermes chat 无 --user-id flag（实测 hermes chat --help 确认）。
    绕缓存用 --source（每题 source 不同即绕过 workflow:{user_id}:{minute_bucket} 缓存）。

    参数：
      skill: hermes skill 名（-s 参数值）
      query: 问题原文（-q 参数值）
      source_tag: session 来源标签（--source 参数值）
      dry_run: True 则不实际调用 hermes，只打印命令
      timeout: hermes chat 超时秒数（默认 900s，由 --timeout 覆盖）

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

# ============================================================================
# 判分别名表与辅助函数（模块级）
#
# bug#9：这套表原困在 judge() 局部，且与 rescore_eval.py 各持一份副本，
# 修 bug 时只改一份 → 两套判分器漂移（20260814 全量跑 95 题 parse 不一致）。
# 现提升为模块级单一事实源：rescore_eval.py 直接复用，test_judge_sync.py 锁覆盖。
# ============================================================================

# D1 method/task_type key → 中文/英文同义词。parse_expected 能产出的每个 key
# 必须在此有条目，否则回退英文字面量匹配 → 中文回答一律漏判（bug#7/#9）。
ALIAS_D1 = {
    "MAD": ["MAD", "中位数绝对偏差", "修正Z", "modified z"],
    "IQR": ["IQR", "四分位距", "interquartile"],
    "percentile": ["percentile", "百分位"],
    "change_rate": ["变化率", "变率", "change rate", "波动"],
    "threshold": ["阈值", "门限", "threshold", "超标", "越限", "临界"],
    "time_window": ["时间窗口", "指定时间", "时间区间", "日期范围", "窗口", "日期", "每日", "每日摘要", "按天", "YYYY-MM-DD", "2026-"],
    "missing": ["缺失", "漏", "missing", "空值", "缺测"],
    "comprehensive": ["综合", "汇总", "联合", "多指标"],
    "anomaly_detection": ["异常检测", "异常分析", "离群", "outlier", "anomaly"],
    "missing_detection": ["缺失检测", "缺测检测", "missing detection"],
    "grade": ["分级", "分类", "等级", "grade", "评级", "严重性", "严重度"],
    "report": ["日报", "报告", "report"],
    "daily_report": ["日报", "每日", "daily report", "daily_report"],  # 防御：历史 parse 产物
    "overview": ["概览", "总览", "overview"],
    "scoring": ["评分", "打分", "score"],
    "detection": ["检测", "分析", "判定", "识别"],
    "judgment": ["判定", "结论", "判断", "诊断"],
    # parse 能产出的 method key 须全部有中文别名，否则 _d1_hit
    # 回退到英文字面量匹配 → 中文回答一律漏判（曾致 DG methods 10 题全 D1=0）
    "cycle": ["周期", "周期性", "cycle", "循环节"],
    "compare": ["比较", "对比", "compare", "同期对比", "横向对比"],
    "expectation": ["期望", "预期", "expectation", "期望值", "期望数"],
    "period_over_period": ["环比", "同比", "period over period", "period_over_period"],
    "trend": ["趋势", "走势", "trend", "趋势分析", "趋向"],
    "interpolation": ["插值", "interpolation", "样条", "填补", "补全", "线性插值", "三次样条", "spline"],
    "adaptive": ["自适应", "adaptive", "自适应窗口"],
    "strategy": ["策略", "方案", "strategy", "策略选择"],
    "station": ["测站", "站点", "station", "指定站", "单站"],
    # routing_en 异常词（parse 下板后为小写英文/原样中文）
    "rz": ["rz", "阻水系数", "渗漏"],
    "water_pressure": ["渗压", "water_pressure", "孔隙水压"],
    "rainfall": ["降雨", "雨量", "rainfall"],
    "level": ["水位", "level"],
    "spike": ["spike", "尖峰", "突变"],
    "extreme": ["极端", "极值", "extreme"],
    "pressure": ["压力", "渗压", "pressure"],
    "percolation": ["渗流", "渗透"],
    "anomaly": ["异常", "anomaly", "离群"],
    # inspection_struct message_contains 同义词（agent 用了同义表述，判分器应认）：
    "三相不平衡": ["三相不平衡", "三相不平", "不平衡"],
    "突变": ["突变", "跳变", "骤变", "剧变", "spike"],
    "MAD统计异常": ["MAD统计异常", "MAD异常", "MAD统计", "MAD"],
    # 告警级别表述：agent 写"一级告警/一级"，expected 用"I级告警/CRITICAL"，应互认
    "I级告警": ["I级告警", "一级告警", "1级告警", "Ⅰ级告警", "一级"],
}

# 一级/I级=最高级=CRITICAL（水利应急惯例 level_r='1' 即 I 级；ALERT-POS-1 expected
# 明文"I级告警 ≥1条即 CRITICAL"）。只加 CRITICAL 一档，WARNING/ERROR 不臆测映射。
_LEVEL_WORD = {
    "WARNING": ["WARNING", "WARN", "警告", "预警"],
    "ERROR": ["ERROR", "错误", "严重"],
    "CRITICAL": ["CRITICAL", "紧急", "致命", "一级", "1级", "I级", "Ⅰ级"],
    "INFO": ["INFO", "信息", "提示"],
}

# 否定/排除语境词：final 里出现 X 但被这些词修饰 → 不算"把 X 当发现报出"
_NEG_WORDS = ("未", "无", "不", "没有", "正常", "排除", "低于", "未超", "未触发",
              "接近", "未达", "刚好", "恰", "稳定", "合理", "符合", "未发现", "不应", "未见")


def _negated(text, term):
    """term 在 text 的每次出现，前后 12 字窗口内是否含否定/排除词。命中一次即 True。
    先 strip 空白再匹配——agent 常写"离线率 `== 0.3` 严格不触发"，空格会把"不触发"
    推到 12 字窗外造成漏判。窗口 12 覆盖夹杂数值/标点的否定。"""
    t = re.sub(r"\s", "", text or "")
    for m in re.finditer(re.escape(term), t):
        lo = max(0, m.start() - 12)
        hi = min(len(t), m.end() + 12)
        if any(w in t[lo:hi] for w in _NEG_WORDS):
            return True
    return False


def _syn_hit(answer, phrase):
    """忽略空白后的子串命中（agent 答案常夹空白/换行）。"""
    if not phrase:
        return False
    return re.sub(r"\s", "", phrase) in re.sub(r"\s", "", answer or "")


def _alias_hit(answer, key):
    """key 经 ALIAS_D1 别名组命中 answer 任一同义词。"""
    return any(a and a in (answer or "") for a in ALIAS_D1.get(key, [key]))


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

    # ---- inspection-eval-cases 结构化：min_level=X; message_contains=Y; no_finding_contains=Z ----
    # bug#9：此分支原只在 rescore_eval.py 有，全量跑 runner 缺失 → 47 题整串落
    # DG 方法短语 fallback，"理由"文本里的"阈值"二字母匹配成 methods=['threshold']
    # 代理判分（与真实断言无关）。现统一进单一 parse。
    if any(k in s for k in ("min_level", "message_contains", "no_finding_contains",
                            "no_diagnosis", "not_no_data", "pattern=")):
        out = {"_kind": "inspection_struct"}
        m = re.search(r"min_level\s*=\s*(\w+)", s)
        if m:
            out["min_level"] = m.group(1)
        m = re.search(r"message_contains\s*=\s*([^|;]+)", s)
        if m:
            out["message_contains"] = m.group(1).strip()
        m = re.search(r"no_finding_contains\s*=\s*([^|;]+)", s)
        if m:
            out["no_finding_contains"] = m.group(1).strip()
        if re.search(r"no_diagnosis\s*=\s*True", s, re.I):
            out["no_diagnosis"] = True
        if re.search(r"not_no_data\s*=\s*True", s, re.I):
            out["not_no_data"] = True
        m = re.search(r"pattern\s*=\s*(\w+)", s)
        if m:
            out["pattern"] = m.group(1)
        return out

    # ---- routing-evals-v2 英文：Provider calls <skill> to analyze <anomaly> ----
    # bug#9：同上，原 runner 缺失 → 45 题落 manual_judge 0.5 地板。
    m = re.search(r"calls?\s+(powerelf-[\w-]+)", s, re.IGNORECASE)
    if m:
        anomalies = re.findall(
            r"\b(rz|water_pressure|rainfall|level|spike|extreme|anomaly|"
            r"percolation|渗压|渗流|水位|雨量|流量|pressure)\b", s, re.IGNORECASE)
        anchors = re.findall(r"\b(\d+\.?\d*|2026-?\d{2}-?\d{2}|606\w*)\b", s)
        # 不带 expected_route：routing-v2 评测已用 -s 预载该 skill，
        # D2 字面匹配必失配 → 误判 0。D1 按异常关键词判，D2 保持中性 0.5。
        return {"_kind": "routing_en",
                "anomalies": list(dict.fromkeys(a.lower() for a in anomalies)),
                "anchors": anchors[:6], "raw": s}

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
    # 支持多目标 "路由到 A / B"（任一命中即可），并去掉反引号避免字面不匹配
    m = re.search(r"(?:应)?路由到\s*([^；|\n]+)", s)
    if m:
        routes = [
            r.strip().strip("`").strip()
            for r in m.group(1).split("/")
            if r.strip().strip("`").strip()
        ]
        routes = [r for r in routes if "原因" not in r]
        if routes:
            return {"expected_route": routes[0], "expected_routes": routes}

    # data-governance-routing-list / inspection-eval-criteria：Pass: ... | Fail: ...
    m = re.search(r"Pass:\s*(.+?)\s*\|\s*Fail:\s*(.+)", s, re.IGNORECASE)
    if m:
        out = {
            "pass_condition": m.group(1).strip(),
            "fail_condition": m.group(2).strip(),
        }
        # inspection-eval-criteria 格式：Pass: 输出包含"X"和"Y" | Fail: ...
        # 原版把整句指令当 pass_condition 字面匹配→结构上永不命中（EVAL1-9 全 D1=0）。
        # 提取引号内关键词，D1 改为关键词命中检查。
        if "包含" in m.group(1):
            kws = re.findall(r'"([^"]+)"', m.group(1))
            if kws:
                out["pass_keywords"] = kws
        # bug#8：描述性计数条件（无引号），如"边界规则章节有 5+场景 和 3+反例"。
        # 字面匹配整句必失配（agent 列举了这些项也判 0）。提取"N+名词"里的名词作关键词，
        # D1 改为这些名词都在 answer 中出现即达标。
        if "pass_keywords" not in out:
            nouns = re.findall(r'\d+\s*\+?\s*([一-龥]{2,4})', m.group(1))
            # 去掉贪婪捕获粘上的连词/助词（"场景和"→"场景"），再弃过短残片
            nouns = [n.rstrip("和或与及、，。 ") for n in nouns]
            nouns = [n for n in nouns if len(n) >= 2]
            if nouns:
                out["pass_keywords"] = list(dict.fromkeys(nouns))
        return out

    # P1 修复：data-governance-routing-list 的方法名短语格式
    # 实测样本（master JSON）：
    #   "MAD 异常检测" / "分指标阈值检测" / "MAD + 变化率综合判定"
    #   "指定时间窗口检测" / "变化率检测 + 综合判定" / "缺失检测"
    # 解析为 {"method": ..., "task_type": ...}，让 D1/D2 做实质评判而非 fallback 0.5
    #
    # bug#9：原表缺 周期/插值/测站/对比/自适应/策略/期望/环比/趋势 等 9 组 pattern，
    # 又把"日报"映成 daily_report（ALIAS 无此键）→ "四策略自适应插值"等题 parse=None
    # 全吃 manual_judge 0.5 地板，"日报生成"题 D1 必 0。与 rescore 的
    # _DG_METHOD_PATTERNS 对齐为同一张表。
    method_patterns = [
        (r"\bMAD\b", "MAD"), (r"\bIQR\b", "IQR"), (r"percentile", "percentile"),
        (r"变化率|变率", "change_rate"), (r"阈值|门限", "threshold"),
        (r"时间窗口|指定时间|时间区间|日期范围", "time_window"), (r"缺失|漏|缺测", "missing"),
        (r"综合", "comprehensive"), (r"等级|分级|分类", "grade"),
        (r"日报|报告", "report"), (r"概览|总览", "overview"), (r"评分|打分", "scoring"),
        (r"周期", "cycle"), (r"环比|同比", "period_over_period"), (r"趋势", "trend"),
        (r"插值", "interpolation"), (r"测站|站点", "station"), (r"比较|对比", "compare"),
        (r"自适应", "adaptive"), (r"策略", "strategy"), (r"期望", "expectation"),
    ]
    task_type_patterns = [
        (r"异常检测|异常分析|离群", "anomaly_detection"),
        (r"缺失检测|缺测", "missing_detection"), (r"等级|分级|分类", "grade"),
        (r"日报|报告", "report"), (r"概览|总览", "overview"), (r"评分|打分", "scoring"),
        (r"检测|分析|比较|插值", "detection"), (r"判定|判断", "judgment"),
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
      D3 工具效率 (15%) - 按复杂度归一化：生产性调用(terminal/execute_code)不罚，
                          仅对"开销调用"(search/read/patch/write/todo)线性评分
      D4 Token 效率 (10%) - input_tokens <15K 且 output_tokens <3K 为达标
      D5 响应时延 (10%) - duration_sec <30s 优秀；30-60s 预警；>60s 失败
      D6 幻觉抑制 (10%) - final_answer 引用的表名全部可在 schema.md 中溯源
      D7 回答完整性 (10%) - final_answer 覆盖 expected_output 所有关键信息点

    返回 verdict dict。
    """
    expected_str = ev["expected_output"]  # P1 #1: 是字符串，不是 dict
    parsed = parse_expected(set_["set_id"], expected_str)

    # ---- 评分语料（bug#9：与 rescore_eval 对齐，两套判分器同一语义）----
    # corpus = 最终回答 + clarify 追问 + assistant 全历史（中间分析常含关键信息，
    # 只看最终一条会漏判）；final_strict = 仅最后一条 assistant 回答
    # （no_finding_contains 误报检查专用——中间讨论过 X 不等于"把 X 当发现报出"）。
    msgs = trace.get("messages", []) or []
    clarify_text = "".join((m.get("content") or "") for m in msgs
                           if m.get("role") == "tool" and m.get("tool_name") == "clarify")
    clarified = bool(clarify_text)
    final_strict = trace.get("final_answer_strict") or trace.get("final_answer") or ""
    actual_answer = trace.get("answer_corpus")
    if actual_answer is None:
        assistant_text = "".join((m.get("content") or "") for m in msgs
                                 if m.get("role") == "assistant")
        actual_answer = final_strict + "\n" + clarify_text + "\n" + assistant_text

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
        elif "pass_keywords" in parsed:
            # inspection-eval-criteria：提取引号内关键词，全部命中即 D1=1.0。
            # 复合词（如"渗压突变"）拆半都算（回答里"渗压""突变"常不连写）。
            kws = parsed["pass_keywords"]
            def _kw_hit(kw):
                if kw in actual_answer:
                    return True
                if len(kw) >= 4:
                    mid = len(kw) // 2
                    if kw[:mid] in actual_answer and kw[mid:] in actual_answer:
                        return True
                return _alias_hit(actual_answer, kw)  # 别名兜底（同义表述互认）
            d1 = 1.0 if all(_kw_hit(k) for k in kws) else 0.0
            d1_note = f"pass_keywords={kws}"
        elif parsed.get("_kind") == "inspection_struct":
            # bug#9 移植自 rescore compute_d1：结构化断言逐项判（此前 runner 缺失，
            # 47 题 inspection-cases 被"阈值"代理误判）。
            hits, tot = 0, 0
            if "message_contains" in parsed:
                tot += 1
                mc = parsed["message_contains"]
                if mc in actual_answer or _syn_hit(actual_answer, mc) or _alias_hit(actual_answer, mc):
                    hits += 1
            if "min_level" in parsed:
                tot += 1
                lv = parsed["min_level"].upper()
                if any(w in actual_answer for w in _LEVEL_WORD.get(lv, [lv])):
                    hits += 1
            if "no_finding_contains" in parsed:
                tot += 1
                nfc = parsed["no_finding_contains"]
                # 判"最终结论是否把 X 当发现报出"——只看 final_strict，
                # 不看整条 corpus（澄清/中间分析里讨论 X 是正常的）。
                if nfc not in final_strict:
                    hits += 1
                elif _negated(final_strict, nfc):
                    # final 里有 X 但被否定语境修饰（"未发现X"/"X正常"）→ 不算报出
                    hits += 1
            if "no_diagnosis" in parsed:
                tot += 1
                if not re.search(r"根因|诊断结论|诊断为|原因[是为]", actual_answer):
                    hits += 1
            d1 = hits / tot if tot else 0.5
            d1_note = "inspection_struct"
        elif parsed.get("_kind") == "routing_en":
            # bug#9 移植自 rescore compute_d1：异常关键词 60% + 数字/日期锚点 40%
            anoms = parsed.get("anomalies", [])
            ah = sum(1 for a in anoms if _alias_hit(actual_answer, a))
            anom_score = ah / len(anoms) if anoms else 0.5
            anchors = parsed.get("anchors", [])
            anch = sum(1 for x in anchors if x in actual_answer) / len(anchors) if anchors else 0.5
            d1 = 0.6 * anom_score + 0.4 * anch
            d1_note = "routing_en"
        elif "pass_condition" in parsed:
            d1 = 1.0 if parsed["pass_condition"] in actual_answer else 0.0
            d1_note = f"pass_condition='{parsed['pass_condition'][:30]}'"
        elif "expected_route" in parsed:
            # 路由类题目：D1 检查 final_answer 是否提到任一 expected_route（多目标任一即可）
            routes = parsed.get("expected_routes") or [parsed["expected_route"]]
            ans_clean = actual_answer.replace("`", "")
            d1 = 1.0 if any(r.replace("`", "") in ans_clean for r in routes) else 0.0
            d1_note = f"expected_routes={routes}"
        elif "methods" in parsed or "task_type" in parsed:
            # P1 修复：方法名短语格式（"MAD 异常检测"/"分指标阈值检测"）
            # 检查 hermes 回答是否提到 expected 的方法/任务类型关键词（含同义词扩）
            methods = parsed.get("methods") or []
            task_type = parsed.get("task_type")
            # 把 method/task_type 扩成别名组，命中任一个就算 D1 通过
            # bug#9：ALIAS_D1 已提升为模块级单一事实源（原局部副本与 rescore 漂移）
            def _d1_hit(key):
                return _alias_hit(actual_answer, key)

            # 方法命中 + 任务类型命中，取 min（两者都应覆盖）
            method_hits = sum(1 for m in methods if _d1_hit(m))
            method_score = method_hits / len(methods) if methods else 1.0
            task_score = 1.0 if (task_type and _d1_hit(task_type)) else (1.0 if not task_type else 0.0)
            d1 = min(method_score, task_score)
            d1_note = f"methods={methods},task_type={task_type}"

    # clarify 地板（bug#9 移植自 rescore）：agent 触发 clarify 是识别歧义而非瞎答，
    # D1 不该是 0
    if clarified and d1 < 0.5:
        d1 = 0.5
        d1_note = f"{d1_note};clarify_floor"

    # ---- D2 路由命中 ----
    routes = (parsed.get("expected_routes") if parsed else None) or (
        [parsed["expected_route"]] if parsed and "expected_route" in parsed else []
    )
    # 检查 system 消息（加载的 rules）或 final_answer 中是否提到任一 expected_route
    loaded_rules = [
        m["content"] for m in trace.get("messages", []) if m["role"] == "system"
    ]
    system_content = str(loaded_rules)
    sys_clean = system_content.replace("`", "")
    ans_clean = actual_answer.replace("`", "")
    if routes and any(
        r.replace("`", "") in sys_clean or r.replace("`", "") in ans_clean for r in routes
    ):
        d2 = 1.0
    elif routes:
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

    # ---- D3 工具效率（按任务复杂度归一化）----
    # 生产性调用(terminal/execute_code)随复杂度增长，不计惩罚；
    # 只对"开销调用"(其余工具)线性评分。扁平 tool_call_count>5=0 会把
    # 合理的多表 DB 查询题全判 0（实测 P50=6），故改为开销口径。
    chain = trace.get("tool_chain", []) or []
    _tn = lambda t: t.get("tool") if isinstance(t, dict) else t  # 兼容 dict/fresh 与 string/重判
    overhead = sum(1 for t in chain if _tn(t) not in D3_PRODUCTIVE_TOOLS)
    if overhead <= D3_OVERHEAD_EXCELLENT:
        d3 = 1.0
    elif overhead >= D3_OVERHEAD_WARNING:
        d3 = 0.0
    else:
        d3 = 1.0 - 0.5 * (overhead - D3_OVERHEAD_EXCELLENT) / (D3_OVERHEAD_WARNING - D3_OVERHEAD_EXCELLENT)

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
        # 未被别名表覆盖的纯中文短语(≥3字) → 拆 2-gram，避免方法标签原子化
        # (expected="历史缺陷查询" 整句当单点，同义"故障记录"字面不命中 → D7 误判0)
        if len(expanded) == 1 and re.fullmatch(r"[一-龥]{3,}", kp):
            expanded.extend(kp[i:i + 2] for i in range(len(kp) - 1))
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
            "tool_chain": [t["tool"] if isinstance(t, dict) else t for t in trace["tool_chain"]],
        },
    }


# ============================================================================
# 报告生成
# ============================================================================

def generate_json_report(results, master, eval_run_id, readiness_filter, skipped_stats,
                         code_freeze_violations=None):
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
        "code_freeze_violations": code_freeze_violations or [],
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

    # 代码冻结违规（评测中被测代码被修改 → 该题及后续结果无效）
    violations = json_report.get("code_freeze_violations") or []
    if violations:
        lines.append("## 🚨 代码冻结违规（CODE-MUTATED）")
        lines.append("")
        lines.append("> **评测有效性警告**：以下题目运行期间，评测 agent 修改了被测代码。")
        lines.append("> 该题结果已判无效（score=0）；其后所有题目均运行在漂移代码上，")
        lines.append("> **整轮评测结果不可直接采信**，应在干净代码上重跑。")
        lines.append("")
        lines.append("| 题号 | 集合 | 被改文件 |")
        lines.append("|---|---|---|")
        for v in violations:
            files = "<br>".join(v["files"])
            lines.append(f"| {v['id']} | {v['set']} | {files} |")
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

    # 2.5 代码冻结基线（护栏：防评测 agent 就地修改被测代码）
    baseline = snapshot_guarded_state()
    code_freeze_violations = []
    if baseline is None:
        print(f"      [WARN] 代码冻结护栏关闭（基线快照失败，见前述警告）")
    else:
        print(f"      代码冻结基线：{len(baseline['hashes'])} 个 tracked guarded 文件"
              f" + {len(baseline['untracked'])} 个已有 untracked 已快照")

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
    # --only-ids 支持「裸 id」（全局匹配）与「set_id:ev_id」（精确到集合，
    # 解决 routing-v1/v2/darwin 数字 id 跨集合冲突）两种形式，逗号分隔混用
    only_ids_set = None
    only_pairs_set = set()
    if args.only_ids:
        for _tok in (x.strip() for x in args.only_ids.split(",") if x.strip()):
            if ":" in _tok:
                only_pairs_set.add(tuple(_tok.split(":", 1)))
            else:
                only_ids_set = only_ids_set or set()
                only_ids_set.add(_tok)
    for set_ in master.get("sets", []):
        if args.only_set and set_["set_id"] != args.only_set:
            continue

        skill = SET_TO_SKILL.get(set_["set_id"])
        if not skill:
            print(f"  [WARN] 集合 {set_['set_id']} 无 SET_TO_SKILL 映射，跳过")
            continue

        print(f"\n[3/6] 评测集合：{set_['set_id']}（skill={skill}）")

        for ev in set_.get("evals", []):
            # --only-ids 过滤（裸 id 全局匹配；set:id 精确到集合，调试/验证用）
            if only_ids_set or only_pairs_set:
                _ok = ev["id"] in only_ids_set if only_ids_set else False
                if not _ok:
                    _ok = (set_["set_id"], ev["id"]) in only_pairs_set
                if not _ok:
                    continue
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

            # 代码冻结护栏：评测中 agent 改了被测代码 → 该题结果无效
            mutations = detect_code_mutation(baseline)
            if mutations:
                print(f"\n      🚨 CODE-MUTATED：被测代码在评测中被修改——")
                for m in mutations:
                    print(f"         {m}")
                print(f"         （该题结果无效；回滚建议：git -C {_PROJECT_ROOT} checkout -- <file>）")
                code_freeze_violations.append({
                    "id": ev_id, "set": set_["set_id"], "files": mutations,
                })
                verdict["verdict"] = "CODE-MUTATED"
                verdict["score"] = 0.0
                verdict["d1_note"] = f"code_mutated: {', '.join(mutations[:3])}"
                verdict["code_mutated_files"] = mutations

            results.append(verdict)
            print(f"{verdict['verdict']}（score={verdict['score']}）")

    # 4. 生成 JSON 报告
    print(f"\n[4/6] 生成 JSON 报告")
    json_report = generate_json_report(
        results, master, eval_run_id, args.readiness, skipped_stats,
        code_freeze_violations=code_freeze_violations,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / f"hermes-eval-results-{timestamp}.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    print(f"      JSON 报告：{json_out}")

    # 5. 生成 Markdown 报告
    print(f"\n[5/6] 生成 Markdown 报告")
    md_report = generate_markdown_report(json_report)
    md_out = out_dir / f"hermes-eval-results-{timestamp}.md"
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
        mutated_count = sum(1 for r in results if r["verdict"] == "CODE-MUTATED")
        print(f"      PASS={pass_count}  PARTIAL={partial_count}  FAIL={fail_count}"
              + (f"  CODE-MUTATED={mutated_count}" if mutated_count else ""))
        print(f"      总体得分：{json_report['overall_score']}（{json_report['overall_verdict']}）")
        if code_freeze_violations:
            print(f"\n      🚨🚨 代码冻结违规 {len(code_freeze_violations)} 题——评测中被测代码被修改，")
            print(f"         受影响题的 CODE-MUTATED 结果无效；后续题均跑在漂移代码上，整轮结果仅供参考：")
            for v in code_freeze_violations:
                print(f"           {v['set']}/{v['id']}: {', '.join(v['files'][:3])}")
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
        "--out-dir", default=str(_OUT_DIR),
        help=f"评测报告输出目录（默认：{_OUT_DIR}，建议 output/ 下带日期戳子目录）",
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
        "--only-ids", default=None,
        help="只跑指定题号（逗号分隔，如 WQ-POS-1,RAIN-POS-1），调试/验证用",
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
        "--timeout", type=int, default=900,
        help="hermes chat 单题超时秒数（默认：900；P3 修复：原 120 偏低致 TIMEOUT；"
             "2026-08-19 再调：600→900，inspection 查库+跑工具长链路实测 600s 仍偶发截断）",
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
