# 恢复判断（智能体）

## 定位

本文件聚焦**智能体层**的恢复判断能力，不包含恢复检测的后端实现。

恢复检测（定时任务、数据准备）由应用层实现，见后端开发文档。

## 智能体能力

### 1. 恢复条件判断

当用户询问告警是否可以恢复时，智能体可以进行综合判断：

**触发场景：**
- 用户问"这条告警可以恢复了吗？"
- 用户问"检查告警恢复状态"

**分析过程：**
1. 查询告警详情（SQL）
2. 查询设备当前值（SQL）
3. 检查恢复条件（规则评估）
4. 检查关联告警（SQL）
5. 检查天气因素（SQL）
6. 综合判断

**示例输出：**
```
用户: "这条告警可以恢复了吗？"

智能体分析结果：

建议暂不恢复。原因：
1. 当前水位(460.5m)仍高于阈值(459.0m)
2. 关联的降雨告警仍在持续
3. 天气预报显示未来6小时仍有降雨
4. 历史数据显示水位下降需要12小时以上

建议操作：
1. 持续关注水位变化
2. 待水位降至458.5m以下再恢复
3. 恢复后继续监测24小时

是否继续等待或手动确认恢复？
```

### 2. 批量恢复检查

当需要检查所有活跃告警的恢复状态时，智能体可以批量分析：

**触发场景：**
- 用户说"检查所有活跃告警的恢复状态"
- 用户说"哪些告警可以恢复了？"

**分析过程：**
1. 查询所有活跃告警（SQL）
2. 批量获取设备当前值（SQL）
3. 逐条评估恢复条件
4. 分类统计
5. 生成报告

**示例输出：**
```
用户: "检查所有活跃告警的恢复状态"

智能体分析结果：

恢复状态检查报告

✅ 可恢复（3条）：
1. 水位告警-606K2155：当前值458.2m，阈值459.0m ✓
2. 降雨告警-606K2151：当前值0mm，阈值10mm ✓
3. 渗压告警-P001：当前值0.8MPa，阈值1.0MPa ✓

❌ 仍异常（5条）：
1. 水位告警-606K2154：当前值461.5m，阈值460.0m ✗
2. 降雨告警-606K2158：当前值15mm，阈值10mm ✗
...

⚠️ 数据缺失（2条）：
1. 设备离线：606K2152
2. 数据延迟：606K2156

建议：
1. 对可恢复告警执行恢复操作
2. 对仍异常告警继续监控
3. 对数据缺失告警进行人工确认

是否执行可恢复告警的恢复操作？
```

### 3. 恢复时机建议

当需要判断最佳恢复时机时，智能体可以提供建议：

**触发场景：**
- 用户问"什么时候可以恢复？"
- 用户问"恢复的最佳时机是什么？"

**分析过程：**
1. 查询告警历史趋势
2. 分析下降速率
3. 预测恢复时间
4. 考虑安全余量
5. 生成建议

**示例输出：**
```
用户: "什么时候可以恢复？"

智能体分析结果：

预计恢复时间分析：

当前状态：
- 水位：460.5m（阈值：459.0m）
- 下降速率：0.3m/小时
- 已持续：6小时

预测结果：
- 预计恢复时间：今晚22:00
- 置信度：85%

建议：
1. 设置自动恢复检测（每30分钟检查一次）
2. 恢复后继续监测24小时
3. 准备应急预案（如果水位再次上升）

是否设置自动恢复提醒？
```

### 4. 恢复后分析

当告警恢复后，智能体可以分析恢复原因：

**触发场景：**
- 用户问"这个告警是怎么恢复的？"
- 用户说"分析恢复原因"

**分析过程：**
1. 查询告警触发时的数据
2. 查询恢复时的数据
3. 对比分析变化
4. 总结恢复原因
5. 生成分析报告

