# 预警规则引擎 — 业务枚举与配置规范

## ew_type — 预警类型枚举

| 值 | 含义 | Bean名 | 对应策略 |
|----|------|--------|----------|
| 0 | 水位预警 | YZ | 阈值预警 |
| 1 | 水质预警 | YZ | 阈值预警 |
| 2 | 雨量预警 | YZ | 阈值预警 |
| 3 | 开关变化预警 | ZGB | 状态变化预警 |
| 4 | 开关量预警 | KG | 开关量预警 |
| 5 | 大坝安全预警 | DAM-YZ | 大坝安全预警 |
| 6 | 洪水预警 | YZ | 阈值预警 |

## level_r — 预警等级定义

| 值 | 名称 | 说明 | 响应要求 |
|----|------|------|----------|
| 1 | I级(特别严重) | 红色预警 | 立即响应，全员通知 |
| 2 | II级(严重) | 橙色预警 | 尽快处理，领导通知 |
| 3 | III级(较重) | 黄色预警 | 需关注，值班通知 |
| 4 | IV级(一般) | 蓝色预警 | 提示性，记录备查 |

等级数值越小越严重。动态等级调整时取 `max(配置等级, 动态等级)` = 数值上取 `min()`。

## condition — 条件枚举

| 枚举值 | 符号 | 数学含义 | 使用的边界 | 判断公式 |
|--------|------|---------|-----------|---------|
| ZERO | `=` | 等于 | min | `value == min` |
| ONE | `!=` | 不等于 | min | `value != min` |
| TOW | `>=` | 大于等于 | min | `value >= min` |
| THREE | `<=` | 小于等于 | max | `value <= max` |
| FOUR | `{}` | 闭区间 | min, max | `value >= min && value <= max` |
| FIVE | `>` | 大于 | min | `value > min` |
| SIX | `<` | 小于 | max | `value < max` |
| SEVEN | `()` | 开区间 | min, max | `value > min && value < max` |
| EIGHT | `{)` | 左闭右开 | min, max | `value >= min && value < max` |
| NINE | `(}` | 左开右闭 | min, max | `value > min && value <= max` |

## notice_type — 通知方式枚举

| 值 | 含义 | Bean名 | 实现服务 |
|----|------|--------|----------|
| 1 | 短信 | SMS | SmsSendService |
| 2 | 邮件 | EMAIL | MailSendApi |
| 3 | 站内信 | IM | NotifySendService |
| 4 | 声光报警 | — | 本地设备 |
| 5 | 微信 | — | 微信企业号 |
| 6 | 钉钉 | — | 钉钉机器人 |

## extend JSON 格式规范

### 阈值预警 (ew_type: 0/1/2/6)

```json
{
  "content": [min, max],
  "condition": "FOUR"
}
```

- 单边条件（TOW/FIVE）: content = [min, null]
- 单边条件（THREE/SIX）: content = [null, max]
- 双边条件（FOUR/SEVEN/EIGHT/NINE）: content = [min, max]

### 开关量预警 (ew_type: 4)

```json
{
  "content": [openValue, downValue],
  "condition": "FOUR"
}
```

- openValue: "开"状态的值（如 1），null 表示不检测
- downValue: "关"状态的值（如 0），null 表示不检测

### 状态变化预警 (ew_type: 3)

```json
{
  "content": [描述用min, 描述用max],
  "condition": "FOUR"
}
```

content 仅用于消息描述，实际判断只比较上次值和当前值。

### 大坝安全预警 (ew_type: 5)

```json
[
  {
    "field": "wgs84DeltaH",
    "content": [0, 5.0],
    "condition": "FIVE"
  },
  {
    "field": "wgs84TotalH",
    "content": [0, 20.0],
    "condition": "FIVE"
  }
]
```

- extend 为数组，支持多条子规则
- field: 大坝监测字段名
- 每条子规则独立判断，位移值取绝对值后比较
- 触发数量由 trigger_number 字段控制（不在 extend 中）

### 大坝监测字段

| field | 显示名 | 说明 |
|-------|--------|------|
| wgs84DeltaH | 三角形H | 垂直位移变化量 |
| wgs84DeltaX | 三角形X | 水平X位移变化量 |
| wgs84DeltaY | 三角形Y | 水平Y位移变化量 |
| wgs84TotalX | X累计变化量 | X方向累计位移 |
| wgs84TotalY | Y累计变化量 | Y方向累计位移 |
| wgs84TotalH | H累计变化量 | H方向累计位移 |

## 趋势预警 — 分指标参数

趋势预警不使用 ew_info_rules 表，而是基于时序数据独立检测。

| 指标 | 指标代码 | 最小连续次数 | 变化率阈值 | 说明 |
|------|---------|-------------|-----------|------|
| 水位 | rz | 3 | 1% | 连续上升可能表示洪水 |
| 渗压 | seepage | 4 | 2% | 连续上升可能表示渗漏 |
| GNSS位移 | gnss | 5 | 0.5% | 连续变化可能表示滑坡 |
| 流量 | flow | 3 | 15% | 连续变化需关注 |

## 沉默期 — 典型配置

| 场景 | 沉默时间 | 理由 |
|------|----------|------|
| 水位预警 | 30 分钟 | 水位变化慢，30分钟内无需重复 |
| 雨量预警 | 60 分钟 | 雨量持续时通知过多 |
| 大坝安全 | 15 分钟 | 安全关键，缩短沉默期 |
| 设备离线 | 120 分钟 | 离线状态恢复慢 |

## 屏蔽机制 — 使用场景

| 场景 | 屏蔽时长 | 理由 |
|------|----------|------|
| 计划维护 | 2-4 小时 | 维护期间设备数据会异常 |
| 已确认问题 | 直到修复 | 已知问题无需重复告警 |
| 测试阶段 | 按需 | 测试数据会触发预警 |

Redis Key: `CLEAN_EW_RULES_KEYS_CONFIRM:{ruleId}`，过期时间 = 当前到截止时间的秒数。
