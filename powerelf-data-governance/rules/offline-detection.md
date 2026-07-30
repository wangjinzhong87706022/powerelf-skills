# 离线检测规则

> 离线配置表：`dg_equip_offline`（设备离线配置表）
> 离线记录表：`eq_equip_offline_record`（设备离线记录表）
> 异常记录表：`eq_equip_anomaly_record`（设备异常记录表）
> 设备主表：`eq_equip_base`（设备基础信息表）
> 设备-业务映射：`eq_business_equip_relation`（业务表和设备的关系表）

## 核心算法

基于最新记录时间 + 离线阈值的三态判定法。

### 输入

- `latestTime` — 设备在业务表中的最新记录时间
- `threshold` — 离线阈值（分钟），来自 `dg_equip_offline.tm` 或 `eq_business_equip_relation.offline_threshold`
- `now` — 当前时间

### 离线阈值配置（dg_equip_offline）

| st_type | 站类型 | tm(阈值min) | frequency(采集频率min) |
|---------|--------|------------|----------------------|
| SP | 水位站 | 360 | — |
| GN | GNSS站 | 60 | 60 |
| EL | 闸门站 | 60 | 60 |
| ZS | 雨量站 | 60 | 60 |
| WQ | 水质站 | 60 | 60 |
| PP | 渗压站 | 60 | 60 |
| DP | 渗流站 | 60 | 60 |
| DD | 位移站 | 60 | 60 |
| YZ | 墒情站 | 60 | 60 |
| ZG/RR/ZQ/TT/BB/MM/SS/DC | 其他站类型 | 0(不检测) | — |

### 设备状态字段（eq_equip_base.status）

| 值 | 含义 |
|----|------|
| 0 | 离线(offline) |
| 1 | 在线(online) |
| 2 | 异常(anomaly) |

### 三态判定

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

### 测站状态聚合

```
测站下所有设备:
  任一设备 ERROR   → 测站 ERROR
  部分 OFFLINE + 部分 ONLINE → 测站 ERROR
  全部 OFFLINE     → 测站 OFFLINE
  全部 ONLINE      → 测站 ONLINE

状态变化时触发预警消息（与 early-warning skill 联动）
```

## 增强规则

### 渐进式告警 — 新增

原始实现只有"离线/在线"二态，增加预警缓冲：

```
剩余时间 = deadline - now
剩余比例 = 剩余时间 / threshold

if 剩余比例 <= 0:
  → OFFLINE（离线）
  → 离线时长 = now - latestTime
elif 剩余比例 <= 0.2:
  → WARNING（即将离线）
  → 消息: "设备将在 {剩余时间} 分钟后判定为离线"
elif 剩余比例 <= 0.5:
  → 注意（数据延迟）
  → 消息: "设备数据延迟 {threshold - 剩余时间} 分钟"
```

### 离线时长分级 — 新增

```
离线时长:
  0-1 小时   → INFO
  1-4 小时   → WARNING
  4-24 小时  → ERROR
  > 24 小时  → CRITICAL
```

### MTTR（平均恢复时间） — 新增

```
每次离线恢复时:
  恢复时间 = now
  离线时长 = 恢复时间 - 离线开始时间
  记录到历史: {equipmentCode, offlineStart, offlineEnd, duration}

MTTR = mean(最近30天的离线时长)

if MTTR > 4小时:
  → 建议: 设备可靠性不足，需要维护
```

## 离线记录管理

```
离线状态:
  新建: 无未结束记录 → 创建新记录 {offlineStartDate, offlineStartTime, totalDuration}
  更新: 有未结束记录 → 更新总时长
  恢复: 从离线变在线 → 更新结束时间，计算总时长

异常状态:
  同离线记录管理逻辑
```

## 离线记录字段映射

### eq_equip_offline_record（离线记录）

| 字段 | 含义 |
|------|------|
| equipment_code | 设备ID（对应 eq_equip_base.id） |
| offline_start_date | 离线开始日期 |
| offline_start_time | 离线开始时间 |
| offline_end_time | 离线结束时间（恢复时更新） |
| total_offline_duration | 累计离线时长（秒） |
| time_period_id | 时间段ID |

### eq_equip_anomaly_record（异常记录）

| 字段 | 含义 |
|------|------|
| equipment_code | 设备ID |
| anomaly_start_date | 异常开始日期 |
| anomaly_start_time | 异常开始时间 |
| anomaly_end_time | 异常结束时间 |
| total_anomaly_duration | 累计异常时长（秒） |

## 与预警模块联动

离线检测到设备状态变化时：
- 设备离线 → 更新 eq_equip_base.status = 0，创建 eq_equip_offline_record
- 设备恢复 → 更新 eq_equip_base.status = 1，更新离线记录结束时间
- 测站状态变化 → 触发 `equipNotice()` 发送通知

## 批量分级（推荐用于离线分析任务）

### 适用场景

当用户询问以下问题时，**优先使用批量脚本** `scripts/classify_offline_by_duration.py`：

- "有多少设备离线？"
- "哪些设备离线最久？"
- "帮我分级所有离线设备"
- "离线设备按时长排序"
- "统计离线设备分布"

**对比单站检测**：
| 方案 | 工具调用次数 | 耗时 | 适用场景 |
|------|-------------|------|---------|
| 逐站循环调用 `offline_detector.py` | N 次（N = 离线设备数） | N × 13 秒 | ❌ 不推荐 |
| **批量脚本 `classify_offline_by_duration.py`** | **1 次** | **< 1 秒** | ✅ **推荐** |

### 使用方法

