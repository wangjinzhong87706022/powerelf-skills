# Hermes Agent 平台实际评测实施方案

> 适用对象：本项目 `powerelf-skills` 下 5 个 skill（early-warning-v3、powerelf-data-governance、powerelf-inspection、powerelf-chatbi、darwin-skill），以及已归一化的全阶段评测问题主清单 `docs/eval-questions-master.json`（8 集合 / 293 题）。
> 目标：把"已生成的评测问题"在 **Hermes Agent 平台**上实际跑通，记录运行轨迹，按多维度对"实际结果 vs 预期结果"进行对比评测，产出可回归、可量化的评测报告。

---

## 1. 评测对象分层

评测前必须先分清被测对象，否则维度会串。本项目存在两层：

| 层级 | 被测对象 | 是否耗 Token | 是否可缓存 | 典型 runner |
|---|---|---|---|---|
| **A. 规则层 / 静态层** | lib/topology.py、sql_lint、inspection_analyzer 等纯规则/算法 | ❌ 不耗 Token | ✅ 可缓存 | `impl/eval_runner.py`（无 DB、无 LLM） |
| **B. Hermes SOP 驱动的 LLM 层** | hermes agent 加载 SKILL.md → 多轮 LLM 推理 → 调用工具 | ✅ 多轮耗 Token | ⚠️ 仅 workflow 级有 5 分钟缓存 | 本方案 §3 的 hermes eval runner |

**关键判断**：
- `intelligent-analysis-workflow.md` 已是 SOP 级 workflow，且有 `workflow:{user_id}:{minute_bucket}` 5 分钟缓存——评测时必须**绕过缓存**（每次用新 user_id 或刷新缓存键），否则会测到缓存命中而非真实推理。
- 切勿把规则层（lib/topology.py）不耗 Token，误推为整个项目不耗 Token。Hermes SOP 驱动的 LLM 层才是 Token 消耗与幻觉的主要来源，也是本方案的重点评测对象。

---

## 2. 评测问题清单的就绪度分级

来源：`docs/eval-questions-master.json`。并非全部 293 题都能"直接喂给 runner 自动跑"，需按就绪度分级处理：

| 就绪度 | 集合 | 题数 | 处理方式 |
|---|---|---|---|
| **🟢 可直接自动评测** | routing-list / routing-v1 / routing-v2 / inspection-eval-criteria / inspection-eval-cases / darwin-test-prompts | 164 | prompt + expected_output 均完整，直接喂 runner |
| **🟡 需人工补全后再自动评测** | data-governance-realdata-tests | 26 | prompt 为真实题面，但 20/26 题的 expected_output 为占位符"见文档预期"，不可自动判分 |
| **🟠 需人工补全 prompt** | early-warning-v3-matrix | 103 | 74 条原文题目仅有标题（prompt=标题），29 条为占位补写（`prompt_source=placeholder-reconstructed`） |

**占位题面的特殊处理**：
- 29 个 `placeholder-reconstructed` 题面**禁止与原文混同**，评测报告中必须单独统计这一批题的通过率，并在结论中标注"占位题面评测结果不代表原文题面的真实能力"。
- 如需复原原文 Q36–Q61 / Q99–Q101，只能回溯原始 hermes 测试会话（`~/.hermes/state.db`）。

---

## 3. 评测执行架构

### 3.1 总体流程

```
eval-questions-master.json (293 题)
        │
        ├─ Layer A：规则层静态评测（无 DB、无 LLM、确定性）
        │   └─ 各 skill 的 impl/eval_runner.py
        │       → autoresearch/results_cases.json
        │
        └─ Layer B：Hermes 平台 LLM 实际评测（本方案核心）
            └─ docs/hermes_eval_runner.py (新增)
                │
                ├─ 1. 加载 master JSON，按就绪度过滤
                ├─ 2. 逐题调用 hermes CLI（绕过 workflow 缓存）
                ├─ 3. 从 ~/.hermes/state.db 提取运行轨迹
                ├─ 4. 按多维度评判 actual vs expected
                └─ 5. 输出 docs/hermes-eval-results-{timestamp}.json + .md
```

