# ChatBI Few-Shots — 常见自然语言查询示例

> 15+ 典型查询场景，覆盖水情、雨情、设备、预警、巡检、数据治理、大坝安全等领域。
> 所有 SQL 均使用 powerelf_data 前缀库，包含 deleted=0 和 tenant_id=1。

---

## 1. 水库最近一周水位趋势

**问题:** "最近一周XX水库的水位"

```sql
SELECT tm, rz AS 水位_m, inq AS 入库流量, otq AS 出库流量, w AS 蓄水量
FROM powerelf_data.st_rsvr_r
WHERE st_id = (
  SELECT id FROM powerelf_data.att_st_base WHERE name LIKE '%XX水库%' AND deleted = 0 LIMIT 1
)
  AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND deleted = 0
  AND tenant_id = 1
ORDER BY tm
```

---

## 2. 各水库最新水位

**问题:** "各水库当前水位是多少"

```sql
SELECT s.name AS 水库名称, r.rz AS 库水位_m, r.inq AS 入库流量, r.otq AS 出库流量, r.tm AS 采集时间
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY st_id ORDER BY tm DESC) AS rn
  FROM powerelf_data.st_rsvr_r
  WHERE deleted = 0 AND tenant_id = 1
) r
JOIN powerelf_data.att_st_base s ON r.st_id = s.id
WHERE r.rn = 1 AND s.deleted = 0
ORDER BY r.rz DESC
```

---

## 3. 今日雨量统计

**问题:** "今天各站下了多少雨"

```sql
SELECT s.name AS 站名, SUM(r.p) AS 总雨量_mm, MAX(r.dyp) AS 最大日雨量_mm
FROM powerelf_data.st_pptn_r r
JOIN powerelf_data.att_st_base s ON r.st_id = s.id
WHERE DATE(r.tm) = CURDATE()
  AND r.deleted = 0 AND s.deleted = 0
  AND r.tenant_id = 1
GROUP BY r.st_id, s.name
ORDER BY 总雨量_mm DESC
```

---

## 4. 哪些设备离线

**问题:** "哪些设备离线了"

```sql
SELECT name AS 设备名称, code AS 设备编码, type_flag AS 设备类型, st_base_id AS 关联测站
FROM powerelf_data.eq_equip_base
WHERE status = 0
  AND deleted = 0
  AND tenant_id = 1
ORDER BY update_time DESC
```

---

## 5. 设备离线时长统计

**问题:** "离线超过24小时的设备有哪些"

```sql
SELECT e.name AS 设备名称, e.code AS 设备编码,
       o.offline_start_time AS 离线开始时间,
       ROUND(o.total_offline_duration / 3600.0, 1) AS 离线时长_小时
FROM powerelf_data.eq_equip_base e
JOIN powerelf_data.eq_equip_offline_record o ON e.code = o.equipment_code
WHERE o.offline_end_time IS NULL
  AND o.total_offline_duration > 86400
  AND e.deleted = 0 AND o.deleted = 0
  AND e.tenant_id = 1
ORDER BY o.total_offline_duration DESC
```

---

## 6. 最近预警消息

**问题:** "最近有哪些预警"

```sql
SELECT ew_name AS 预警名称,
       CASE level_r WHEN '1' THEN 'I级' WHEN '2' THEN 'II级' WHEN '3' THEN 'III级' WHEN '4' THEN 'IV级' END AS 预警等级,
       value AS 触发值,
       gather_time AS 采集时间,
       CASE message_confirm WHEN 0 THEN '未确认' WHEN 1 THEN '已确认' END AS 确认状态
FROM powerelf_data.ew_info_message
WHERE deleted = 0 AND tenant_id = 1
ORDER BY gather_time DESC
LIMIT 20
```

---

## 7. 预警等级统计

**问题:** "本月各等级预警数量统计"

```sql
SELECT
  CASE level_r WHEN '1' THEN 'I级' WHEN '2' THEN 'II级' WHEN '3' THEN 'III级' WHEN '4' THEN 'IV级' END AS 预警等级,
  COUNT(*) AS 预警次数
FROM powerelf_data.ew_info_message
WHERE MONTH(gather_time) = MONTH(NOW())
  AND YEAR(gather_time) = YEAR(NOW())
  AND deleted = 0 AND tenant_id = 1
GROUP BY level_r
ORDER BY level_r
```

