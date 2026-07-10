# 算法详解

数据质量治理引擎的完整算法定义、公式推导与伪代码。

---

## 1. MAD 异常检测算法

### 1.1 数学定义

MAD（Median Absolute Deviation）是一种稳健的异常值检测方法，不受极端值影响。

```
MAD = median(|Xi - median(X)|)

Modified Z-score = 0.6745 * (Xi - median) / MAD
```

其中 0.6745 是正态分布下的归一化因子，使 MAD 与标准差在正态分布下一致。

### 1.2 伪代码

```python
def detect_outliers(data, windowSize, threshold):
    results = [False] * len(data)

    for i in range(len(data)):
        # 确定窗口范围
        halfWindow = windowSize // 2
        start = max(0, i - halfWindow)
        end = min(len(data), i + halfWindow + 1)
        window = data[start:end]

        # 计算中位数
        median = sorted(window)[len(window) // 2]

        # 计算 MAD
        absDeviations = sorted([abs(x - median) for x in window])
        mad = absDeviations[len(absDeviations) // 2]

        # 异常判定
        if mad > 0:
            modified_z_score = 0.6745 * abs(data[i] - median) / mad
            if modified_z_score > threshold:
                results[i] = True
        else:
            # MAD=0 时退化为与中位数的绝对差判断
            if abs(data[i] - median) > 0:
                results[i] = True

    return results
```

### 1.3 自适应窗口

```
windowSize = min(max(N * 0.15, 10), 50)

N < 10:     window = N（数据太少，只能全局）
N = 10:     window = 10
N = 100:    window = 15
N = 200:    window = 30
N = 333:    window = 50
N > 333:    window = 50（固定上限，避免计算量过大）
```

选择 15% 的理由：
- 水利数据通常每小时采集一次，一天 24 个点
- 15% 约等于 3-4 小时的窗口，能捕捉小时级异常
- 下限 10 保证小样本的统计意义
- 上限 50 限制计算复杂度

### 1.4 分指标阈值校准

| 指标 | 日常波动范围 | 典型标准差 | 推荐阈值 | 理由 |
|------|-------------|-----------|----------|------|
| 水位(rz) | +/-0.1m | ~0.05m | 3.0 | 变化平缓，3-sigma足够 |
| 雨量(p) | 0-50mm/h | 高度偏态 | 5.0 | 零膨胀分布，需要更高容忍 |
| 渗压 | +/-0.5kPa | ~0.2kPa | 4.0 | 中等波动 |
| GNSS | +/-0.5mm | ~0.2mm | 3.5 | 缓慢变化 |
| 流量 | +/-10% | 变化大 | 4.0 | 受闸门操作影响 |

阈值校准方法：
```
如果有历史正常数据:
  1. 对正常数据计算 MAD
  2. 统计正常数据中被误判为异常的比例（误报率）
  3. 调整阈值使误报率 < 1%

推荐:
  阈值 = 3.0 -> 误报率约 0.3%（正态分布下）
  阈值 = 4.0 -> 误报率约 0.01%
  阈值 = 5.0 -> 误报率约 0.0001%
```

### 1.5 变化率检测

MAD 只检测绝对偏差，对"缓慢但持续的偏移"不敏感。补充变化率检测：

```
changeRate = |Xi - Xi-1| / |Xi-1|

if previousValue != 0 and changeRate > 变化率阈值:
  -> 标记为"可疑"

变化率阈值:
  水位: 5%（日变化通常 < 1%）
  渗压: 3%
  GNSS: 2%
  流量: 10%
  雨量: 不适用（可突变）
```

### 1.6 综合判定

```
if MAD检测为异常 and 变化率超标:
  -> 确认异常（高置信度）
if MAD检测为异常 and 变化率正常:
  -> 可能异常（中置信度），检查是否为正常波动峰值
if MAD正常 and 变化率超标:
  -> 可疑（低置信度），标记待人工确认
```

---

## 2. 智能插值算法

### 2.1 四种策略对比

