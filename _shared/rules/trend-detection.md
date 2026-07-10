# 趋势异常检测规则

## 概述

对监测数据进行趋势分析，发现潜在异常。

## 趋势检测方法

### 1. 线性趋势（Mann-Kendall 检验简化版）

```
输入: 时间序列 values[]

计算:
  S = 0
  for i in range(n):
    for j in range(i+1, n):
      if values[j] > values[i]: S += 1
      elif values[j] < values[i]: S -= 1

  if S > 0: 趋势上升
  if S < 0: 趋势下降
  if S ≈ 0: 无明显趋势

显著性:
  |S| > 临界值 → 趋势显著
```

### 2. 变化点检测

```
对时间序列 values[]:
  for i in range(1, n-1):
    leftMean = mean(values[:i])
    rightMean = mean(values[i:])
    diff = |rightMean - leftMean|

    if diff > 阈值:
      → 位置 i 可能是变化点

变化点含义: 数据的统计特性在此位置发生突变
```

### 3. 周期性检测

```
对时间序列 values[]:
  计算自相关函数 ACF(lag)
  if ACF 在某个 lag 处出现显著峰值:
    → 存在周期性，周期 = lag

典型周期:
  水位: 24小时（日变化）
  温度: 24小时（日变化）
  雨量: 季节性
```

## 与其他规则的配合

```
趋势检测发现异常趋势:
  → 结合阈值规则(threshold-rules.md)判断是否超限
  → 结合趋势规则(trend-rules in early-warning)判断是否需要预警

监控模块的趋势检测偏向"数据层面的异常发现"
预警模块的趋势规则偏向"是否触发预警通知"
```
