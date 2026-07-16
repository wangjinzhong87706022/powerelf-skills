# 告警状态查询与建议（智能体）

## 定位

本文件聚焦**智能体层**的状态查询和操作建议能力。

状态机的后端实现（Java Service）由应用层负责，见后端开发文档。

## 状态定义

| 状态 | 代码 | 含义 | 可转换状态 |
|------|------|------|------------|
| TRIGGERED | 0 | 已触发 | CONFIRMED, IGNORED |
| CONFIRMED | 1 | 已确认 | ESCALATED, RESOLVED, IGNORED |
| ESCALATED | 2 | 已升级 | RESOLVED, RECOVERED |
| RESOLVED | 3 | 已处理 | RECOVERED |
| RECOVERED | 4 | 已恢复 | 终态 |
| IGNORED | 5 | 已忽略 | 终态 |

## 智能体能力

### 1. 状态查询与解释

当用户询问告警状态时，智能体可以查询并解释：

**触发场景：**
- 用户问"这条告警现在什么状态？"
- 用户问"告警状态是什么意思？"

**示例输出：**
```
用户: "这条告警现在什么状态？"

智能体查询结果：

告警状态：已触发（TRIGGERED）
告警名称：水位超限告警
告警级别：L1（红色）
触发时间：2026-06-03 10:00
已持续：6小时

状态说明：
- 已触发：告警刚产生，等待确认
- 下一步：可以确认（CONFIRMED）或忽略（IGNORED）

建议操作：
1. 确认告警，开始处理
2. 或忽略告警（如果是误报）

是否执行确认操作？
```

### 2. 操作建议

当用户询问如何操作告警时，智能体可以提供建议：

**触发场景：**
- 用户问"这条告警怎么处理？"
- 用户问"要不要确认这条告警？"

**示例输出：**
```
用户: "要不要确认这条告警？"

智能体分析结果：

建议暂不确认。原因：
1. 该告警触发于2小时前，水位仍在上升
2. 关联的降雨告警仍在持续
3. 天气预报显示未来3小时仍有强降雨
4. 历史数据显示类似情况下水位还会继续上涨

建议操作：
1. 持续关注水位变化
2. 准备应急预案
3. 待水位下降后再确认

如果确定要确认，请说明确认原因。
```

### 3. 状态转换建议

当用户询问应该进行什么操作时，智能体可以分析并建议：

**触发场景：**
- 用户问"现在应该做什么？"
- 用户问"下一步操作是什么？"

**示例输出：**
```
用户: "现在应该做什么？"

智能体分析结果：

当前有5条活跃告警，建议操作：

🔴 L1告警（2条）- 立即处理：
1. 水位超限告警-606K2155：建议确认并开始处理
2. 降雨超限告警-606K2151：建议确认并监控

🟡 L2告警（2条）- 尽快处理：
1. 渗压告警-P001：建议确认并检查设备
2. 位移告警-D001：建议确认并现场检查

🟢 L3告警（1条）- 适时处理：
1. 水质告警-W001：建议忽略（已知设备问题）

优先级建议：
1. 先处理L1告警，确保安全
2. L2告警可以稍后处理
3. L3告警可以批量忽略

是否执行批量确认？
```

### 4. 历史状态分析

当用户询问告警的历史状态时，智能体可以查询并分析：

**触发场景：**
- 用户问"这条告警的历史操作记录"
- 用户问"谁操作过这条告警？"

**示例输出：**
```
用户: "这条告警的历史操作记录"

智能体查询结果：

告警操作历史：

时间                    操作人    操作      状态变化
2026-06-03 10:00:00    系统      触发      → 已触发
2026-06-03 10:05:00    张三      确认      已触发 → 已确认
2026-06-03 12:00:00    系统      升级      已确认 → 已升级
2026-06-03 14:00:00    李四      处理      已升级 → 已处理
2026-06-03 16:00:00    系统      恢复      已处理 → 已恢复

处理效率：
- 确认响应：5分钟
- 处理响应：4小时
- 总持续时间：6小时

经验总结：
1. 该类告警平均处理时间4小时
2. 主要耗时在设备检查环节
3. 建议优化设备检查流程
```

## SQL 查询模板

### 查询告警当前状态

```sql
SELECT id, ew_name, ew_type, level_r, status, value, 
       gather_time, create_time, aggregate_count
FROM ew_info_message 
WHERE id = #{alarmId} AND deleted = 0
```

### 查询状态统计

```sql
SELECT status, COUNT(*) as count
FROM ew_info_message
WHERE deleted = 0 AND tenant_id = #{tenantId}
GROUP BY status
```

### 查询长时间未处理告警

```sql
SELECT id, ew_name, level_r, status, create_time,
       TIMESTAMPDIFF(HOUR, create_time, NOW()) as hours_pending
FROM ew_info_message
WHERE status IN ('TRIGGERED', 'CONFIRMED')
  AND deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time < DATE_SUB(NOW(), INTERVAL #{hours} HOUR)
ORDER BY level_r ASC, create_time ASC
```

### 查询告警操作历史

```sql
SELECT ae.id, ae.action, ae.operator_name, ae.remark,
       ae.old_status, ae.new_status, ae.create_time
FROM ew_audit_log ae
WHERE ae.alarm_id = #{alarmId}
ORDER BY ae.create_time DESC
```

### 查询操作人员统计

```sql
SELECT 
  ae.operator_name,
  COUNT(*) as total_operations,
  COUNT(CASE WHEN ae.action = 'CONFIRM' THEN 1 END) as confirm_count,
  COUNT(CASE WHEN ae.action = 'RESOLVE' THEN 1 END) as resolve_count
FROM ew_audit_log ae
WHERE ae.create_time >= #{startTime}
GROUP BY ae.operator_name
ORDER BY total_operations DESC
```

## Agent 行为指引

1. **状态查询**：查询并解释告警当前状态
2. **操作建议**：根据告警情况建议下一步操作
3. **状态转换**：分析应该进行什么状态转换
4. **历史分析**：查询并分析告警操作历史
5. **效率分析**：分析处理效率，提供改进建议
