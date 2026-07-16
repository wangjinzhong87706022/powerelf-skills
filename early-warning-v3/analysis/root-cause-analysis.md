# 根因分析

## 分析流程

当用户请求"分析这条告警"时，Agent 执行以下步骤：

### Step 1: 获取告警上下文（读 — 直连数据库）

```sql
-- 告警详情
SELECT im.id, im.ew_name, im.st_code, im.eq_code, im.ew_type, 
       im.level_r, im.value, im.gather_time, im.content,
       im.ew_rules_info, im.dam_id, im.section_id,
       im.create_time, im.status, im.aggregate_count
FROM ew_info_message im
WHERE im.id = #{alarmId} AND im.deleted = 0

-- 关联规则
SELECT er.id, er.name, er.type, er.ew_type, er.level_r, 
       er.extend, er.status, er.dot_address
FROM ew_info_rules er
WHERE er.id = #{ewRulesId} AND er.deleted = 0
```

### Step 2: 查询设备历史数据（读 — 直连数据库）

```sql
-- 最近 24 小时水位数据
SELECT rz as value, tm as time
FROM st_rsvr_r 
WHERE st_id = #{stId} 
  AND tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY tm ASC

-- 最近 24 小时降雨数据
SELECT p as value, tm as time, dr as duration
FROM st_pptn_r 
WHERE st_id = #{stId}
  AND tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY tm ASC

-- 最近 24 小时渗压数据
SELECT water_pressure as value, tm as time
FROM st_pressure_r 
WHERE st_id = #{stId}
  AND tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY tm ASC

-- 最近 24 小时渗流数据
SELECT percolation as value, tm as time
FROM st_percolation_r 
WHERE st_id = #{stId}
  AND tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY tm ASC
```

### Step 3: 查询关联告警（读 — 直连数据库）

```sql
-- 同一测站的其他告警
SELECT id, ew_name, ew_type, level_r, value, create_time
FROM ew_info_message 
WHERE st_code = #{stCode} 
  AND status IN (0, 1, 2) AND deleted = 0
  AND id != #{alarmId}
  AND create_time >= DATE_SUB(#{gatherTime}, INTERVAL 1 HOUR)
  AND create_time <= DATE_ADD(#{gatherTime}, INTERVAL 1 HOUR)
ORDER BY create_time DESC

-- 同一水库的其他告警
SELECT id, ew_name, ew_type, level_r, value, create_time, st_code
FROM ew_info_message 
WHERE tenant_id = #{tenantId}
  AND status IN (0, 1, 2) AND deleted = 0
  AND id != #{alarmId}
  AND create_time >= DATE_SUB(#{gatherTime}, INTERVAL 1 HOUR)
  AND create_time <= DATE_ADD(#{gatherTime}, INTERVAL 1 HOUR)
ORDER BY create_time DESC
```

### Step 4: 查询天气数据（读 — 直连数据库）

```sql
-- 最近的天气预警
SELECT docid, docabstract, docpubtime
FROM weather_warn 
WHERE docpubtime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY docpubtime DESC

-- 最近的降雨预报
SELECT tm, drp, intv
FROM f_rnfl_h 
WHERE tm >= NOW()
ORDER BY tm ASC
LIMIT 24
```

### Step 5: 趋势分析

根据历史数据计算：
1. **变化趋势**：最近 N 小时是上升/下降/平稳
2. **变化速率**：每小时变化量
3. **与阈值的距离**：当前值离阈值还有多远
4. **历史极值**：最近 24 小时的最大/最小值

### Step 6: 生成诊断报告

```
📊 告警诊断报告

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 告警信息
- 告警名称：{ewName}
- 告警等级：{levelName} ({level})
- 告警类型：{ewTypeName}
- 触发时间：{gatherTime}
- 当前状态：{statusName}
- 已持续：{duration}

📍 设备信息
- 测站：{stName} ({stCode})
- 设备：{eqName} ({eqCode})
- 水库：{projectName}

📈 趋势分析
- 最近 24 小时变化趋势：{trend}（上升 ↑ / 下降 ↓ / 平稳 →）
- 变化速率：{rate} {unit}/小时
- 当前值：{currentValue} {unit}
- 阈值：{threshold}
- 距阈值：{distance} {unit}
- 24h 极值：{min} ~ {max} {unit}

🔗 关联分析
- 同时段关联告警：{relatedAlarmCount} 条
  {relatedAlarmList}
- 天气关联：{weatherCorrelation}

🎯 可能根因
1. {cause1}（置信度：{confidence1}）
2. {cause2}（置信度：{confidence2}）

💡 处理建议
{suggestion}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Agent 行为指引

当用户说"分析这条告警"时：
1. 执行 Step 1-4 获取完整上下文
2. 执行 Step 5 趋势分析
3. 综合分析生成诊断报告
4. 给出可能根因和处理建议

当用户说"为什么这个设备报警？"时：
1. 查询该设备的所有活跃告警
2. 分析告警之间的关联关系
3. 结合历史数据和天气数据
4. 给出综合诊断

当用户说"这个告警应该怎么处理？"时：
1. 分析告警根因
2. 查询历史类似告警的处理方式
3. 参考应急预案（如果有）
4. 给出具体处理建议
