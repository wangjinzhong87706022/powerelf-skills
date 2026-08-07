# 告警升级建议（智能体）

## 定位

本文件聚焦**智能体层**的升级决策建议能力，不包含升级检测的后端实现。

升级检测（定时任务）由应用层实现，见后端开发文档。

## 智能体能力

### 1. 升级决策建议

当用户询问是否应该升级告警时，智能体可以分析并给出建议：

**触发场景：**
- 用户问"这条告警要不要手动升级？"
- 用户问"什么时候应该升级？"
- 用户问"升级到谁？"

**分析过程：**
1. 查询告警详情（SQL）
2. 检查告警历史（SQL）
3. 检查关联告警（SQL）
4. 分析处理难度
5. 生成建议

**示例输出：**
```
用户: "这条告警要不要手动升级？"

智能体分析结果：

建议手动升级。原因：
1. 该告警已持续3小时，接近自动升级阈值
2. 当前值班人员处理经验不足
3. 涉及设备较多，需要协调
4. 历史数据显示类似告警平均处理时间4小时

建议操作：
1. 立即升级到部门负责人
2. 通知设备维护团队
3. 准备应急预案

是否执行升级？
```

### 2. 升级通知模板生成

当需要发送升级通知时，智能体可以生成合适的模板：

**触发场景：**
- 用户说"升级通知怎么写？"
- 用户说"生成升级通知"

**分析过程：**
1. 查询告警类型和级别
2. 分析升级原因
3. 确定通知对象
4. 生成通知模板

**示例输出：**
```
用户: "升级通知怎么写？"

智能生的升级通知模板：

⚠️ 告警升级通知

原告警：水位超限告警
类型：水位预警
等级：L1(红色) → L2(橙色)
水库：张家咀水库
测点：606K2155-3B
当前值：461.96m
已持续：3小时
升级原因：超时未处理
本次为第1次升级

请立即处理！

[立即处理] [查看详情]
```

### 3. 升级策略分析

当需要制定升级策略时，智能体可以提供建议：

**触发场景：**
- 用户问"升级时间应该设多长？"
- 用户问"升级通知对象怎么配置？"

**分析过程：**
1. 分析历史告警数据
2. 计算平均处理时间
3. 评估人员配置
4. 生成策略建议

**示例输出：**
```
用户: "升级时间应该设多长？"

智能体分析结果：

建议升级时间配置：

| 告警等级 | 首次升级 | 二次升级 | 三次升级 |
|----------|----------|----------|----------|
| L1 (红) | 2小时 | 4小时 | 8小时 |
| L2 (橙) | 4小时 | 8小时 | 24小时 |
| L3 (黄) | 8小时 | 24小时 | 48小时 |
| L4 (蓝) | 24小时 | 48小时 | 不升级 |

理由：
1. 基于最近30天的告警处理数据分析
2. L1告警平均处理时间为1.5小时，设置2小时升级阈值
3. L2告警平均处理时间为3小时，设置4小时升级阈值
4. 留出足够的处理时间，避免不必要的升级

通知对象建议：
- 首次升级：值班负责人
- 二次升级：部门负责人
- 三次升级：分管领导
```

## SQL 查询模板

### 查询告警详情

```sql
SELECT id, ew_name, ew_type, level_r, status, 
       create_time, escalate_count,
       TIMESTAMPDIFF(MINUTE, create_time, NOW()) as duration_minutes,
       st_code, eq_code, value
FROM ew_info_message 
WHERE id = #{alarmId} AND deleted = 0
```

### 查询升级历史

```sql
SELECT ae.id, ae.alarm_id, ae.action, ae.old_level, ae.new_level, 
       ae.operator_name, ae.create_time, ae.remark,
       im.ew_name, im.level_r
FROM ew_audit_log ae
LEFT JOIN ew_info_message im ON ae.alarm_id = im.id
WHERE ae.action = 'ESCALATE'
  AND ae.create_time >= #{startTime}
ORDER BY ae.create_time DESC
```

### 查询升级统计

```sql
SELECT 
  COUNT(*) as total_escalations,
  COUNT(DISTINCT alarm_id) as unique_alarms,
  AVG(escalation_count) as avg_escalation_count
FROM ew_info_message
WHERE escalation_count > 0
  AND deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
```

