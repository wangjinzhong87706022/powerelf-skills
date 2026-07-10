# 综合检测四步骤实现模板

用户说"综合检测"或"全面质量评估"时，按此流程执行。

## Step 0: 数据探查（必须第一步）

```python
# 查所有监测表的数据概况
monitor_tables = [
    ('st_rsvr_r', '水库水情', ['rz', 'inq', 'otq']),
    ('st_river_r', '河道水位', ['z']),
    ('st_pptn_r', '雨量', ['p']),
    ('st_pressure_r', '渗压', ['ext_pressure', 'water_pressure']),
    ('st_percolation_r', '渗流', ['percolation']),
    ('dsm_dfr_srvrds_srhrds', 'GNSS位移', ['wgs84_delta_h', 'wgs84_delta_x', 'wgs84_delta_y'])
]

for table_name, desc, fields in monitor_tables:
    result = query(f"SELECT MIN(tm), MAX(tm), COUNT(*), COUNT(DISTINCT stcd) FROM {table_name}")
    # 输出：记录数、时间范围、站点数
```

## Step 1: MAD 异常检测（按站点分组）

```python
def mad_detection(data, threshold=3.0):
    window_size = min(max(int(len(data) * 0.15), 10), 50)
    z_scores = []
    for i in range(len(data)):
        start = max(0, i - window_size)
        end = min(len(data), i + window_size + 1)
        window = data[start:end]
        median = np.median(window)
        mad = np.median(np.abs(window - median))
        if mad < 0.001:  # MAD 过小，避免溢出
            z_scores.append(0)
        else:
            z_scores.append(np.abs(data[i] - median) / (1.4826 * mad))
    return np.array(z_scores)

def change_rate_detection(data, threshold=0.05):
    change_rates = np.abs(np.diff(data) / data[:-1])
    change_rates = np.insert(change_rates, 0, 0)
    return change_rates, change_rates > threshold

def composite_judge(mad_anomaly, change_anomaly):
    high = mad_anomaly & change_anomaly      # 双触发
    medium = mad_anomaly & ~change_anomaly   # 仅MAD
    low = ~mad_anomaly & change_anomaly      # 仅变化率
    return high, medium, low
```

分指标阈值：水位 3.0 / 雨量 5.0 / 渗压 4.0 / GNSS 3.5 / 流量 4.0

## Step 2: 缺失检测

```python
def missing_detection(times, expected_interval_hours=1):
    time_span_hours = (times.max() - times.min()).total_seconds() / 3600
    expected_count = int(time_span_hours / expected_interval_hours)
    actual_count = len(times)
    missing_rate = max(0, 1 - actual_count / expected_count)  # 截断到0
    
    # 连续缺失检测
    time_diffs = times.diff().dt.total_seconds() / 3600
    consecutive_missing = time_diffs[time_diffs > expected_interval_hours * 1.5]
    
    return {
        'expected_count': expected_count,
        'actual_count': actual_count,
        'missing_rate': missing_rate,
        'consecutive_missing': len(consecutive_missing),
        'max_gap_hours': time_diffs.max()
    }
```

**注意**：缺失率可能为负（实际>期望），用 `max(0, ...)` 截断。

## Step 3: 离线检测

```python
def offline_detection(latest_time, current_time):
    offline_hours = (current_time - latest_time).total_seconds() / 3600
    if offline_hours < 1:   return 'ONLINE', '正常'
    elif offline_hours < 6: return 'WARNING', '警告'
    elif offline_hours < 24: return 'OFFLINE', '离线'
    else:                   return 'CRITICAL', '严重离线'
```

**注意**：如果 `current_time = MAX(tm) + 1h`，所有站点都显示 WARNING。在报告中说明。

## Step 4: 四维度质量评分

```python
def quality_score(anomaly_rate, missing_rate, offline_hours, cv):
    quality = max(0, 100 - anomaly_rate * 1000)      # 异常率，35%
    stability = max(0, 100 - cv * 100)                # 变异系数，10%
    fault = max(0, 100 - offline_hours * 2)           # 离线时长，40%
    completeness = max(0, 100 - missing_rate * 1000)  # 缺失率，15%
    total = quality*0.35 + stability*0.10 + fault*0.40 + completeness*0.15
    return {'quality': quality, 'stability': stability, 
            'fault': fault, 'completeness': completeness, 'total': total}
```

分级：≥90 优秀 / ≥80 良好 / <80 需改进

## 汇总报告模板

### 可视化（四子图）
1. 左上：质量评分柱状图（绿≥90/黄≥80/红<80）
2. 右上：异常分布堆叠图（高/中/低置信度）
3. 左下：缺失率柱状图（绿≤5%/黄≤10%/红>10%）
4. 右下：离线时长柱状图（绿<1h/黄<6h/红>24h）

### Markdown 报告结构
1. 检测概览（汇总表）
2. 各站点详细分析（逐站列出四项检测结果 + 评分）
3. 异常点详情（高置信度优先列出）
4. 处理建议（优先处理 / 持续监控 / 预防措施）
5. 附件清单（JSON + PNG + CSV）

### 输出文件
- `/tmp/comprehensive_quality_report.png` — 可视化报告
- `/tmp/comprehensive_quality_report.json` — 详细结果（可供后续分析）
- `/tmp/comprehensive_quality_report.md` — Markdown 报告
