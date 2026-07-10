# 开关量预警规则

## 概述

监测开关量状态变化（Bean名: "KG"），当值等于预设的"开"或"关"阈值时触发预警。

## 判断逻辑

```
输入: value(采集值), rule(规则对象)

1. 解析 rule.extend → {content: [open, down]}
2. if open != null and value == open:
     → 触发预警（开状态）
3. elif down != null and value == down:
     → 触发预警（关状态）
4. else:
     → 正常
```

比较使用 BigDecimal.compareTo == 0（精确相等）。

## 规则配置格式

```json
{
  "content": [openValue, downValue],
  "condition": "FOUR"
}
```

- `openValue` — "开"状态的值（如 1）
- `downValue` — "关"状态的值（如 0）
- 任一为 null 表示不检测该状态

## 典型应用场景

| 场景 | open | down | 说明 |
|------|------|------|------|
| 闸门开关 | 1 | 0 | 1=开启，0=关闭 |
| 水泵运行 | 1 | 0 | 1=运行，0=停止 |
| 报警器 | 1 | 0 | 1=报警，0=正常 |
| 阀门状态 | 1 | 2 | 1=全开，2=全关 |

## 预警描述

```
开状态触发: "已触发【开关量预警】: 设备处于开启状态"
关状态触发: "已触发【开关量预警】: 设备处于关闭状态"
```
