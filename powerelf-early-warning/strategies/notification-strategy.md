# 通知分发策略

## 概述

预警触发后的多通道通知分发机制。

> **生成结论文案前**：`statement` / `alarmInfo` 等面向人的措辞涉及统计结论时，
> 先查 [`../../_shared/references/statistical-caution.md`](../../_shared/references/statistical-caution.md)
> 过一遍措辞自检清单（相关≠因果、假精度、幸存者偏差等）。

> **通知交付前 QA 闸**：通知文案定稿前，先过一遍
> [`../../_shared/references/analysis-qa-checklist.md`](../../_shared/references/analysis-qa-checklist.md)
> 的交付前 QA 清单（数据质量/计算/合理性/呈现）。

## 通知流程

```
预警触发 → 策略匹配 → 用户获取 → 参数组装 → 沉默期检查 → 异步发送 → 记录入库
```

### 1. 策略匹配

通过预警等级(level)和预警类别(ewRulesType)匹配通知策略：

```
SELECT * FROM ew_notice_tactics
WHERE enable = 1
  AND find_in_set(#{level}, ewLevel)
  AND find_in_set(#{ewRulesType}, ewRulesType)
```

### 2. 通知参数

标准参数：
- `projectName` — 工程名称
- `stDotName` — 测点名称
- `statement` — 预警描述语句
- `unit` — 单位
- `value` — 当前值
- `alarmTime` — 预警时间（yyyy年MM月dd日 HH时mm分ss秒）
- `alarmLevel` — 预警等级名称
- `alarmInfo` — 预警名称

大坝预警额外参数：
- `damName` — 大坝名称
- `sectionName` — 断面名称
- `noticeTemplateType` — 模板类型（切换为 DAM_ALARM_INFORM）

## 三种通知渠道

| 渠道 | Bean名 | 实现 | 说明 |
|------|--------|------|------|
| 短信 | SMS | SmsSendService | 模板: alarm-sms |
| 邮件 | EMAIL | MailSendApi | 模板: ALARM_INFORM / DAM_ALARM_INFORM |
| 站内信 | IM | NotifySendService | 站内消息通知 |

### 短信通知

```
调用: SmsSendService.sendSingleSms(phone, templateCode, params)
模板: alarm-sms
参数: projectName, stDotName, statement, unit, value, alarmTime, alarmLevel, alarmInfo
```

### 邮件通知

```
调用: MailSendApi.sendSingleMailToAdmin(email, templateCode, params)
模板: ALARM_INFORM（标准）/ DAM_ALARM_INFORM（大坝）
```

### 站内信通知

```
调用: NotifySendService.sendSingleNotifyToAdmin(userId, templateCode, params)
```

## 通知记录

每次通知发送后生成 `NoticeRecordDO` 记录入库，包含：
- 通知策略ID
- 通知方式
- 接收用户ID
- 发送状态（成功/失败）
- 发送时间
