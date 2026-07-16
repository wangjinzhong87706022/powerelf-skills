# 审计日志分析（智能体）

## 定位

本文件聚焦**智能体层**的审计日志分析能力。

审计日志的后端实现（AOP 切面 + 异步写入）由应用层负责，见后端开发文档。

## 智能体能力

### 1. 操作历史查询

当用户询问告警的操作历史时，智能体可以查询并分析：

**触发场景：**
- 用户问"这条告警的操作历史"
- 用户问"谁操作过这条告警？"

**示例输出：**
```
用户: "这条告警的操作历史"

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

操作统计：
- 系统操作：3次（触发、升级、恢复）
- 人工操作：2次（确认、处理）

经验总结：
1. 该类告警平均处理时间4小时
2. 主要耗时在设备检查环节
3. 建议优化设备检查流程
```

### 2. 处理效率分析

当用户询问告警处理效率时，智能体可以分析：

**触发场景：**
- 用户问"告警的平均响应时间是多少？"
- 用户问"处理效率怎么样？"

**示例输出：**
```
用户: "告警的平均响应时间是多少？"

智能体分析结果：

告警处理效率分析（最近30天）：

📊 总体统计：
- 总告警数：156条
- 平均确认时间：45分钟
- 平均处理时间：2.5小时
- 处理率：92%

📈 按等级分析：
- L1(红色)：平均确认15分钟，处理1小时
- L2(橙色)：平均确认30分钟，处理2小时
- L3(黄色)：平均确认1小时，处理4小时
- L4(蓝色)：平均确认2小时，处理8小时

📉 趋势分析：
- 本周处理效率提升15%
- L1告警响应时间缩短20%
- 主要瓶颈：设备维修等待时间

建议：
1. 优化设备维修流程
2. 增加备件库存
3. 加强值班人员培训
```

### 3. 操作人员绩效

当用户询问操作人员绩效时，智能体可以分析：

**触发场景：**
- 用户问"谁处理的告警最多？"
- 用户问"操作人员绩效怎么样？"

**示例输出：**
```
用户: "谁处理的告警最多？"

智能体分析结果：

操作人员绩效排名（最近30天）：

🥇 张三：处理告警45条，平均响应时间30分钟
🥈 李四：处理告警38条，平均响应时间45分钟
🥉 王五：处理告警32条，平均响应时间1小时

📊 工作量分布：
- 张三：L1告警12条，L2告警18条，L3告警15条
- 李四：L1告警8条，L2告警15条，L3告警15条
- 王五：L1告警5条，L2告警12条，L3告警15条

💡 洞察：
- 张三处理效率最高，适合处理紧急告警
- 李四工作量最均衡
- 王五处理时间较长，建议加强培训

建议：
1. 张三负责L1告警处理
2. 李四负责L2告警处理
3. 王五负责L3告警处理
4. 定期组织培训，提升整体效率
```

### 4. 操作模式分析

当需要分析操作模式时，智能体可以识别规律：

**触发场景：**
- 用户问"有没有操作规律？"
- 用户问"什么时候操作最频繁？"

**示例输出：**
```
用户: "什么时候操作最频繁？"

智能体分析结果：

操作时间分布（最近30天）：

📊 按小时分布：
- 08:00-10:00：操作最频繁（占35%）
- 14:00-16:00：次频繁（占25%）
- 22:00-06:00：操作最少（占10%）

📅 按星期分布：
- 周一：操作最多（占20%）
- 周五：操作次多（占18%）
- 周末：操作较少（占12%）

💡 洞察：
- 上午是操作高峰期
- 周一需要特别关注
- 夜间操作较少，建议加强值班

建议：
1. 上午增加值班人员
2. 周一安排专人负责
3. 夜间设置自动告警处理
4. 优化操作流程，减少处理时间
```

### 5. 异常操作检测

当需要检测异常操作时，智能体可以识别：

**触发场景：**
- 用户问"有没有异常操作？"
- 用户说"检查操作异常"

**示例输出：**
```
用户: "有没有异常操作？"

智能体分析结果：

异常操作检测（最近7天）：

⚠️ 发现3个异常：

1. 批量忽略操作
   - 操作人：王五
   - 时间：2026-06-02 23:00
   - 操作：批量忽略15条告警
   - 原因：未填写
   - 风险：高

2. 快速连续操作
   - 操作人：李四
   - 时间：2026-06-01 10:00
   - 操作：1分钟内确认10条告警
   - 原因：可能误操作
   - 风险：中

3. 深夜操作
   - 操作人：张三
   - 时间：2026-06-03 02:00
   - 操作：处理L1告警
   - 原因：正常值班
   - 风险：低

建议：
1. 调查批量忽略操作原因
2. 优化批量操作确认流程
3. 加强深夜值班管理
4. 添加操作风险提示
```