---

## 8. GNSS 位移趋势

**问题:** "XX测点最近一个月的GNSS位移变化"

```sql
SELECT tm AS 采集时间,
       wgs84_delta_h AS 高程变化_mm,
       wgs84_delta_x AS X方向变化_mm,
       wgs84_delta_y AS Y方向变化_mm,
       wgs84_total_h AS 累计高程变化_mm,
       speed_gh AS 高程速率
FROM powerelf_data.dsm_dfr_srvrds_srhrds
WHERE point_id = 'XX测点ID'
  AND tm > DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND deleted = 0 AND tenant_id = 1
ORDER BY tm
```

---

## 9. 渗压变化

**问题:** "XX断面最近一周渗压变化"

```sql
SELECT tm AS 采集时间,
       ext_pressure AS 渗压_kPa,
       water_pressure AS 水位压力_kPa,
       ext_temperature AS 温度_℃
FROM powerelf_data.st_pressure_r
WHERE section_id = XX
  AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND deleted = 0 AND tenant_id = 1
ORDER BY tm
```

---

## 10. 本月巡检缺陷

**问题:** "本月发现了多少巡检缺陷"

```sql
SELECT COUNT(*) AS 缺陷总数,
       SUM(CASE WHEN status = '0' OR status = 'pending' THEN 1 ELSE 0 END) AS 待处理,
       SUM(CASE WHEN status = '1' OR status = 'processed' THEN 1 ELSE 0 END) AS 已处理
FROM powerelf_data.business_check_error
WHERE MONTH(create_time) = MONTH(NOW())
  AND YEAR(create_time) = YEAR(NOW())
  AND deleted = 0 AND tenant_id = 1
```

---

## 11. 未完成的巡检任务

**问题:** "有哪些未完成的巡检任务"

```sql
SELECT name AS 任务名称, serial AS 任务编号, plan_time AS 计划时间,
       begin_time AS 开始时间, status AS 状态, bad_num AS 缺陷数
FROM powerelf_data.business_check_task
WHERE status NOT IN ('completed', '3')
  AND deleted = 0 AND tenant_id = 1
ORDER BY plan_time
```

---

## 12. 数据质量总览

**问题:** "最近一周数据采集质量如何"

```sql
SELECT c.tm AS 日期, c.table_name AS 数据表,
       c.collection_data_number AS 采集条数,
       IFNULL(m.missing_data_number, 0) AS 缺失条数,
       IFNULL(a.anomaly_data_number, 0) AS 异常条数,
       ROUND((1 - (IFNULL(m.missing_data_number, 0) + IFNULL(a.anomaly_data_number, 0)) / GREATEST(c.collection_data_number, 1)) * 100, 2) AS 质量率_百分比
FROM powerelf_data.stats_data_collection_daily c
LEFT JOIN powerelf_data.stats_data_missing_daily m
  ON c.tm = m.tm AND c.table_name = m.table_name AND m.deleted = 0
LEFT JOIN powerelf_data.stats_data_anomaly_daily a
  ON c.tm = a.tm AND c.table_name = a.table_name AND a.deleted = 0
WHERE c.tm > DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND c.deleted = 0 AND c.tenant_id = 1
ORDER BY c.tm DESC, c.table_name
```

---

## 13. 闸门当前状态

**问题:** "所有闸门的当前状态"

```sql
SELECT s.name AS 站名, r.slcd AS 闸码,
       r.gtophgt AS 开启高度_m, r.gtopnum AS 开启孔数,
       r.gtq AS 流量_m3s,
       CASE r.status WHEN 0 THEN '关闭' WHEN 1 THEN '开启' END AS 开关状态,
       r.tm AS 采集时间
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY slcd ORDER BY tm DESC) AS rn
  FROM powerelf_data.rei_gate_r
  WHERE deleted = 0 AND tenant_id = 1
) r
JOIN powerelf_data.att_st_base s ON r.st_id = s.id
WHERE r.rn = 1 AND s.deleted = 0
ORDER BY s.name
```

---

## 14. 泵站运行参数

**问题:** "泵站的电压和功率情况"

