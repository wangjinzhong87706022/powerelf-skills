# 告警报告生成

## 功能

Agent 查询告警统计数据，生成日报/周报/月报。比固定模板更灵活，支持自然语言定制。

## 报告类型

### 日报

```sql
-- 今日告警统计
SELECT 
  COUNT(*) as total_count,
  SUM(CASE WHEN level_r = '1' THEN 1 ELSE 0 END) as level1_count,
  SUM(CASE WHEN level_r = '2' THEN 1 ELSE 0 END) as level2_count,
  SUM(CASE WHEN level_r = '3' THEN 1 ELSE 0 END) as level3_count,
  SUM(CASE WHEN level_r = '4' THEN 1 ELSE 0 END) as level4_count,
  SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) as triggered_count,
  SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as confirmed_count,
  SUM(CASE WHEN status = 3 THEN 1 ELSE 0 END) as resolved_count,
  SUM(CASE WHEN status = 4 THEN 1 ELSE 0 END) as recovered_count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND DATE(create_time) = CURDATE()
```

```sql
-- 今日告警按类型分布
SELECT ew_type, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND DATE(create_time) = CURDATE()
GROUP BY ew_type
ORDER BY count DESC
```

```sql
-- 今日告警按小时分布
SELECT HOUR(create_time) as hour, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND DATE(create_time) = CURDATE()
GROUP BY HOUR(create_time)
ORDER BY hour
```

```sql-- 今日 Top 10 高频告警设备
SELECT st_code, eq_code, ew_name, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND DATE(create_time) = CURDATE()
GROUP BY st_code, eq_code, ew_name
ORDER BY count DESC
LIMIT 10
```

### 周报

```sql
-- 本周每日告警趋势
SELECT DATE(create_time) as date, 
       COUNT(*) as total,
       SUM(CASE WHEN level_r = '1' THEN 1 ELSE 0 END) as level1,
       SUM(CASE WHEN level_r = '2' THEN 1 ELSE 0 END) as level2,
       SUM(CASE WHEN level_r = '3' THEN 1 ELSE 0 END) as level3,
       SUM(CASE WHEN level_r = '4' THEN 1 ELSE 0 END) as level4
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(create_time)
ORDER BY date
```

```sql
-- 本周告警处理效率
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN status IN (3, 4) THEN 1 ELSE 0 END) as handled,
  ROUND(SUM(CASE WHEN status IN (3, 4) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as handle_rate,
  AVG(CASE WHEN status = 3 THEN TIMESTAMPDIFF(MINUTE, create_time, update_time) END) as avg_resolve_minutes,
  AVG(CASE WHEN status = 4 THEN TIMESTAMPDIFF(MINUTE, create_time, update_time) END) as avg_recover_minutes
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
```

```sql
-- 本周与上周对比
SELECT 
  '本周' as period,
  COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0 AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
UNION ALL
SELECT 
  '上周' as period,
  COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0 AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
  AND create_time < DATE_SUB(CURDATE(), INTERVAL 7 DAY)
```

### 月报

```sql
-- 本月每周告警趋势
SELECT 
  YEARWEEK(create_time, 1) as week,
  MIN(DATE(create_time)) as week_start,
  COUNT(*) as total,
  SUM(CASE WHEN level_r = '1' THEN 1 ELSE 0 END) as level1,
  SUM(CASE WHEN level_r = '2' THEN 1 ELSE 0 END) as level2
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY YEARWEEK(create_time, 1)
ORDER BY week
```

```sql
-- 本月告警类型分布
SELECT ew_type, COUNT(*) as count,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ew_info_message 
         WHERE deleted = 0 AND tenant_id = #{tenantId}
         AND create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)), 1) as percentage
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY ew_type
ORDER BY count DESC
```

```sql
-- 本月告警等级分布
SELECT level_r, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY level_r
ORDER BY level_r
```

## 报告模板

### 日报模板

```
📊 告警日报
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 日期：{date}
📊 总告警数：{totalCount}

📈 等级分布
🔴 红色 (L1)：{level1} 条
🟠 橙色 (L2)：{level2} 条
🟡 黄色 (L3)：{level3} 条
🔵 蓝色 (L4)：{level4} 条

📋 状态分布
- 待处理：{triggered} 条
- 已确认：{confirmed} 条
- 已处理：{resolved} 条
- 已恢复：{recovered} 条

⏰ 高峰时段
{peakHour}:00 — {peakCount} 条告警

🏭 高频设备
1. {device1}：{count1} 次
2. {device2}：{count2} 次
3. {device3}：{count3} 次

📊 按类型
{typeDistribution}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 周报模板

```
📊 告警周报
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 周期：{startDate} ~ {endDate}
📊 总告警数：{totalCount}

📈 每日趋势
{dailyTrendTable}

📊 与上周对比
- 本周：{thisWeek} 条
- 上周：{lastWeek} 条
- 变化：{change} ({changePercent}%)

⏱️ 处理效率
- 处理率：{handleRate}%
- 平均处理时间：{avgResolveMinutes} 分钟
- 平均恢复时间：{avgRecoverMinutes} 分钟

📋 类型分布
{typeDistribution}

⚠️ 重点关注
{focusItems}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Agent 行为指引

当用户说"生成今天的告警日报"时：
1. 执行日报 SQL 查询
2. 填充报告模板
3. 展示给用户

当用户说"生成上周的告警周报"时：
1. 执行周报 SQL 查询
2. 计算与上上周的对比
3. 填充报告模板
4. 展示给用户

当用户说"生成 5 月份的告警月报"时：
1. 执行月报 SQL 查询
2. 按周分组展示趋势
3. 分析告警类型和等级分布
4. 填充报告模板
5. 展示给用户

当用户说"把报告导出为文件"时：
1. 生成报告内容
2. 保存为 Markdown 文件
3. 告知用户文件路径
