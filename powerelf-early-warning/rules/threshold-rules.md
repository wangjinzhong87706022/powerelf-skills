# 阈值预警规则

## 概述

最基础的预警策略（Bean名: "YZ"），将采集值与配置的阈值区间进行比较。

## 10种条件枚举

| 枚举值 | 符号 | 数学含义 | 判断公式 |
|--------|------|---------|---------|
| ZERO | `=` | 等于 | `value == min` |
| ONE | `!=` | 不等于 | `value != min` |
| TOW | `>=` | 大于等于 | `value >= min` |
| THREE | `<=` | 小于等于 | `value <= max` |
| FOUR | `{}` | 闭区间 [min, max] | `value >= min && value <= max` |
| FIVE | `>` | 大于 | `value > min` |
| SIX | `<` | 小于 | `value < max` |
| SEVEN | `()` | 开区间 (min, max) | `value > min && value < max` |
| EIGHT | `{)` | 左闭右开 [min, max) | `value >= min && value < max` |
| NINE | `(}` | 左开右闭 (min, max] | `value > min && value <= max` |

## 规则配置格式

```json
{
  "content": [min, max],
  "condition": "FOUR"
}
```

- 单边条件（TOW/FIVE）只使用 min
- 单边条件（THREE/SIX）只使用 max
- 双边条件（FOUR/SEVEN/EIGHT/NINE）使用 min 和 max

## 预警等级

| 等级 | 名称 | 说明 |
|------|------|------|
| 1 | I级(特别严重) | 需立即响应 |
| 2 | II级(严重) | 需尽快处理 |
| 3 | III级(较重) | 需关注 |
| 4 | IV级(一般) | 提示性预警 |

原始实现中等级在规则创建时固定配置。

## 动态等级调整 — 新增

超标幅度自动调整等级，无需手动配置：

```
超标比例 = |value - threshold| / |threshold|

if 超标比例 <= 10%:
  动态等级 = IV级(一般)
elif 超标比例 <= 30%:
  动态等级 = III级(较重)
elif 超标比例 <= 60%:
  动态等级 = II级(严重)
else:
  动态等级 = I级(特别严重)

最终等级 = max(配置等级, 动态等级)  # 取更严重的
```

### 示例

```
规则: 水位 > 150m (配置等级: III级)
实际值: 155m
超标比例: (155-150)/150 = 3.3%
动态等级: IV级
最终等级: III级 (配置等级更严重)

规则: 水位 > 150m (配置等级: IV级)
实际值: 170m
超标比例: (170-150)/150 = 13.3%
动态等级: III级
最终等级: III级 (动态等级更严重)
```

## 预警描述语句生成

每种条件对应不同的中文描述：

| 条件 | 描述模板 |
|------|---------|
| = | 值等于{min}，触发预警 |
| != | 值不等于{min}，触发预警 |
| >= | 值{value}超过阈值{min}，超出{diff} |
| <= | 值{value}低于阈值{max}，低出{diff} |
| {} | 值{value}在区间[{min},{max}]内，触发预警 |
| > | 值{value}大于{min}，超出{diff} |
| < | 值{value}小于{max}，低出{diff} |
| () | 值{value}在开区间({min},{max})内，触发预警 |
| {) | 值{value}在区间[{min},{max})内，触发预警 |
| (} | 值{value}在区间({min},{max}]内，触发预警 |

## 判断流程

```
输入: value(采集值), rule(规则对象)

1. 解析 rule.extend → {content: [min, max], condition}
2. 根据 condition 枚举执行比较
3. if 匹配:
     计算动态等级
     调用屏蔽判断(WarningShield.check)
     if 未屏蔽:
       生成预警记录
       触发通知分发
```
