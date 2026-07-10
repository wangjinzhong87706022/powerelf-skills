# 评分公式详解

## 总分构成

```
总分 = 数据质量(35%) + 运行稳定性(10%) + 故障频率(40%) + 数据完整性(15%)
```

原始实现为三维度(50%+10%+40%)，改进为四维度。

## 维度一：数据质量（35%）

### 公式

```
missingScore = max(0, (0.3 - missingRatio) * 10/3) * 0.6
anomalyScore = max(0, (0.3 - anomalyRatio) * 10/3) * 0.4

qualityScore = (missingScore + anomalyScore) * 0.35 * 100
```

### 解读

- 缺失率+异常率 >= 30% 时，缺失分数为 0
- 缺失率权重 0.6，异常率权重 0.4（缺失比异常更影响数据可用性）
- 最终乘以 0.35 的维度权重

### 示例

```
missingRatio = 5%, anomalyRatio = 3%
missingScore = (0.3 - 0.05) * 10/3 * 0.6 = 0.500
anomalyScore = (0.3 - 0.03) * 10/3 * 0.4 = 0.360
qualityScore = (0.500 + 0.360) * 0.35 * 100 = 30.1
```

## 维度二：运行稳定性（10%）

### 公式

```
stabilityScore = ((1 - offlineDateRatio) * 0.5 + (1 - anomalyDateRatio) * 0.5) * 0.1 * 100
```

### 示例

```
offlineDateRatio = 10% (一个月3天离线)
anomalyDateRatio = 5%
stabilityScore = (0.9 * 0.5 + 0.95 * 0.5) * 0.1 * 100 = 9.25
```

## 维度三：故障频率（40%）

### 公式

```
penalty = offlineCount * 5 + anomalyCount * 5

if penalty > 100:
  faultScore = 0
else:
  faultScore = (100 - penalty) * 0.4
```

### 解读

- 每次离线扣 5 分，每次异常扣 5 分
- 超过 20 次（100/5）故障即得 0 分
- 最终乘以 0.4 的维度权重

### 示例

```
offlineCount = 3, anomalyCount = 2
penalty = 3*5 + 2*5 = 25
faultScore = (100 - 25) * 0.4 = 30.0
```

## 维度四：数据完整性（15%）— 新增

### 公式

```
completenessRatio = actualRecords / expectedRecords

if completenessRatio >= 0.95:
  completenessScore = 15
elif completenessRatio >= 0.8:
  completenessScore = completenessRatio * 15
else:
  completenessScore = completenessRatio * 10  # 低于80%加重惩罚
```

### 示例

```
actualRecords = 22, expectedRecords = 24 (每小时一次)
completenessRatio = 22/24 = 0.917
completenessScore = 0.917 * 15 = 13.75
```

## 时间衰减

### 公式

```
weight(dayAgo) = exp(-lambda * dayAgo)
lambda = 0.05

应用: 各维度的输入指标按天加权平均
weightedMetric = sum(metric[i] * weight(i)) / sum(weight(i))
```

### 衰减曲线

```
天数    权重
0       1.000
3       0.861
7       0.705
14      0.497
30      0.223
```

### 效果

- 近期数据权重高，反映设备当前状态
- 30天前的数据权重仅 22%，避免历史问题过度影响当前评分
- 如果近期表现好但历史差，评分会逐渐回升

## 综合示例

```
某设备评分:
  数据质量: missingRatio=5%, anomalyRatio=3%  → qualityScore = 30.1
  运行稳定性: offlineDateRatio=10%, anomalyDateRatio=5%  → stabilityScore = 9.25
  故障频率: offlineCount=3, anomalyCount=2  → faultScore = 30.0
  数据完整性: completenessRatio=91.7%  → completenessScore = 13.75

总分 = 30.1 + 9.25 + 30.0 + 13.75 = 83.1 → 良好

与上期(78分)对比: +5.1 → 趋势: 稳定→
```
