# 异常判定与复杂工况识别规则

## 一、异常判定：怎么判断数据是异常？

### 判定层次

```
第1层: 阈值判定（绝对值超限）     → 明确异常
第2层: 变化率判定（突变检测）     → 可疑异常
第3层: 趋势判定（持续单向变化）   → 潜在异常
第4层: 统计异常（偏离历史分布）   → 隐性异常
第5层: 关联异常（多指标矛盾）     → 复杂异常
```

### 第1层：阈值判定（基于 ew_info_rules 表）

预警阈值存储在 `ew_info_rules` 表的 `extend` 字段中，JSON格式：
```json
{"content": ["248", null], "condition": ">"}
```
- `condition`: 比较运算符（`>`, `>=`, `<`, `<=`）
- `content[0]`: 阈值（如水位248m）
- `level_r`: 预警等级（1=一级/紧急, 2=二级/严重, 3=三级/警告）

#### 水位阈值（st_river_r.z）

```sql
-- 获取预警阈值
SELECT name, level_r, extend FROM ew_info_rules
WHERE type='YZ' AND ew_type='0' AND deleted=0 AND is_ignore='0';

-- 获取当前水位
SELECT z, q, tm FROM st_river_r
WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;
```

判定逻辑：
```
  if z > ew_info_rules[level_r=1].extend.content[0]:  → I级异常（紧急）
  if z > ew_info_rules[level_r=2].extend.content[0]:  → II级异常（严重）
  if z > ew_info_rules[level_r=3].extend.content[0]:  → III级异常（警告）

  实际数据示例:
    1#水位站一级预警: z > 248 → I级
    2#水位站二级预警: z > 245 → II级
    水位三级预警: z >= 38 → III级
```

#### 渗压阈值（st_pressure_r.water_pressure）

```sql
SELECT water_pressure, ext_pressure, ext_temperature, tm
FROM st_pressure_r WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;
```

```
  if water_pressure > 设计允许值:        → I级异常
  if water_pressure > 历史最大值*1.1:    → II级异常
  if water_pressure > 历史最大值:        → III级异常

  -- 获取历史最大值
  SELECT MAX(water_pressure) FROM st_pressure_r
  WHERE st_id={st_id} AND tm >= NOW()-INTERVAL 365 DAY;
```

#### GNSS位移阈值（srm_gnss_data_day）

```sql
SELECT wgs84_delta_h, wgs84_delta_x, wgs84_delta_y,
       speed_gh, speed_gx, speed_gy, tm
FROM srm_gnss_data_day WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;
```

```
  if wgs84_delta_h > 设计允许值:    → I级异常（累计位移超限）
  if speed_gh > 1.0:               → II级异常（日位移速率>1mm/d）
  if speed_gh > 0.5:               → III级异常（日位移速率>0.5mm/d）
```

#### 测量机器人位移阈值（srm_robot_data_day）

> 与 GNSS 互补：GNSS 连续自动监测（每小时/每日），机器人精确人工测量（每周/每月）。
> 机器人数据精度更高，用于校核 GNSS 数据。

```sql
SELECT wgs84_delta_h, wgs84_delta_x, wgs84_delta_y,
       speed_gh, speed_gx, speed_gy,
       timely_change_north, timely_change_east, timely_change_height,
       dot_address, tm
FROM srm_robot_data_day WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;
```

```
  if speed_gh > 1.0:               → II级异常（日位移速率>1mm/d）
  if speed_gh > 0.5:               → III级异常（日位移速率>0.5mm/d）
  if timely_change_height > 设计允许值: → I级异常（累计高程变化超限）

  -- 与GNSS交叉校验:
  if GNSS显示异常 AND 机器人数据正常:
    → 可能是GNSS误差，建议加密机器人复测
  if GNSS显示正常 AND 机器人数据异常:
    → 可能是GNSS漏检，按机器人数据报警
```

#### 雨量阈值（st_pptn_r.p）

```sql
SELECT p, dr, tm FROM st_pptn_r
WHERE st_id={st_id} AND tm >= NOW()-INTERVAL 24 HOUR ORDER BY tm DESC;
```

```
  if SUM(p) WHERE tm >= NOW()-1h > 50:    → III级异常（暴雨）
  if SUM(p) WHERE tm >= NOW()-24h > 100:  → II级异常（大暴雨）
```

#### 设备状态阈值（eq_equip_base.status）

```sql
SELECT id, name, code, status, status_flag FROM eq_equip_base
WHERE project_id={project_id} AND deleted=0;
```

