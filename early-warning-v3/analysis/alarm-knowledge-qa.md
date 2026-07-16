# 告警知识问答

## 功能

用户用自然语言提问告警相关问题，Agent 查询数据库、分析数据、用自然语言回答。

## 典型问题与查询

### 问题 1: "渗压计 P-001 最近一周的告警趋势？"

```sql
SELECT DATE(create_time) as date, 
       ew_type, level_r, COUNT(*) as count
FROM ew_info_message 
WHERE eq_code = 'EQ_P001' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY DATE(create_time), ew_type, level_r
ORDER BY date, level_r
```

Agent 回答：
> 渗压计 P-001 最近一周共触发 12 次告警，其中红色 2 次、橙色 5 次、黄色 5 次。
> 告警主要集中在 6 月 1 日和 6 月 3 日，与降雨时段吻合。
> 整体趋势：告警频率略有上升，建议关注。

### 问题 2: "这个水库现在有多少未处理的告警？"

```sql
SELECT ew_type, level_r, COUNT(*) as count
FROM ew_info_message im
LEFT JOIN st_base sb ON im.st_code = sb.code
WHERE sb.project_id = #{projectId} 
  AND im.status IN (0, 1, 2) AND im.deleted = 0
GROUP BY ew_type, level_r
ORDER BY level_r
```

Agent 回答：
> 张家嘴水库当前有 8 条未处理告警：
> - 红色 1 条（水位超限）
> - 橙色 3 条（2 条渗压、1 条渗流）
> - 黄色 4 条（降雨相关）
> 建议优先处理红色告警。

### 问题 3: "告警一般在什么时间发生？"

```sql
SELECT HOUR(create_time) as hour, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0 AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY HOUR(create_time)
ORDER BY count DESC
LIMIT 5
```

Agent 回答：
> 最近 30 天告警高峰时段：
> 1. 凌晨 2:00-3:00（夜间降雨集中）
> 2. 下午 14:00-15:00（午后气温升高）
> 3. 傍晚 18:00-19:00（日落前后水位变化）
> 建议在这些时段加强值班。

### 问题 4: "哪个设备告警最频繁？"

```sql
SELECT st_code, eq_code, ew_name, ew_type,
       COUNT(*) as total_count,
       COUNT(DISTINCT DATE(create_time)) as active_days,
       ROUND(COUNT(*) / COUNT(DISTINCT DATE(create_time)), 2) as avg_per_day
FROM ew_info_message 
WHERE deleted = 0 AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY st_code, eq_code, ew_name, ew_type
ORDER BY total_count DESC
LIMIT 10
```

Agent 回答：
> 最近 30 天高频告警设备：
> 1. 渗压计 P-003（主坝）：47 次，平均 1.6 次/天
> 2. 水位计 WL-001（坝前）：32 次，平均 1.1 次/天
> 3. 雨量计 RN-002（库区）：28 次，平均 0.9 次/天
> 渗压计 P-003 告警频率异常偏高，建议检查设备状态。

### 问题 5: "这个告警是什么原因？"

调用 `root-cause-analysis.md` 的分析流程。

### 问题 6: "历史上类似告警是怎么处理的？"

```sql
SELECT im.ew_name, im.ew_type, im.level_r, im.value,
       im.create_time, im.status, im.update_time,
       ae.action, ae.remark, ae.operator_name, ae.create_time as action_time
FROM ew_info_message im
LEFT JOIN ew_audit_log ae ON im.id = ae.alarm_id
WHERE im.ew_type = #{ewType} 
  AND im.deleted = 0
  AND im.status IN (3, 4)  -- 已处理或已恢复
ORDER BY im.update_time DESC
LIMIT 10
```

Agent 回答：
> 历史上类似告警（渗压超限）的处理方式：
> 1. 2026-05-28：确认后检查设备，发现传感器漂移，校准后恢复
> 2. 2026-05-15：确认后加强巡检，2 小时后自动恢复
> 3. 2026-05-03：确认后联系厂家，更换传感器
> 建议先检查设备状态，再决定是否需要更换。

## Agent 行为指引

当用户提问时：
1. 理解用户意图（查询什么数据、什么时间范围、什么维度）
2. 构造合适的 SQL 查询
3. 执行查询获取数据
4. 分析数据，提取关键信息
5. 用自然语言回答，避免只展示数字
6. 如果数据有异常，主动指出并给出建议

回答风格：
- 先给结论，再给数据支撑
- 用通俗语言解释专业数据
- 主动指出异常和趋势
- 给出可操作的建议
