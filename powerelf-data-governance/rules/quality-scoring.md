# 统计评分规则

> 统计数据来源：
> - 缺失统计：`stats_data_missing_daily`（每日缺失统计）
> - 异常统计：`stats_data_anomaly_daily`（每日异常统计）
> - 采集统计：`stats_data_collection_daily`（每日采集统计）
> - 缺失记录：`eq_data_missing_record`（缺失记录明细）
> - 异常记录：`eq_data_anomaly_record`（异常记录明细）
> - 离线记录：`eq_equip_offline_record`（离线记录）
> - 设备主表：`eq_equip_base`（设备信息，含厂商 manufacturer 字段）

## 核心算法

四维度加权评分（总分100）。详见 `algorithms/scoring-formulas.md`。

## 评分维度

| 维度 | 权重 | 原权重 | 说明 |
|------|------|--------|------|
| 数据质量 | 35% | 50% | 基于缺失率+异常率 |
| 运行稳定性 | 10% | 10% | 基于离线天数比+异常天数比 |
| 故障频率 | 40% | 40% | 基于离线次数+异常次数 |
| 数据完整性 | 15% | [新增] | 基于数据覆盖率 |

摒弃原始实现中质量50%的过高权重，增加完整性维度。

## 维度一：数据质量（35%）

```
输入: missingRatio（缺失率）, anomalyRatio（异常率）

if missingRatio + anomalyRatio >= 0.3:
  missingScore = 0
else:
  missingScore = (0.3 - missingRatio) * 10/3 * 0.6

if anomalyRatio >= 0.3:
  anomalyScore = 0
else:
  anomalyScore = (0.3 - anomalyRatio) * 10/3 * 0.4

qualityScore = (missingScore + anomalyScore) * 0.35 * 100
```

## 维度二：运行稳定性（10%）

```
输入: offlineDateRatio（离线天数占比）, anomalyDateRatio（异常天数占比）

stabilityScore = ((1 - offlineDateRatio) * 0.5 + (1 - anomalyDateRatio) * 0.5) * 0.1 * 100
```

## 维度三：故障频率（40%）

```
输入: offlineCount（离线次数）, anomalyCount（异常次数）

faultPenalty = offlineCount * 5 + anomalyCount * 5

if faultPenalty > 100:
  faultScore = 0
else:
  faultScore = (100 - faultPenalty) * 0.4
```

## 维度四：数据完整性（15%）— 新增

```
输入: actualRecords（实际采集记录数）, expectedRecords（期望记录数）

completenessRatio = actualRecords / expectedRecords

if completenessRatio >= 0.95:
  completenessScore = 15
elif completenessRatio >= 0.8:
  completenessScore = completenessRatio * 15
else:
  completenessScore = completenessRatio * 10  # 低于80%加重惩罚
```

> **完整性 tier 定义**（绿>99% / 黄95-99% / 橙80-95% / 红<80%）以 [`../../_shared/references/data-profiling.md`](../../_shared/references/data-profiling.md) 的 `completeness_tier` 函数为单一事实源，本规则不复制阈值。

## 时间衰减 — 新增

原始实现中所有日期的数据权重相同。增加时间衰减：

```
lambda = 0.05（衰减系数）
weight(dayAgo) = exp(-lambda * dayAgo)

示例:
  当天数据: weight = 1.0
  7天前:    weight = 0.70
  14天前:   weight = 0.50
  30天前:   weight = 0.22

应用: 各维度的输入指标按时间加权平均
```

## 评分趋势 — 新增

```
当前评分 = score_current
上期评分 = score_previous
变化 = score_current - score_previous

if 变化 > 5:
  → 趋势: 改善 ↑
if 变化 < -5:
  → 趋势: 恶化 ↓
else:
  → 趋势: 稳定 →
```

## 评分区间

| 区间 | 等级 | 含义 |
|------|------|------|
| 90-100 | 优秀 | 设备运行健康 |
| 80-89 | 良好 | 轻微问题 |
| 60-79 | 一般 | 需要关注 |
| < 60 | 较差 | 需要维护 |

## 厂商排名

按厂商分组统计设备评分：
- 平均分 = mean(该厂商所有设备评分)
- 评分分布: <60 / 60-79 / 80-89 / 90-100 各区间设备数
- 排名: 按平均分降序
