# Hermes 平台 LLM 实际评测报告

| 字段 | 值 |
|---|---|
| 评测运行 ID | `hermes-eval-20260812-120415` |
| 评测时间 | 2026-08-12T12:12:24.438700 |
| master 版本 | 1.0 |
| 就绪度过滤 | green |
| 总题数 | 293 |
| 实际评测题数 | 5 |
| 总体得分 | **0.564** |
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
| data-governance-routing-list | 5 | 0.564 | 1 | 4 | 0 |

## 按维度汇总

| 维度 | 平均得分 | 失败题数（<0.4） |
|---|---|---|
| D1_functional | 0.5 | 0 |
| D2_routing | 0.5 | 0 |
| D3_tool_eff | 0.3 | 3 |
| D4_token_eff | 0.941 | 0 |
| D5_latency | 0.1 | 4 |
| D6_halluc | 1.0 | 0 |
| D7_completeness | 0.9 | 0 |

---

*报告由 `docs/hermes_eval_runner.py` 自动生成，评测运行 ID：`hermes-eval-20260812-120415`*