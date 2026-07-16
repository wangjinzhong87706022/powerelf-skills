# 模式识别

## 模式类型

### 1. 周期性模式

**识别方法：**
```sql
-- 按小时统计告警分布
SELECT
  HOUR(gather_time) as hour,
  COUNT(*) as count
FROM ew_info_message
WHERE deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY HOUR(gather_time)
ORDER BY hour;

-- 按星期统计告警分布
SELECT
  DAYOFWEEK(gather_time) as day_of_week,
  COUNT(*) as count
FROM ew_info_message
WHERE deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DAYOFWEEK(gather_time)
ORDER BY day_of_week;
```

**特征：**
- 固定时间重复出现
- 每天/每周/每月规律
- 可预测性强

### 2. 聚集性模式

**识别方法：**
```sql
-- 查询短时间大量告警
SELECT
  DATE(gather_time) as date,
  HOUR(gather_time) as hour,
  COUNT(*) as count
FROM ew_info_message
WHERE deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(gather_time), HOUR(gather_time)
HAVING COUNT(*) > 5
ORDER BY count DESC;
```

**特征：**
- 短时间内大量告警
- 可能是告警风暴
- 需要抑制处理

### 3. 级联模式

**识别方法：**
```sql
-- 查询同一时间段的多测站告警
SELECT
  DATE(gather_time) as date,
  HOUR(gather_time) as hour,
  COUNT(DISTINCT st_code) as station_count,
  COUNT(*) as alarm_count
FROM ew_info_message
WHERE deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(gather_time), HOUR(gather_time)
HAVING COUNT(DISTINCT st_code) > 1
ORDER BY station_count DESC;
```

**特征：**
- 一个告警触发其他告警
- 存在因果关系
- 需要根因分析

### 4. 异常模式

**识别方法：**
```sql
-- 查询告警值与阈值不匹配的告警
SELECT
  a.ew_name,
  a.st_code,
  a.value as alarm_value,
  b.extend as rule_extend
FROM ew_info_message a
JOIN ew_info_rules b ON a.ew_rules_id = b.id
WHERE a.deleted = 0
  AND a.value IS NOT NULL
LIMIT 20;
```

**特征：**
- 告警值与阈值不匹配
- 可能是规则配置错误
- 需要检查规则

## 模式分析报告模板

```
模式识别报告

1. 周期性模式
   - 发现: X点告警最多
   - 原因: XXX
   - 建议: XXX

2. 聚集性模式
   - 发现: X月X日X时爆发X条告警
   - 原因: XXX
   - 建议: XXX

3. 级联模式
   - 发现: X个测站同时告警
   - 原因: XXX
   - 建议: XXX

4. 异常模式
   - 发现: X条告警值与阈值不匹配
   - 原因: XXX
   - 建议: XXX
```