### 3.2 Layer B runner 的核心设计

**输入**：`docs/eval-questions-master.json` + hermes CLI + `~/.hermes/state.db`
**输出**：`docs/hermes-eval-results-{timestamp}.json`（机器可读）+ `.md`（人读报告）

逐题执行流程（伪代码）：

```python
for set in master["sets"]:
    for ev in set["evals"]:
        if not is_runnable(ev, set_):          # INFO #8: 就绪度过滤，只跑🟢集
            continue
        # 1. 调用 hermes，用 --source 标签便于事后按 source 反查 session_id
        source_tag = f"eval-{run_ts}-{ev['id']}"
        run_hermes(
            skill=SET_TO_SKILL[set_["set_id"]],  # P1 #2: set 无 source_skill 字段，用内置映射表
            query=ev["prompt"],
            source=source_tag,                   # P1 #4: hermes 无 --user-id flag，改用 --source 标签
        )
        # 2. 从 state.db 按 source_tag 反查 session_id，再提取轨迹
        session_id = find_session_by_source(source_tag)
        trace = extract_trace(session_id)        # 见 §4.2
        if trace is None:
            continue                              # session 未写入，跳过
        # 3. 按多维度评判
        verdict = judge(ev, trace, set_)          # 见 §5
        results.append(verdict)
```

**`SET_TO_SKILL` 映射表**（P1 #2：set 无 `source_skill` 字段，需内置映射）：

```python
# set_id → hermes skill 名（-s 参数值）
SET_TO_SKILL = {
    "early-warning-v3-matrix":          "early-warning-v3",       # 新目录名
    "data-governance-routing-list":     "powerelf-data-governance",
    "data-governance-realdata-tests":   "powerelf-data-governance",
    "routing-evals-v1":                 "powerelf-data-governance",
    "routing-evals-v2":                 "powerelf-data-governance",
    "inspection-eval-criteria":         "powerelf-inspection",
    "inspection-eval-cases":            "powerelf-inspection",
    "darwin-test-prompts":              "darwin-skill",
}
```

> ⚠️ early-warning 存在新旧目录并存问题：`early-warning-v3/`（现行）与 `powerelf-early-warning/`（旧）。hermes `-s` 参数用现行目录名 `early-warning-v3`。如遇 `powerelf-early-warning` 也在 hermes config 注册，需先确认哪个是 hermes 实际加载的 skill 名。

**hermes CLI 调用方式**（实测 `hermes chat --help` 确认可用）：

```bash
# 单次提问，--source 打标签便于事后反查 session_id
hermes chat -s powerelf-data-governance \
  -q "帮我分级所有离线设备" \
  --source "eval-20260811-DG-P01" \
  -Q
```

**绕过 workflow 缓存的两种方式**（P1 #4：`hermes chat` 无 `--user-id` flag）：
1. 用 `--source` 给 session 打来源标签（推荐）：既绕过 `workflow:{user_id}:{minute_bucket}` 缓存（每题 source 不同），又便于事后按 source 反查 session_id（`SELECT id FROM sessions WHERE source = ?`）。
2. 评测前手动清缓存：删除 `workflow:{user_id}:{minute_bucket}` 对应的缓存条目。

> ❌ `hermes chat --user-id "..."` 不存在（实测 `hermes chat --help` 无此 flag）。`user_id` 来自 hermes 登录态/config，CLI 不暴露。原方案 §3.2:93 的 `--user-id` 写法是错的。

---

## 4. 运行轨迹的记录与分析

### 4.1 Hermes 运行轨迹的存储位置

Hermes 平台把所有运行轨迹存在 SQLite 数据库：

```
~/.hermes/state.db
```

核心表结构（基于现有测试脚本逆向）：

| 表 | 关键字段 | 用途 |
|---|---|---|
| `sessions` | id, source, user_id, model, started_at(REAL), ended_at(REAL,可空), tool_call_count, message_count, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens | 会话级汇总指标（实测 schema，非推测） |
| `messages` | session_id, timestamp(REAL), role(user/assistant/tool/system), content, tool_name, tool_call_id, tool_calls, token_count | 逐条消息轨迹 |