## SQL 查询模板

### 查询告警操作历史

```sql
SELECT ae.id, ae.action, ae.operator_name, ae.remark,
       ae.old_status, ae.new_status, ae.create_time
FROM ew_audit_log ae
WHERE ae.alarm_id = #{alarmId}
ORDER BY ae.create_time DESC
```

### 查询用户操作记录

```sql
SELECT ae.id, ae.alarm_id, ae.action, ae.remark, ae.create_time,
       im.ew_name, im.level_r
FROM ew_audit_log ae
LEFT JOIN ew_info_message im ON ae.alarm_id = im.id
WHERE ae.operator_id = #{userId}
  AND ae.create_time >= #{startTime}
ORDER BY ae.create_time DESC
LIMIT #{limit}
```

### 查询操作类型统计

```sql
SELECT action, COUNT(*) as count
FROM ew_audit_log 
WHERE create_time >= #{startTime}
GROUP BY action
ORDER BY count DESC
```

### 查询告警处理效率

```sql
SELECT 
  im.id,
  im.ew_name,
  im.level_r,
  im.create_time as trigger_time,
  MAX(CASE WHEN ae.action = 'CONFIRM' THEN ae.create_time END) as confirm_time,
  MAX(CASE WHEN ae.action = 'RESOLVE' THEN ae.create_time END) as resolve_time,
  TIMESTAMPDIFF(MINUTE, im.create_time, 
    MAX(CASE WHEN ae.action = 'CONFIRM' THEN ae.create_time END)) as minutes_to_confirm,
  TIMESTAMPDIFF(MINUTE, im.create_time, 
    MAX(CASE WHEN ae.action = 'RESOLVE' THEN ae.create_time END)) as minutes_to_resolve
FROM ew_info_message im
LEFT JOIN ew_audit_log ae ON im.id = ae.alarm_id
WHERE im.deleted = 0
  AND im.create_time >= #{startTime}
GROUP BY im.id, im.ew_name, im.level_r, im.create_time
ORDER BY im.create_time DESC
```

### 查询操作人员绩效

```sql
SELECT 
  ae.operator_id,
  ae.operator_name,
  COUNT(*) as total_operations,
  COUNT(CASE WHEN ae.action = 'CONFIRM' THEN 1 END) as confirm_count,
  COUNT(CASE WHEN ae.action = 'RESOLVE' THEN 1 END) as resolve_count,
  AVG(CASE WHEN ae.action = 'CONFIRM' 
      THEN TIMESTAMPDIFF(MINUTE, im.create_time, ae.create_time) END) as avg_confirm_minutes,
  AVG(CASE WHEN ae.action = 'RESOLVE' 
      THEN TIMESTAMPDIFF(MINUTE, im.create_time, ae.create_time) END) as avg_resolve_minutes
FROM ew_audit_log ae
LEFT JOIN ew_info_message im ON ae.alarm_id = im.id
WHERE ae.create_time >= #{startTime}
GROUP BY ae.operator_id, ae.operator_name
ORDER BY total_operations DESC
```

### 查询操作时间分布

```sql
SELECT 
  HOUR(create_time) as hour,
  COUNT(*) as operation_count
FROM ew_audit_log
WHERE create_time >= #{startTime}
GROUP BY HOUR(create_time)
ORDER BY hour
```

### 查询异常操作

```sql
SELECT 
  ae.operator_name,
  ae.action,
  COUNT(*) as operation_count,
  MIN(ae.create_time) as first_time,
  MAX(ae.create_time) as last_time
FROM ew_audit_log ae
WHERE ae.create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY ae.operator_name, ae.action, DATE(ae.create_time), HOUR(ae.create_time)
HAVING COUNT(*) > 10
ORDER BY operation_count DESC
```

## Agent 行为指引

1. **历史查询**：查询并分析告警操作历史
2. **效率分析**：分析处理效率，提供改进建议
3. **绩效评估**：评估操作人员绩效，提供排名
4. **模式识别**：识别操作模式和规律
5. **异常检测**：检测异常操作，提供风险提示
