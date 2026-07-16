# 维护窗口期处理

## 概念

设备维护期间，该设备的告警自动标记为"维护中"，不触发通知，但仍然记录。

## 配置（写 — 走后端 API）

```
POST {API_BASE}/alarm/maintenance
Headers: Authorization: Bearer {TOKEN}, tenant-id: {tenantId}
Body: {
  "deviceId": 123,
  "startTime": "2026-06-03 08:00:00",
  "endTime": "2026-06-03 18:00:00",
  "reason": "设备检修",
  "operator": 1
}
```

## 查询维护窗口（读 — 直连数据库）

### 查询当前维护中的设备

```sql
-- 需要后端扩展维护窗口表
SELECT device_id, start_time, end_time, reason, operator
FROM alarm_maintenance_window 
WHERE start_time <= NOW() AND end_time >= NOW()
  AND deleted = 0
ORDER BY end_time ASC
```

### 查询告警是否在维护窗口内

```sql
-- 检查告警触发时设备是否在维护
SELECT im.id, im.ew_name, im.st_code, im.eq_code, im.create_time,
       CASE 
         WHEN EXISTS (
           SELECT 1 FROM alarm_maintenance_window mw
           WHERE mw.device_id = im.eq_code
             AND mw.start_time <= im.create_time
             AND mw.end_time >= im.create_time
             AND mw.deleted = 0
         ) THEN '维护中'
         ELSE '正常'
       END as maintenance_status
FROM ew_info_message im
WHERE im.id = #{alarmId} AND im.deleted = 0
```

## 处理逻辑

1. **维护窗口期间**：该设备的告警自动标记为"维护中"
2. **不触发通知**：但仍然记录告警
3. **维护窗口结束后**：
   - 如果设备已恢复正常 → 自动标记为恢复
   - 如果设备仍然异常 → 触发正常告警流程
4. **维护窗口期间的告警在统计中单独标记**

## 维护窗口通知模板

```
🔧 设备维护通知

设备：{deviceName}
维护时间：{startTime} ~ {endTime}
维护原因：{reason}
操作人：{operator}

维护期间该设备的告警将被自动标记为"维护中"，不会触发通知。
维护结束后将自动检查设备状态。

[确认] [查看详情]
```

## Agent 行为指引

当用户说"设置设备维护窗口"时：
1. 询问设备、维护时间、原因
2. 调用 API 创建维护窗口
3. 确认维护窗口已创建
4. 告知用户维护期间的告警处理方式

当用户问"哪些设备在维护？"时：
1. 查询当前维护中的设备
2. 展示设备名称、维护时间、原因
3. 标注每个设备的剩余维护时间

当用户说"提前结束维护"时：
1. 查询该设备的维护窗口
2. 调用 API 更新维护窗口的结束时间为当前时间
3. 检查设备当前状态
4. 如果仍异常，触发正常告警流程