```sql
SELECT s.name AS 站名,
       r.uab AS A相电压_V, r.ubc AS B相电压_V, r.uca AS C相电压_V,
       r.ia AS A相电流_A, r.ib AS B相电流_A, r.ic AS C相电流_A,
       r.p AS 有功功率_kW, r.freq AS 频率_Hz,
       CASE r.status WHEN 0 THEN '停机' WHEN 1 THEN '运行' END AS 运行状态,
       r.tm AS 采集时间
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY st_id ORDER BY tm DESC) AS rn
  FROM powerelf_data.rei_pump_r
  WHERE deleted = 0 AND tenant_id = 1
) r
JOIN powerelf_data.att_st_base s ON r.st_id = s.id
WHERE r.rn = 1 AND s.deleted = 0
```

---

## 15. 墒情监测总览

**问题:** "各测站的土壤墒情"

```sql
SELECT s.name AS 站名,
       soil_water10cm AS 10cm含水量, soil_water30cm AS 30cm含水量,
       soil_water60cm AS 60cm含水量, soil_water100cm AS 100cm含水量,
       ec AS 电导率, ph AS pH值,
       soil_moist_evaluation AS 墒情评价,
       r.tm AS 采集时间
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY st_id ORDER BY tm DESC) AS rn
  FROM powerelf_data.st_soil_moisture_r
  WHERE deleted = 0 AND tenant_id = 1
) r
JOIN powerelf_data.att_st_base s ON r.st_id = s.id
WHERE r.rn = 1 AND s.deleted = 0
```

---

## 16. 白蚁监测情况

**问题:** "哪些测站发现了白蚁"

```sql
SELECT s.name AS 站名, r.termite_species AS 蚁种,
       r.pest_density AS 密度等级, r.damage_level AS 危害等级,
       r.check_result AS 检查结果, r.tm AS 监测时间
FROM powerelf_data.st_termite_monitor_r r
JOIN powerelf_data.att_st_base s ON r.st_id = s.id
WHERE r.check_result LIKE '%发现%'
  AND r.deleted = 0 AND s.deleted = 0
  AND r.tenant_id = 1
ORDER BY r.tm DESC
```

---

## 17. 视频AI报警记录

**问题:** "最近的视频AI报警"

```sql
SELECT s.name AS 站名, c.device_id AS 设备ID,
       c.type AS 报警类型, c.alarm_grade AS 报警等级,
       CASE c.alarm_stat WHEN 1 THEN '产生' WHEN 2 THEN '消失' END AS 报警状态,
       c.info AS 报警信息, c.create_time AS 报警时间,
       CASE c.confirm WHEN 0 THEN '未确认' WHEN 1 THEN '已确认' END AS 确认状态
FROM powerelf_data.ew_camera_info c
LEFT JOIN powerelf_data.att_st_base s ON c.st_id = s.id
WHERE c.deleted = 0 AND c.tenant_id = 1
ORDER BY c.create_time DESC
LIMIT 20
```

---

## 18. 渗流量趋势

**问题:** "XX站最近一周渗流量变化"

```sql
SELECT tm AS 采集时间, percolation AS 渗流量_Ls
FROM powerelf_data.st_percolation_r
WHERE st_id = XX
  AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND deleted = 0 AND tenant_id = 1
ORDER BY tm
```

---

## 19. 河道水位超警戒

**问题:** "哪些河道水位超过警戒值"

```sql
SELECT s.name AS 站名, r.z AS 当前水位_m, r.q AS 流量_m3s, r.tm AS 采集时间
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY st_id ORDER BY tm DESC) AS rn
  FROM powerelf_data.st_river_r
  WHERE deleted = 0 AND tenant_id = 1
) r
JOIN powerelf_data.att_st_base s ON r.st_id = s.id
WHERE r.rn = 1 AND s.deleted = 0
  AND r.z > 3.5  -- 警戒水位（根据实际情况调整）
ORDER BY r.z DESC
```

---

## 20. 设备在线率统计

**问题:** "设备在线率是多少"

```sql
SELECT
  COUNT(*) AS 设备总数,
  SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS 在线数,
  SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS 离线数,
  SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS 异常数,
  ROUND(SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS 在线率_百分比
FROM powerelf_data.eq_equip_base
WHERE deleted = 0 AND tenant_id = 1
```