```bash
# 基础用法（Markdown 输出）
python3 scripts/classify_offline_by_duration.py --db "$DB_URL"

# 输出到 CSV（用于人工复核）
python3 scripts/classify_offline_by_duration.py --db "$DB_URL" --format csv --output /tmp/offline_devices.csv

# 输出到 JSON（用于二次处理）
python3 scripts/classify_offline_by_duration.py --db "$DB_URL" --format json --output /tmp/offline_devices.json
```

### 输出说明

#### Markdown 格式（默认）

```markdown
## 离线设备分级分析结果

**统计时间**: 2026-07-28 14:21
**离线设备总数**: 504 台

### 分级汇总

- **CRITICAL**（严重离线（>24 小时））: 79 台
- **ERROR**（长期离线（4-24 小时））: 150 台
- **WARNING**（短期离线（1-4 小时））: 160 台
- **INFO**（轻度离线（<1 小时））: 115 台

### 详细列表

| 严重级别 | 设备名称 | 设备编码 | 类型 | 离线时长(h) | 开始时间 | 业务表 | 阈值 | 采集频率 |
|---------|---------|---------|------|-----------|---------|-------|------|---------|
| CRITICAL | 振弦渗压计D09 | 2023510006-26 | 20 | 332.83h | 2026-05-20 19:00 | 未知 | 未配置 | 未知 |
| ...
```

#### CSV 格式

```csv
severity,device_name,device_code,type_flag,offline_hours,offline_start,business_table,offline_threshold_min,frequency_min,total_offline_duration_sec
CRITICAL,振弦渗压计D09,2023510006-26,20,332.83,2026-05-20 19:00,,,,1198201
...
```

#### JSON 格式

```json
[
  {
    "id": 26,
    "name": "振弦渗压计D09",
    "code": "2023510006-26",
    "type_flag": 20,
    "offline_hours": 332.83,
    "offline_start": "2026-05-20 19:00",
    "business_table": null,
    "severity": "CRITICAL",
    ...
  }
]
```

### SQL 逻辑说明

批量脚本的核心 SQL（已优化）：

```sql
SELECT
    e.id,
    e.name,
    e.code,
    e.type_flag,
    r.total_offline_duration,
    r.offline_start_date,
    r.offline_start_time,
    b.business_table,
    b.offline_threshold,
    b.frequency
FROM eq_equip_base e
LEFT JOIN eq_equip_offline_record r
    ON e.id = r.equipment_code  -- ⚠️ bigint 关联，不是 code
LEFT JOIN eq_business_equip_relation b
    ON e.id = b.eq_id
WHERE e.status = 0  -- 仅离线设备
  AND e.deleted = 0  -- 过滤已删除
ORDER BY r.total_offline_duration DESC  -- 按离线时长降序
```

**关键设计点**：
- ✅ **LEFT JOIN**：无离线记录的设备也会被包含（`total_offline_duration` 为 NULL，设为 INFO）
- ✅ **复用 `lib.offline.classify_offline_duration()`**：分级阈值与单站检测完全一致
- ✅ **排序优化**：`ORDER BY r.total_offline_duration DESC`，最严重离线设备优先展示

### 常见问题

#### Q1：为什么有些设备的"业务表"和"阈值"显示为"未知"？

**原因**：`eq_business_equip_relation` 表中没有该设备的映射记录（当前覆盖率约 32%）。

**影响**：不影响分级结果（`severity` 仍基于 `total_offline_duration` 计算），只影响业务表名和阈值显示。

**处理建议**：如需补充映射，联系管理员更新 `eq_business_equip_relation` 表。

#### Q2：为什么离线时长为 0 小时的设备也被标记为 INFO？

**原因**：`eq_equip_base.status = 0`（离线）但 `eq_equip_offline_record` 中无对应记录。

**可能情况**：
1. 设备刚变为离线状态，离线记录尚未生成
2. 离线记录表有延迟（非实时同步）

**处理建议**：运行 `scripts/classify_offline_by_duration.py --format json` 检查 `total_offline_duration` 字段，若为 `null` 则属于此类情况。

#### Q3：如何对特定设备深度分析？

批量脚本提供概览，如需单站深度分析（含最新记录时间、阈值判定、告警状态），使用单站检测工具：

```bash
python3 impl/offline_detector.py --db "$DB_URL" --table st_pressure_r --st-id 201 --threshold 60
```

### 性能对比

| 指标 | 逐站循环（N=50） | 批量脚本 | 提升 |
|------|----------------|---------|------|
| 工具调用次数 | 50 次 | **1 次** | **50×** |
| 墙钟耗时 | ~650 秒（11 分钟） | **< 1 秒** | **650×** |
| 输出 tokens | ~50,000 | **~2,000** | **25×** |
| Prefill 开销 | 50 轮 × 30KB = 1.5MB | **一次性 50KB** | **30×** |

**实际案例**（2026-07-28 session 20260728_084051_fca604）：
- 逐站循环：222 秒，17 次工具调用，12,811 tokens
- 批量脚本（预期）：< 10 秒，1-2 次工具调用，< 3,000 tokens

### 扩展：按业务表过滤

如需仅查询特定业务表的离线设备，可修改脚本添加 `business_table` 过滤条件，或直接查询：

```python
from db import query
offline_in_pressure = query("""
    SELECT e.name, e.code, r.total_offline_duration
    FROM eq_equip_base e
    JOIN eq_equip_offline_record r ON e.id = r.equipment_code
    JOIN eq_business_equip_relation b ON e.id = b.eq_id
    WHERE e.status = 0
      AND e.deleted = 0
      AND b.business_table = 'st_pressure_r'
    ORDER BY r.total_offline_duration DESC
""")
```

