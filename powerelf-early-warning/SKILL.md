---
name: powerelf-early-warning
description: "水利工程预警系统：阈值预警、开关量预警、状态变化预警、大坝安全预警、趋势预警。规则引擎内嵌，可独立判断。"
version: 2.0.0
author: Powerelf Team
license: MIT
platforms: [linux, windows, macos]
metadata:
  hermes:
    tags: [water-conservancy, early-warning, alarm, notification, threshold]
    related_skills: [powerelf-data-governance, powerelf-monitor]
prerequisites:
  env_vars: [POWERELF_API_BASE, POWERELF_API_TOKEN]
---

# 预警系统 Skill v2

水利工程预警规则引擎。规则内嵌，Agent 可独立执行预警判断。

## 核心数据表

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| ew_info_rules | 预警规则 | name, ew_type, level_r, extend(JSON), status, st_id, eq_id, dot_id |
| ew_info_rules_dam | 大坝预警规则 | name, ew_type, level_r, extend(JSON), dam_id, section_id, point_ids(JSON), trigger_number |
| ew_info_message | 预警消息 | ew_name, ew_type, level_r, value, gather_time, ew_rules_id, message_confirm, dam_id, section_id |
| ew_notice_record | 通知记录 | ew_info_id, notice_message, notice_type(1=短信/2=邮件/3=站内/4=声光/5=微信/6=钉钉), notice_status |
| ew_notice_tactics | 通知策略 | name, ew_level, ew_rules_type, notice_manner, silence_time(min), enable, st_ids |
| ew_notice_tactics_user | 策略用户关联 | tactcs_id, user_id |
| ew_camera_info | 视频AI报警 | st_id, device_id, alarm_code(UUID), alarm_stat(1=产生/2=消失), alarm_grade, type, confirm, info |

## ew_type 预警类型枚举

| 值 | 含义 | 对应规则 |
|----|------|----------|
| 0 | 水位预警 | threshold-rules (YZ) |
| 1 | 水质预警 | threshold-rules (YZ) |
| 2 | 雨量预警 | threshold-rules (YZ) |
| 3 | 开关变化预警 | state-change-rules (KG-BH) |
| 4 | 开关量预警 | switch-rules (KG) |
| 5 | 大坝安全预警 | dam-rules (DAM-YZ) |
| 6 | 洪水预警 | threshold-rules (YZ) |

## 能力概览

| 子模块 | 文件 | 功能 |
|--------|------|------|
| 阈值预警 | `rules/threshold-rules.md` | 10种条件比较，动态等级调整 |
| 开关量预警 | `rules/switch-rules.md` | 开/关状态匹配 |
| 状态变化预警 | `rules/state-change-rules.md` | 值变化检测 |
| 大坝安全预警 | `rules/dam-rules.md` | 多测点多指标，触发数量机制 |
| 趋势预警 | `rules/trend-rules.md` | 连续单调变化检测（新增） |
| 通知分发 | `strategies/notification-strategy.md` | SMS/Email/IM 多通道 |
| 沉默期 | `strategies/silence-period.md` | 防重复通知 |
| 屏蔽机制 | `strategies/warning-shield.md` | 临时屏蔽规则 |

## 按需加载指令

```
"预警规则"/"创建规则"     → rules/threshold-rules.md
"开关量"/"闸门预警"       → rules/switch-rules.md
"状态变化"/"值改变"       → rules/state-change-rules.md
"大坝安全"/"位移预警"     → rules/dam-rules.md
"趋势"/"连续上升"/"持续下降" → rules/trend-rules.md
"通知"/"短信"/"邮件"      → strategies/notification-strategy.md
"沉默期"/"通知频率"       → strategies/silence-period.md
"屏蔽"/"忽略预警"         → strategies/warning-shield.md
```

## 自我进化

- 可调参数：`evolution/parameters.md`
- 反馈日志：`evolution/feedback-log.md`

---

## API 附录

### 预警规则

| 端点 | 说明 |
|------|------|
| `GET /earlywaring/info-rules/page` | 预警规则列表 |
| `POST /earlywaring/info-rules/create` | 创建规则 |
| `PUT /earlywaring/info-rules/update` | 更新规则 |
| `DELETE /earlywaring/info-rules/delete` | 删除规则 |

### 预警消息

| 端点 | 说明 |
|------|------|
| `GET /earlywaring/info-message/page` | 预警消息列表 |
| `PUT /earlywaring/info-message/confirm` | 确认预警 |

### 通知策略

| 端点 | 说明 |
|------|------|
| `GET /earlywaring/notice-tactics/page` | 通知策略列表 |
| `POST /earlywaring/notice-tactics/create` | 创建通知策略 |

### 视频AI报警

| 端点 | 说明 |
|------|------|
| `GET /earlywaring/camera-info/page` | 视频AI报警列表 |
| `PUT /earlywaring/camera-info/confirm` | 确认视频报警 |

### 统计

| 端点 | 说明 |
|------|------|
| `GET /earlywaring/overview/statistics` | 预警统计 |

通用头与鉴权约定：见 [`../_shared/api-auth.md`](../_shared/api-auth.md)（`Authorization: Bearer ${POWERELF_API_TOKEN}` + `tenant-id: 1`）