| 策略 | 适用场景 | 优势 | 劣势 |
|------|----------|------|------|
| 线性插值 | 短缺失、线性趋势 | 简单、稳定 | 不适合非线性 |
| 二次插值 | 轻度非线性 | 捕捉曲率 | 过拟合风险 |
| 样条插值 | 周期性数据 | 平滑、保形 | 计算量稍大 |
| 滑动平均 | 无规律波动 | 稳健 | 丢失趋势信息 |

### 2.2 策略选择决策树

```
                    +-- nullCount < 3? ---> 线性插值
                    |
数据 --> 计算指标 --+-- R² > 0.9 && |a| < 0.05? ---> 线性插值
                    |
                    +-- R² > 0.7 && |a| < 0.2? ---> 二次插值
                    |
                    +-- 周期性明显? ---> 样条插值
                    |
                    +-- 其他 ---> 滑动平均
```

### 2.3 线性插值 (LinearFiller)

```
输入: validPoints = [(idx0, val0), (idx1, val1), ...]
      missingIndices = [i, j, k, ...]

处理:
  开头缺失 (idx < validPoints[0].idx):
    data[idx] = validPoints[0].val

  结尾缺失 (idx > validPoints[-1].idx):
    data[idx] = validPoints[-1].val

  中间缺失:
    找前后最近有效点 (idx0, val0) 和 (idx1, val1)
    data[idx] = val0 + (val1 - val0) * (idx - idx0) / (idx1 - idx0)

精度: 3位小数，HALF_UP
```

### 2.4 二次插值 (QuadraticFiller)

```
输入: 缺失点位置 idx，最近3个有效点 (x0,y0), (x1,y1), (x2,y2)

求解方程组:
  [x0^2  x0  1] [a]   [y0]
  [x1^2  x1  1] [b] = [y1]
  [x2^2  x2  1] [c]   [y2]

方法: LU 分解

预测: y = a*idx^2 + b*idx + c

降级条件:
  - 有效点不足3个 -> 线性插值
  - 求解失败(行列式=0) -> 线性插值
  - 预测值超出合理范围(+/-3倍标准差) -> 线性插值
```

### 2.5 样条插值 (SplineFiller)

```
适用: 周期性数据（水位日变化、温度日变化等）

方法: 三次自然样条 (Cubic Natural Spline)

对 N 个有效点构建 N-1 个三次多项式:
  Si(x) = ai + bi(x-xi) + ci(x-xi)^2 + di(x-xi)^3

约束:
  1. Si(xi) = yi（插值点经过）
  2. Si(xi+1) = Si+1(xi+1)（连续性）
  3. Si'(xi+1) = Si+1'(xi+1)（一阶导连续）
  4. Si''(xi+1) = Si+1''(xi+1)（二阶导连续）
  5. S''(x0) = 0, S''(xn) = 0（自然边界）

求解: 三对角矩阵追赶法（Thomas算法），O(N) 复杂度

优势: 曲线平滑，不会出现二次插值的振荡问题
```

### 2.6 滑动平均 (MovingAverageFiller)

```
适用: 波动大、无明显趋势的数据

窗口: 5个有效点（从缺失位置前后各取最近的有效值）

data[idx] = mean(窗口内有效值)

如果有效点不足5个:
  - 有3-4个: 用所有有效点的均值
  - 有1-2个: 用最近有效点的值（退化为前向填充）

优势: 不受极端值影响，结果始终在合理范围内
```

### 2.7 置信度评估

```
confidence = R² * (1 - nullCount / totalCount) * (validCount / totalCount)

各因子含义:
  R²: 拟合质量（0-1）
  (1 - nullCount/totalCount): 缺失比例越低越可靠
  (validCount/totalCount): 有效数据越多越可靠

阈值:
  >= 0.8:  高置信度，直接使用
  0.6-0.8: 中置信度，标记"建议复核"
  < 0.6:   低置信度，标记"需人工复核"，不自动写入
```

---