```
  if status=0 且 离线时长 > 24h:    → II级异常
  if status=0 且 离线时长 > 4h:     → III级异常

  -- 离线时长计算（通过 eq_equip_offline_record 表）
  -- 该表由 Flyway 管理，字段: equipment_code, offline_start_time, offline_end_time, total_offline_duration
  SELECT equipment_code, offline_start_time, offline_end_time,
         total_offline_duration
  FROM eq_equip_offline_record
  WHERE equipment_code={code} AND offline_end_time IS NULL;
  -- total_offline_duration 单位为秒，>86400=24h, >14400=4h
```

#### 泵站三相电流不平衡（rei_pump_r）

```sql
SELECT ia, ib, ic, tm FROM rei_pump_r
WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;
```

```
  avg_current = (ia + ib + ic) / 3
  max_deviation = max(|ia-avg|, |ib-avg|, |ic-avg|)
  imbalance_rate = max_deviation / avg_current

  if imbalance_rate > 0.10:  → III级异常（三相不平衡>10%）
```

### 第2层：变化率判定（突变检测）

```
规则: 相邻数据点的变化幅度

公式:
  change_rate = |当前值 - 前值| / 前值
  change_abs  = |当前值 - 前值|

SQL获取相邻数据:
  SELECT z, LAG(z) OVER (ORDER BY tm) as prev_z, tm
  FROM st_river_r WHERE st_id={st_id}
  AND tm >= NOW()-INTERVAL 24 HOUR ORDER BY tm;

水位突变(st_river_r.z):
  if |z - prev_z| > 0.5:          → 疑似突变（0.5m/h）
  if |z - prev_z| / prev_z > 0.05: → 疑似突变（5%/h）

渗压突变(st_pressure_r.water_pressure):
  if |wp - prev_wp| > 5:           → 疑似突变（5kPa/h）
  if |wp - prev_wp| / prev_wp > 0.10: → 疑似突变（10%/h）

GNSS突变(srm_gnss_data_day):
  if |delta_h - prev_delta_h| > 2:  → 疑似突变（2mm/d）

流量突变(st_river_r.q):
  if |q - prev_q| / prev_q > 0.20:  → 疑似突变（20%/h）

判定逻辑:
  突变 ≠ 一定异常
  需要结合上下文:
    - 闸门操作(rei_gate_r.gtophgt变化) → 正常
    - 降雨(st_pptn_r.p>0)导致的水位上涨 → 正常
    - 无外部因素的突变 → 真异常
```

### 第3层：趋势判定（持续单向变化）

```
规则: 连续N次数据单调递增/递减

SQL检测连续上升:
  WITH ranked AS (
    SELECT z, tm,
           ROW_NUMBER() OVER (ORDER BY tm DESC) as rn,
           z - LAG(z) OVER (ORDER BY tm) as z_change
    FROM st_river_r
    WHERE st_id={st_id} AND tm >= NOW()-INTERVAL 48 HOUR
  )
  SELECT COUNT(*) as consecutive_rise
  FROM ranked WHERE z_change > 0 AND rn <= 12;

阈值（按指标，基于实际采集频率）:
  水位(st_river_r):   连续上升 >= 6次 (每小时1次 = 6小时持续上升)
  渗压(st_pressure_r): 连续上升 >= 12次 (每小时1次 = 12小时持续上升)
  GNSS(srm_gnss_data_day): 连续位移 >= 7次 (每日1次 = 7天持续位移)
  流量(st_river_r.q): 连续上升 >= 6次

趋势异常等级:
  if 连续次数 >= 阈值*2:      → II级
  if 连续次数 >= 阈值:        → III级
  if 连续次数 >= 阈值*0.5:    → IV级（预警）
```

### 第4层：统计异常（MAD检测）

```
规则: 当前值偏离历史分布的程度

方法: Modified Z-Score (MAD)
  median = 近N个数据的中位数
  MAD = median(|xi - median|) * 1.4826
  z_score = |xi - median| / MAD

SQL实现（以水位为例）:
  WITH stats AS (
    SELECT z,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY z) as median
    FROM st_river_r
    WHERE st_id={st_id} AND tm >= NOW()-INTERVAL 7 DAY
  ),
  mad AS (
    SELECT median,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ABS(z - median)) * 1.4826 as mad_value
    FROM stats
  )
  SELECT z, (ABS(z - median) / mad_value) as z_score
  FROM st_river_r, mad
  WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;

阈值（按指标）:
  水位(st_river_r.z):         z_score > 3.0  → 异常
  雨量(st_pptn_r.p):          z_score > 5.0  → 异常（雨量波动大）
  渗压(st_pressure_r.wp):     z_score > 4.0  → 异常
  GNSS(srm_gnss_data_day):    z_score > 3.5  → 异常
  流量(st_river_r.q):         z_score > 4.0  → 异常

窗口大小（基于实际采集频率）:
  水位:   近7天 (168个点 @ 1小时/次)
  渗压:   近30天 (720个点 @ 1小时/次)
  GNSS:   近90天 (90个点 @ 1日/次)
  雨量:   近30天 (720个点 @ 1小时/次)
```

