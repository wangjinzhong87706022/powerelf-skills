# 规则进化引擎

## 概述

规则不是写死的，而是通过人工反馈持续进化。每次异常判定都产生反馈，反馈积累到一定量后触发规则调整。

## 规则存储（实际数据库）

预警规则存储在 `ew_info_rules` 表中：

```sql
-- 规则表结构
CREATE TABLE ew_info_rules (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255),           -- 规则名称，如"1#水位站一级预警"
  status CHAR(2) NOT NULL DEFAULT '1',  -- 状态: 1=启用, 0=禁用
  type CHAR(5) NOT NULL,       -- 规则类型: YZ=阈值模式, KG=开关量, ZGB=状态变化
  ew_type CHAR(2),             -- 预警类型: 0=水位, 1=雨量...
  level_r CHAR(2) NOT NULL DEFAULT '0',  -- 预警等级: 1=一级, 2=二级, 3=三级
  pro_id BIGINT,               -- 项目ID
  eq_id BIGINT,                -- 设备ID
  st_id BIGINT,                -- 测站ID
  st_code VARCHAR(255),        -- 测站编码
  extend JSON,                 -- 规则条件（JSON格式）
  dot_address VARCHAR(255),    -- 监测点地址
  is_ignore CHAR(2) DEFAULT '0',  -- 是否屏蔽: 0=否, 1=是
  is_ignore_time DATETIME,     -- 屏蔽时间
  is_work_order CHAR(2) DEFAULT '0',  -- 是否生成工单
  dot_id BIGINT,               -- 监测点ID
  deleted BIT(1) DEFAULT 0,
  tenant_id BIGINT DEFAULT 1
);

-- extend 字段JSON格式示例:
-- {"content": ["248", null], "condition": ">"}
-- content[0] = 阈值, condition = 比较运算符
```

### 规则更新SQL

```sql
-- 调整阈值（阈值自适应）
UPDATE ew_info_rules
SET extend = JSON_SET(extend, '$.content[0]', '250')
WHERE id = 128;

-- 屏蔽规则（排除规则）
UPDATE ew_info_rules SET is_ignore = '1', is_ignore_time = NOW()
WHERE id = 128;

-- 取消屏蔽
UPDATE ew_info_rules SET is_ignore = '0', is_ignore_time = NULL
WHERE id = 128;

-- 新增规则
INSERT INTO ew_info_rules (name, type, ew_type, level_r, st_id, st_code, extend, dot_address)
VALUES ('渗压趋势预警', 'YZ', '2', '3', 18, '1#syz',
        '{"content": ["70", null], "condition": ">"}', '大坝渗压监测点');

-- 禁用规则
UPDATE ew_info_rules SET status = '0' WHERE id = 128;

-- 启用规则
UPDATE ew_info_rules SET status = '1' WHERE id = 128;
```

## 进化循环

```
Agent判定 → 人工反馈 → 统计分析 → 参数调整 → 规则更新 → Agent判定（更准确）
    ↑                                                        ↓
    └────────────────── 持续循环 ←──────────────────────────┘
```

## 反馈数据结构

每条反馈记录：

```json
{
  "id": "fb_20260531_001",
  "timestamp": "2026-05-31 10:30:00",
  "rule_id": "threshold_water_level_v2",
  "rule_type": "threshold",
  "metric": "water_level",
  "station_id": "st_001",
  "point_id": 42,
  "value": 152.3,
  "threshold": 150.0,
  "deviation_pct": 1.53,
  "agent_judgment": {
    "level": "III",
    "confidence": 78,
    "reason": "水位超汛限水位2.3m"
  },
  "human_judgment": {
    "is_anomaly": false,
    "actual_reason": "闸门调度操作",
    "action": "none",
    "note": "上游水库泄洪，属正常调度"
  },
  "context": {
    "gate_operation": true,
    "gate_opening_change": "+20%",
    "rainfall_24h": 0,
    "inflow_change": "+30%",
    "season": "non_flood",
    "data_quality": 95
  },
  "feedback_type": "FP",
  "confidence_delta": -5
}
```

## 进化规则

### 规则1：阈值自适应