## 3. 质量评分公式

### 3.1 总分构成

```
总分 = 数据质量(35%) + 运行稳定性(10%) + 故障频率(40%) + 数据完整性(15%)
```

### 3.2 维度一：数据质量（35%）

```
missingScore = max(0, (0.3 - missingRatio) * 10/3) * 0.6
anomalyScore = max(0, (0.3 - anomalyRatio) * 10/3) * 0.4

qualityScore = (missingScore + anomalyScore) * 0.35 * 100
```

解读：
- 缺失率 + 异常率 >= 30% 时，缺失分数为 0
- 缺失率权重 0.6，异常率权重 0.4（缺失比异常更影响数据可用性）
- 最终乘以 0.35 的维度权重

示例：
```
missingRatio = 5%, anomalyRatio = 3%
missingScore = (0.3 - 0.05) * 10/3 * 0.6 = 0.500
anomalyScore = (0.3 - 0.03) * 10/3 * 0.4 = 0.360
qualityScore = (0.500 + 0.360) * 0.35 * 100 = 30.1
```

### 3.3 维度二：运行稳定性（10%）

```
stabilityScore = ((1 - offlineDateRatio) * 0.5 + (1 - anomalyDateRatio) * 0.5) * 0.1 * 100
```

示例：
```
offlineDateRatio = 10% (一个月3天离线)
anomalyDateRatio = 5%
stabilityScore = (0.9 * 0.5 + 0.95 * 0.5) * 0.1 * 100 = 9.25
```

### 3.4 维度三：故障频率（40%）

```
penalty = offlineCount * 5 + anomalyCount * 5

if penalty > 100:
  faultScore = 0
else:
  faultScore = (100 - penalty) * 0.4
```

解读：
- 每次离线扣 5 分，每次异常扣 5 分
- 超过 20 次（100/5）故障即得 0 分
- 最终乘以 0.4 的维度权重

示例：
```
offlineCount = 3, anomalyCount = 2
penalty = 3*5 + 2*5 = 25
faultScore = (100 - 25) * 0.4 = 30.0
```

### 3.5 维度四：数据完整性（15%）

```
completenessRatio = actualRecords / expectedRecords

if completenessRatio >= 0.95:
  completenessScore = 15
elif completenessRatio >= 0.8:
  completenessScore = completenessRatio * 15
else:
  completenessScore = completenessRatio * 10  # 低于80%加重惩罚
```

示例：
```
actualRecords = 22, expectedRecords = 24 (每小时一次)
completenessRatio = 22/24 = 0.917
completenessScore = 0.917 * 15 = 13.75
```

### 3.6 时间衰减

```
weight(dayAgo) = exp(-lambda * dayAgo)
lambda = 0.05

应用: 各维度的输入指标按天加权平均
weightedMetric = sum(metric[i] * weight(i)) / sum(weight(i))
```

衰减曲线：
```
天数    权重
0       1.000
3       0.861
7       0.705
14      0.497
30      0.223
```

效果：
- 近期数据权重高，反映设备当前状态
- 30天前的数据权重仅 22%，避免历史问题过度影响当前评分
- 如果近期表现好但历史差，评分会逐渐回升

### 3.7 综合示例

```
某设备评分:
  数据质量: missingRatio=5%, anomalyRatio=3%  -> qualityScore = 30.1
  运行稳定性: offlineDateRatio=10%, anomalyDateRatio=5%  -> stabilityScore = 9.25
  故障频率: offlineCount=3, anomalyCount=2  -> faultScore = 30.0
  数据完整性: completenessRatio=91.7%  -> completenessScore = 13.75

总分 = 30.1 + 9.25 + 30.0 + 13.75 = 83.1 -> 良好

与上期(78分)对比: +5.1 -> 趋势: 稳定
```

### 3.8 评分趋势

```
当前评分 = score_current
上期评分 = score_previous
变化 = score_current - score_previous

if 变化 > 5:   -> 趋势: 改善
if 变化 < -5:  -> 趋势: 恶化
else:           -> 趋势: 稳定
```

