---
name: powerelf-early-warning
description: "预警规则引擎 — 10种阈值条件判断/动态等级调整/大坝多测点预警/趋势预警/通知分发/沉默期/屏蔽。判断是否触发预警，不是查预警记录。核心表: powerelf_data.ew_info_rules, powerelf_data.ew_info_message"
version: 2.0.0
author: dataagent-powerelf
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [early-warning, alarm, threshold, dam, trend, notification, silence, shield, water-conservancy]
    category: powerelf
---

# 预警规则引擎

水利工程预警分析引擎。Agent 可独立完成从规则读取、条件判断、等级计算到通知分发的全流程预警分析。

## When to Use

- 判断采集值是否触发预警（阈值/开关量/状态变化/大坝/趋势）
- 评估预警等级（含动态等级调整）
- 判断大坝安全状态（多测点多指标 + 方向性分析）
- 检测趋势预警（连续单调变化）
- 管理通知策略（沉默期、屏蔽机制）
- 生成预警描述语句并分发通知

## Prerequisites

| 依赖 | 说明 |
|------|------|
| **本地 MySQL** | `127.0.0.1:3306/powerelf_data`（环境变量 POWERELF_DB_* / SRM_DB_*） |
| `db.py` helper | **必须用** `skills/powerelf/lib/db.py`（不要用 water-resources 的） |

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from db import query, get_connection
```

## 核心分析能力

### 1. 阈值预警（Bean: "YZ"）

10种条件枚举，覆盖全部数值比较场景：

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

**动态等级调整** — 超标幅度自动调整等级：

```
超标比例 = |value - threshold| / |threshold|
  <= 10%  -> IV级(一般)
  <= 30%  -> III级(较重)
  <= 60%  -> II级(严重)
  >  60%  -> I级(特别严重)
最终等级 = max(配置等级, 动态等级)
```

**预警描述生成模板**：

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

### 2. 开关量预警（Bean: "KG"）

BigDecimal 精确比较（compareTo == 0），匹配开/关状态：

- 配置: `content: [openValue, downValue]`
- openValue 非 null 且值匹配 -> 触发（开状态）
- downValue 非 null 且值匹配 -> 触发（关状态）

### 3. 状态变化预警（Bean: "ZGB"）

值变化检测，与开关量互补：

- stateStore 记录上次值: key = `{eqCode}:{dotAddress}:{ruleId}`
- 当前值 != 上次值 -> 触发预警
- 无论是否触发，更新 stateStore

### 4. 大坝安全预警（Bean: "DAM-YZ"）

最复杂的预警策略，多测点多指标：

- extend JSON -> `List<DamExtendVo>`（支持多条子规则）
- 每个测点遍历所有子规则，位移值取绝对值后比较
- 触发数量机制: triggerCount >= triggerNumber 才产生预警
- 方向性分析（带符号原始值）:
  - deltaX > 0 = 下游偏移, deltaX < 0 = 上游偏移
  - deltaH > 0 = 下沉, deltaH < 0 = 上升
  - 同断面方向一致 = 整体滑动（升级告警）

### 5. 趋势预警（新增）

连续单调变化检测，per-indicator 参数：

| 指标 | 最小连续次数 | 变化率阈值 |
|------|-------------|-----------|
| 水位(rz) | 3 | 1% |
| 渗压 | 4 | 2% |
| GNSS位移 | 5 | 0.5% |
| 流量 | 3 | 15% |

### 6. 通知策略

多通道通知分发:

| notice_type | 渠道 |
|-------------|------|
| 1 | 短信 (SMS) |
| 2 | 邮件 (EMAIL) |
| 3 | 站内信 (IM) |
| 4 | 声光报警 |
| 5 | 微信 |
| 6 | 钉钉 |

策略匹配: 按 ew_level + ew_rules_type 查找 ew_notice_tactics（enable=1）。

### 7. 沉默期

Redis TTL 防重复通知:

| 场景 | 沉默时间 |
|------|----------|
| 水位预警 | 30 分钟 |
| 雨量预警 | 60 分钟 |
| 大坝安全 | 15 分钟 |
| 设备离线 | 120 分钟 |

### 8. 屏蔽机制

临时屏蔽（维护/确认问题/测试）:

- Redis Key: `CLEAN_EW_RULES_KEYS_CONFIRM:{ruleId}`
- 设置屏蔽: isIgnore="1" + isIgnoreTime（截止时间）
- 取消屏蔽: 删除 Redis Key + isIgnore="0"

## Workflow

```
0. 确定时间窗口 🔴 CHECKPOINT
     用户指定 → 使用用户给定的起止时间
     用户未指定 → 按分析类型选择默认窗口（与源码一致）:
       实时预警判断 → 取各设备最新一条采集值（不限时间，MAX(tm)）
       预警统计/趋势 → 当前月（源码 EquipScheduledJob 用月初到现在）
         START = DATE_FORMAT(CURDATE(), '%Y-%m-01')
         END = NOW()
       视频AI报警统计 → 近1个月（源码 CameraInfoServiceImpl 用 now.minusMonths(1））
         START = DATE_SUB(NOW(), INTERVAL 1 MONTH)
         END = NOW()
     参数化: START='YYYY-MM-DD HH:MM:SS', END='YYYY-MM-DD HH:MM:SS'

1. 读取规则 (ew_info_rules / ew_info_rules_dam) — 限定 status='1' 启用的规则
2. 获取采集值（最新值或限定时间窗口内）
3. 执行条件判断 (10种条件 / 开关量 / 状态变化 / 大坝 / 趋势)
4. 计算动态等级 (max(配置等级, 动态等级))
5. 检查屏蔽 (isIgnore + Redis Key)
6. 检查沉默期 (Redis TTL)
7. 生成预警记录 (ew_info_message)
8. 触发通知分发 (按策略匹配通道和用户)
```

## Related Skills

- `powerelf-monitor` — 监测数据采集与实时推送
- `powerelf-data-governance` — 数据质量治理与清洗

## 参考文档

| 文档 | 内容 |
|------|------|
| [references/algorithm.md](references/algorithm.md) | 完整算法细节：条件判断伪代码、动态等级公式、大坝判定、趋势检测、沉默期/屏蔽逻辑 |
| [references/schema.md](references/schema.md) | 数据库表结构：ew_info_rules, ew_info_message, ew_info_rules_dam, 通知相关表 |
| [references/business_rules.md](references/business_rules.md) | 业务枚举：ew_type, level_r, notice_type, condition, extend JSON 格式 |
