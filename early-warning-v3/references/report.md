# 报告生成

## 报告类型

### 1. 日报

```sql
-- 今日告警统计
SELECT
  level_r as level,
  COUNT(*) as count
FROM ew_info_message
WHERE DATE(gather_time) = CURDATE() AND deleted = 0
GROUP BY level_r
ORDER BY level_r;

-- 今日告警详情
SELECT id, ew_name, st_code, level_r, value, gather_time
FROM ew_info_message
WHERE DATE(gather_time) = CURDATE() AND deleted = 0
ORDER BY gather_time DESC;
```

### 2. 周报

```sql
-- 本周告警统计
SELECT
  DATE(gather_time) as date,
  COUNT(*) as count
FROM ew_info_message
WHERE gather_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND deleted = 0
GROUP BY DATE(gather_time)
ORDER BY date;

-- 本周告警趋势
SELECT
  level_r as level,
  COUNT(*) as count
FROM ew_info_message
WHERE gather_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND deleted = 0
GROUP BY level_r
ORDER BY level_r;
```

### 3. 月报

```sql
-- 本月告警统计
SELECT
  DATE_FORMAT(gather_time, '%Y-%m-%d') as date,
  COUNT(*) as count
FROM ew_info_message
WHERE gather_time >= DATE_FORMAT(CURDATE(), '%Y-%m-01') AND deleted = 0
GROUP BY DATE_FORMAT(gather_time, '%Y-%m-%d')
ORDER BY date;

-- 本月测站排名
SELECT st_code, COUNT(*) as count
FROM ew_info_message
WHERE gather_time >= DATE_FORMAT(CURDATE(), '%Y-%m-01') AND deleted = 0
GROUP BY st_code
ORDER BY count DESC
LIMIT 10;
```

### 4. 测站报告

```sql
-- 测站告警统计
SELECT
  ew_name as type,
  COUNT(*) as count
FROM ew_info_message
WHERE st_code = '606K2158' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY ew_name
ORDER BY count DESC;

-- 测站告警趋势
SELECT
  DATE(gather_time) as date,
  COUNT(*) as count
FROM ew_info_message
WHERE st_code = '606K2158' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(gather_time)
ORDER BY date;
```

## 报告模板

### 日报模板

```
告警日报

日期: YYYY-MM-DD

1. 告警概况
   - 今日告警总数: X条
   - 一级(红色): X条
   - 二级(橙色): X条
   - 三级(黄色): X条
   - 四级(蓝色): X条

2. 主要告警
   - XXX告警: X条
   - XXX告警: X条

3. 处理情况
   - 已确认: X条
   - 未确认: X条
   - 确认率: XX%

4. 建议
   - XXX
```

### 周报模板

```
告警周报

周期: YYYY-MM-DD ~ YYYY-MM-DD

1. 告警趋势
   - 本周告警: X条
   - 上周告警: X条
   - 变化: +/-XX%

2. 测站排名
   1. XXX: X条
   2. XXX: X条
   3. XXX: X条

3. 处理效率
   - 平均确认时间: XX分钟
   - 确认率: XX%

4. 问题分析
   - XXX

5. 改进建议
   - XXX
```
