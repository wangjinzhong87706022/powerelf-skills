# Hermes 平台 LLM 实际评测报告

| 字段 | 值 |
|---|---|
| 评测运行 ID | `hermes-eval-20260812-133118` |
| 评测时间 | 2026-08-12T13:40:43.311847 |
| master 版本 | 1.0 |
| 就绪度过滤 | green |
| 总题数 | 293 |
| 实际评测题数 | 5 |
| 总体得分 | **0.62** |
| 总体结论 | **PARTIAL** |

## 跳过统计

| 跳过原因 | 题数 |
|---|---|
| placeholder_reconstructed | 0 |
| readiness_filter | 0 |
| empty_prompt_or_expected | 0 |
| max_questions_limit | 48 |

## 按集合汇总

| 集合 | 题数 | 平均得分 | PASS | PARTIAL | FAIL |
|---|---|---|---|---|---|
| data-governance-routing-list | 5 | 0.62 | 2 | 2 | 1 |

## 按维度汇总

| 维度 | 平均得分 | 失败题数（<0.4） |
|---|---|---|
| D1_functional | 0.433 | 2 |
| D2_routing | 0.8 | 0 |
| D3_tool_eff | 0.3 | 3 |
| D4_token_eff | 0.764 | 1 |
| D5_latency | 0.584 | 2 |
| D6_halluc | 1.0 | 0 |
| D7_completeness | 0.9 | 0 |

## 失败题明细（score < 0.4）

| 题号 | 集合 | 得分 | 结论 | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|---|---|---|---|
| DG-P01 | data-governance-routing-list | 0.263 | FAIL | 0.0 | 0.75 | 0.0 | 0.0 | 0.0 | 1.0 | 0.5 |

---

*报告由 `docs/hermes_eval_runner.py` 自动生成，评测运行 ID：`hermes-eval-20260812-133118`*