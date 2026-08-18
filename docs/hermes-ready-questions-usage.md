# Hermes CLI 正式可用问题集使用指南

> **文件清单**：
> - `docs/eval-questions-formal-full.json` — 290题完整正式问题集（JSON）
> - `docs/hermes-ready-questions.md` — 按skill分类的问题清单（Markdown）
> - `docs/hermes-ready-questions.json` — 带skill映射的机器可读版本（JSON）

---

## 📊 总览

| 维度 | 数据 |
|------|------|
| **总题数** | 290 题 |
| ✅ **可自动判分（green）** | 241 题 |
| ⚠️ **需人工判分（yellow）** | 49 题 |
| **覆盖 Skill** | 4 个 |

---

## 🎯 4 个 Skill 的问题分布

| Skill | green | yellow | 合计 | 说明 |
|-------|-------|--------|------|------|
| **powerelf-early-warning** | 74 | 29 | 103 | 预警分析（103题场景矩阵） |
| **powerelf-data-governance** | 59 | 20 | 79 | 数据治理（53+26题） |
| **powerelf-inspection** | 57 | 0 | 57 | 智能巡检（10+47题） |
| **powerelf-chatbi** | 51 | 0 | 51 | 路由测试（6+45题） |

---

## 💡 使用方式

### 方式 1：直接在 Hermes CLI 中提问

```bash
# 基本语法
hermes chat -s <skill> -q "<问题>" -Q

# 示例：查询水位异常（data-governance）
hermes chat -s powerelf-data-governance -q "帮我检查一下最近24小时水库水位数据有没有异常值，用MAD算法检测一下" -Q

# 示例：渗压突变检测（inspection）
hermes chat -s powerelf-inspection -q "渗压计416在5月20日有10kPa突变，工具是否检出？" -Q

# 示例：告警分析（early-warning）
hermes chat -s powerelf-early-warning -q "在场景1场景下，未确认告警数量。（4条未确认告警）" -Q
```

### 方式 2：批量测试（逐题提问）

```bash
# 提取所有 data-governance 的 green 题目
jq '.evals[] | select(.set_id=="data-governance-routing-list" and .readiness=="green")' docs/hermes-ready-questions.json

# 循环提问（示例：前5题）
jq -r '.evals[0:5][] | "\(.id)|\(.prompt)|\(.set_id)"' docs/hermes-ready-questions.json | while IFS='|' read id prompt set_id; do
  skill=$(jq -r --arg sid "$set_id" '.by_set[$sid].skill // "powerelf-data-governance"' docs/hermes-ready-questions.json)
  echo "=== $id ==="
  hermes chat -s "$skill" -q "$prompt" -Q
done
```

### 方式 3：查看完整问题清单

```bash
# Markdown 格式（推荐人工阅读）
less docs/hermes-ready-questions.md

# JSON 格式（推荐脚本处理）
jq '.summary' docs/hermes-ready-questions.json
```

---

## 📋 题目质量说明

### ✅ Green（241题）：可直接用于自动判分

**特点**：
- prompt 为完整问题语句
- expected_output 明确可判分
- 可直接用于 `hermes_eval_runner.py` 自动评测

**示例**（来自 data-governance-routing-list）：

| ID | Prompt | Expected |
|----|--------|----------|
| DG-P01 | "帮我检查一下最近24小时水库水位数据有没有异常值，用MAD算法检测一下" | "MAD 异常检测" |
| DG-P02 | "帮我检测一下渗压数据的异常值" | "分指标阈值检测" |
| DG-P03 | "这些水位数据里有异常值吗？用 MAD 算法跑一下" | "MAD + 变化率综合判定" |

### ⚠️ Yellow（49题）：prompt 完整但 expected 需人工判分

**来源**：
1. **data-governance-realdata-tests**（20题）：基于真实库的验证题，expected_output 为"见文档预期"
2. **early-warning 占位题**（29题）：补写的完整问题，expected_output 也为占位符

**示例**（来自 data-governance-realdata-tests）：

