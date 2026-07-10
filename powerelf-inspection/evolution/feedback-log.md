# 巡检模块执行反馈日志

> 反馈驱动规则进化。每次异常判定后记录人工反馈，积累到阈值后触发规则调整。
> 进化规则详见：`rules/rule-evolution.md`

## 反馈数据结构

每条反馈记录格式：

```json
{
  "id": "fb_YYYYMMDD_NNN",
  "timestamp": "YYYY-MM-DD HH:mm:ss",
  "rule_id": "规则标识",
  "rule_type": "threshold | trend | complex",
  "metric": "water_level | pressure | gnss | rainfall | gate | pump",
  "station_id": "测站ID（对应 ew_info_rules.st_id）",
  "value": 152.3,
  "threshold": 150.0,
  "agent_judgment": {
    "level": "I | II | III | IV",
    "confidence": 78,
    "reason": "判定原因"
  },
  "human_judgment": {
    "is_anomaly": true,
    "actual_reason": "人工确认的实际原因",
    "action": "none | confirm | escalate",
    "note": "备注"
  },
  "context": {
    "gate_operation": false,
    "rainfall_24h": 0,
    "data_quality": 95
  },
  "feedback_type": "TP | FP | FN | TN",
  "confidence_delta": -5
}
```

## 进化触发条件

| 进化类型 | 触发条件 | 操作 |
|----------|----------|------|
| 阈值自适应 | 同一规则反馈 >= 10条 | precision < 0.70 → 收紧阈值；recall < 0.70 → 放松阈值 |
| 排除规则生成 | 同一"正常原因"的 FP >= 3次 | 自动生成排除条件 |
| 新规则生成 | 同一"异常模式"的 FN >= 3次 | 自动生成新检测规则 |
| 置信度校准 | 反馈累计 >= 50条 | 校准 Agent 置信度模型 |

## 日志条目

_（暂无记录。首次运行后开始积累。）_

<!--
## 2026-06-02 示例（待填写）

- 规则: threshold_water_level_128
- 触发: 1#水位站一级预警（z > 248m）
- Agent判定: III级异常，置信度 82%
- 人工判定: 正常（闸门调度操作导致）
- 反馈类型: FP
- 后续: 积累到10条后触发阈值调整
-->
