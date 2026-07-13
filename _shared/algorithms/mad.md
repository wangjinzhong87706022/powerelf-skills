# MAD 异常检测算法（单一事实源）

> 本文件合并自 `data-governance/algorithms/mad-algorithm.md`（自适应窗口版）与
> `inspection/algorithms/mad-statistical-method.md`（numpy 简版）。两者描述同一算法，
> 现统一为跨 skill 单一事实源。data-governance 与 inspection 的本地文档现为指向本文件的指针。

## 一、原理

MAD（Median Absolute Deviation，中位数绝对偏差）是鲁棒的离群点检测方法。相比基于
均值/标准差的 Z-Score，MAD 基于中位数，对极端值不敏感——非常适合水利监测数据
（受设备跳变、汛期极值影响）。

## 二、公式

```
MAD = median(|x_i - median(x)|) × 1.4826        # 1.4826 使 MAD 在正态分布下等价于标准差
M_i = 0.6745 × (x_i - median(x)) / MAD           # Modified Z-Score
若 |M_i| > threshold → 异常
```

- `1.4826`：MAD 归一化到标准差的因子
- `0.6745`：标准正态分布分位数因子（与上式联立后二者相消，等价）

## 三、自适应窗口设计（推荐）

朴素 MAD 用全量数据做窗口，会退化为全局统计，无法捕捉局部突变（如某小时跳变被整天数据稀释）。

```
windowSize = clamp(N × 0.15, 10, 50)

N < 10  → window = N（数据太少，只能全局）
N = 10  → window = 10
N = 100 → window = 15
N = 200 → window = 30
N > 333 → window = 50（固定上限，控计算量）
```

选择 15% 的依据：水利数据约每小时一采，一天 ~24 点；15% ≈ 3–4 小时窗口，能捕捉小时级异常；
下限 10 保小样本统计意义；上限 50 限复杂度。

> 对比（inspection 简版）：按**天**设固定窗口（水位 7 天、雨量 30 天、渗压 30 天、GNSS 90 天）。
> 两种窗口策略可按场景选用：自适应窗口适合高频实时检测，固定天数窗口适合周期性回溯分析。

## 四、分指标阈值

| 指标 | 推荐阈值 | 日常波动 | 固定窗口(天) | 理由 |
|------|----------|----------|------------|------|
| 水位 rz/z | 3.0 | ±0.1m | 7 | 变化平缓，3σ 足够 |
| 雨量 p | 5.0 | 0–50mm/h 高度偏态 | 30 | 零膨胀分布，需更高容忍 |
| 渗压 water_pressure | 4.0 | ±0.5kPa | 30 | 中等波动 |
| GNSS wgs84_delta_h | 3.5 | ±0.5mm | 90 | 缓慢变化，突变即异常 |
| 流量 inq/otq | 4.0 | ±10% | 30 | 受闸门操作影响 |
| 通用默认 | 4.0 | — | — | 兜底 |

阈值校准：用历史正常数据算 MAD，统计误报率，调阈值使**误报率 < 1%**。
（3.0→约 0.3%，4.0→约 0.01%，5.0→约 0.0001%，正态分布下）

## 五、变化率检测（MAD 的补充）

MAD 只看绝对偏差，对"缓慢但持续的偏移"不敏感，需叠加变化率检测：

```
changeRate = |x_i - x_{i-1}| / |x_{i-1}|
if changeRate > 阈值 → 标记"可疑"

水位 5% / 渗压 3% / GNSS 2% / 流量 10% / 雨量 不适用（可突变）
```

最终判定：**MAD 与变化率交叉验证**，二者皆中则高置信异常。

## 六、Python 实现

### 6.1 自适应窗口版（data-governance 风格）

```python
def detect_outliers(data, window_size, threshold):
    results = [False] * len(data)
    half = window_size // 2
    for i in range(len(data)):
        window = data[max(0, i - half): min(len(data), i + half + 1)]
        median = sorted(window)[len(window) // 2]
        abs_devs = sorted([abs(x - median) for x in window])
        mad = abs_devs[len(abs_devs) // 2]
        if mad > 0:
            z = 0.6745 * abs(data[i] - median) / mad
            if z > threshold:
                results[i] = True
        elif abs(data[i] - median) > 0:   # MAD=0 退化为绝对差判断
            results[i] = True
    return results
```

### 6.2 全局 numpy 版（inspection 风格）

```python
import numpy as np

def detect_anomalies(values, threshold=4.0):
    median = np.median(values)
    mad = np.median(np.abs(values - median)) * 1.4826
    if mad == 0:
        anomalies = [i for i, v in enumerate(values) if abs(v - median) > 0]
        z_scores = [0.0] * len(values)
    else:
        z_scores = 0.6745 * np.abs(values - median) / mad
        anomalies = np.where(z_scores > threshold)[0].tolist()
    return {"median": median, "mad": mad,
            "anomaly_count": len(anomalies), "anomaly_indices": anomalies}
```

## 七、注意事项

- `MAD == 0`（所有值相同）时退化为绝对差判断
- 数据点 < 10 时不充分，不做检测
- 窗口权衡：太小样本不足，太大对近期变化不敏感
- **卡滞检测叠加**：雨量传感器是步进式读数（0.5mm 步进），连续相同值属正常，需单独处理
  （雨量站建议 tolerance=0.5 或 min_consecutive=24）

## 八、姊妹方法

MAD 适合正态/缓变指标。对偏态分布（雨量、流量）改用 IQR 或百分位法，三者对比与选择指南见
[`outlier-methods.md`](outlier-methods.md)。CLI 调用：`anomaly_detector.py --method iqr|percentile`。
生成统计结论文案时另见 [`../references/statistical-caution.md`](../references/statistical-caution.md)。