### 查询平均处理时间

```sql
SELECT 
  level_r,
  AVG(TIMESTAMPDIFF(HOUR, create_time, update_time)) as avg_hours,
  COUNT(*) as count
FROM ew_info_message
WHERE status IN (3, 4, 5)  -- 已处理/已恢复/已忽略
  AND deleted = 0
  AND tenant_id = #{tenantId}
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY level_r
ORDER BY level_r
```

## Agent 行为指引

1. **升级决策**：分析告警详情、历史数据、关联告警，给出是否升级的建议
2. **通知模板**：根据告警类型和级别，生成合适的升级通知
3. **策略分析**：基于历史数据，建议升级时间配置
4. **升级对象**：根据升级次数，建议通知对象
5. **不可逆操作拦截**：凡涉及下方白名单/黑名单的操作，必须先过 HITL 二次确认闸（见下节）

## 不可逆操作白名单与拦截闸

> 对齐腾讯 TCOP "给 AI 装刹车"经验：命令白名单 + 人工审批 + 低置信度降级三道闸一个都不能少。
> 本节是第二道闸（HITL 人工审批）的具体规则，与 `lib/topology.py` 的 `apply_confidence_gate`（第一道闸：置信度阈值降级）互补。
> 第一道闸管"AI 说得对不对"，本节管"就算 AI 说对了，能不能执行"。

### 设计原则

1. **AI 只建议，不执行**：本智能体只有读权限（查 ew_info_message / ew_audit_log 等），写操作一律走后端 API，不直接执行任何运维命令。
2. **不可逆操作必须人确认**：凡涉及物理世界状态改变且无法一键撤回的操作（开闸、停泵、断阀、泄洪、水库调度），强制 HITL 二次确认。
3. **白名单优先于黑名单**：用"只放行白名单"逻辑而非"拦截黑名单"，避免新型危险操作漏网。
4. **留痕可追溯**：所有 HITL 确认动作写入 `ew_audit_log`，含操作人、时间、原始建议、确认结果。

### 不可逆操作分级表

| 等级 | 操作类别 | 典型动作 | 拦截策略 |
|------|----------|----------|----------|
| **S0 禁止** | 数据库写 | 直接 SQL 写 `powerelf_srm_yml` / `powerelf_data` 任何业务表 | Agent 无写权限，硬拦截；若后端 API 要求写，必须走 API 不走裸 SQL |
| **S0 禁止** | 配置变更 | 删除/修改测站、设备、阈值规则、用户权限 | 禁止 Agent 直接操作，只生成建议报告交人工处置 |
| **S1 强制 HITL** | 闸门操作 | 开闸泄洪、关闸拦洪、闸门开度调整 | 必须值班负责人 + �分管领导双签确认，附泄洪影响评估 |
| **S1 强制 HITL** | 泵组操作 | 启泵抽排、停泵、泵组切换 | 必须值班负责人确认，附抽排水区域影响评估 |
| **S1 强制 HITL** | 阀门操作 | 切阀、断阀、换阀、阀门开度调整 | 必须值班负责人确认，附管路影响评估 |
| **S1 强制 HITL** | 水库调度 | 调度令、泄洪令、蓄水令、应急放水 | 必须分管领导 + 防汛指挥部双签，附上下游影响评估 |
| **S2 建议 HITL** | 告警处置 | 确认告警、忽略告警、升级告警、关闭告警 | 建议值班人员确认，可由 Agent 直接建议不强制 |
| **S2 建议 HITL** | 设备维护 | 远程重启设备、校准、清洗探头 | 建议维护团队确认，可由 Agent 直接建议不强制 |
| **S3 放行** | 只读查询 | 查告警、查历史、查拓扑、查阈值 | Agent 直接执行，无需 HITL |

