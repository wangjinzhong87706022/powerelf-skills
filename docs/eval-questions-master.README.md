# 全阶段评测问题主清单（eval-questions-master）说明

> 本文档说明 `docs/eval-questions-master.json` 的用途、结构、来源与维护方式。
> 生成脚本：`docs/build_eval_questions_master.py`（可复跑，输出直接覆盖 master JSON）。

---

## 1. 用途

将本项目**各阶段、各 skill 独立生成的评测问题清单**归一化为单一 JSON 文件，
统一采用 `evals-database-v2.json` 的规范格式，便于：

- 跨阶段横向比对（各阶段测了什么、覆盖什么能力）
- 统一跑评测（`prompt` + `expected_output` 可直接喂给 runner）
- 追踪缺口（哪些问题原文缺失、哪些是补写的占位题面）

---

## 2. 数据来源（8 个集合，共 293 题）

| set_id | 阶段 | 来源文件 | 题数 |
|---|---|---|---|
| `early-warning-v3-matrix` | 阶段1 预警分析 | `early-warning-v3/tests/test-data-scenarios.md` + 3 个 SQL | 103（74 原文 + 29 占位） |
| `data-governance-routing-list` | 阶段2 数据治理 | `powerelf-data-governance/docs/questions.md` | 53（46 正例 + 7 负例） |
| `data-governance-realdata-tests` | 阶段2 数据治理 | `powerelf-data-governance/docs/test-questions.md` | 26（T1.1–T11.1） |
| `routing-evals-v1` | 阶段3 路由评测 | `skill-creator-workspace/data-governance-routing/evals.json` | 6 |
| `routing-evals-v2` | 阶段3 路由评测 | `skill-creator-workspace/data-governance-routing/evals-database-v2.json` | 45 |
| `inspection-eval-criteria` | 阶段4 智能巡检 | `powerelf-inspection/autoresearch/eval_criteria.md` | 10（EVAL 1–10） |
| `inspection-eval-cases` | 阶段4 智能巡检 | `powerelf-inspection/autoresearch/eval_cases/cases.json` | 47 |
| `darwin-test-prompts` | 阶段5 skill 优化器 | `darwin-skill/test-prompts.json` | 3 |

> 注：`skill-creator-workspace/.../iteration-1/eval-0..44/` 的 45 个 `eval_metadata.json`
> 是 routing-evals-v2 的运行时逐题元数据（断言形式），内容与 v2 对应，不重复收编。

---

## 3. 格式规范

顶层结构：

```json
{
  "master_version": "1.0",
  "generated_at": "2026-08-10",
  "base_format": "evals-database-v2.json 规范: {id, name, prompt, expected_output}",
  "summary": { "total_questions": 293, "per_set": {...}, "known_gaps": {...} },
  "sets": [ ... ]
}
```

每个 set：

| 字段 | 说明 |
|---|---|
| `set_id` | 集合唯一标识 |
| `phase` | 所属阶段 |
| `source_files` | 原始来源文件 |
| `description` | 集合说明 |
| `gap_note` | 缺口说明（仅 early-warning 有） |
| `placeholder_count` / `placeholder_ids` | 占位题数量与 ID 列表（仅 early-warning 有） |
| `gaps` | 原文缺失的题号 |
| `evals` | 题目数组 |

每条 eval（统一字段）：

| 字段 | 说明 |
|---|---|
| `id` | 题号（Q001/Q103、DG-P01、T1.1、EVAL1、WL-POS-1 …） |
| `name` | 题名 |
| `prompt` | 问题原文（可直接喂给 agent） |
| `expected_output` | 预期输出/判定标准 |
| `prompt_source` | 来源标记：`title-only`（仅标题）／`placeholder-reconstructed`（补写占位）／缺省（原文完整） |

---

## 4. early-warning-v3 缺口与占位说明

**缺口事实**（已核实仓库 + git 历史）：
- `test-data-scenarios.md` 矩阵跳号：Q36–Q61、Q99–Q101 无题面；
- 3 个测试 SQL 仅覆盖 Q1–Q12 / Q64 / Q73 / Q75 / Q77 / Q89 / Q90 / Q98 / Q102 / Q103；
- 即「SQL 声称覆盖 103 个问题」，实际矩阵仅有 74 题有映射。

**占位补写策略**：29 个缺号按相邻分类 + SKILL.md 真实能力补写，
全部标注 `prompt_source: "placeholder-reconstructed"`，并在 `expected_output`
中追加「（占位：非原文，按相邻分类补写）」字样，禁止与原文混同：

| 缺号段 | 题数 | 补写分类 |
|---|---|---|
| Q36–Q40 | 5 | 告警处置与建议 |
| Q41–Q45 | 5 | 告警合并与去重 |
| Q46–Q50 | 5 | 告警升级 |
| Q51–Q56 | 6 | 告警恢复与生命周期（状态机） |
| Q57–Q61 | 5 | 审计与操作分析 |
| Q99–Q101 | 3 | 组合边界 / 跨域边界叠加 / 气象关联边界 |

如需复原**原文**，只能回溯原始 hermes 测试会话；占位题面仅作占位与覆盖率补全。

---

## 5. 维护与复跑

```bash
# 修改任意来源文件（如 test-data-scenarios.md 补上原文）后：
python3 docs/build_eval_questions_master.py
# → 重新生成 docs/eval-questions-master.json，并打印每集合题数统计
```

新增评测题的推荐路径：

1. 在对应 skill 的原始清单文件（如 `docs/questions.md`）中新增题目；
2. 若新清单不属于现有 8 个集合，在脚本 `build()` 中新增一个 set；
3. 复跑脚本，确认 `summary.total_questions` 与 `per_set` 正确。

**校验方式**：脚本输出 + 手工检查 `eval-questions-master.json` 的
`summary.total_questions`、`per_set`、`known_gaps` 三项一致即视为生成成功。

---

## 6. 已知限制

- `early-warning-v3-matrix` 中 74 条原文题目仅有标题（矩阵只存标题+场景+数据要求），
  prompt 字段为标题而非完整提问语句；
- 29 条占位题面为补写内容，非原始测试问题；
- 其余 6 个集合均为原文完整（prompt/expected_output 可直接使用）。