> ⚠️ state.db 无独立 `tool_calls` 表——工具调用明细存于 `messages` 表的 `tool_calls`/`tool_name`/`tool_call_id` 列（`role='tool'` 行）。§4.2 的 `extract_trace` 查的就是 `messages`，代码本身对。

### 4.2 轨迹提取脚本（`extract_trace`）

```python
import sqlite3, os, time

def extract_trace(session_id, db_path="~/.hermes/state.db"):
    db = sqlite3.connect(os.path.expanduser(db_path))  # P1 #3: str 无 .expanduser()，需 os.path.expanduser
    db.row_factory = sqlite3.Row

    # 1. 会话级汇总
    sess = db.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if sess is None:                                   # INFO #10: 空值防护
        return None

    # 2. 逐条消息（含 tool 调用与返回）
    msgs = db.execute(
        "SELECT timestamp, role, tool_name, content "
        "FROM messages WHERE session_id = ? ORDER BY timestamp",
        (session_id,)
    ).fetchall()

    # 3. 工具调用序列（重构为有序链）
    tool_chain = [
        {"seq": i, "ts": m["timestamp"], "tool": m["tool_name"],
         "args": extract_tool_args(m["content"]),       # 桩函数，见 §5.3 注
         "result_preview": m["content"][:200]}
        for i, m in enumerate(msgs) if m["role"] == "tool"
    ]

    # INFO #10: ended_at 可能为 NULL（session 未结束），用 time.time() 兜底
    ended_at = sess["ended_at"] if sess["ended_at"] is not None else time.time()

    return {
        "session_id": session_id,
        "started_at": sess["started_at"],
        "ended_at": ended_at,
        "duration_sec": ended_at - sess["started_at"],
        "tool_call_count": sess["tool_call_count"],
        "message_count": sess["message_count"],
        "input_tokens": sess["input_tokens"],
        "output_tokens": sess["output_tokens"],
        "cache_read_tokens": sess["cache_read_tokens"],    # INFO #9: 补 cache/reasoning token 列
        "cache_write_tokens": sess["cache_write_tokens"],
        "reasoning_tokens": sess["reasoning_tokens"],
        "messages": [dict(m) for m in msgs],
        "tool_chain": tool_chain,
        # 最终 assistant 回答（最后一条 role=assistant 的 content）
        "final_answer": next((m["content"] for m in reversed(msgs)
                              if m["role"] == "assistant"), ""),
    }
```

### 4.3 轨迹分析维度

从提取的 `trace` 中可计算的分析维度：

