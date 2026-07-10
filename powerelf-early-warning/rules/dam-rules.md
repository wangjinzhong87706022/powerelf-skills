# 大坝安全预警规则

## 概述

针对大坝安全的多测点多指标阈值预警（Bean名: "DAM-YZ"），是最复杂的预警策略。

## 判断逻辑

```
输入: damValues(断面下所有测点的监测数据), rule(大坝预警规则)

1. 解析 rule.extend → List<DamExtendVo> (支持多条子规则)
2. 对每个测点:
     isWarning = false
     triggerFields = []
     for each 子规则:
       value = 测点数据[子规则.field]
       value = abs(value)  # 位移值取绝对值
       if 满足子规则条件(使用10种条件枚举):
         isWarning = true
         triggerFields.add(子规则.field)

3. triggerCount = 统计 isWarning=true 的测点数

4. if triggerCount >= rule.triggerNumber:
     → 触发预警
```

## 大坝监测字段

| 字段名 | 显示名 | 说明 |
|--------|--------|------|
| wgs84DeltaH | 三角形H | 垂直位移变化量 |
| wgs84DeltaX | 三角形X | 水平X位移变化量 |
| wgs84DeltaY | 三角形Y | 水平Y位移变化量 |
| wgs84TotalX | X累计变化量 | X方向累计位移 |
| wgs84TotalY | Y累计变化量 | Y方向累计位移 |
| wgs84TotalH | H累计变化量 | H方向累计位移 |

## 触发机制

- 多测点之间是**或关系**（任一测点满足条件即算触发该子规则）
- 触发测点数量必须 >= `triggerNumber` 才最终产生预警
- `triggerNumber` 来自规则配置，用于过滤偶发个别测点异常

## 规则配置格式

```json
{
  "extend": [
    {"field": "wgs84DeltaH", "content": [0, 5.0], "condition": "FIVE"},
    {"field": "wgs84TotalH", "content": [0, 20.0], "condition": "FIVE"}
  ],
  "triggerNumber": 3,
  "sectionId": 100,
  "damId": 1
}
```

## 方向性分析 — 新增

原始实现中位移值取绝对值，丢失了方向信息。增加方向性分析：

```
对每个测点:
  deltaX = wgs84DeltaX（带符号）
  deltaY = wgs84DeltaY（带符号）
  deltaH = wgs84DeltaH（带符号）

  方向判断:
    if deltaX > 0: X方向向下游偏移
    if deltaX < 0: X方向向上游偏移
    if deltaY > 0: Y方向向左偏移
    if deltaY < 0: Y方向向右偏移
    if deltaH > 0: H方向下沉
    if deltaH < 0: H方向上升

  一致性检查:
    if 同一断面多个测点偏移方向一致:
      → 可能是整体滑动，升级告警
    if 相邻测点偏移方向相反:
      → 可能是局部变形，关注
```

## 预警记录特殊字段

大坝预警记录比标准预警多以下字段：

| 字段 | 说明 |
|------|------|
| damId | 大坝ID |
| sectionId | 断面ID |
| pointIds | 触发预警的测点ID列表 |
| damValues | 测点数据（含名称翻译后的JSON） |

测点数据会进行名称翻译：stId→测站名、eqId→设备编码/名称、pointId→测点名称。
