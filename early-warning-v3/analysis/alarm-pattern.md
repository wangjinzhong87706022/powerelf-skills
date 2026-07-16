# 告警模式识别

## 模式类型

### 1. 周期性模式
告警在固定时间间隔重复出现。

### 2. 聚集性模式
告警在短时间内集中爆发。

### 3. 级联模式
一个告警触发后，相关设备陆续告警。

### 4. 季节性模式
告警与季节/月份相关。

## 查询历史告警（读 — 直连数据库）

### 按小时统计告警分布

```sql
SELECT HOUR(create_time) as hour, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY HOUR(create_time)
ORDER BY hour
```

### 按星期统计告警分布

```sql
SELECT DAYOFWEEK(create_time) as day_of_week, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 90 DAY)
GROUP BY DAYOFWEEK(create_time)
ORDER BY day_of_week
```

### 按设备统计告警频率

```sql
SELECT st_code, eq_code, ew_name,
       COUNT(*) as total_count,
       COUNT(DISTINCT DATE(create_time)) as active_days,
       ROUND(COUNT(*) / COUNT(DISTINCT DATE(create_time)), 2) as avg_per_day,
       MIN(create_time) as first_alarm,
       MAX(create_time) as last_alarm
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY st_code, eq_code, ew_name
HAVING COUNT(*) > 5
ORDER BY total_count DESC
```

### 检测级联告警

```sql
-- 检测同一时间窗口内的多设备告警（级联模式）
SELECT 
  DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:00') as time_window,
  COUNT(DISTINCT st_code) as station_count,
  COUNT(*) as alarm_count,
  GROUP_CONCAT(DISTINCT st_code) as stations
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:00')
HAVING COUNT(DISTINCT st_code) > 1
ORDER BY time_window DESC
```

### 检测告警聚集

```sql
-- 检测告警聚集（5分钟内超过 10 条）
SELECT 
  DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:00') as time_window,
  COUNT(*) as alarm_count,
  COUNT(DISTINCT ew_type) as type_count,
  GROUP_CONCAT(DISTINCT ew_type) as types
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:00')
HAVING COUNT(*) > 10
ORDER BY alarm_count DESC
```

## 模式分析报告

```
📊 告警模式分析报告

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 分析时间范围：{startTime} ~ {endTime}
📊 总告警数：{totalCount}

⏰ 时间分布
- 高峰时段：{peakHour}:00（{peakCount} 条）
- 低谷时段：{lowHour}:00（{lowCount} 条）
- 工作日/周末比：{weekdayRatio}

🔄 周期性检测
- {periodicPattern}

📈 聚集性检测
- 最近 24 小时聚集事件：{burstCount} 次
- 最大聚集：{maxBurst} 条/分钟

🔗 级联检测
- 级联事件：{cascadeCount} 次
- 涉及最多设备：{maxCascade} 个

🏭 高频设备
1. {device1}：{count1} 次（{avgPerDay1} 次/天）
2. {device2}：{count2} 次（{avgPerDay2} 次/天）
3. {device3}：{count3} 次（{avgPerDay3} 次/天）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Agent 行为指引

当用户问"最近的告警有什么规律？"时：
1. 查询最近 30 天的告警统计
2. 分析时间分布、设备分布
3. 检测周期性、聚集性、级联模式
4. 生成模式分析报告

当用户问"哪个设备告警最频繁？"时：
1. 按设备统计告警频率
2. 计算平均每天告警次数
3. 展示 Top 10 高频设备

当用户问"告警一般在什么时间发生？"时：
1. 按小时统计告警分布
2. 识别高峰和低谷时段
3. 分析工作日/周末差异
