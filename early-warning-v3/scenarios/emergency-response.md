# 运维辅助决策

## 功能

用户问"这个红色预警应该怎么处理？"，Agent 结合历史案例、告警上下文和应急预案给出建议。

## 决策流程

### Step 1: 获取告警完整上下文

```sql
SELECT im.id, im.ew_name, im.st_code, im.eq_code, im.ew_type, 
       im.level_r, im.value, im.gather_time, im.content,
       im.ew_rules_info, im.aggregate_count, im.status,
       im.create_time, im.update_time
FROM ew_info_message im
WHERE im.id = #{alarmId} AND im.deleted = 0
```

### Step 2: 查询历史类似告警的处理方式

```sql
-- 查询同类告警的历史处理记录
SELECT im.ew_name, im.ew_type, im.level_r, im.value,
       im.create_time, im.status, im.update_time,
       TIMESTAMPDIFF(MINUTE, im.create_time, im.update_time) as handle_minutes,
       ae.action, ae.remark, ae.operator_name
FROM ew_info_message im
LEFT JOIN ew_audit_log ae ON im.id = ae.alarm_id
WHERE im.ew_type = #{ewType} 
  AND im.deleted = 0
  AND im.status IN (3, 4)  -- 已处理或已恢复
ORDER BY im.update_time DESC
LIMIT 20
```

### Step 3: 查询同类告警的处理统计

```sql
-- 统计同类告警的处理方式分布
SELECT ae.remark, COUNT(*) as count
FROM ew_audit_log ae
JOIN ew_info_message im ON ae.alarm_id = im.id
WHERE im.ew_type = #{ewType} 
  AND ae.action = 'RESOLVE'
  AND im.deleted = 0
GROUP BY ae.remark
ORDER BY count DESC
LIMIT 10
```

### Step 4: 查询设备当前状态

```sql
-- 水位
SELECT rz, tm FROM st_rsvr_r WHERE st_id = #{stId} ORDER BY tm DESC LIMIT 1

-- 渗压
SELECT water_pressure, tm FROM st_pressure_r WHERE st_id = #{stId} ORDER BY tm DESC LIMIT 1

-- 渗流
SELECT percolation, tm FROM st_percolation_r WHERE st_id = #{stId} ORDER BY tm DESC LIMIT 1
```

### Step 5: 查询设备基础信息

```sql
SELECT sb.name as station_name, sb.code as station_code,
       eb.name as device_name, eb.code as device_code,
       eb.status as device_status
FROM st_base sb
LEFT JOIN equip_base eb ON sb.id = eb.st_base_id
WHERE sb.code = #{stCode} AND eb.code = #{eqCode}
```

### Step 6: 查询应急预案（如果有）

```sql
-- 查询关联的应急预案
SELECT id, name, content, level, create_time
FROM emergency_plan 
WHERE ew_type = #{ewType} AND deleted = 0
ORDER BY level_r DESC
LIMIT 5
```

## 决策建议模板

```
🔧 运维决策建议

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 告警信息
- 告警：{ewName}
- 等级：{levelName} ({level})
- 设备：{deviceName} ({deviceCode})
- 当前值：{value} {unit}（阈值：{threshold}）
- 已持续：{duration}

📊 历史处理参考
同类告警历史上共处理 {totalCount} 次：
1. {action1}（{count1} 次，{percentage1}%）
2. {action2}（{count2} 次，{percentage2}%）
3. {action3}（{count3} 次，{percentage3}%）

最近一次处理：{lastAction}（{lastTime}，耗时 {lastDuration} 分钟）

🎯 推荐处理方案

方案 1（推荐）：{recommendAction1}
- 依据：{reason1}
- 预计耗时：{estimatedTime1}
- 成功率：{successRate1}

方案 2：{recommendAction2}
- 依据：{reason2}
- 预计耗时：{estimatedTime2}

方案 3：{recommendAction3}
- 依据：{reason3}
- 预计耗时：{estimatedTime3}

📋 处理步骤
1. {step1}
2. {step2}
3. {step3}
4. {step4}

⚠️ 注意事项
{caution}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 不同告警类型的处理建议库

### 水位超限 (ew_type=0)

```
常见处理方式：
1. 检查水位计是否正常（传感器漂移、数据异常）
2. 开启泄洪闸排水
3. 加强巡查频次
4. 通知下游做好准备
5. 启动应急预案

判断逻辑：
- 如果水位缓慢上升 → 可能是正常汛期，加强监测
- 如果水位突然上升 → 可能是暴雨，开启泄洪
- 如果水位持续不变但告警 → 可能是传感器故障
```

### 渗压异常 (ew_type=5, 渗压)

```
常见处理方式：
1. 检查渗压计是否正常
2. 检查坝体是否有渗漏
3. 加强坝体巡查
4. 记录渗压变化趋势
5. 必要时启动应急预案

判断逻辑：
- 如果渗压缓慢上升 → 可能是正常水位变化导致
- 如果渗压突然上升 → 可能是坝体渗漏，需紧急处理
- 如果渗压波动大 → 可能是传感器故障
```

### 渗流异常 (ew_type=5, 渗流)

```
常见处理方式：
1. 检查渗流量计是否正常
2. 检查排水设施是否通畅
3. 记录渗流量变化
4. 必要时降低库水位
5. 启动应急预案

判断逻辑：
- 如果渗流量增加但水质清澈 → 可能是正常渗流
- 如果渗流量增加且水质浑浊 → 可能是坝体管涌，需紧急处理
- 如果渗流量突然降为零 → 可能是堵塞或传感器故障
```

### 降雨超限 (ew_type=2)

```
常见处理方式：
1. 确认降雨量数据准确性
2. 预测入库流量
3. 提前开启泄洪设施
4. 通知下游做好准备
5. 加强水位监测频次

判断逻辑：
- 如果是短时强降雨 → 关注水位变化速率
- 如果是持续降雨 → 关注累积降雨量和入库流量
```

## Agent 行为指引

当用户问"这个红色预警应该怎么处理？"时：
1. 查询告警详情
2. 查询历史类似告警的处理方式
3. 查询设备当前状态
4. 结合告警类型和严重程度
5. 生成决策建议（包含多个方案）
6. 给出具体处理步骤

当用户说"帮我处理这条告警"时：
1. 查询告警详情
2. 给出处理建议
3. 询问用户选择哪种方案
4. 调用 API 执行确认/处理
5. 确认操作成功

当用户问"这个告警严重吗？"时：
1. 查询告警等级和持续时间
2. 查询同类告警的历史严重程度
3. 查询设备当前值与阈值的距离
4. 综合评估严重程度
5. 给出判断依据