```
触发条件: 同一规则的反馈积累 >= 10条

统计:
  precision = TP / (TP + FP)
  recall = TP / (TP + FN)

调整策略:
  # 误报太多 → 收紧阈值
  if precision < 0.70:
    old_threshold = threshold
    threshold = threshold * (1 + (0.7 - precision) * 0.5)  # 最多上调15%
    log("阈值调整: {metric} 从 {old} 调整到 {new}, 原因: 误报率{rate}%")

  # 漏报太多 → 放松阈值
  if recall < 0.70:
    old_threshold = threshold
    threshold = threshold * (1 - (0.7 - recall) * 0.5)  # 最多下调15%
    log("阈值调整: {metric} 从 {old} 调整到 {new}, 原因: 漏报率{rate}%")

  # 两者都差 → 需要增加辅助规则
  if precision < 0.70 and recall < 0.70:
    log("阈值调整无效，需要增加辅助判定规则")
    → 触发"规则生成"流程

约束:
  - 单次调整幅度 <= 15%
  - 两次调整间隔 >= 7天
  - 阈值不能超出物理合理范围
  - 调整需记录原因，可回滚
```

### 规则2：排除规则自动生成

```
触发条件: FP反馈中，同一"正常原因"出现 >= 3次

学习流程:
  1. 提取所有FP反馈的 human_judgment.actual_reason
  2. 聚类相同原因
  3. 分析这些反馈的context共同特征
  4. 生成排除规则

示例:
  FP反馈中"闸门操作导致"出现5次
  → 分析context: gate_operation=true 出现5/5次
  → 生成排除规则:
    if 原规则触发 AND gate_operation == true:
      → 不报警，标记为"调度导致的正常变化"

生成的排除规则格式:
  {
    "rule_id": "exclude_gate_operation",
    "parent_rule": "threshold_water_level",
    "condition": "context.gate_operation == true",
    "action": "suppress",
    "confidence_adjustment": -30,
    "created_from": "5条FP反馈",
    "created_at": "2026-05-31"
  }
```

### 规则3：新检测规则自动生成

```
触发条件: FN反馈中，同一"异常模式"出现 >= 3次

学习流程:
  1. 提取所有FN反馈中，人工发现的异常特征
  2. 分析这些异常发生时的监测数据模式
  3. 提取可量化的检测条件
  4. 生成新检测规则

示例:
  FN反馈: "渗压变化小但实际有渗漏" 出现3次
  → 分析: 渗压日变化 < 1kPa（未触发阈值），但连续7天单向上升
  → 生成新规则:
    if 渗压日变化 < 1kPa AND 连续7天单向上升:
      → IV级异常（潜在渗漏）
      → 置信度: 60%（需人工确认）

生成的新规则格式:
  {
    "rule_id": "trend_pressure_gradual",
    "rule_type": "trend",
    "metric": "pressure",
    "condition": "daily_change < 1kPa AND consecutive_rise >= 7",
    "level": "IV",
    "confidence": 60,
    "action": "alert_with_confirmation",
    "created_from": "3条FN反馈（渗压缓慢上升漏报）",
    "created_at": "2026-05-31"
  }
```

### 规则4：复杂工况规则进化

```
触发条件: 人工对复杂工况判定给出修正

进化方式:

1. 增加排除条件
   人工: "这个点在溢洪道附近，水位上升时渗压上升是正常的"
   → 在规则中增加:
     exclude_if: point.location_type == "溢洪道" AND distance < 200m

2. 增加关联条件
   人工: "单看渗压上升不够，要结合渗流量一起判断"
   → 在规则中增加:
     additional_condition: seepage_flow > historical_avg * 1.2

3. 调整触发阈值
   人工: "这个坝型渗压对水位响应慢，3天不够，要7天"
   → 修改规则参数:
     consecutive_days: 3 → 7

4. 新增场景
   人工: "你们没检测到坝脚渗水，我是现场发现的"
   → 分析: 渗水时渗流计读数变化模式
   → 新增规则:
     if 渗流计读数突增>20% AND 上游水位稳定:
       → 坝脚可能渗漏，需人工现场确认
```

