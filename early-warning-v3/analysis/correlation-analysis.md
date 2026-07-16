# 关联分析

## 关联维度

### 时间关联
同一时间窗口（±30 分钟）内的其他告警，检测时间序列上的因果关系。

### 空间关联
同一测站的多个设备、同一水库的多个测站、上下游水库的水位关联。

### 业务关联
- 降雨 → 水位上涨 → 超警戒（因果链）
- 设备故障 → 数据异常 → 误报（故障链）
- 维护操作 → 参数变化 → 告警（操作链）

## 查询关联告警（读 — 直连数据库）

### 时间关联查询

```sql
-- 指定告警前后 30 分钟内的其他告警
SELECT id, ew_name, st_code, eq_code, ew_type, level_r, 
       value, create_time,
       TIMESTAMPDIFF(MINUTE, #{centerTime}, create_time) as time_diff
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(#{centerTime}, INTERVAL 30 MINUTE)
  AND create_time <= DATE_ADD(#{centerTime}, INTERVAL 30 MINUTE)
  AND id != #{alarmId}
ORDER BY ABS(TIMESTAMPDIFF(MINUTE, #{centerTime}, create_time))
```

### 空间关联查询

```sql
-- 同一测站的告警
SELECT id, ew_name, ew_type, level_r, value, create_time
FROM ew_info_message 
WHERE st_code = #{stCode} AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY create_time DESC

-- 同一水库的告警
SELECT id, ew_name, st_code, ew_type, level_r, value, create_time
FROM ew_info_message im
LEFT JOIN st_base sb ON im.st_code = sb.code
WHERE sb.project_id = #{projectId} AND im.deleted = 0
  AND im.create_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY im.create_time DESC
```

### 因果链检测

```sql
-- 检测降雨 → 水位 → 告警 因果链
SELECT 
  p.st_code as rain_station,
  p.p as rainfall,
  p.tm as rain_time,
  r.st_code as reservoir_station,
  r.rz as water_level,
  r.tm as level_time,
  im.id as alarm_id,
  im.ew_name as alarm_name,
  im.create_time as alarm_time
FROM st_pptn_r p
JOIN st_rsvr_r r ON r.tm >= p.tm AND r.tm <= DATE_ADD(p.tm, INTERVAL 6 HOUR)
JOIN ew_info_message im ON im.st_code = r.st_code 
  AND im.create_time >= r.tm AND im.create_time <= DATE_ADD(r.tm, INTERVAL 2 HOUR)
WHERE p.p > 10  -- 降雨量超过 10mm
  AND p.tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY p.tm DESC
```

## 关联图谱

```
降雨量 ↑ ─────→ 水位 ↑ ─────→ 超警戒
                  │
                  ├──→ 入库流量 ↑ ─→ 调度告警
                  │
                  └──→ 渗压 ↑ ────→ 大坝安全告警
```

## Agent 行为指引

当用户说"分析这组告警的关联关系"时：
1. 查询指定时间窗口内的所有告警
2. 按测站/水库分组
3. 按时间排序
4. 检测因果关系（时间先后 + 业务逻辑）
5. 生成关联图谱

当用户说"这个告警和降雨有关系吗？"时：
1. 查询告警触发时间前后的降雨数据
2. 计算降雨量与水位变化的相关性
3. 判断是否存在因果关系

当用户说"这个水库最近的告警规律是什么？"时：
1. 查询该水库最近 30 天的告警
2. 按类型、等级、时间分组统计
3. 检测周期性模式（如每天固定时间、每周固定天）
4. 生成规律分析报告