### 第5层：关联异常（多指标矛盾）

```
规则: 多个指标之间的逻辑关系不一致

示例1: 水位上升但入库流量下降
  SQL:
    SELECT z, q FROM st_river_r WHERE st_id={st_id}
    AND tm >= NOW()-INTERVAL 6 HOUR ORDER BY tm;
  判定:
    if z趋势上升 AND q趋势下降 AND rei_gate_r无操作:
      → 异常! 可能是闸门故障或数据错误

示例2: 降雨量大但水位不涨
  SQL:
    SELECT SUM(p) as total_rain FROM st_pptn_r
    WHERE st_id={st_id} AND tm >= NOW()-INTERVAL 24 HOUR;
  判定:
    if total_rain > 50 AND z变化 < 0.1:
      → 检查: 是否有泄洪操作？雨量站是否准确？

示例3: 渗压与水位不相关
  判定:
    if z上升 > 1 AND water_pressure无变化:
      → 疑似渗压计故障
    if z稳定 AND water_pressure持续上升:
      → 异常! 可能是防渗体损坏

示例4: GNSS位移与水位相关性异常
  判定:
    if z上升期 AND wgs84_delta_x/y方向指向库区外:
      → 正常（水压推动坝体）
    if z稳定期 AND speed_gh持续增大:
      → 异常! 可能是坝体失稳
```

## 二、复杂工况识别：什么情况需要人工介入？

### 复杂工况定义

```
复杂工况 = 单一指标可能正常，但多个指标组合起来显示异常

Agent 判断为"复杂工况"的条件（满足任一即触发）:
  1. 同一巡检点有 >= 2个指标同时触发异常
  2. 不同巡检点的异常存在空间关联（同一区域）
  3. 异常指标之间存在因果关系
  4. Agent 置信度 < 70%（不确定是否真异常）
```

### 复杂工况场景库（基于实际数据表）

#### 场景1：汛期高水位 + 渗压上升

```
触发条件:
  st_river_r.z > ew_info_rules[level_r=3].extend.content[0]
  AND st_pressure_r.water_pressure 连续上升

SQL检测:
  -- 水位是否超阈值
  SELECT z FROM st_river_r WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;
  -- 渗压趋势
  SELECT water_pressure, tm FROM st_pressure_r
  WHERE st_id={st_id} AND tm >= NOW()-INTERVAL 12 HOUR ORDER BY tm;

判定逻辑:
  expected_pressure_change = z_change * k (k为水压传递系数，需根据坝型确定)
  actual_pressure_change = 当前water_pressure - 12小时前water_pressure

  if actual > expected * 1.5:  → 复杂工况! 可能是防渗体损坏
  elif actual > expected * 1.2: → 关注，继续监测
  else:                         → 正常

需要人工做的:
  1. 到渗压计位置现场检查是否有渗水
  2. 检查渗压计读数是否准确
  3. 检查附近是否有裂缝或损坏
```

#### 场景2：GNSS位移加速 + 降雨

```
触发条件:
  srm_gnss_data_day.speed_gh > 0.3
  AND SUM(st_pptn_r.p WHERE tm>=NOW()-3DAY) > 30

SQL检测:
  -- GNSS位移速率
  SELECT speed_gh, wgs84_delta_x, wgs84_delta_y FROM srm_gnss_data_day
  WHERE st_id={st_id} ORDER BY tm DESC LIMIT 1;
  -- 近3日累计雨量
  SELECT SUM(p) as total FROM st_pptn_r
  WHERE st_id={rain_st_id} AND tm >= NOW()-INTERVAL 3 DAY;

判定逻辑:
  if wgs84_delta_x指向库区外 AND 降雨量大:
    → 可能是雨水入渗导致，继续监测
  elif wgs84_delta_x指向库区内 AND z稳定:
    → 异常! 可能是坝体内部冲刷
  elif speed_gh环比增长 > 50%:
    → 复杂工况! 需人工现场确认

需要人工做的:
  1. 检查坝面是否有裂缝
  2. 检查排水设施是否正常
  3. 检查坝脚是否有隆起或滑移
```

#### 场景3：多设备同时离线

```
触发条件:
  eq_equip_base 中同一区域 >= 3台设备 status=0

SQL检测:
  SELECT position, COUNT(*) as offline_count
  FROM eq_equip_base
  WHERE status=0 AND deleted=0
  GROUP BY position
  HAVING COUNT(*) >= 3;

判定逻辑:
  if 某区域offline_count >= 3:  → 可能是通信/电源故障
  elif 全站offline_count >= 5:  → 可能是主通信链路故障

需要人工做的:
  1. 检查通信设备（基站、交换机）
  2. 检查UPS/电源
  3. 检查网线/光纤
```