### HITL 二次确认闸流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Agent 识别到操作涉及 S0/S1/S2 分级表                      │
├─────────────────────────────────────────────────────────────┤
│ 2. S0 → 硬拦截，输出"此操作禁止 AI 执行，请联系运维"        │
│    S1 → 进 HITL 强制确认闸                                  │
│    S2 → 进 HITL 建议确认闸（可跳过）                        │
│    S3 → 直接放行                                            │
├─────────────────────────────────────────────────────────────┤
│ 3. S1 强制确认闸：                                          │
│    a. Agent 生成操作建议卡片（含风险评估、影响范围、回滚方案）│
│    b. 卡片推送至值班负责人 + 分管领导                       │
│    c. 等待双签确认（超时 30 分钟未确认 → 自动取消）         │
│    d. 确认通过 → 调后端 API 执行；写入 ew_audit_log          │
│    e. 确认拒绝 → 终止；写入 ew_audit_log                    │
├─────────────────────────────────────────────────────────────┤
│ 4. S2 建议确认闸：                                          │
│    a. Agent 生成操作建议卡片                                 │
│    b. 推送至值班人员                                        │
│    c. 值班人员可直接确认或忽略                              │
│    d. 写入 ew_audit_log                                     │
└─────────────────────────────────────────────────────────────┘
```

### 操作建议卡片模板（S1 强制 HITL）

```json
{
  "card_id": "HITL-20260805-001",
  "operation_level": "S1",
  "operation_type": "gate_open",
  "suggested_action": "开启 3# 泄洪闸，开度 50%",
  "reason": "库水位 116.41m 超校核洪水位，根因排序置信度 0.92 指向降雨事件 EVT-20260805-001",
  "risk_assessment": {
    "downstream_peak_flow": "120 m³/s（下游河道安全泄量 200 m³/s）",
    "downstream_peak_time": "泄洪后 4 小时",
    "affected_stations": ["station:2151", "station:2158"],
    "rollback_plan": "若下游水位超警戒，立即关闸至 20%"
  },
  "confidence_gate": {
    "root_cause_score": 0.92,
    "display_action": "show",
    "display_reason": "✅ 置信度充足"
  },
  "approval_chain": {
    "required": ["值班负责人", "分管领导"],
    "status": "pending",
    "timeout_min": 30
  },
  "audit_log": {
    "table": "ew_audit_log",
    "fields": ["alarm_id", "action", "operator_name", "create_time", "remark"]
  }
}
```

### 与根因排序的联动

本节 HITL 闸与 `lib/topology.py` 的 `apply_confidence_gate` 联动：

| 根因置信度 | 第一道闸（置信度） | 第二道闸（HITL） | 最终动作 |
|------------|-------------------|------------------|----------|
| < 0.5 | suppress（不列根因） | 不触发 | 输出"建议人工介入"，不生成操作建议卡片 |
| 0.5 ≤ score < 0.7 | show_with_warning（⚠️ 低置信度） | S1 强制双签 | 生成卡片但标注"⚠️ 根因置信度低，请人工覆核" |
| ≥ 0.7 | show（✅ 置信度充足） | S1 强制双签 | 生成卡片，正常走 HITL 流程 |

> 即：**置信度低不阻止执行，但会标注警告让人更谨慎**；不可逆操作无论置信度多高都必须 HITL。
> 这符合腾讯"绝不胡编"原则——AI 可以错，但错了的操作不能自动执行。

### SQL 查询模板（HITL 审计）

```sql
-- 查询 HITL 审计记录
SELECT ae.id, ae.alarm_id, ae.action, ae.old_level, ae.new_level,
       ae.operator_name, ae.create_time, ae.remark,
       im.ew_name, im.level_r
FROM ew_audit_log ae
LEFT JOIN ew_info_message im ON ae.alarm_id = im.id
WHERE ae.action IN ('HITL_APPROVED', 'HITL_REJECTED', 'HITL_TIMEOUT')
  AND ae.create_time >= #{startTime}
ORDER BY ae.create_time DESC
```

### 自检清单（每次生成操作建议前必须过）

- [ ] 操作是否在白名单内？不在 → S0 禁止
- [ ] 操作是否可一键撤回？不可 → 至少 S1 强制 HITL
- [ ] 是否附风险评估（下游影响、回滚方案）？无 → 补齐再推送
- [ ] 是否引用根因排序的拓扑路径 + ew_info_message.id？无 → 补齐
- [ ] 是否写入 ew_audit_log？未写 → 补写
- [ ] 是否标注置信度闸状态？未标 → 补标
