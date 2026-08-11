# Hermes 平台 LLM 实际评测报告

| 字段 | 值 |
|---|---|
| 评测运行 ID | `hermes-eval-20260811-114111` |
| 评测时间 | 2026-08-11T11:41:11.586746 |
| master 版本 | 1.0 |
| 就绪度过滤 | green |
| 总题数 | 293 |
| 实际评测题数 | 164 |
| 总体得分 | **0.0** |
| 总体结论 | **FAIL** |

## 跳过统计

| 跳过原因 | 题数 |
|---|---|
| placeholder_reconstructed | 29 |
| readiness_filter | 94 |
| empty_prompt_or_expected | 6 |
| max_questions_limit | 0 |

## 按集合汇总

| 集合 | 题数 | 平均得分 | PASS | PARTIAL | FAIL |
|---|---|---|---|---|---|
| darwin-test-prompts | 3 | 0.0 | 0 | 0 | 3 |
| data-governance-routing-list | 53 | 0.0 | 0 | 0 | 53 |
| inspection-eval-cases | 47 | 0.0 | 0 | 0 | 47 |
| inspection-eval-criteria | 10 | 0.0 | 0 | 0 | 10 |
| routing-evals-v1 | 6 | 0.0 | 0 | 0 | 6 |
| routing-evals-v2 | 45 | 0.0 | 0 | 0 | 45 |

## 按维度汇总

| 维度 | 平均得分 | 失败题数（<0.4） |
|---|---|---|
| D1_functional | 0.0 | 164 |
| D2_routing | 0.0 | 164 |
| D3_tool_eff | 0.0 | 164 |
| D4_token_eff | 0.0 | 164 |
| D5_latency | 0.0 | 164 |
| D6_halluc | 0.0 | 164 |
| D7_completeness | 0.0 | 164 |

## 失败题明细（score < 0.4）

| 题号 | 集合 | 得分 | 结论 | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|---|---|---|---|
| DG-P01 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P02 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P03 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P04 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P05 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P06 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P07 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P08 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P09 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P10 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P11 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P12 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P13 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P14 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P15 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P16 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P17 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P18 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P19 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P20 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P21 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P22 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P23 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P24 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P25 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P26 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P27 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P28 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P29 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P30 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P31 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P32 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P33 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P34 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P35 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P36 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P37 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P38 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P39 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P40 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P41 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P42 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P43 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P44 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P45 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-P46 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-N01 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-N02 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-N03 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-N04 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-N05 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-N06 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DG-N07 | data-governance-routing-list | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 0 | routing-evals-v1 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1 | routing-evals-v1 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2 | routing-evals-v1 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 3 | routing-evals-v1 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 4 | routing-evals-v1 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 5 | routing-evals-v1 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 0 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 3 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 4 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 5 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 6 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 7 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 8 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 9 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 10 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 11 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 12 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 13 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 14 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 15 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 16 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 17 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 18 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 19 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 20 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 21 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 22 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 23 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 24 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 25 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 26 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 27 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 28 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 29 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 30 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 31 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 32 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 33 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 34 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 35 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 36 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 37 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 38 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 39 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 40 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 41 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 42 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 43 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 44 | routing-evals-v2 | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL1 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL2 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL3 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL4 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL5 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL6 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL7 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL8 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL9 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EVAL10 | inspection-eval-criteria | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| WL-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| WL-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| WL-POS-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| WL-NEG-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| RAIN-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| RAIN-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PRES-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PRES-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PRES-SPIKE-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PERC-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PERC-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GNSS-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GNSS-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GATE-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GATE-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GATE-POS-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GATE-NEG-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PUMP-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PUMP-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PUMP-POS-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| WQ-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| WQ-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SOIL-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SOIL-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| TERM-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| TERM-POS-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| TERM-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| INSP-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| INSP-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EQUIP-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EQUIP-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| ALERT-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| ALERT-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MAD-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MAD-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| CORR-POS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| CORR-NEG-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| CORR-POS-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| CORR-NEG-2 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| QG-RED-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| QG-PLACEHOLDER-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SEASON-GUARD-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DIAG-HIT-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| DIAG-MISS-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EMPTY-NA-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EMPTY-ND-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EMPTY-QF-1 | inspection-eval-cases | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1 | darwin-test-prompts | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2 | darwin-test-prompts | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 3 | darwin-test-prompts | 0.0 | DRY-RUN | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

---

*报告由 `docs/hermes_eval_runner.py` 自动生成，评测运行 ID：`hermes-eval-20260811-114111`*