| 分析维度 | 计算方式 | 评测意义 |
|---|---|---|
| **意图识别** | trace.messages 中 role=system 的内容是否加载了正确的 rules/*.md | 判断路由是否命中 |
| **工具选择链** | trace.tool_chain 的 tool_name 序列 | 是否走了批量脚本而非逐站循环 |
| **工具调用次数** | trace.tool_call_count | ≤2 为优秀，>5 为失败 |
| **中途停顿** | 相邻 message 的 timestamp 差 | 无 >5s 停顿为达标 |
| **prefill 负担** | trace.input_tokens | <15K 为达标 |
| **输出精简度** | trace.output_tokens | <3K 为达标 |
| **幻觉检测** | final_answer 中提到的表名/字段是否在 schema.md 中存在 | 任何幻觉表名为失败 |
| **回答完整性** | final_answer 是否覆盖 expected_output 中的所有关键信息点 | 缺关键点为 partial |

---

## 5. 评测维度（actual vs expected 的对比）

### 5.1 核心评测维度总表

本方案采用 **7 个维度** 对每道评测题进行 actual vs expected 对比：

| # | 维度 | 判定方式 | 权重 |
|---|---|---|---|
| D1 | **功能性正确** | actual 是否满足 expected_output 的核心断言（should_report/should_not_report/contains/equals） | 30% |
| D2 | **路由命中** | hermes 是否加载了正确的 rules/*.md（而非全量 SKILL.md） | 15% |
| D3 | **工具调用效率** | tool_call_count ≤2 优秀；3-5 预警；>5 失败 | 15% |
| D4 | **Token 效率** | input_tokens <15K 且 output_tokens <3K 为达标 | 10% |
| D5 | **响应时延** | duration_sec <30s 优秀；30-60s 预警；>60s 失败 | 10% |
| D6 | **幻觉抑制** | final_answer 引用的表名/字段/阈值全部可在 schema.md/rules 中溯源 | 10% |
| D7 | **回答完整性** | final_answer 覆盖 expected_output 所有关键信息点 | 10% |

### 5.2 综合评分公式

```
score = D1*0.30 + D2*0.15 + D3*0.15 + D4*0.10 + D5*0.10 + D6*0.10 + D7*0.10
```

每个维度归一化到 [0, 1]：
- 二值维度（D1/D2/D6）：命中=1，未命中=0
- 分档维度（D3/D4/D5）：优秀=1，预警=0.5，失败=0
- 覆盖维度（D7）：覆盖关键点数 / 总关键点数

### 5.3 评判器实现（`judge` 函数）

> ⚠️ P1 #1 关键修正：master JSON 的 `expected_output` 是**自由文本字符串**（如 `"场景：场景1；数据要求：4条未确认告警"` / `"Pass: 路由到 offline-detection | Fail: 路由到其他"` / `"应路由到 X；原因：Y"`），**不是** `{should_report/contains/equals}` 结构。原 §5.3 把字符串当 dict 用（`expected["should_report"]`），每道题都会 `TypeError`。
>
> 修法：`judge` 按 `set_id` 分支，用正则解析 `expected_output` 字符串。各 set 的 expected 格式不同，需分别 parse。

```python
import re

# 各 set 的 expected_output 字符串解析规则（P1 #1）
# 格式样本（实测 master JSON）：
#   early-warning-v3-matrix:     "场景：场景1；数据要求：4条未确认告警"
#   data-governance-routing-list: "Pass: 路由到 offline-detection | Fail: 路由到其他"
#   routing-evals-v2:            "应路由到 governance-profiler；原因：…"
#   inspection-eval-cases:       "should_report: WARNING | should_not_report: …"
#   darwin-test-prompts:         自由文本，需人工判

def parse_expected(set_id, expected_str):
    """把 expected_output 字符串解析为结构化断言。返回 dict 或 None（无法解析）。"""
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
        return out or None

    # routing-evals-v2 / data-governance-routing-list：应路由到 X
    m = re.search(r"路由到\s*(\S+?)[\s；|]|应路由到\s*(\S+?)[\s；|]", s)
    if m:
        return {"expected_route": m.group(1) or m.group(2)}

    # data-governance-routing-list：Pass: ... | Fail: ...
    m = re.search(r"Pass:\s*(.+?)\s*\|\s*Fail:\s*(.+)", s)
    if m:
        return {"pass_condition": m.group(1).strip(),
                "fail_condition": m.group(2).strip()}

    # early-warning-v3-matrix：自由文本场景描述，无法自动 parse
    return None


def judge(ev, trace, set_):
    expected_str = ev["expected_output"]          # P1 #1: 是字符串，不是 dict
    actual_answer = trace["final_answer"] or ""
    parsed = parse_expected(set_["set_id"], expected_str)

    # D1 功能性正确（按 parsed 结构分支；无法 parse 时给中位并标记 manual_judge）
    d1 = 0.5
    d1_note = "manual_judge"
    if parsed:
        if "should_report" in parsed:
            d1 = 1.0 if parsed["should_report"] in actual_answer else 0.0
            d1_note = f"should_report={parsed['should_report']}"
        elif "pass_condition" in parsed:
            d1 = 1.0 if parsed["pass_condition"] in actual_answer else 0.0
            d1_note = f"pass_condition='{parsed['pass_condition'][:30]}'"

    # D2 路由命中（检查 system 消息是否加载了正确 rules）
    expected_route = parsed.get("expected_route", "") if parsed else ""
    loaded_rules = [m["content"] for m in trace["messages"] if m["role"] == "system"]
    d2 = 1.0 if expected_route and expected_route in str(loaded_rules) else 0.0

    # D3 工具调用效率
    tc = trace["tool_call_count"]
    d3 = 1.0 if tc <= 2 else (0.5 if tc <= 5 else 0.0)

    # D4 Token 效率（INFO #9：补 cache/reasoning token 列）
    total_in = trace["input_tokens"] + trace.get("cache_read_tokens", 0)
    d4 = 1.0 if (total_in < 15000 and trace["output_tokens"] < 3000) else 0.5

    # D5 响应时延
    dur = trace["duration_sec"]
    d5 = 1.0 if dur < 30 else (0.5 if dur <= 60 else 0.0)

    # D6 幻觉抑制（P1 #5：ground truth 必须是 schema.md 规范表名集，非 profiler 白名单）
    mentioned_tables = extract_table_names(actual_answer)   # 桩函数，见下方注
    hallucinated = [t for t in mentioned_tables if t not in SCHEMA_TABLES_FROM_SCHEMA_MD]
    d6 = 1.0 if not hallucinated else 0.0

    # D7 回答完整性（expected_output 字符串中的关键信息点覆盖率）
    # 粗略启发：把 expected_str 中出现的中文关键词（≥2字）当作 key_points
    key_points = re.findall(r"[\u4e00-\u9fa5]{2,}", expected_str)
    covered = sum(1 for kp in key_points if kp in actual_answer)
    d7 = covered / len(key_points) if key_points else 1.0

    score = d1*0.30 + d2*0.15 + d3*0.15 + d4*0.10 + d5*0.10 + d6*0.10 + d7*0.10
    return {
        "id": ev["id"], "set": set_["set_id"],
        "score": round(score, 3),
        "dimensions": {"D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5, "D6": d6, "D7": d7},
        "d1_note": d1_note,                   # 人工判分时的提示
        "trace_summary": {
            "duration_sec": trace["duration_sec"],
            "tool_call_count": trace["tool_call_count"],
            "input_tokens": trace["input_tokens"],
            "output_tokens": trace["output_tokens"],
            "tool_chain": [t["tool"] for t in trace["tool_chain"]],
        },
        "verdict": "PASS" if score >= 0.7 else ("PARTIAL" if score >= 0.4 else "FAIL"),
    }
```

> ℹ️ 下列符号为**待实现桩函数**，非可直接调用的完整实现（INFO #12）：
> - `extract_tool_args(content)`：从 `messages.content`（role='tool'）中解析工具入参，建议按 tool_name 分支用正则。
> - `extract_table_names(text)`：从 final_answer 中正则提取 `st_xxx_r` / `dsm_xxx` / `eq_xxx` 形态表名。
> - `SCHEMA_TABLES_FROM_SCHEMA_MD`：**必须**从 `_shared/references/schema.md` 解析得到的规范表名集，**不能**复用 `references/data-profiling.md` §6.7 那个含 11 张幽灵表的 profiler 白名单（reviews/review-shared.md M2 已确认该白名单被污染）。
> - `find_session_by_source(source_tag)`：`SELECT id FROM sessions WHERE source = ? ORDER BY started_at DESC LIMIT 1`。
> - `is_runnable(ev, set_)`：就绪度过滤，只跑🟢集（见 §2 就绪度分级表）。

---

## 6. 评测报告格式

### 6.1 机器可读 JSON（`hermes-eval-results-{timestamp}.json`）

```json
{
  "eval_run_id": "hermes-eval-20260811-{timestamp}",
  "evaluated_at": "2026-08-11T...",
  "master_version": "1.0",
  "total_questions": 293,
  "evaluated_questions": 164,
  "skipped": {
    "placeholder_reconstructed": 29,
    "expected_placeholder": 26,
    "title_only_prompt": 74
  },
  "overall_score": 0.72,
  "overall_verdict": "PARTIAL",
  "per_set_summary": {
    "routing-evals-v2": {"avg_score": 0.85, "pass": 38, "partial": 5, "fail": 2},
    "inspection-eval-cases": {"avg_score": 0.78, "pass": 30, "partial": 12, "fail": 5}
  },
  "per_dimension_summary": {
    "D1_functional": {"avg": 0.82, "fail_count": 12},
    "D2_routing":    {"avg": 0.91, "fail_count": 3},
    "D3_tool_eff":   {"avg": 0.74, "fail_count": 8},
    "D4_token_eff":  {"avg": 0.68, "fail_count": 15},
    "D5_latency":    {"avg": 0.71, "fail_count": 10},
    "D6_halluc":     {"avg": 0.95, "fail_count": 1},
    "D7_completeness":{"avg": 0.79, "fail_count": 7}
  },
  "results": [ {judge output per question} ]
}
```

### 6.2 人读 Markdown 报告（`hermes-eval-results-{timestamp}.md`）

报告结构：

1. **评测概览**：时间、题数、总体得分、总体结论
2. **就绪度分级统计**：🟢/🟡/🟠 三类各多少题，跳过原因
3. **按集合汇总表**：每个 set 的 avg_score / pass / partial / fail
4. **按维度汇总表**：7 个维度各自的 avg / fail_count
5. **失败题明细**：score < 0.4 的题，列出 dimensions 细项与 trace_summary
6. **占位题面评测专项**：29 个 placeholder-reconstructed 题的通过率单独统计
7. **与历史评测对比**（若有）：本次 vs 上次的 overall_score / per_dimension 变化

---

## 7. 执行步骤（操作手册）

### Step 0：前置确认

```bash
# 1. 确认 hermes CLI 可用
which hermes && hermes --version

# 2. 确认 state.db 存在且可读
ls -la ~/.hermes/state.db
sqlite3 ~/.hermes/state.db ".tables"

# 3. 确认 master JSON 就位
python3 -c "import json; d=json.load(open('docs/eval-questions-master.json')); print(d['summary'])"
```

### Step 1：Layer A 静态评测（先跑，作为基线）

```bash
# chatbi SQL lint 评测
cd powerelf-chatbi && python3 impl/eval_runner.py

# inspection 规则层评测
cd powerelf-inspection && python3 impl/eval_runner.py
```

这些 runner 不连真实库、不耗 LLM Token、确定性可重复，先跑出基线。

### Step 2：Layer B Hermes 平台 LLM 实际评测

```bash
# 新增 runner
python3 docs/hermes_eval_runner.py \
  --master docs/eval-questions-master.json \
  --skip-placeholder \
  --out-dir docs/
```

参数说明：
- `--readiness green`：只跑🟢可自动评测集（默认）；`yellow|orange` 可切换；INFO #8：runner 内置 `is_runnable(ev, set_)` 按就绪度过滤，默认跳过 29 个 placeholder + 26 个 expected-placeholder + 74 个 title-only，只跑 164 题
- `--only-set routing-evals-v2`：只跑指定集合（调试用）
- `--no-fresh-user-id`：关闭每题新 user_id 绕缓存（默认开启）

> ⚠️ P1 #4 修正：原 `--fresh-user-id` 描述引用了不存在的 `hermes chat --user-id` flag。实际绕缓存用 `--source` 标签（每题 source 不同即绕过 `workflow:{user_id}:{minute_bucket}` 缓存），`--fresh-user-id` 改为 runner 内部用 `--source eval-{ts}-{qid}` 实现的语义开关。

### Step 3：轨迹分析与报告生成

```bash
# 从 state.db 提取所有评测 session 的轨迹
python3 docs/hermes_eval_runner.py --analyze-only --eval-run-id hermes-eval-20260811-{timestamp}
```

生成：
- `docs/hermes-eval-results-{timestamp}.json`
- `docs/hermes-eval-results-{timestamp}.md`

### Step 4：人工复核失败题

对 score < 0.4 的题，人工检查：
- 是 prompt 质量问题（题面模糊）还是 skill 能力问题
- 是路由未命中还是工具选择错误
- 是否为占位题面的补写质量问题

---

## 8. 评测维度与现有评测产物的映射

本方案 7 个维度并非凭空设计，而是对现有评测产物中已出现但分散的指标的归一化：

| 维度 | 现有评测产物中的对应指标 |
|---|---|
| D1 功能性正确 | inspection `eval_cases/cases.json` 的 should_report/should_not_report；chatbi cases.json 的 fails_with/clean |
| D2 路由命中 | `routing-evals-v1/v2` 的路由正确性；`powerelf-data-governance/tests/HERMES_TESTING_GUIDE.md` 的"Route 验证"段 |
| D3 工具调用效率 | `_shared/hermes_test_final_report.md` 的 tool_call_count KPI（≤2 优秀） |
| D4 Token 效率 | `_shared/hermes_test_final_report.md` 的 input/output_tokens KPI（<15K/<3K） |
| D5 响应时延 | `_shared/hermes_test_final_report.md` 的 duration KPI（<30s 优秀） |
| D6 幻觉抑制 | `reviews/review-shared.md` M2 发现的"profiler 白名单含 11 张 schema.md 未记录的表名"——正是幻觉表名。⚠️ D6 ground truth **必须**是 `_shared/references/schema.md` 的规范表名集，**不能**复用 `references/data-profiling.md` §6.7 那个含 11 张幽灵表的 profiler 白名单（M2 已确认该白名单被污染） |
| D7 回答完整性 | inspection `eval_criteria.md` EVAL1-EVAL10 的"结论应包含 X"类断言 |

---

## 9. 已知限制与风险

| 限制 | 影响 | 缓解措施 |
|---|---|---|
| early-warning-v3 矩阵 74 题仅标题无完整 prompt | 这 74 题无法自动评测 | 人工补全 prompt，或回溯原始 hermes 会话 |
| 29 个占位题面为补写非原文 | 评测结果不代表原文题面真实能力 | 报告中单独统计占位题通过率，结论加免责声明 |
| data-governance-realdata-tests 20/26 题的 expected_output 为占位符 | 不可自动判分 | 人工补全 expected_output 后再跑 |
| hermes SOP 驱动的 LLM 层多轮耗 Token 难缓存 | 每次评测都消耗真实 Token，成本高 | 用 `--only-set` 先小规模跑，确认无问题再全量 |
| state.db 的 tool_calls 表结构为推测 | extract_trace 可能字段不匹配 | Step 0 先 `.schema` 确认实际表结构，再调整脚本 |
| workflow 缓存 5 分钟窗口 | 若不绕过缓存，会测到缓存命中 | 每题用新 user_id（`--fresh-user-id`） |

---

## 10. 交付物清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `docs/hermes-eval-implementation-plan.md` | ✅ 本文档 | 实施方案 |
| `docs/hermes_eval_runner.py` | 🔲 待新增 | Layer B 评测 runner |
| `docs/hermes-eval-results-{timestamp}.json` | 🔲 运行后生成 | 机器可读评测结果 |
| `docs/hermes-eval-results-{timestamp}.md` | 🔲 运行后生成 | 人读评测报告 |
| `docs/eval-questions-master.json` | ✅ 已生成 | 全阶段评测问题主清单（293 题） |

---

## 11. 后续演进

1. **自动回归门禁**：把 `hermes_eval_runner.py` 接入 CI，每次 SKILL.md / rules 变更后自动跑 Layer A + Layer B，score 下降即阻断合入。
2. **占位题面原文复原**：回溯原始 hermes 测试会话，把 29 个 placeholder-reconstructed 题面替换为原文。
3. **expected_output 补全**：人工补全 data-governance-realdata-tests 20 题的 expected_output，使其可自动判分。
4. **维度权重调优**：积累 3-5 轮评测数据后，根据各维度的 fail_count 与业务重要性，重新校准 D1-D7 的权重。
5. **A/B 对比评测**：对同一批评测题，分别跑"优化前 SKILL.md"和"优化后 SKILL.md"，量化 per-dimension 提升。