**示例输出：**
```
用户: "这个告警是怎么恢复的？"

智能体分析结果：

告警恢复分析报告

告警信息：
- 名称：水位超限告警
- 触发时间：2026-06-03 10:00
- 恢复时间：2026-06-03 16:00
- 持续时间：6小时

数据对比：
- 触发时水位：461.96m
- 恢复时水位：458.20m
- 水位下降：3.76m

恢复原因：
1. 降雨停止（10:30停止降雨）
2. 持续泄洪（泄洪流量：50m³/s）
3. 入库流量减少（从380m³/s降至120m³/s）

经验总结：
1. 该类告警恢复时间约6-8小时
2. 降雨停止后2小时水位开始下降
3. 泄洪措施有效加速恢复

建议：
1. 记录本次恢复经验
2. 优化预测模型
3. 更新应急预案
```

## SQL 查询模板

### 查询告警详情

```sql
SELECT id, ew_name, ew_type, level_r, status, value, 
       gather_time, create_time, ew_rules_id, st_code, eq_code
FROM ew_info_message 
WHERE id = #{alarmId} AND deleted = 0
```

### 查询告警规则

```sql
SELECT id, name, ew_type, level_r, extend
FROM ew_info_rules
WHERE id = #{ruleId} AND deleted = 0
```

### 查询设备当前值

```sql
-- 水位
SELECT rz as current_value, tm as current_time
FROM st_rsvr_r WHERE st_id = #{stId} ORDER BY tm DESC LIMIT 1

-- 降雨
SELECT p as current_value, tm as current_time
FROM st_pptn_r WHERE st_id = #{stId} ORDER BY tm DESC LIMIT 1

-- 渗压
SELECT water_pressure as current_value, tm as current_time
FROM st_pressure_r WHERE st_id = #{stId} ORDER BY tm DESC LIMIT 1

-- 渗流
SELECT percolation as current_value, tm as current_time
FROM st_percolation_r WHERE st_id = #{stId} ORDER BY tm DESC LIMIT 1
```

### 查询告警历史趋势

```sql
SELECT rz, tm
FROM st_rsvr_r
WHERE st_id = #{stId}
  AND tm >= #{startTime}
  AND tm <= #{endTime}
ORDER BY tm ASC
```

### 查询关联告警

```sql
SELECT id, ew_name, ew_type, level_r, status, value, gather_time
FROM ew_info_message
WHERE st_code = #{stCode}
  AND status IN (0, 1, 2)
  AND deleted = 0
  AND tenant_id = #{tenantId}
ORDER BY gather_time DESC
```

### 查询天气信息

```sql
SELECT docid, docabstract, docpubtime, warn_status
FROM weather_warn
WHERE warn_status = 1
  AND docpubtime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY docpubtime DESC
```

### 查询恢复统计

```sql
SELECT 
  ew_type,
  COUNT(*) as total_recovered,
  AVG(TIMESTAMPDIFF(HOUR, gather_time, recovered_time)) as avg_recovery_hours
FROM ew_info_message
WHERE status = 4
  AND deleted = 0
  AND tenant_id = #{tenantId}
  AND recovered_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY ew_type
```

## 恢复条件评估

### 阈值条件

| 条件 | 恢复判断 |
|------|----------|
| `>=` | current_value < threshold |
| `<=` | current_value > threshold |
| `>` | current_value <= threshold |
| `<` | current_value >= threshold |
| `{}` (闭区间) | current_value < min OR current_value > max |
| `()` (开区间) | current_value <= min OR current_value >= max |

### 特殊情况

1. **设备离线**：不自动恢复，需人工确认
2. **数据缺失**：不自动恢复，等待数据恢复
3. **大坝告警**：需要所有测点都恢复正常
4. **关联告警**：关联告警未恢复时，建议暂不恢复

## Agent 行为指引

1. **恢复判断**：综合考虑阈值、趋势、关联告警、天气因素
2. **批量检查**：高效处理多个告警的恢复状态
3. **时机建议**：基于历史数据预测最佳恢复时间
4. **恢复分析**：总结恢复原因，积累经验
5. **安全余量**：建议设置安全余量（如阈值的5%）
