# 缺陷趋势预测

## 线性回归预测（短期 1-3 月）

```
y = a × x + b
```

- `y`：月缺陷数
- `x`：时间序号（1, 2, 3, ...）
- `a`：斜率（趋势方向）
- `b`：截距

### 趋势判定

| 斜率 a | 趋势 |
|--------|------|
| a > 0.5 | 上升 ↑ |
| a < -0.5 | 下降 ↓ |
| a ∈ [-0.5, 0.5] | 稳定 → |

### Python 实现

```python
from sklearn.linear_model import LinearRegression
import numpy as np

def predict_trend(monthly_counts, predict_months=3):
    X = np.arange(len(monthly_counts)).reshape(-1, 1)
    y = np.array(monthly_counts)
    model = LinearRegression()
    model.fit(X, y)

    slope = model.coef_[0]

    if slope > 0.5:
        trend = "rising"
    elif slope < -0.5:
        trend = "falling"
    else:
        trend = "stable"

    future_X = np.arange(len(monthly_counts),
                         len(monthly_counts) + predict_months).reshape(-1, 1)
    predictions = model.predict(future_X).astype(int).tolist()

    return {"trend": trend, "slope": round(slope, 4), "predictions": predictions}
```

## 季节性分析

| 季节 | 月份 | 高风险类型 |
|------|------|-----------|
| 汛期 | 6-9月 | 闸门、泵站缺陷增加 |
| 冬季 | 12-2月 | 电气设备故障增加 |
| 定期检查后 | — | 集中发现缺陷 |

## 贝叶斯热点预测

```
P(设备 i 有缺陷) = (历史缺陷数_i + 1) / (总月数 + 总设备数)
```

| 概率 | 等级 | 含义 |
|------|------|------|
| >0.3 | 高风险 | 重点关注 |
| [0.1, 0.3] | 中风险 | 常规关注 |
| <0.1 | 低风险 | 正常维护 |

## 预警规则

| 规则 | 级别 | 动作 |
|------|------|------|
| 月缺陷数环比增长 >1.5倍 | WARNING | 分析原因 |
| 同一设备月缺陷 ≥3次 | WARNING | 建议专项检查 |
| 未处理缺陷 >20 且持续增长 | CRITICAL | 组织整改 |
