# 预警屏蔽机制

## 概述

临时屏蔽指定规则的预警，屏蔽期间不生成预警记录和通知。

## 判断流程

```
输入: rule(规则对象)

1. if rule.isIgnore != "1":
     → 不屏蔽，正常处理

2. 屏蔽Key = "CLEAN_EW_RULES_KEYS_CONFIRM:{ruleId}"

3. if Redis 中 Key 存在:
     → 在屏蔽期内，忽略本次预警
     → 返回 false
   else:
     → 已过屏蔽期或未设置
     → 返回 true，正常处理
```

## 屏蔽时间管理

### 设置屏蔽

```
屏蔽截止时间 = rule.isIgnoreTime
剩余时长 = Duration.between(now, 屏蔽截止时间)

if 剩余时长 <= 0:
  → 抛出异常：截止时间不能早于当前时间

Redis Key 过期时间 = 剩余时长
```

### 取消屏蔽

```
直接删除 Redis Key
设置 rule.isIgnore = "0"
```

## API 操作

```
设置屏蔽:
  POST /earlywaring/info-rules/ignoreConfirm
  Body: { "id": ruleId, "isIgnore": "1", "isIgnoreTime": "2026-05-31 18:00:00" }

取消屏蔽:
  POST /earlywaring/info-rules/ignoreConfirm
  Body: { "id": ruleId, "isIgnore": "0" }
```

## 典型应用场景

| 场景 | 屏蔽时长 | 理由 |
|------|----------|------|
| 计划维护 | 2-4小时 | 维护期间设备数据会异常 |
| 已确认问题 | 直到修复 | 已知问题无需重复告警 |
| 测试阶段 | 按需 | 测试数据会触发预警 |
