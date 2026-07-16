# 告警合并分析（智能体）

## 定位

本文件聚焦**智能体层**的告警合并分析能力。

告警合并的后端实现（Java Service + Redis）由应用层负责，见后端开发文档。

## 智能体能力

### 1. 合并状态查询

当用户询问告警的合并状态时，智能体可以查询并解释：

**触发场景：**
- 用户问"这条告警触发了多少次？"
- 用户问"这条告警是重复的吗？"

**示例输出：**
```
用户: "这条告警触发了多少次？"

智能体查询结果：

告警合并信息：
- 告警名称：水位超限告警
- 触发次数：156次
- 首次触发：2026-06-03 10:00:00
- 最后触发：2026-06-03 16:00:00
- 持续时间：6小时

触发频率：
- 平均每小时触发26次
- 最高频率：每分钟3次（10:00-10:05）

设备信息：
- 测站编码：606K2155
- 设备编码：606K215502
- 当前值：461.96m
- 阈值：460.00m

建议：
1. 该告警仍在持续，需要关注
2. 触发频率较高，建议检查设备
3. 已触发156次，建议尽快处理
```

### 2. 高频告警分析

当用户询问哪些告警触发最频繁时，智能体可以分析：

**触发场景：**
- 用户问"哪些告警触发最频繁？"
- 用户问"有没有频繁重复的告警？"

**示例输出：**
```
用户: "哪些告警触发最频繁？"

智能体分析结果：

高频告警TOP5：

1. 水位超限告警-606K2155
   - 触发次数：156次
   - 持续时间：6小时
   - 频率：26次/小时

2. 降雨超限告警-606K2151
   - 触发次数：89次
   - 持续时间：3小时
   - 频率：30次/小时

3. 渗压超限告警-P001
   - 触发次数：45次
   - 持续时间：2小时
   - 频率：22次/小时

4. 水位超限告警-606K2154
   - 触发次数：32次
   - 持续时间：1小时
   - 频率：32次/小时

5. 位移超限告警-D001
   - 触发次数：18次
   - 持续时间：30分钟
   - 频率：36次/小时

分析：
1. 水位告警触发最频繁，需要重点关注
2. 降雨告警频率高，与天气相关
3. 部分告警频率异常，建议检查设备

建议：
1. 优先处理水位告警
2. 检查高频告警设备
3. 优化告警阈值
```

### 3. 合并策略建议

当需要调整合并策略时，智能体可以提供建议：

**触发场景：**
- 用户问"合并时间窗口应该设多长？"
- 用户问"怎么减少重复告警？"

**示例输出：**
```
用户: "怎么减少重复告警？"

智能体分析结果：

减少重复告警建议：

1. 调整合并时间窗口
   - 当前设置：30分钟
   - 建议设置：10分钟
   - 理由：大多数告警在10分钟内会恢复

2. 优化告警阈值
   - 当前阈值：460.00m
   - 建议阈值：461.00m
   - 理由：减少边界波动触发的告警

3. 增加告警抑制
   - 风暴期间自动合并相同告警
   - 设置最大合并次数（如100次）

4. 设备检查
   - 部分设备告警频率异常
   - 建议检查设备状态

预期效果：
- 重复告警减少80%
- 数据库存储减少70%
- 通知发送减少90%

是否应用这些建议？
```

### 4. 告警风暴检测

当检测到告警风暴时，智能体可以分析并建议：

**触发场景：**
- 用户问"现在有告警风暴吗？"
- 用户说"检查告警风暴状态"

**示例输出：**
```
用户: "现在有告警风暴吗？"

智能体分析结果：

告警风暴状态：⚠️ 检测到风暴

风暴指标：
- 最近1分钟告警数：67条
- 最近1小时告警数：890条
- 风暴阈值：50条/分钟

风暴类型：水位告警风暴
影响范围：
- 测站：606K2155, 606K2154, 606K2153
- 设备：水位计
- 持续时间：15分钟

原因分析：
1. 强降雨导致水位快速上升
2. 多个测站同时超限
3. 设备采集频率过高

建议操作：
1. 启动风暴抑制模式
2. 合并相同告警
3. 通知防汛部门
4. 密切关注水位变化

是否启动风暴抑制？
```

## SQL 查询模板

### 查询告警合并信息

```sql
SELECT id, ew_name, st_code, eq_code, ew_type, level_r,
       aggregate_count, first_trigger_time, last_trigger_time,
       TIMESTAMPDIFF(MINUTE, first_trigger_time, last_trigger_time) as duration_minutes
FROM ew_info_message 
WHERE id = #{alarmId} AND deleted = 0
```

### 查询高频告警

```sql
SELECT id, ew_name, st_code, eq_code, level_r, 
       aggregate_count, first_trigger_time, last_trigger_time
FROM ew_info_message 
WHERE status IN (0, 1, 2) AND deleted = 0
  AND tenant_id = #{tenantId}
  AND aggregate_count > 10
ORDER BY aggregate_count DESC
LIMIT 20
```

### 查询告警触发频率

```sql
SELECT st_code, eq_code, ew_rules_id,
       COUNT(*) as total_count,
       AVG(aggregate_count) as avg_merge_count,
       MAX(aggregate_count) as max_merge_count
FROM ew_info_message
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY st_code, eq_code, ew_rules_id
HAVING COUNT(*) > 10
ORDER BY total_count DESC
```

### 查询告警风暴状态

```sql
SELECT 
  COUNT(*) as recent_count,
  SUM(CASE WHEN create_time >= DATE_SUB(NOW(), INTERVAL 1 MINUTE) THEN 1 ELSE 0 END) as last_minute,
  SUM(CASE WHEN create_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR) THEN 1 ELSE 0 END) as last_hour
FROM ew_info_message
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
```

### 查询重复告警分布

```sql
SELECT 
  st_code,
  ew_type,
  COUNT(*) as alarm_count,
  SUM(aggregate_count) as total_triggers,
  AVG(aggregate_count) as avg_triggers
FROM ew_info_message
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY st_code, ew_type
HAVING COUNT(*) > 5
ORDER BY total_triggers DESC
```

## Agent 行为指引

1. **合并查询**：查询告警的合并状态和触发次数
2. **频率分析**：分析告警触发频率，识别高频告警
3. **策略建议**：根据分析结果建议合并策略调整
4. **风暴检测**：检测告警风暴状态，提供应对建议
5. **优化建议**：提供减少重复告警的优化建议