| ID | Prompt | Expected |
|----|--------|----------|
| T1.1 | "请检测128号测站(st_rsvr_r)最近1周的水位(rz)数据是否有异常。" | 见文档预期 |
| T2.1 | "检查一下st_rsvr_r表的606K2153号站在5月份有没有数据缺失" | 见文档预期 |

**处理方式**：可人工提问后核对实际输出是否满足业务需求

---

## 🔍 与原始评测集的差异

| 维度 | eval-questions-master.json | eval-questions-formal-full.json（本集） |
|------|---------------------------|------------------------------------------|
| **总题数** | 290 | 290（全部保留，red 已过滤） |
| **title-only 题目** | 74 题（early-warning Q1-Q74） | ✅ 已补全为完整问题语句 |
| **placeholder 题目** | 29 题（Q036-Q061, Q099-Q101） | ✅ 已补全为完整问题语句 |
| **expected 占位符** | 49 题（realdata-tests + 占位题） | ⚠️ 保留，标注为 yellow |
| **可直接提问** | ❌ 74 题太简短 | ✅ 290 题均可直接提问 |

---

## 📌 重要说明

### 1. early-warning 的补全策略

**原始 title-only**：
```
prompt: "未确认告警数量"
expected: "场景：场景1；数据要求：4条未确认告警"
```

**补全为完整问题**：
```
prompt: "在场景1场景下，未确认告警数量。（4条未确认告警）"
```

**注意**：这是基于 expected_output 的元数据自动补全的，**不是原始测试问题**。

如需原始问题，需回溯原始 hermes 测试会话。

### 2. data-governance-realdata-tests 的黄色题目

这 20 题的 expected_output 均为"见文档预期"，是因为：
- 基于**真实库数据**（基准日 2026-07-08）
- 预期结果依赖于**真实查询结果**，无法在文档中静态描述
- 适合用于**人工验证**或**回归测试**，不适合自动判分

### 3. skill 映射关系

| set_id | hermes skill |
|--------|-------------|
| early-warning-v3-matrix | `powerelf-early-warning` |
| data-governance-routing-list | `powerelf-data-governance` |
| data-governance-realdata-tests | `powerelf-data-governance` |
| routing-evals-v1/v2 | `powerelf-chatbi` |
| inspection-eval-criteria/cases | `powerelf-inspection` |

---

## 🚀 快速开始

### 推荐流程

1. **浏览问题集**：
   ```bash
   less docs/hermes-ready-questions.md
   ```

2. **选择 skill 和问题**：
   ```bash
   # 查看所有 data-governance 的 green 题目
   jq '.evals[] | select(.set_id=="data-governance-routing-list" and .readiness=="green") | {id, prompt}' docs/hermes-ready-questions.json
   ```

3. **在 hermes CLI 中提问**：
   ```bash
   hermes chat -s powerelf-data-governance -q "帮我检查一下最近24小时水库水位数据有没有异常值，用MAD算法检测一下" -Q
   ```

4. **自动评测**（仅 green 题目）：
   ```bash
   python3 docs/hermes_eval_runner.py --only-set data-governance-routing-list
   ```

---

## 📁 文件清单

| 文件 | 说明 |
|------|------|
| `docs/eval-questions-master.json` | 原始评测集（290题） |
| `docs/eval-questions-formal.json` | 过滤 red 后的版本（216题） |
| `docs/eval-questions-formal-full.json` | 完整正式问题集（290题，含补全） |
| `docs/hermes-ready-questions.md` | 按 skill 分类的 Markdown 清单 |
| `docs/hermes-ready-questions.json` | 带 skill 映射的 JSON 版本 |
| `docs/generate_formal_eval_set.py` | 生成 formal 集的脚本 |
| `docs/generate_full_formal_set.py` | 补全 title-only 的脚本 |
| `docs/extract_hermes_ready_questions.py` | 生成 hermes-ready 清单的脚本 |

---

**生成时间**：2026-08-18
**版本**：v1.0
