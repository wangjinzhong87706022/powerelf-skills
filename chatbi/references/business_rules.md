# ChatBI 业务规则

> 自然语言→表映射、SQL 模式、JOIN 规则、租户过滤

---

## 一、查询意图→表映射

### 水文气象

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 水库水位/库水位/蓄水量/入库流量/出库流量 | st_rsvr_r | att_st_base |
| 河道水位/河流水位/流量/流速 | st_river_r | att_st_base |
| 闸站水位/过闸流量/上下游水位 | st_was_r | att_st_base |
| 潮位/潮汐/高低潮 | st_tide_r | att_st_base |
| 雨量/降雨/降水/暴雨/日雨量 | st_pptn_r | att_st_base |
| 分区雨量/区域降雨 | st_pptn_region_r | — |
| 防洪水位/防洪区 | st_flood_r | att_st_base |

### 设备工情

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 闸门/开启高度/过闸流量/闸门状态 | rei_gate_r | att_st_base |
| 泵站/电压/电流/功率/频率/转速 | rei_pump_r | att_st_base |

### 大坝安全

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| GNSS/位移/变形/累计变化/速率 | dsm_dfr_srvrds_srhrds | srm_gnss_stat_day |
| 渗流/渗流量 | st_percolation_r | att_st_base |
| 渗压/压力/水压力/温度 | st_pressure_r | — |

### 其他监测

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 墒情/土壤含水量/土壤温度/电导率 | st_soil_moisture_r | — |
| 白蚁/蚁害/蚁种/密度 | st_termite_monitor_r | — |

### 预警

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 预警/告警/报警/预警消息 | ew_info_message | ew_info_rules |
| 预警规则/规则配置 | ew_info_rules | ew_info_rules_dam |
| 大坝预警/坝体预警 | ew_info_rules_dam | ew_info_message |
| 通知策略/短信/邮件/微信通知 | ew_notice_tactics | ew_notice_record |
| 通知记录/发送记录 | ew_notice_record | — |
| 视频报警/摄像头报警/AI报警 | ew_camera_info | — |

### 设备管理

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 设备/设备列表/在线/离线/异常 | eq_equip_base | eq_equip_offline_record |
| 数据缺失/缺失记录 | eq_data_missing_record | — |
| 数据异常/异常记录 | eq_data_anomaly_record | — |
| 离线记录/离线时长 | eq_equip_offline_record | — |
| 设备异常/异常时长 | eq_equip_anomaly_record | — |

### 巡检

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 巡检任务/巡检计划/巡检完成 | business_check_task | business_check_route |
| 巡检路线/巡检线路 | business_check_route | business_check_point |
| 巡检结果/巡检情况 | business_check_result | business_check_task |
| 缺陷/问题/未处理缺陷 | business_check_error | business_check_task |
| 巡检对象/巡检设施 | business_check_obj | business_check_point |
| 巡检点/巡检位置 | business_check_point | — |

### 数据治理

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 离线阈值/离线配置 | dg_equip_offline | — |
| 设备映射/业务关联 | eq_business_equip_relation | — |
| 采集统计/数据采集量 | stats_data_collection_daily | — |
| 缺失统计/数据缺失量 | stats_data_missing_daily | — |
| 异常统计/数据异常量 | stats_data_anomaly_daily | — |
| 数据质量总览/质量评分 | stats_data_collection_daily + stats_data_missing_daily + stats_data_anomaly_daily | — |

### 基础信息

| 自然语言关键词 | 主表 | 备选/关联表 |
|---------------|------|------------|
| 测站/站点/站码 | att_st_base | — |
| 大坝/坝体 | att_dam_base | — |

---

## 二、常见 SQL 模式

### 1. 最新一条记录

```sql
SELECT * FROM {table}
WHERE {condition} AND deleted = 0 AND tenant_id = 1
ORDER BY tm DESC
LIMIT 1
```

### 2. 时间范围查询

```sql
SELECT tm, {fields} FROM {table}
WHERE {condition}
  AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND deleted = 0 AND tenant_id = 1
ORDER BY tm
```

### 3. 每个实体的最新记录（窗口函数）

```sql
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY st_id ORDER BY tm DESC) AS rn
  FROM {table}
  WHERE deleted = 0 AND tenant_id = 1
) t
WHERE rn = 1
```

### 4. 聚合统计

```sql
-- 日均值
SELECT DATE(tm) AS dt, AVG({field}) AS avg_val
FROM {table}
WHERE {condition} AND deleted = 0 AND tenant_id = 1
GROUP BY dt
ORDER BY dt

-- 月统计
SELECT DATE_FORMAT(tm, '%Y-%m') AS month, SUM({field}) AS total
FROM {table}
WHERE {condition} AND deleted = 0 AND tenant_id = 1
GROUP BY month
ORDER BY month

-- 按站点统计
SELECT st_id, COUNT(*) AS cnt, AVG({field}) AS avg_val
FROM {table}
WHERE {condition} AND deleted = 0 AND tenant_id = 1
GROUP BY st_id
```

