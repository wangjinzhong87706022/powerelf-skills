# 闸门/泵站状态分析规则

> 闸门数据表：`rei_gate_r`（闸门工情历史表）
> 泵站数据表：`rei_pump_r`（泵站工情历史表）

## 闸门工情字段

| DB字段 | Java字段 | 含义 | 类型 | 单位 |
|--------|----------|------|------|------|
| gtq | gtq | 流量 | decimal(10,3) NOT NULL | m³/s |
| gtophgt | gtophgt | 开启高度 | decimal(6,2) NOT NULL | m |
| gtopnum | gtopnum | 开启孔数 | tinyint NOT NULL | 个 |
| status | status | 开关状态 | bit | 0=关/1=开 |
| stcd | stCode | 站码 | varchar(20) NOT NULL | — |
| slcd | slcd | 闸码 | char(18) NOT NULL | — |
| eq_code | eqCode | 设备编码 | varchar(20) NOT NULL | — |
| st_id | stId | 测站ID | bigint NOT NULL | — |
| eq_id | eqId | 设备ID | bigint | — |
| tm | tm | 采集时间 | datetime | — |
| msqmt | msqmt | 流量测法 | char | — |

## 泵站工情字段

> ⚠️ 注意：泵站的电气参数字段（uab/ia/p/freq等）在数据库中为 **varchar** 类型，使用时需要先做数值解析。

| DB字段 | Java字段 | 含义 | 类型 | 单位 |
|--------|----------|------|------|------|
| uab/ubc/uca | uab/ubc/uca | 三相线电压 | **varchar** | V |
| ia/ib/ic | ia/ib/ic | 三相电流 | **varchar** | A |
| p | p | 有功功率 | **varchar** | kW |
| q | q | 无功功率 | **varchar** | kvar |
| cos | cos | 功率因数 | **varchar** | — |
| freq | freq | 频率 | **varchar** | Hz |
| speed | speed | 转速 | **varchar** | rpm |
| angle | angle | 叶片角度 | **varchar** | ° |
| status | status | 运行状态 | bit | 0=停/1=运行 |
| lx | lx | 冷却水流量 | decimal(8,1) | L/s |
| lu | lu | 冷却水压力 | decimal(8,1) | MPa |
| fan_run | fanRun | 风机运行 | bit | 0=停/1=运行 |
| fan_fault | fanFault | 风机故障 | bit | 0=正常/1=故障 |
| ot | ot | 进水温度 | decimal(8,1) | ℃ |
| it | it | 出水温度 | decimal(8,1) | ℃ |
| ul | ul | 励磁电压 | decimal(8,1) | V |
| al | al | 励磁电流 | decimal(8,1) | A |
| extend | extend | 扩展信息 | json | — |
| stcd | stCode | 站码 | varchar(20) | — |
| idstcd | idstcd | 泵站编码 | char(18) NOT NULL | — |
| eq_code | eqCode | 设备编码 | varchar(20) | — |
| st_id | stId | 测站ID | bigint NOT NULL | — |
| eq_id | eqId | 设备ID | bigint | — |
| tm | tm | 采集时间 | datetime | — |

## 闸门分析规则

### 流量合理性

```
if gtophgt == 0 and gtq > 0:
  → 异常: 闸门关闭但有流量（可能漏水）
if gtophgt > 0 and gtq == 0:
  → 异常: 闸门开启但无流量（可能堵塞）
if gtopnum > 总孔数:
  → 异常: 开启孔数超限
```

### 开关状态一致性

```
if status == 0 (关) and gtophgt > 0:
  → 异常: 状态为关但有开度
if status == 1 (开) and gtophgt == 0:
  → 异常: 状态为开但开度为0
```

## 泵站分析规则

### 电气参数校验

> ⚠️ 所有电气参数为 varchar 类型，需先 parseFloat() 转换后再比较。

```
电压 = parseFloat(uab)
频率 = parseFloat(freq)

if isNaN(电压) or 电压 < 340 or 电压 > 420:
  → 电压异常（正常380V±10%）

# ⚠️ 频率判定分口径（严格比较——恰等于边界值不触发；变频泵VFD均不适用）。
# 本文件是 inspection 与 monitor 的共享事实源，两层各取各的口径：
if isNaN(频率) or 频率 < 45 or 频率 > 55:
  → 【巡检口径·inspection】频率异常WARNING（工频50Hz±10%，数据合理性层；
    与巡检引擎 inspection_analyzer.py pump_freq_low_hz=45/high_hz=55 一致。
    例：44.9 触发；恰 45.0 不触发）
if isNaN(频率) or 频率 < 48 or 频率 > 52:
  → 【实时监控口径·monitor】频率异常（50Hz±2Hz，电气运行监视层；
    monitor/references/algorithm.md 实现、evolution/parameters.md 2026-05-30 标定，
    正常带 49-51。例：47.9 触发；恰 48.0 不触发）
# 做巡检/数据质量分析（powerelf-inspection）→ 用 45/55；做实时运行监控（powerelf-monitor）→ 用 48/52。

# 三相不平衡度
ia_val = parseFloat(ia)
ib_val = parseFloat(ib)
ic_val = parseFloat(ic)
mean_current = (ia_val + ib_val + ic_val) / 3
不平衡度 = max(|ia_val-ib_val|, |ib_val-ic_val|, |ia_val-ic_val|) / mean_current
if 不平衡度 > 10%:
  → 三相不平衡预警
```

### 功率分析

```
实际功率 = parseFloat(p)
if isNaN(实际功率):
  → 数据异常，功率值无法解析

额定功率 = 设备铭牌功率（从 eq_equip_base 获取）
负载率 = 实际功率 / 额定功率

if 负载率 > 0.95:
  → 过载预警
if 负载率 < 0.1 and status == 1 (运行):
  → 空载运行，建议检查
```

### 冷却系统检查

```
if fan_fault == 1:
  → 风机故障预警
if fan_run == 0 and status == 1:
  → 泵运行但风机未开，需确认

if ot != null and it != null:
  温升 = it - ot
  if 温升 > 10:
    → 冷却不足，温升过大
```

### 励磁系统检查

```
励磁电压 = parseFloat(ul)
励磁电流 = parseFloat(al)

if 励磁电压 == 0 and status == 1:
  → 励磁系统异常
```
