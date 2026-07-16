# 告警风暴处理

## 定义

同一类型告警在 1 分钟内超过 50 条，判定为告警风暴。

## 检测（读 — 直连数据库）

### 检测当前是否处于告警风暴

```sql
-- 检查最近 1 分钟内每种 ew_type 的告警数
SELECT ew_type, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 1 MINUTE)
GROUP BY ew_type
HAVING COUNT(*) > 50
```

### 查询风暴期间的告警

```sql
SELECT id, ew_name, ew_type, level_r, st_code, eq_code, value, create_time
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND ew_type = #{ewType}
  AND create_time >= #{stormStartTime}
ORDER BY create_time DESC
```

### 统计风暴影响范围

```sql
SELECT 
  COUNT(*) as total_alarms,
  COUNT(DISTINCT st_code) as affected_stations,
  COUNT(DISTINCT eq_code) as affected_devices,
  MIN(level_r) as highest_level,
  MIN(create_time) as storm_start,
  MAX(create_time) as storm_end,
  TIMESTAMPDIFF(MINUTE, MIN(create_time), MAX(create_time)) as duration_minutes
FROM ew_info_message 
WHERE deleted = 0
  AND tenant_id = #{tenantId}
  AND ew_type = #{ewType}
  AND create_time >= #{stormStartTime}
```

## 处理策略

### 1. 检测阶段
- 统计最近 1 分钟内每种 ew_type 的告警数
- 如果超过阈值，标记为"告警风暴"

### 2. 抑制阶段
- 暂停逐条通知（通过通知策略的沉默期机制）
- 合并为一条"风暴告警"通知

### 3. 恢复阶段
- 风暴结束后（连续 5 分钟无新告警）
- 生成风暴汇总报告
- 发送汇总通知

## 风暴告警通知模板

```
⚠️ 告警风暴通知

类型：{ewTypeName} 预警
最近 1 分钟内触发 {count} 条告警
涉及 {stationCount} 个测站，{deviceCount} 个设备
最高等级：{maxLevelName}

系统已自动合并告警，风暴结束后将汇总通知。

[查看详情]
```

## 风暴汇总报告模板

```
📊 告警风暴汇总报告

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏱️ 风暴时间：{stormStart} ~ {stormEnd}
⏱️ 持续时间：{duration} 分钟

📈 告警统计
- 总告警数：{totalAlarms}
- 涉及测站：{stationCount} 个
- 涉及设备：{deviceCount} 个
- 最高等级：{maxLevelName}

📋 涉及设备
1. {device1}：{count1} 次
2. {device2}：{count2} 次
3. {device3}：{count3} 次
...

🔍 风暴原因分析
{stormCauseAnalysis}

💡 处理建议
{suggestion}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Agent 行为指引

当用户问"现在有告警风暴吗？"时：
1. 检测最近 1 分钟的告警数量
2. 如果超过阈值，告知用户正在发生告警风暴
3. 展示风暴的类型、数量、影响范围

当用户问"最近的告警风暴情况"时：
1. 查询最近 7 天的告警聚集事件
2. 统计每次风暴的持续时间和影响范围
3. 分析风暴原因
4. 生成风暴趋势报告

当用户说"抑制告警风暴"时：
1. 确认当前是否处于风暴状态
2. 如果是，建议启用通知沉默期
3. 调用 API 设置沉默期（如果需要）
4. 告知用户风暴期间的告警仍会记录，但不会逐条通知
