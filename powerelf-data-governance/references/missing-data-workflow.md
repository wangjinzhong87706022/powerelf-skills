# 缺失数据溯源与修复工作流

## 适用场景

当质量评分中「完整性」维度得分偏低（缺失率 > 3%），或用户要求分析缺失数据时触发。

## 执行步骤

### Step 1: 构建期望时间序列

```python
from datetime import datetime, timedelta

start = datetime(2026, 3, 1, 0, 0)
end = datetime(2026, 5, 31, 23, 0)
expected = []
t = start
while t <= end:
    expected.append(t)
    t += timedelta(hours=1)  # 按实际采样频率调整
```

### Step 2: 识别缺失区间

```python
actual_map = {r['tm']: float(r['rz']) for r in rows}
gap_idx = [i for i, t in enumerate(expected) if t not in actual_map]

# 找连续缺口
gaps = []
gap_start = None
for i, t in enumerate(expected):
    if t not in actual_map:
        if gap_start is None:
            gap_start = t
    else:
        if gap_start is not None:
            gaps.append((gap_start, expected[i-1], ...))
            gap_start = None
```

### Step 3: 上下文分析

对每个缺口：
- 取前后48h数据
- 计算均值、标准差、范围
- 计算衔接跳变（前最后值 vs 后首值）
- 跳变幅度 / 标准差 = 几个σ

### Step 4: 缺失模式判定

| 模式 | 特征 | 典型原因 |
|------|------|----------|
| 单一连续缺口 | 1个大缺口占全部缺失 | 通信中断、设备停机 |
| 多个连续缺口 | 2+个中等缺口 | 间歇性通信故障 |
| 零散缺失 | 散布在各处 | 传感器间歇故障 |
| 周期性缺失 | 固定时段缺数据 | 采集计划配置错误 |

### Step 5: 插值策略选择

按缺口长度选策略：

| 缺口长度 | 推荐策略 | 理由 |
|----------|----------|------|
| ≤ 6小时 | 交叉验证选最优（4策略均可） | 短缺口外推安全 |
| 6~48小时 | **线性插值**（必选） | quadratic/spline外推爆炸 |
| > 48小时 | **线性趋势 + 日周期修正** | 保留日内波动特征 |

大缺口季节修正代码：
```python
trend_vals = np.interp(gap_idx, real_idx, real_vals)
global_mean = np.mean(real_vals)
hourly_offset = {h: np.mean(profiles[h]) - global_mean for h in range(24)}
trend_mean = np.mean(trend_vals)
for i, idx in enumerate(gap_idx):
    h = expected[idx].hour
    trend_h_mean = np.mean([trend_vals[j] for j in range(len(gap_idx)) if expected[gap_idx[j]].hour == h])
    repaired[i] = trend_vals[i] + (hourly_offset[h] - (trend_h_mean - trend_mean))
```

### Step 6: 质量验证

```python
# 合并完整序列后跑MAD
full_map = dict(actual_map)
for idx, val in zip(gap_idx, repaired):
    full_map[expected[idx]] = float(val)
# 检查缺口区间内是否有新异常
gap_anomalies = [a for a in anomalies if gap_start <= a['time'] <= gap_end]
# 期望：缺口内异常 = 0
```

### Step 7: 报告生成

三子图可视化：
1. **全景时序** — 原始数据(蓝) + 修复数据(红) + 缺口区域着色
2. **缺口放大** — 前后7天上下文 + 逐日均值标注
3. **日周期对比** — 缺失前/修复/缺失后 三线对比

CSV明细字段：序号、时间、日期、小时、修复水位、日均值、偏差、复核结论（空列）

## 实际案例

### SW001 — 144小时连续缺口（2026-04-10 ~ 04-15）

| 指标 | 值 |
|------|-----|
| 缺失率 | 6.52% (144/2208) |
| 缺失类型 | 单一连续缺口 |
| 可能原因 | 通信中断（连续6天无数据） |
| 修复策略 | 线性趋势 + 日周期修正 |
| 修复范围 | 237.640 ~ 238.771m（正常区间） |
| 衔接偏差 | 起点 0.018m，终点 0.054m |
| 缺口内MAD异常 | 0个 |
| 交叉验证R² | 0.809（线性） |