### 3.9 评分区间

| 区间 | 等级 | 含义 |
|------|------|------|
| 90-100 | 优秀 | 设备运行健康 |
| 80-89 | 良好 | 轻微问题 |
| 60-79 | 一般 | 需要关注 |
| < 60 | 较差 | 需要维护 |

### 3.10 厂商排名

按厂商分组统计设备评分：
- 平均分 = mean(该厂商所有设备评分)
- 评分分布: <60 / 60-79 / 80-89 / 90-100 各区间设备数
- 排名: 按平均分降序

---

## 4. 缺失检测算法

### 4.1 核心算法

基于采集频率的期望周期数比较法。

**输入：**
- `freq` -- 采集频率（分钟/次），来自设备-表映射配置
- `startTime` / `endTime` -- 检测时间范围（默认前一天 00:00 ~ 当天 00:00）
- `collectTimes` -- 实际采集时间戳列表

**判断流程：**
```
1. expectedCount = ceil((endTime - startTime) / freq)
2. if expectedCount > len(collectTimes) -> 存在缺失
3. 在 collectTimes 首尾添加 startTime 和 endTime 作为边界
4. for i in range(1, len(collectTimes)):
     timeDiff = collectTimes[i] - collectTimes[i-1]  (分钟)
     expectedPeriods = ceil(timeDiff / freq)
     if expectedPeriods >= 2:
       missingCount = expectedPeriods - 1
       if i == 1: missingCount += 1   # 首条数据就缺失
       记录: {startTime: collectTimes[i-1], endTime: collectTimes[i], count: missingCount}
```

**输出：** 缺失记录列表 `{equipmentCode, missingStartTime, missingEndTime, missingCount, timePeriodId}`

### 4.2 连续缺失递增告警

```
连续缺失周期数:
  1-2 个周期  -> INFO
  3-5 个周期  -> WARNING
  6-10 个周期 -> ERROR
  > 10 个周期 -> CRITICAL
```

### 4.3 缺失模式识别

```
如果同一设备连续 3 天在相同时段(+/-30分钟)出现缺失:
  -> 标记为"周期性缺失"，可能原因：定时维护、信号遮挡
  -> 建议：调整采集频率或排查该时段的环境因素

如果缺失分布随机，无明显时间规律:
  -> 标记为"随机缺失"，可能原因：网络不稳定、设备故障
  -> 建议：检查设备通信模块
```

### 4.4 缺失率趋势

```
当日缺失率 = 当日缺失次数 / 当日期望采集次数
环比变化 = (当日缺失率 - 前日缺失率) / 前日缺失率

if 环比变化 > 50%:
  -> 预警：缺失率显著上升
if 连续 3 天缺失率 > 10%:
  -> 预警：设备数据质量持续恶化
```

### 4.5 时间段枚举

| 时段ID | 名称 | 时间范围 |
|--------|------|----------|
| 1 | 凌晨 | 00:00 - 05:59 |
| 2 | 早晨 | 06:00 - 07:59 |
| 3 | 上午 | 08:00 - 10:59 |
| 4 | 中午 | 11:00 - 13:59 |
| 5 | 下午 | 14:00 - 16:59 |
| 6 | 傍晚 | 17:00 - 18:59 |
| 7 | 晚上 | 19:00 - 23:59 |

---

## 5. 离线判定算法

### 5.1 核心算法

基于最新记录时间 + 离线阈值的三态判定法。

**输入：**
- `latestTime` -- 设备在业务表中的最新记录时间
- `threshold` -- 离线阈值（分钟），来自 `dg_equip_offline.tm` 或 `eq_business_equip_relation.offline_threshold`
- `now` -- 当前时间

**三态判定：**
```
if threshold == 0:
  状态 = ONLINE（阈值为0表示不检测离线）

deadline = latestTime + threshold分钟

if deadline < now:
  状态 = OFFLINE（已超时）
else:
  状态 = ONLINE（在线）

# 同一设备多表状态不一致时:
if 不同业务表的状态不一致（一个在线一个离线）:
  状态 = ERROR（异常）
```