#### 场景4：闸门异常 + 水位异常

```
触发条件:
  rei_gate_r 状态异常 AND st_river_r.z 变化异常

SQL检测:
  -- 闸门状态
  SELECT gtophgt, gtopnum, gtq, status, tm FROM rei_gate_r
  WHERE st_id={st_id} ORDER BY tm DESC LIMIT 6;
  -- 水位变化
  SELECT z, tm FROM st_river_r
  WHERE st_id={st_id} AND tm >= NOW()-INTERVAL 6 HOUR ORDER BY tm;

判定逻辑:
  if gtophgt=最大值 AND z仍在上升:
    → 可能是来水量超过泄洪能力
    → 需要启动应急预案
  elif gtophgt未变 AND z上升:
    → 闸门可能卡阻
    → 需要人工现场检查
  elif gtophgt波动 AND z波动:
    → 可能是控制系统不稳定
    → 需要电气工程师检查

需要人工做的:
  1. 现场检查闸门机械状态
  2. 检查液压系统
  3. 检查控制柜
```

#### 场景5：数据质量异常 + 监测异常

```
触发条件:
  数据缺失率上升 AND 同时出现监测异常

SQL检测:
  -- 数据完整性（预期24条/天，实际多少条）
  SELECT DATE(tm) as dt, COUNT(*) as cnt
  FROM st_river_r WHERE st_id={st_id}
  AND tm >= NOW()-INTERVAL 7 DAY
  GROUP BY DATE(tm);

  -- 异常数（使用 eq_equip_anomaly_record 表）
  -- 字段: equipment_code, anomaly_start_time, anomaly_end_time, total_anomaly_duration
  SELECT COUNT(*) FROM eq_equip_anomaly_record
  WHERE equipment_code={equipment_code}
  AND anomaly_start_time >= NOW()-INTERVAL 24 HOUR;

判定逻辑:
  if 缺失率 > 40% AND anomaly_count > 5:
    → 可能是传感器问题，不是真异常
    → 建议先检查传感器，再判断
  elif 缺失率 < 10% AND anomaly_count > 0:
    → 数据可信，异常可能是真的
    → 按正常异常处理流程
  else:
    → 数据质量一般，异常需人工确认
```

## 三、Agent 置信度评估

```
Agent 对每次异常判定给出置信度:

置信度 = f(异常层级, 数据质量, 历史一致性, 外部因素)

高置信度 (>85%): 直接推送，无需人工确认
  - 阈值超限(ew_info_rules触发) + 数据完整 + 有历史佐证
  - 示例: st_river_r.z > 248 (1#水位站一级预警阈值)

中置信度 (60-85%): 推送 + 建议人工确认
  - 变化率异常 + 数据质量一般
  - 示例: st_pressure_r.water_pressure 突变但无明显外部原因

低置信度 (<60%): 必须人工确认才能判定
  - 统计异常或多指标关联异常
  - 示例: MAD检测到异常但单看阈值正常

计算公式:
  confidence = 0.3 * threshold_score    # 阈值越明确，分越高（参考ew_info_rules.level_r）
             + 0.2 * data_quality_score  # 数据质量越好，分越高（缺失率越低）
             + 0.2 * trend_score         # 趋势越一致，分越高
             + 0.2 * history_score       # 历史越吻合，分越高
             + 0.1 * context_score       # 外部因素越明确，分越高（闸门/降雨）
```

## 四、异常处理决策树

```
Agent 发现数据异常
  │
  ├─ 阈值超限(对比ew_info_rules)?
  │   ├─ 是 → 立即推送预警 + 记录到business_check_error
  │   └─ 否 → 进入变化率检测
  │
  ├─ 变化率异常?
  │   ├─ 是 → 检查外部因素:
  │   │   ├─ rei_gate_r.gtophgt变化 → 标记"已解释异常"
  │   │   ├─ st_pptn_r.p>0 → 标记"降雨导致"
  │   │   └─ 无外部因素 → 推送预警 + 建议人工确认
  │   └─ 否 → 进入趋势检测
  │
  ├─ 趋势异常?
  │   ├─ 是 → 评估趋势持续时间和幅度
  │   │   ├─ 持续时间短且幅度小 → 记录，继续监测
  │   │   └─ 持续时间长或幅度大 → 推送预警
  │   └─ 否 → 进入统计异常检测
  │
  ├─ 统计异常(MAD)?
  │   ├─ 是 → 评估置信度
  │   │   ├─ 高置信度 → 推送预警
  │   │   └─ 低置信度 → 标记"待确认"，增加采集频率
  │   └─ 否 → 正常
  │
  └─ 多指标关联异常?
      ├─ 是 → 触发"复杂工况"流程
      │   └─ 推送详细分析报告 + 要求人工现场确认
      └─ 否 → 正常
```
