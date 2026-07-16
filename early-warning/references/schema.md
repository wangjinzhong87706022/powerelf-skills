# 预警规则引擎 — 数据库表结构

## ew_info_rules — 预警规则

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| name | varchar | 规则名称 |
| ew_type | int | 预警类型 (0=水位/1=水质/2=雨量/3=开关变化/4=开关量/5=大坝/6=洪水) |
| level_r | int | 配置预警等级 (1=I级/2=II级/3=III级/4=IV级) |
| extend | text | 规则配置 JSON（条件枚举 + 阈值区间） |
| status | int | 状态 (1=启用/0=禁用) |
| st_id | bigint | 测站ID |
| eq_id | bigint | 设备ID |
| dot_id | bigint | 测点ID |
| is_ignore | varchar | 是否屏蔽 ("1"=屏蔽/"0"=正常) |
| is_ignore_time | datetime | 屏蔽截止时间 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| creator | varchar | 创建人 |
| updater | varchar | 更新人 |
| deleted | tinyint | 逻辑删除 |

## ew_info_rules_dam — 大坝预警规则

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| name | varchar | 规则名称 |
| ew_type | int | 预警类型 (固定为 5=大坝安全) |
| level_r | int | 配置预警等级 |
| extend | text | 子规则 JSON 数组 `List<DamExtendVo>` |
| dam_id | bigint | 大坝ID |
| section_id | bigint | 断面ID |
| point_ids | text | 关联测点ID列表 (JSON数组) |
| trigger_number | int | 触发数量阈值（达到此数量才产生预警） |
| status | int | 状态 |
| is_ignore | varchar | 是否屏蔽 |
| is_ignore_time | datetime | 屏蔽截止时间 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| creator | varchar | 创建人 |
| updater | varchar | 更新人 |
| deleted | tinyint | 逻辑删除 |

## ew_info_message — 预警消息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| ew_name | varchar | 预警名称 |
| ew_type | int | 预警类型 |
| level_r | int | 最终预警等级（含动态调整） |
| value | decimal | 触发时的采集值 |
| gather_time | datetime | 数据采集时间 |
| ew_rules_id | bigint | 关联的规则ID |
| message_confirm | int | 确认状态 (0=未确认/1=已确认) |
| dam_id | bigint | 大坝ID（仅大坝预警） |
| section_id | bigint | 断面ID（仅大坝预警） |
| point_ids | text | 触发测点ID列表（仅大坝预警） |
| dam_values | text | 测点数据JSON（含名称翻译，仅大坝预警） |
| statement | text | 预警描述语句 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| creator | varchar | 创建人 |
| updater | varchar | 更新人 |
| deleted | tinyint | 逻辑删除 |

## ew_notice_tactics — 通知策略

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| name | varchar | 策略名称 |
| ew_level | varchar | 适用预警等级 (逗号分隔, 如 "1,2,3") |
| ew_rules_type | varchar | 适用预警类别 (逗号分隔, 如 "0,1,2") |
| notice_manner | varchar | 通知方式 (逗号分隔, 如 "1,2,3") |
| silence_time | int | 沉默时间（分钟） |
| enable | int | 是否启用 (1=启用/0=禁用) |
| st_ids | varchar | 关联测站ID (逗号分隔) |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| creator | varchar | 创建人 |
| updater | varchar | 更新人 |
| deleted | tinyint | 逻辑删除 |

## ew_notice_tactics_user — 策略用户关联

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| tactcs_id | bigint | 通知策略ID |
| user_id | bigint | 接收用户ID |

## ew_notice_record — 通知记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| ew_info_id | bigint | 关联的预警消息ID |
| notice_message | text | 通知内容 |
| notice_type | int | 通知方式 (1=短信/2=邮件/3=站内/4=声光/5=微信/6=钉钉) |
| notice_status | int | 发送状态 (1=成功/0=失败) |
| user_id | bigint | 接收用户ID |
| create_time | datetime | 发送时间 |
| update_time | datetime | 更新时间 |
| creator | varchar | 创建人 |
| updater | varchar | 更新人 |
| deleted | tinyint | 逻辑删除 |

## ew_camera_info — 视频AI报警

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| st_id | bigint | 测站ID |
| device_id | varchar | 摄像头设备ID |
| alarm_code | varchar | 报警编码 (UUID) |
| alarm_stat | int | 报警状态 (1=产生/2=消失) |
| alarm_grade | int | 报警等级 |
| type | varchar | 报警类型 |
| confirm | int | 确认状态 (0=未确认/1=已确认) |
| info | text | 报警详情 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| creator | varchar | 创建人 |
| updater | varchar | 更新人 |
| deleted | tinyint | 逻辑删除 |
