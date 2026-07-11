# 离群检测方法对比（IQR / 百分位 / MAD）

> 跨 skill 单一事实源。`powerelf-data-governance/impl/anomaly_detector.py` 的 `--method mad|iqr|percentile`
> 与 `lib/outliers.py` 实现均以本文档为准。姊妹方法见 [`mad.md`](mad.md)。

## 一、三法对比

| 方法 | 适用分布 | 稳健性 | 参数 | 计算成本 | 何时用 |
|------|----------|--------|------|----------|--------|
| **MAD**（修正 Z） | 正态 / 缓变 | 极高（基于中位数） | 修正 Z 阈值 3.0–5.0 | 低 | 水位、GNSS、渗压等近正态/缓变指标 |
| **IQR**（四分位距） | 偏态 / 长尾 | 高（基于分位数） | IQR 倍数 k=1.5(标准)/3.0(激进) | 低 | 雨量、流量等零膨胀/偏态分布 |
| **百分位法** | 任意 | 中（总会标记尾部） | 尾部百分位 p=1(p1/p99) | 极低 | 海量数据快速筛查，对分布无假设 |

选法口诀：**正态缓变用 MAD，偏态长尾用 IQR，海量筛查用百分位。**

## 二、IQR（四分位距法）

### 公式

```
Q1 = p25,  Q3 = p75,  IQR = Q3 - Q1
lower = Q1 - k * IQR
upper = Q3 + k * IQR
超出 [lower, upper] 即离群
```

- `k=1.5`：标准箱线图规则，温和（标记明显离群）。
- `k=3.0`：激进，仅标记极端值，减少误报。

### Python

```python
import numpy as np

def detect_iqr(values, k=1.5):
    arr = np.asarray(values, dtype=float)
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lower, upper = q1 - k * iqr, q3 + k * iqr
    if iqr == 0:
        return []                      # 所有值相同，无离群
    mask = (arr < lower) | (arr > upper)
    return np.where(mask)[0].tolist()
```

### 注意

- **样本 < 10 不检测**（统计意义不足，`anomaly_detector` 已在上游拦截）。
- `IQR == 0`（四分位重合，常见于大量重复值）退化为"无离群"，不报错。
- 对极端偏态（如雨量 0 占 90%），IQR 仍可能把大量非零值判为离群——此时优先用百分位法或分段分析。

## 三、百分位法

### 公式

```
low_bound  = p_low   (默认 p1)
high_bound = p_high  (默认 p99)
超出 [low_bound, high_bound] 即离群
```

### Python

```python
import numpy as np

def detect_percentile(values, low=1, high=99):
    arr = np.asarray(values, dtype=float)
    low_bound, high_bound = np.percentile(arr, [low, high])
    mask = (arr < low_bound) | (arr > high_bound)
    return np.where(mask)[0].tolist()
```

### 注意

- **总会标记尾部**：p1/p99 在大样本下约标记 2% 的点。这是特性非缺陷——适合"快速筛查找候选"，不适合"精确定量异常率"。
- 对非典型分布（多峰、重尾）无理论保证。
- `low >= high` 时回退到 1/99（`lib/outliers.py` 已处理）。

## 四、与 MAD 的关系（互补，非替代）

- **MAD** 基于中位数与绝对偏差，对单峰近正态分布最优；对零膨胀/重尾分布，MAD 常被大量重复值拉到 0，退化为绝对差判断，灵敏度下降。
- **IQR** 基于分位数，不依赖中位数邻近结构，对偏态更稳。
- **百分位** 不假设分布形状，最通用但最粗。
- 三者不互斥：同一指标可分别用 MAD 与 IQR 跑，结果交集=高置信异常。**多方法 composite 投票** 为后续增强（见 spec §9），当前 CLI 为单方法互斥（方案甲）。

## 五、`anomaly_detector` CLI 语义

| `--method` | `--threshold` 含义 | 默认 | 输出分析块 |
|------------|---------------------|------|------------|
| `mad`（默认） | 修正 Z 阈值 | 按字段（rz=3.0 / p=5.0 / 渗压=4.0 / 默认 4.0） | `mad_analysis` |
| `iqr` | IQR 倍数 k | 1.5 | `iqr_analysis` |
| `percentile` | 尾部百分位 p（取 p 与 100-p） | 1（p1/p99） | `percentile_analysis` |

输出 JSON 顶层含 `method` 字段溯源；其余结构与 `mad` 路径一致（`change_rate_analysis`、`judgment`、`anomaly_details`、`explanation`）。

## 六、卡滞检测注意

雨量传感器是**步进式读数**（如 0.5mm 一跳），连续相同值属正常工况，不是卡滞。
- 用 IQR/百分位检测雨量时，大量 0 值会把非零降雨全推到上尾——需结合 `_shared/references/schema.md` 的字段语义判断是否合理。
- 卡滞判定应走独立的 `lib/stagnation.py`（tolerance / min_consecutive），不要用离群检测替代。