### 规则5：置信度模型校准

```
目的: 让Agent的置信度更准确

方法: 用历史反馈校准置信度

收集:
  所有反馈中，Agent置信度 vs 实际是否异常

计算校准曲线:
  将置信度分为10个区间: [0-10%, 10-20%, ..., 90-100%]
  统计每个区间内的实际准确率

示例:
  Agent说置信度80%的判断 → 实际准确率72%
  Agent说置信度90%的判断 → 实际准确率88%
  → Agent的置信度偏高，需要下调

校准公式:
  calibrated_confidence = agent_confidence * calibration_factor
  calibration_factor = 实际准确率 / Agent置信度均值

更新频率: 每积累50条反馈重新校准一次
```

## 进化日志格式

每次进化都记录到 evolution/feedback-log.md：

```markdown
## 2026-05-31 水位阈值调整

- 规则: threshold_water_level_v2
- 调整: 150m → 155m
- 原因: 近30天FP率35%（10/28条反馈为误报）
- 主要误报原因: 闸门调度操作导致水位正常上涨
- 改进: 同时新增排除规则 exclude_gate_operation
- 状态: 已生效

## 2026-05-31 新增渗压趋势规则

- 规则: trend_pressure_gradual (新增)
- 触发条件: 日变化<1kPa 且 连续7天单向上升
- 原因: 3条FN反馈显示缓慢渗漏被漏报
- 置信度: 60%（需人工确认）
- 状态: 已生效，观察中

## 2026-06-01 复杂工况规则优化

- 规则: complex_water_pressure
- 修改: 增加排除条件"溢洪道200m内"
- 原因: 5条FP反馈显示溢洪道附近渗压上升是正常响应
- 状态: 已生效
```

## 参数注册表更新

进化后自动更新 evolution/parameters.md：

```markdown
## 水位阈值

| 参数 | 初始值 | 当前值 | 调整次数 | 最后调整 | 原因 |
|------|--------|--------|----------|----------|------|
| 汛限水位阈值 | 150.0m | 155.0m | 1 | 2026-05-31 | FP率35% |
| 突变检测阈值 | 0.5m/h | 0.5m/h | 0 | — | 运行良好 |
| 趋势检测次数 | 6次 | 6次 | 0 | — | 运行良好 |

## 渗压阈值

| 参数 | 初始值 | 当前值 | 调整次数 | 最后调整 | 原因 |
|------|--------|--------|----------|----------|------|
| MAD阈值 | 4.0 | 3.8 | 1 | 2026-05-31 | FN率25% |
| 突变检测阈值 | 5kPa/h | 5kPa/h | 0 | — | 运行良好 |
| 趋势检测天数 | 3天 | 7天 | 1 | 2026-05-31 | 坝型响应慢 |
```

## 人工干预接口

除了自动进化，专家也可以主动干预：

### 手动调整阈值

```
Agent指令: "将渗压MAD阈值从4.0调整为3.5"
→ 直接更新 parameters.md
→ 记录调整原因
→ 生效
```

### 手动新增规则

```
Agent指令: "新增规则：如果雨量>100mm且水位上升>2m，自动启动防汛预案"
→ 解析条件和动作
→ 写入规则库
→ 记录来源: "专家手动添加"
→ 生效
```

### 手动禁用规则

```
Agent指令: "暂停GNSS趋势检测规则，近期施工干扰"
→ 标记规则状态为 disabled
→ 记录禁用原因
→ 禁用期间不触发该规则
→ 施工结束后恢复
```

## 进化效果评估

定期评估进化效果：

```
每月统计:
  1. 总反馈数
  2. 各类型反馈占比 (TP/FP/FN/TN)
  3. 整体精确率和召回率
  4. 置信度校准因子
  5. 规则调整次数
  6. 新增规则数

进化目标:
  precision > 0.85  (误报率 < 15%)
  recall > 0.90     (漏报率 < 10%)
  人工干预率 < 20%  (80%的判断Agent可独立完成)

不达标时:
  → 分析哪些规则贡献了最多的误报/漏报
  → 针对性调整
  → 或标记为"需要人工重新定义"
```