### 5. 排名/TopN

```sql
SELECT {fields}, {metric}
FROM {table}
WHERE {condition} AND deleted = 0 AND tenant_id = 1
ORDER BY {metric} DESC
LIMIT 10
```

### 6. 变化率计算（相邻记录差值）

```sql
SELECT t1.tm, t1.{field},
       t1.{field} - LAG(t1.{field}) OVER (ORDER BY t1.tm) AS delta
FROM {table} t1
WHERE t1.{condition} AND t1.deleted = 0 AND t1.tenant_id = 1
ORDER BY t1.tm
```

### 7. 状态统计（GROUP BY status）

```sql
SELECT status, COUNT(*) AS cnt
FROM {table}
WHERE deleted = 0 AND tenant_id = 1
GROUP BY status
```

---

## 三、跨表 JOIN 模式

### 1. 测站 + 时序数据

```sql
SELECT s.name AS station_name, r.*
FROM st_rsvr_r r
JOIN att_st_base s ON r.st_id = s.id
WHERE s.deleted = 0 AND r.deleted = 0 AND r.tenant_id = 1
ORDER BY r.tm DESC
```

### 2. 设备 + 离线记录

```sql
SELECT e.name, e.code, o.offline_start_time, o.total_offline_duration
FROM eq_equip_base e
JOIN eq_equip_offline_record o ON e.code = o.equipment_code
WHERE e.status = 0 AND e.deleted = 0 AND o.deleted = 0 AND e.tenant_id = 1
```

### 3. 预警消息 + 规则

```sql
SELECT m.ew_name, m.level_r, m.value, m.gather_time, r.name AS rule_name
FROM ew_info_message m
JOIN ew_info_rules r ON m.ew_rules_id = r.id
WHERE m.deleted = 0 AND r.deleted = 0 AND m.tenant_id = 1
ORDER BY m.gather_time DESC
```

### 4. 巡检任务 + 缺陷

```sql
SELECT t.name AS task_name, t.plan_time, e.problem, e.status
FROM business_check_task t
JOIN business_check_error e ON t.id = e.task_id
WHERE t.deleted = 0 AND e.deleted = 0 AND t.tenant_id = 1
```

### 5. 巡检路线 + 巡检点

```sql
SELECT r.name AS route_name, p.point_name, p.lon_lat
FROM business_check_route r
JOIN business_check_point p ON FIND_IN_SET(p.id, r.select_id)
WHERE r.deleted = 0 AND p.deleted = 0 AND r.tenant_id = 1
```

### 6. 数据质量三表联合

```sql
SELECT c.tm, c.table_name,
       c.collection_data_number,
       m.missing_data_number,
       a.anomaly_data_number
FROM stats_data_collection_daily c
LEFT JOIN stats_data_missing_daily m ON c.tm = m.tm AND c.table_name = m.table_name
LEFT JOIN stats_data_anomaly_daily a ON c.tm = a.tm AND c.table_name = a.table_name
WHERE c.deleted = 0 AND c.tenant_id = 1
ORDER BY c.tm DESC
```

---

## 四、租户与权限过滤

### 必备条件（每条 SQL 都必须包含）

```sql
AND deleted = 0       -- 软删除过滤
AND tenant_id = 1     -- 多租户过滤（默认租户ID=1）
```

### 设备状态过滤

```sql
-- 离线设备
WHERE status = 0 AND deleted = 0 AND tenant_id = 1

-- 在线设备
WHERE status = 1 AND deleted = 0 AND tenant_id = 1

-- 异常设备
WHERE status = 2 AND deleted = 0 AND tenant_id = 1
```

### 预警等级过滤

```sql
-- I级（特别严重）
WHERE level_r = '1'

-- II级及以上
WHERE level_r IN ('1', '2')

-- 未确认的预警
WHERE message_confirm = 0
```

---

## 五、特殊字段处理

### 泵站电气参数（varchar 类型）

```sql
-- 数值比较需 CAST
SELECT * FROM rei_pump_r
WHERE CAST(p AS DECIMAL(10,2)) > 100
  AND deleted = 0 AND tenant_id = 1
```

### 雨量时段长单位差异

```sql
-- st_pptn_r: dr 单位是分钟
-- st_pptn_region_r: intv 单位是小时

-- 计算雨强 (mm/h) 示例
SELECT tm, p, dr, p / (dr / 60.0) AS intensity_mm_per_hour
FROM st_pptn_r
WHERE deleted = 0 AND tenant_id = 1
```

### JSON 字段查询

```sql
-- 预警规则 extend 字段
SELECT * FROM ew_info_rules
WHERE JSON_EXTRACT(extend, '$.threshold') > 100
  AND deleted = 0 AND tenant_id = 1
```
