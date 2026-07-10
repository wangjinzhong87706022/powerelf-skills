# 多指标关联异常分析

## 概述

水利工程中各监测指标之间存在物理关联关系。当两个本应相关的指标出现趋势矛盾时，往往预示着潜在问题。本算法检测 4 种关键关联矛盾。

## 关联场景

### 场景1：水位上升 但 入库流量下降

```
检测条件: rz 连续上升(≥3) 且 inq 连续下降(≥3)
可能原因:
  - 出库流量增大（闸门开启）
  - 上游来水被拦截
  - 传感器故障
```

### 场景2：强降雨 但 水位无明显变化

```
检测条件: 24h 累计降雨 >50mm 但 rz 变化 <0.1m
可能原因:
  - 闸门开启泄洪 → 正常调节
  - 大坝存在渗漏通道 → 需关注
  - 水位计故障
```

### 场景3：渗压 脱离 水位 独立上升

```
检测条件: water_pressure 连续上升(≥6) 但 rz 稳定/下降
可能原因:
  - 防渗体受损
  - 坝体内部异常
```

### 场景4：GNSS位移 与 水位 相关性异常

```
检测条件: 水位大幅波动 但 GNSS位移无明显响应
        或：位移加速 但 水位稳定
可能原因:
  - 坝基问题
  - 测量系统异常
```

## 实现逻辑

```python
def detect_correlation_anomaly(water_level, inflow, rainfall, pressure, displacement):
    findings = []
    # 场景1：水位↑ 但 入库↓
    if rising(water_level) and falling(inflow):
        findings.append({
            "type": "water_inflow_conflict",
            "level": "WARNING",
        })
    # 场景2：强降雨 但 水位不变
    if heavy_rain(rainfall) and stable(water_level):
        findings.append({
            "type": "rain_level_conflict",
            "level": "INFO",
        })
    # 场景3：渗压↑ 但 水位不变
    if rising(pressure) and not rising(water_level):
        findings.append({
            "type": "pressure_level_disconnect",
            "level": "CRITICAL",
        })
    # 场景4：GNSS 异常
    if accelerating(displacement) and stable(water_level):
        findings.append({
            "type": "displacement_anomaly",
            "level": "CRITICAL",
        })
    return findings
```
