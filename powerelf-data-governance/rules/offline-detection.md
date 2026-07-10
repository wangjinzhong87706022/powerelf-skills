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
