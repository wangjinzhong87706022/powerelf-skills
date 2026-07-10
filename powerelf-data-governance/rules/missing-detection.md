# 缺失检测规则

## 核心算法

基于采集频率的期望周期数比较法。

### 输入

- `freq` — 采集频率（分钟/次），来自设备-表映射配置
- `startTime` / `endTime` — 检测时间范围（默认前一天 00:00 ~ 当天 00:00）
- `collectTimes` — 实际采集时间戳列表

### 判断流程

```
1. expectedCount = ceil((endTime - startTime) / freq)
2. if expectedCount > len(collectTimes) → 存在缺失
3. 在 collectTimes 首尾添加 startTime 和 endTime 作为边界
4. for i in range(1, len(collectTimes)):
     timeDiff = collectTimes[i] - collectTimes[i-1]  (分钟)
     expectedPeriods = ceil(timeDiff / freq)
     if expectedPeriods >= 2:
       missingCount = expectedPeriods - 1
       if i == 1: missingCount += 1   # 首条数据就缺失
       记录: {startTime: collectTimes[i-1], endTime: collectTimes[i], count: missingCount}
```

### 输出

缺失记录列表：`{equipmentCode, missingStartTime, missingEndTime, missingCount, timePeriodId}`

## 增强规则

### 连续缺失递增告警

```
连续缺失周期数:
  1-2 个周期 → INFO
  3-5 个周期 → WARNING
  6-10 个周期 → ERROR
  > 10 个周期 → CRITICAL
```

### 缺失模式识别

```
如果同一设备连续 3 天在相同时段(±30分钟)出现缺失:
  → 标记为"周期性缺失"，可能原因：定时维护、信号遮挡
  → 建议：调整采集频率或排查该时段的环境因素

如果缺失分布随机，无明显时间规律:
  → 标记为"随机缺失"，可能原因：网络不稳定、设备故障
  → 建议：检查设备通信模块
```

### 缺失率趋势

```
当日缺失率 = 当日缺失次数 / 当日期望采集次数
环比变化 = (当日缺失率 - 前日缺失率) / 前日缺失率

if 环比变化 > 50%:
  → 预警：缺失率显著上升
if 连续 3 天缺失率 > 10%:
  → 预警：设备数据质量持续恶化
```

## 时间段枚举

| 时段ID | 名称 | 时间范围 |
|--------|------|----------|
| 1 | 凌晨 | 00:00 - 05:59 |
| 2 | 早晨 | 06:00 - 07:59 |
| 3 | 上午 | 08:00 - 10:59 |
| 4 | 中午 | 11:00 - 13:59 |
| 5 | 下午 | 14:00 - 16:59 |
| 6 | 傍晚 | 17:00 - 18:59 |
| 7 | 晚上 | 19:00 - 23:59 |
