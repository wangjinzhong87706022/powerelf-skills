# 告警升级建议（智能体）

## 定位

本文件聚焦**智能体层**的升级决策建议能力，不包含升级检测的后端实现。

升级检测（定时任务）由应用层实现，见后端开发文档。

## 智能体能力

### 1. 升级决策建议

当用户询问是否应该升级告警时，智能体可以分析并给出建议：

**触发场景：**
- 用户问"这条告警要不要手动升级？"
- 用户问"什么时候应该升级？"
- 用户问"升级到谁？"

**分析过程：**
1. 查询告警详情（SQL）
2. 检查告警历史（SQL）
3. 检查关联告警（SQL）
4. 分析处理难度
5. 生成建议

**示例输出：**
```
用户: "这条告警要不要手动升级？"

智能体分析结果：

建议手动升级。原因：
1. 该告警已持续3小时，接近自动升级阈值
2. 当前值班人员处理经验不足
3. 涉及设备较多，需要协调
4. 历史数据显示类似告警平均处理时间4小时

建议操作：
1. 立即升级到部门负责人
2. 通知设备维护团队
3. 准备应急预案

是否执行升级？
```

### 2. 升级通知模板生成

当需要发送升级通知时，智能体可以生成合适的模板：

**触发场景：**
- 用户说"升级通知怎么写？"
- 用户说"生成升级通知"

**分析过程：**
1. 查询告警类型和级别
2. 分析升级原因
3. 确定通知对象
4. 生成通知模板

**示例输出：**
```
用户: "升级通知怎么写？"

智能生的升级通知模板：

⚠️ 告警升级通知

原告警：水位超限告警
类型：水位预警
等级：L1(红色) → L2(橙色)
水库：张家咀水库
测点：606K2155-3B
当前值：461.96m
已持续：3小时
升级原因：超时未处理
本次为第1次升级

请立即处理！

[立即处理] [查看详情]
```

### 3. 升级策略分析

当需要制定升级策略时，智能体可以提供建议：

**触发场景：**
- 用户问"升级时间应该设多长？"
- 用户问"升级通知对象怎么配置？"

**分析过程：**
1. 分析历史告警数据
2. 计算平均处理时间
3. 评估人员配置
4. 生成策略建议

**示例输出：**
```
用户: "升级时间应该设多长？"

智能体分析结果：

建议升级时间配置：

| 告警等级 | 首次升级 | 二次升级 | 三次升级 |
|----------|----------|----------|----------|
| L1 (红) | 2小时 | 4小时 | 8小时 |
| L2 (橙) | 4小时 | 8小时 | 24小时 |
| L3 (黄) | 8小时 | 24小时 | 48小时 |
| L4 (蓝) | 24小时 | 48小时 | 不升级 |

理由：
1. 基于最近30天的告警处理数据分析
2. L1告警平均处理时间为1.5小时，设置2小时升级阈值
3. L2告警平均处理时间为3小时，设置4小时升级阈值
4. 留出足够的处理时间，避免不必要的升级

通知对象建议：
- 首次升级：值班负责人
- 二次升级：部门负责人
- 三次升级：分管领导
```

## SQL 查询模板

### 查询告警详情

```sql
SELECT id, ew_name, ew_type, level_r, status, 
       create_time, escalate_count,
       TIMESTAMPDIFF(MINUTE, create_time, NOW()) as duration_minutes,
       st_code, eq_code, value
FROM ew_info_message 
WHERE id = #{alarmId} AND deleted = 0
```

### 查询升级历史

```sql
SELECT ae.id, ae.alarm_id, ae.action, ae.old_level, ae.new_level, 
       ae.operator_name, ae.create_time, ae.remark,
       im.ew_name, im.level_r
FROM ew_audit_log ae
LEFT JOIN ew_info_message im ON ae.alarm_id = im.id
WHERE ae.action = 'ESCALATE'
  AND ae.create_time >= #{startTime}
ORDER BY ae.create_time DESC
```

### 查询升级统计

```sql
SELECT 
  COUNT(*) as total_escalations,
  COUNT(DISTINCT alarm_id) as unique_alarms,
  AVG(escalation_count) as avg_escalation_count
FROM ew_info_message
WHERE escalation_count > 0
  AND deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
```

### 查询平均处理时间

```sql
SELECT 
  level_r,
  AVG(TIMESTAMPDIFF(HOUR, create_time, update_time)) as avg_hours,
  COUNT(*) as count
FROM ew_info_message
WHERE status IN (3, 4, 5)  -- 已处理/已恢复/已忽略
  AND deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY level_r
ORDER BY level_r
```

## Agent 行为指引

1. **升级决策**：分析告警详情、历史数据、关联告警，给出是否升级的建议
2. **通知模板**：根据告警类型和级别，生成合适的升级通知
3. **策略分析**：基于历史数据，建议升级时间配置
4. **升级对象**：根据升级次数，建议通知对象