### 5.2 测站状态聚合

```
测站下所有设备:
  任一设备 ERROR                       -> 测站 ERROR
  部分 OFFLINE + 部分 ONLINE           -> 测站 ERROR
  全部 OFFLINE                         -> 测站 OFFLINE
  全部 ONLINE                          -> 测站 ONLINE

状态变化时触发预警消息（与 early-warning skill 联动）
```

### 5.3 渐进式告警

```
剩余时间 = deadline - now
剩余比例 = 剩余时间 / threshold

if 剩余比例 <= 0:
  -> OFFLINE（离线）
  -> 离线时长 = now - latestTime
elif 剩余比例 <= 0.2:
  -> WARNING（即将离线）
  -> 消息: "设备将在 {剩余时间} 分钟后判定为离线"
elif 剩余比例 <= 0.5:
  -> 注意（数据延迟）
  -> 消息: "设备数据延迟 {threshold - 剩余时间} 分钟"
```

### 5.4 离线时长分级

```
离线时长:
  0-1 小时   -> INFO
  1-4 小时   -> WARNING
  4-24 小时  -> ERROR
  > 24 小时  -> CRITICAL
```

### 5.5 MTTR（平均恢复时间）

```
每次离线恢复时:
  恢复时间 = now
  离线时长 = 恢复时间 - 离线开始时间
  记录到历史: {equipmentCode, offlineStart, offlineEnd, duration}

MTTR = mean(最近30天的离线时长)

if MTTR > 4小时:
  -> 建议: 设备可靠性不足，需要维护
```

### 5.6 离线记录管理

```
离线状态:
  新建: 无未结束记录 -> 创建新记录 {offlineStartDate, offlineStartTime, totalDuration}
  更新: 有未结束记录 -> 更新总时长
  恢复: 从离线变在线 -> 更新结束时间，计算总时长

异常状态:
  同离线记录管理逻辑
```

---

## 6. 卡滞传感器检测算法

### 6.1 问题描述

传感器硬件故障导致采集卡死在某一固定值。MAD 无法检测此类异常（方差为0，不偏离中位数）。

### 6.2 精确卡滞检测

```python
def detect_stagnation(values, min_consecutive=3, tolerance=1e-6):
    """检测连续相同值"""
    results = []
    start_idx = 0
    count = 1

    for i in range(1, len(values)):
        if abs(values[i] - values[start_idx]) <= tolerance:
            count += 1
        else:
            if count >= min_consecutive:
                results.append({
                    "start_idx": start_idx,
                    "end_idx": start_idx + count - 1,
                    "value": values[start_idx],
                    "count": count,
                })
            start_idx = i
            count = 1

    # 处理最后一段
    if count >= min_consecutive:
        results.append({
            "start_idx": start_idx,
            "end_idx": start_idx + count - 1,
            "value": values[start_idx],
            "count": count,
        })

    return results
```

### 6.3 近似卡滞检测

允许微小波动（传感器噪声）：

```python
def detect_near_stagnation(values, min_consecutive=5, max_variation=0.01):
    """检测近似卡滞（值在极小范围内波动）"""
    # 滑动窗口计算变异系数 CV = std/mean
    # CV < max_variation 视为近似卡滞
```

### 6.4 分级标准

| 连续次数 | 等级 | 说明 |
|---------|------|------|
| 1-2 | INFO | 可能是正常波动 |
| 3-6 | WARNING | 短暂卡滞 |
| 6-24 | ERROR | 明显卡滞 |
| >24 | CRITICAL | 严重卡滞（如3天） |

---

## 7. 极端事件区分算法

### 7.1 问题描述

MAD 会把汛期高水位标记为异常，但实际上是合法的极端天气事件。需要多维度判断来区分两者。

### 7.2 判断规则

