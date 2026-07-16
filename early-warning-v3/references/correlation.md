# 关联分析

## 关联维度

### 1. 同测站关联

同一测站的告警可能存在关联：

```sql
SELECT id, ew_name, level_r, value, gather_time
FROM ew_info_message
WHERE st_code = '606K2155' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY gather_time DESC;
```

### 2. 同类型关联

同类型告警可能存在规律：

```sql
SELECT id, ew_name, st_code, level_r, value, gather_time
FROM ew_info_message
WHERE ew_name LIKE '%水位%' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY gather_time DESC;
```

### 3. 同级别关联

同级别告警需要同等重视：

```sql
SELECT id, ew_name, st_code, value, gather_time
FROM ew_info_message
WHERE level_r = '1' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY gather_time DESC;
```

### 4. 时间关联

同一时间段的告警可能存在因果关系：

```sql
SELECT id, ew_name, st_code, level_r, gather_time
FROM ew_info_message
WHERE DATE(gather_time) = '2026-06-01' AND deleted = 0
ORDER BY gather_time;
```

## 因果链分析

### 典型因果链

```
强降雨 → 水位上升 → 水位告警 → 渗流增加 → 渗流告警
```

### 查询因果链

```sql
-- 查询某天的告警序列
SELECT ew_name, st_code, level_r, gather_time
FROM ew_info_message
WHERE DATE(gather_time) = '2026-06-01' AND deleted = 0
ORDER BY gather_time;

-- 分析降雨与水位的关系
SELECT
  DATE(a.gather_time) as date,
  COUNT(DISTINCT a.id) as alarm_count,
  SUM(b.p) as total_rainfall
FROM ew_info_message a
LEFT JOIN st_pptn_r b ON DATE(a.gather_time) = DATE(b.tm)
WHERE a.deleted = 0
  AND a.create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(a.gather_time)
ORDER BY date;
```

## 关联分析报告模板

```
关联分析报告

1. 告警概况
   - 总告警数: X条
   - 涉及测站: X个
   - 时间范围: YYYY-MM-DD ~ YYYY-MM-DD

2. 关联发现
   - 同测站关联: 测站XXX有X条关联告警
   - 同类型关联: 水位类告警X条，雨量类X条
   - 时间关联: X月X日X时集中爆发X条告警

3. 因果分析
   - 主要原因: XXX
   - 影响范围: XXX
   - 处理建议: XXX
```