```
输入: value(异常值), indicator_type(指标类型), timestamp, historical_stats, rainfall_data

规则1: 汛期水位
  if 月份 in [6,7,8,9] and 近24h降雨 > 20mm:
    → 极端天气事件, 置信度=0.85
  elif 月份 in [6,7,8,9]:
    → 可能极端事件, 置信度=0.60
  elif value > historical_stats.p99:
    → 可能极端事件, 置信度=0.70

规则2: 降雨极端值
  if 24h降雨 ≥ 250mm: 特大暴雨, 置信度=0.95
  elif 24h降雨 ≥ 100mm: 大暴雨, 置信度=0.90
  elif 24h降雨 ≥ 50mm and 汛期: 暴雨, 置信度=0.70

规则3: 时间维度
  if 凌晨2-4点 and 非极端事件:
    → 可能是维护窗口, 置信度=0.30
```

### 7.3 季节性基线

按月分组构建历史基线：

```python
def build_seasonal_baseline(values, timestamps, method="monthly"):
    groups = {}
    for val, ts in zip(values, timestamps):
        key = f"{ts.month:02d}"  # 或 ts.hour, 或 f"{ts.month}_{ts.hour}"
        groups.setdefault(key, []).append(val)

    baselines = {}
    for key, vals in groups.items():
        baselines[key] = {
            "mean": mean(vals),
            "std": std(vals),
            "p5": percentile(vals, 5),
            "p95": percentile(vals, 95),
        }
    return baselines
```

### 7.4 基线偏离检测

```python
def check_against_baseline(value, timestamp, baselines, method="monthly", sigma=3.0):
    key = f"{timestamp.month:02d}"
    baseline = baselines[key]
    deviation = abs(value - baseline["mean"]) / baseline["std"]
    return {
        "is_outlier": deviation > sigma,
        "deviation_sigma": deviation,
    }
```

---

## 8. 相关性异常检测算法

### 8.1 问题描述

单指标都在正常范围内，但物理上不可能同时发生的组合。例如：渗压上升 + 渗流下降 = 物理矛盾。

### 8.2 内置物理规则

```python
PHYSICS_RULES = [
    {
        "id": "pressure_flow_contradiction",
        "name": "渗压-渗流矛盾",
        "condition": lambda c: c["seepage_pressure"] > 0 and c["seepage_flow"] < 0,
        "severity": "HIGH",
        "confidence": 0.9,
    },
    {
        "id": "water_level_seepage_contradiction",
        "name": "水位-渗流矛盾",
        "condition": lambda c: c["water_level"] > 0.5 and c["seepage_flow"] < -0.1,
        "severity": "MEDIUM",
    },
    {
        "id": "rainfall_level_contradiction",
        "name": "降雨-水位矛盾",
        "condition": lambda c: c["rainfall"] > 30 and c["water_level"] < -1.0,
        "severity": "MEDIUM",
    },
    {
        "id": "pump_flow_contradiction",
        "name": "泵站功率-流量矛盾",
        "condition": lambda c: c["pump_power"] > 10 and c["pump_flow"] == 0,
        "severity": "HIGH",
    },
    {
        "id": "gate_flow_contradiction",
        "name": "闸门开度-流量矛盾",
        "condition": lambda c: c["gate_opening"] == 0 and c["gate_flow"] > 0,
        "severity": "HIGH",
    },
]
```

### 8.3 相关系数突变检测

检测两个指标的相关关系突然改变：

```python
def detect_correlation_break(values_a, values_b, window_size=24, threshold=0.5):
    """滑动窗口计算相关系数，检测突变"""
    for i in range(window_size, len(values_a) - window_size):
        prev_corr = pearson(values_a[i-window_size:i], values_b[i-window_size:i])
        curr_corr = pearson(values_a[i:i+window_size], values_b[i:i+window_size])
        if abs(curr_corr - prev_corr) > threshold:
            return {"index": i, "prev_corr": prev_corr, "curr_corr": curr_corr, "is_break": True}
```
