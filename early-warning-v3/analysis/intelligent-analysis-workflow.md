# 智能分析工作流

## 概述

智能分析工作流是预警系统的核心编排模块，将数据采集、告警聚合、关联分析、根因分析、风险评估、趋势预测和响应建议串联为完整的端到端分析流程。当用户询问当前告警情况、风险状态或安全态势时，Agent 按照本工作流逐步执行，最终输出结构化的风险评估报告和响应建议。

本工作流调用以下子模块：
- `correlation-analysis.md` — 跨域关联分析
- `root-cause-analysis.md` — 根因分析
- `risk-scoring-matrix.md` — 风险评分矩阵
- `predictive-warning.md` — 预测性预警
- `plan-generation` Skill — 预案生成（仅高风险触发）

## 触发条件

当用户输入包含以下意图时触发本工作流：

| 触发类别 | 触发关键词 | 说明 |
|---------|-----------|------|
| 告警情况 | "当前告警情况"、"告警情况如何"、"最近告警"、"告警怎么这么多" | 查询当前告警全貌 |
| 风险评估 | "有什么风险"、"风险大不大"、"风险评估"、"整体风险"、"风险多大" | 风险态势评估 |
| 安全确认 | "现在安全吗"、"安全吗"、"有没有隐患"、"有没有问题" | 安全态势判断 |
| 告警分析 | "告警分析"、"分析告警"、"哪些测站最危险"、"最重要的是哪些" | 告警综合分析 |
| 大坝安全 | "大坝安全吗"、"大坝情况"、"水位降雨渗流"、"大坝综合风险" | 大坝安全评估 |
| 应急预案 | "需要启动预案吗"、"需要应急预案吗"、"情况严重吗"、"启动什么预案" | 预案触发评估 |
| 未来预测 | "水位会涨吗"、"未来会怎样"、"会继续涨吗"、"未来24小时" | 趋势预测 |
| 值班关注 | "今天关注什么"、"值班注意"、"重点关注" | 值班重点关注 |
| 水位趋势 | "水位还会涨吗"、"什么时候能降"、"水位趋势" | 水位趋势预测 |
| 告警解除 | "告警什么时候能解除"、"需要等多久" | 告警解除预测 |
| 降低风险 | "怎么降低风险"、"有什么措施"、"怎么处理" | 风险降低建议 |
| 气象关联 | "暴雨预警"、"天气对水位的影响"、"气象预警" | 气象与洪水关联 |

## 工作流步骤

### Step 1: 数据采集

**超时控制：30 秒**

采集当前活跃告警和实时监测数据，为后续分析提供数据基础。

#### 优化策略

**推荐：使用一条SQL获取所有告警数据**

```sql
-- 一次性获取告警统计和详情（推荐）
SELECT 
  level_r,
  ew_type,
  COUNT(*) as total,
  SUM(CASE WHEN message_confirm = 0 THEN 1 ELSE 0 END) as unconfirmed,
  MIN(gather_time) as earliest,
  MAX(gather_time) as latest
FROM ew_info_message 
WHERE deleted = 0 AND create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY level_r, ew_type
ORDER BY level_r, total DESC;
```

**备选：使用脚本（较慢）**

```bash
# 未确认告警
python3 scripts/query_early_warning.py --type unconfirmed --days 7

# 高级别告警
python3 scripts/query_early_warning.py --type high_level --days 30

# 告警风暴检测
python3 scripts/query_early_warning.py --type alarm_storm

# 气象预警
python3 scripts/query_early_warning.py --type weather_warning
```

#### 直接 SQL

```sql
-- 一次性获取水位+降雨数据（推荐）
SELECT 
  'water_level' as data_type,
  st_code,
  rz as value,
  tm as time
FROM st_rsvr_r 
WHERE tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
UNION ALL
SELECT 
  'rainfall' as data_type,
  st_code,
  p as value,
  tm as time
FROM st_pptn_r 
WHERE tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY data_type, time DESC
LIMIT 100;
```

#### 异常处理

| 异常场景 | 处理方式 |
|---------|---------|
| 数据库连接失败 | 返回错误信息"数据采集失败：数据库连接异常"，终止工作流 |
| 查询超时（>30s） | 返回已采集的部分数据，标注"部分数据采集超时" |
| weather_warn 表不存在 | 跳过气象预警采集，标注"气象预警数据不可用" |
| 告警数据为空 | 返回"当前无活跃告警，系统运行正常"，跳过后续步骤 |

---

### Step 2: 告警聚合与去噪

对采集的原始告警进行聚合、去噪、排序，生成告警摘要。

#### 聚合规则

1. **按 st_code + ew_type 分组**：同一测站的同类告警归为一组
2. **30 分钟合并窗口**：同一分组内 30 分钟内的告警合并为一条，取最高级别
3. **过滤已确认告警**：排除 message_confirm = 1 的告警
4. **按级别排序**：level_r 升序（1=红色最高优先级）
5. **截断上限**：最多保留 100 条告警

#### 聚合伪代码

```python
def aggregate_alerts(raw_alerts):
    # Step 1: 过滤已确认
    active = [a for a in raw_alerts if a['message_confirm'] == 0 and a['deleted'] == 0]

    # Step 2: 按 st_code + ew_type 分组
    groups = {}
    for alert in active:
        key = (alert['st_code'], alert['ew_type'])
        groups.setdefault(key, []).append(alert)

    # Step 3: 组内 30 分钟合并
    merged = []
    for key, alerts in groups.items():
        alerts.sort(key=lambda x: x['create_time'])
        window = [alerts[0]]
        for a in alerts[1:]:
            if time_diff(a['create_time'], window[-1]['create_time']) <= 30:
                window.append(a)
            else:
                merged.append(merge_window(window))
                window = [a]
        merged.append(merge_window(window))

    # Step 4: 按级别排序
    merged.sort(key=lambda x: x['level_r'])

    # Step 5: 截断
    return merged[:100]

def merge_window(alerts):
    """合并窗口内的告警，取最高级别，保留最新值"""
    return {
        'st_code': alerts[0]['st_code'],
        'ew_type': alerts[0]['ew_type'],
        'level_r': min(a['level_r'] for a in alerts),
        'value': alerts[-1]['value'],
        'create_time': alerts[0]['create_time'],
        'count': len(alerts),
        'merged_ids': [a['id'] for a in alerts]
    }
```

#### 输出

```json
{
  "alert_summary": {
    "total": 12,
    "by_level": { "1": 2, "2": 3, "3": 4, "4": 3 },
    "by_type": { "0": 5, "2": 3, "20": 2, "12": 2 },
    "top_alerts": [
      { "st_code": "606K2155", "ew_type": "0", "level_r": 1, "value": "463.2", "count": 3 }
    ]
  }
}
```

---

### Step 3: 跨域关联分析

**超时控制：60 秒**

调用 `correlation-analysis.md` 模块，分析告警之间的跨域关联关系。

> **注意**：本步骤直接使用 Step 2 的聚合输出（`alert_summary`）作为输入，对聚合后的告警进行跨域关联判定，而不是重新查询数据库。下方 SQL 仅用于辅助补充或验证。

#### 关联场景

| 场景 | 关联域 | 触发条件 |
|------|--------|---------|
| dam_risk | 水位 + 降雨 + 渗流 | 同时存在 ew_type=0、2、20/40 的告警 |
| flood_risk | 水位 + 气象 | 存在 ew_type=0 告警且有气象预警 |
| data_reliability | 多设备离线 | ew_type=12 告警数 ≥ 3 |

#### 关联强度

| 强度 | 判断标准 |
|------|---------|
| strong | 三域关联且时间窗口 ≤ 30 分钟 |
| moderate | 双域关联或三域关联但时间窗口 > 30 分钟 |
| weak | 单域关联或仅时间重叠 |

#### 查询 SQL

```sql
-- 告警类型分布
SELECT ew_type, COUNT(*) as cnt, MIN(level_r) as highest_level
FROM ew_info_message
WHERE deleted = 0 AND message_confirm = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY ew_type

-- 离线设备计数
SELECT COUNT(*) as offline_count
FROM ew_info_message
WHERE ew_type = '12' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
```

#### 输出

```json
{
  "correlation_result": {
    "compound_risks": [
      {
        "scenario": "dam_risk",
        "domains": ["water_level", "rainfall", "seepage"],
        "strength": "strong",
        "evidence": "606K2155 水位红色告警 + 606K2155 降雨橙色告警 + 606K2155 渗压黄色告警，时间窗口 15 分钟"
      }
    ],
    "domain_coverage": { "water_level": true, "rainfall": true, "seepage": true },
    "cross_domain_score": 4
  }
}
```

> **cross_domain_score 映射**（参见 `risk-scoring-matrix.md`）：三域关联 = 4，双域关联 = 3，单域 = 2。

---

### Step 4: 根因分析与风险评估

调用 `root-cause-analysis.md` 和 `risk-scoring-matrix.md` 模块，执行根因诊断和风险量化评分。

#### 调用模块

1. **根因分析**（`root-cause-analysis.md`）：对 top_alerts 中的高优先级告警执行 Step 1-6 的完整诊断流程
2. **风险评分**（`risk-scoring-matrix.md`）：基于 5 因素加权评分

#### 参数说明

| 参数 | 定义 |
|------|------|
| `alerts` | Step 2 聚合输出的活跃告警列表 |
| `correlation_result` | Step 3 跨域关联分析输出 |
| `duration_hours` | 最早活跃告警的 `create_time` 到当前时间的小时差（`time elapsed from the earliest active alert's create_time to now`） |

#### 风险评分计算

```python
def calculate_risk_score(alerts, correlation_result, duration_hours):
    """
    基于 risk-scoring-matrix.md 的 5 因素评分

    参数:
        alerts: 聚合后的活跃告警列表（Step 2 输出）
        correlation_result: 跨域关联分析结果（Step 3 输出）
        duration_hours: 最早活跃告警的 create_time 到当前时间的小时差
    """
    # ── 空列表守卫 ──
    if not alerts:
        return {
            'overall_score': 0,
            'risk_level': 'none',
            'factors': {},
            'message': '当前无活跃告警，无需评估风险'
        }

    # ── 直接判定规则（优先级 1：命中即跳过加权计算）──
    # 规则 1: 红色告警 + 三域关联 → 直接高风险
    has_red = any(a['level_r'] == 1 for a in alerts)
    three_domain = correlation_result.get('cross_domain_score', 0) == 4
    if has_red and three_domain:
        return {
            'overall_score': 4.0,
            'risk_level': 'high',
            'factors': {},
            'direct_rule': '红色告警 + 三域关联，直接判定高风险'
        }

    # 规则 2: 告警风暴（>50 条/小时） → 直接高风险
    if len(alerts) > 50:
        return {
            'overall_score': 4.0,
            'risk_level': 'high',
            'factors': {},
            'direct_rule': '告警风暴（{} 条），直接判定高风险'.format(len(alerts))
        }

    # ── 因素 1: 告警级别 (权重 30%) ──
    level_r_value = min(a['level_r'] for a in alerts)
    level_factor_score = {1: 4, 2: 3, 3: 2, 4: 1}.get(level_r_value, 1)

    # ── 因素 2: 告警数量 (权重 20%) ──
    count = len(alerts)
    if count >= 5:
        count_factor = 4
    elif count >= 3:
        count_factor = 3
    elif count >= 2:
        count_factor = 2
    else:
        count_factor = 1

    # ── 因素 3: 跨域关联 (权重 25%) ──
    # 映射：三域关联=4, 双域关联=3, 单域=2（参见 risk-scoring-matrix.md）
    cross_score = correlation_result.get('cross_domain_score', 2)
    cross_factor = cross_score

    # ── 因素 4: 持续时间 (权重 15%) ──
    if duration_hours > 4:
        duration_factor = 4
    elif duration_hours > 2:
        duration_factor = 3
    elif duration_hours > 1:
        duration_factor = 2
    else:
        duration_factor = 1

    # ── 因素 5: 趋势 (权重 10%) ──
    trend_assessment = assess_trend(alerts)  # 返回 'worsening' | 'stable' | 'improving'
    trend_factor = {'worsening': 4, 'stable': 3, 'improving': 2}.get(trend_assessment, 3)

    # ── 加权计算 ──
    overall = (
        level_factor_score * 0.30 +
        count_factor * 0.20 +
        cross_factor * 0.25 +
        duration_factor * 0.15 +
        trend_factor * 0.10
    )

    # ── 边界提升规则（优先级 4：3.40-3.49 → 上浮为高风险）──
    if 3.40 <= overall < 3.50:
        risk_level = 'high'
    elif overall >= 3.5:
        risk_level = 'high'
    elif overall >= 2.5:
        risk_level = 'medium'
    else:
        risk_level = 'low'

    return {
        'overall_score': round(overall, 2),
        'risk_level': risk_level,
        'factors': {
            'level': {'score': level_factor_score, 'weight': 0.30, 'value': level_r_value},
            'count': {'score': count_factor, 'weight': 0.20, 'value': count},
            'cross_domain': {'score': cross_factor, 'weight': 0.25, 'value': cross_score},
            'duration': {'score': duration_factor, 'weight': 0.15, 'value': duration_hours},
            'trend': {'score': trend_factor, 'weight': 0.10, 'value': trend_assessment}
        }
    }


def assess_trend(alerts):
    """
    趋势判断：两级指标体系

    PRIMARY（主要指标）：水位变化趋势 — 查询 st_rsvr_r 表最近 N 条记录的 rz 值
    SECONDARY（辅助指标）：告警数量变化趋势 — 仅在水位数据不可用时使用

    返回: 'worsening' | 'stable' | 'improving'
    """
    # PRIMARY: 水位趋势
    water_data = query_water_level_trend()
    if water_data and len(water_data) >= 2:
        first_val = water_data[0]['value']
        last_val = water_data[-1]['value']
        change_pct = (last_val - first_val) / first_val * 100 if first_val else 0
        if change_pct > 5:
            return 'worsening'
        elif change_pct < -5:
            return 'improving'
        else:
            return 'stable'

    # SECONDARY: 告警数量趋势（水位数据不可用时的回退）
    recent = sum(1 for a in alerts
                 if time_since(a['create_time']) <= 1)      # 最近 1 小时
    earlier = sum(1 for a in alerts
                  if 1 < time_since(a['create_time']) <= 2)  # 1-2 小时前
    if recent > earlier:
        return 'worsening'
    elif recent < earlier:
        return 'improving'
    else:
        return 'stable'
```

#### 输出

```json
{
  "risk_assessment": {
    "overall_score": 3.65,
    "risk_level": "high",
    "factors": {
      "level": { "score": 4, "weight": 0.30, "value": 1 },
      "count": { "score": 3, "weight": 0.20, "value": 4 },
      "cross_domain": { "score": 4, "weight": 0.25, "value": 4 },
      "duration": { "score": 3, "weight": 0.15, "value": 2.5 },
      "trend": { "score": 4, "weight": 0.10, "value": "worsening" }
    },
    "root_causes": [
      { "cause": "持续强降雨导致库水位快速上涨", "confidence": 0.85 }
    ]
  }
}
```

> **注意**：上例中 `trend.value` 为 `"worsening"` 是示例值，实际运行时由 `assess_trend()` 函数根据水位/告警数量趋势动态返回，可能为 `"worsening"`、`"stable"` 或 `"improving"`。

---

### Step 5: 趋势预测

**超时控制：60 秒**

调用 `predictive-warning.md` 模块，基于历史数据预测水位和风险演变趋势。

#### 数据查询

```sql
-- 最近 6 小时水位数据
SELECT rz as value, tm as time
FROM st_rsvr_r
WHERE st_id = #{stId}
  AND tm >= DATE_SUB(NOW(), INTERVAL 6 HOUR)
ORDER BY tm ASC
```

#### 水位预测（线性外推）

```python
def predict_water_level(history_data, forecast_hours=6):
    """
    基于最近 6 小时数据线性外推
    """
    if len(history_data) < 2:
        return {'status': 'insufficient_data'}

    first = history_data[0]
    last = history_data[-1]
    hours = (last['time'] - first['time']).total_seconds() / 3600

    if hours == 0:
        return {'status': 'insufficient_timespan'}

    rate = (last['value'] - first['value']) / hours  # m/h
    predicted = last['value'] + rate * forecast_hours

    predicted_time = last['time'] + timedelta(hours=forecast_hours)
    return {
        'status': 'ok',
        'current': last['value'],
        'rate_per_hour': round(rate, 4),
        'predicted_6h': round(predicted, 2),
        'predicted_time': predicted_time.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    }
```

#### 风险演变预测

```python
def predict_risk_evolution(risk_level, trend, correlation_result):
    """
    预测未来 6 小时风险演变
    """
    evolution = {
        'current': risk_level,
        'trend': trend,
        'scenarios': []
    }

    if risk_level == 'high' and trend == 'worsening':
        evolution['scenarios'].append({
            'condition': '降雨持续',
            'predicted_level': 'critical',
            'probability': 0.7,
            'action': '立即启动应急预案'
        })
        evolution['scenarios'].append({
            'condition': '降雨减弱',
            'predicted_level': 'high',
            'probability': 0.3,
            'action': '维持当前响应级别'
        })
    elif risk_level == 'medium' and trend == 'worsening':
        evolution['scenarios'].append({
            'condition': '趋势持续',
            'predicted_level': 'high',
            'probability': 0.6,
            'action': '准备应急预案'
        })

    return evolution
```

#### 输出

```json
{
  "trend_prediction": {
    "water_level": {
      "status": "ok",
      "current": 462.5,
      "rate_per_hour": 0.15,
      "predicted_6h": 463.4,
      "predicted_time": "2026-06-09T20:00:00+08:00"
    },
    "risk_evolution": {
      "current": "high",
      "trend": "worsening",
      "scenarios": [
        {
          "condition": "降雨持续",
          "predicted_level": "critical",
          "probability": 0.7,
          "action": "立即启动应急预案"
        }
      ]
    }
  }
}
```

---

### Step 6: 响应建议与预案触发

基于风险评估和趋势预测结果，生成响应建议，必要时触发预案生成。

#### 响应规则

| 风险等级 | 响应建议 |
|---------|---------|
| high | 立即响应，建议触发预案，通知防汛责任人到岗 |
| medium | 加强监控，准备预案，加密监测频率 |
| low | 持续监控，记录分析结果 |

#### 预案触发条件

以下 3 个条件**必须同时满足**才会触发预案生成：

1. **风险等级为高风险**：risk_level = 'high'
2. **趋势为恶化或持平**：trend IN ('worsening', 'stable')
3. **存在跨域关联**：compound_risks 非空

#### 预案参数推断

```python
def infer_plan_params(risk_assessment, trend_prediction, correlation_result):
    """
    基于分析结果推断预案参数
    """
    params = {}

    # 调度目标
    if risk_assessment['risk_level'] == 'high':
        params['schedulingTarget'] = 0  # 防洪优先
    else:
        params['schedulingTarget'] = 2  # 综合平衡

    # 调度时长
    risk_evolution = trend_prediction.get('risk_evolution', {})
    if risk_evolution.get('trend') == 'worsening':
        params['tmSpan'] = 24  # 持续降雨
    else:
        params['tmSpan'] = 6   # 短时关注

    # 水位参数
    water = trend_prediction.get('water_level', {})
    if water.get('predicted_6h'):
        params['adjustedWaterLevel'] = water['predicted_6h']

    return params
```

#### 调用预案生成

当触发条件满足时，调用 plan-generation Skill：

```
调用参数:
- schedulingTarget: 推断的调度目标
- tmSpan: 推断的调度时长
- adjustedWaterLevel: 预测水位
- save: false（仅生成，不保存，等待 HITL 确认）
```

---

## HITL 检查点

### 检查点 1: 风险确认

**位置**：Step 4 完成后

**触发条件**：风险评估完成（任何风险等级）

**模板变量查表**：

| 变量 | 来源 | 查表规则 |
|------|------|----------|
| `level_name` | `factors.level.value` (level_r) | 1→"特别严重（红色）", 2→"严重（橙色）", 3→"较重（黄色）", 4→"一般（蓝色）" |
| `trend_desc` | `factors.trend.value` | "worsening"→"恶化", "stable"→"持平", "improving"→"改善" |
| `cross_desc` | `factors.cross_domain.value` | 4→"三域关联", 3→"双域关联", 2→"单域" |

**交互内容**：

```
📊 风险评估结果

- 综合得分：{overall_score}
- 风险等级：{risk_level}
- 主要因素：
  - 告警级别：{level_name} (得分 {level_factor_score})
  - 告警数量：{count} 条 (得分 {count_score})
  - 跨域关联：{cross_desc} (得分 {cross_score})
  - 持续时间：{duration} 小时 (得分 {duration_score})
  - 变化趋势：{trend_desc} (得分 {trend_score})

请确认风险评估结果：
1. [确认] — 认可当前评估，继续后续分析
2. [调整] — 调整风险等级（请说明调整理由）
```

**处理逻辑**：
- 用户选择"确认" → 继续 Step 5
- 用户选择"调整" → 更新 risk_level，继续 Step 5

### 检查点 2: 预案触发确认

**位置**：Step 6 完成后

**触发条件**：仅当风险等级为高风险且满足预案触发的 3 个条件时

**交互内容**：

```
⚠️ 高风险预警 — 建议触发应急预案

风险摘要：
- 综合得分：{overall_score}
- 风险等级：高风险
- 主要原因：{root_cause}
- 趋势预测：{trend_prediction}

推断预案参数：
- 调度目标：{scheduling_target_desc}
- 调度时长：{tm_span} 小时
- 预测水位：{predicted_level} m

请确认是否触发预案生成：
1. [确认触发] — 使用推断参数生成预案
2. [调整参数] — 修改参数后生成预案
3. [取消] — 不触发预案，仅记录分析结果
```

**处理逻辑**：
- 用户选择"确认触发" → 调用 plan-generation Skill，save=false
- 用户选择"调整参数" → 用户修改参数后调用 plan-generation Skill
- 用户选择"取消" → 跳过预案生成，输出分析报告

---

## 输出格式

完整分析结果的 JSON Schema：

```json
{
  "workflow": "intelligent-analysis",
  "version": "1.0.0",
  "timestamp": "2026-06-09T14:00:00+08:00",
  "trigger": "用户询问当前告警情况",

  "step1_data_collection": {
    "status": "success | partial | failed",
    "alerts_raw": [...],
    "water_level": [...],
    "rainfall": [...],
    "weather_warning": [...],
    "errors": []
  },

  "step2_alert_aggregation": {
    "alert_summary": {
      "total": 12,
      "by_level": { "1": 2, "2": 3, "3": 4, "4": 3 },
      "by_type": { "0": 5, "2": 3, "20": 2, "12": 2 },
      "top_alerts": [
        {
          "st_code": "606K2155",
          "ew_type": "0",
          "level_r": 1,
          "value": "463.2",
          "count": 3,
          "merged_ids": [14898, 14901, 14905]
        }
      ]
    }
  },

  "step3_correlation": {
    "compound_risks": [
      {
        "scenario": "dam_risk",
        "domains": ["water_level", "rainfall", "seepage"],
        "strength": "strong",
        "evidence": "..."
      }
    ],
    "cross_domain_score": 4
  },

  "step4_risk_assessment": {
    "overall_score": 3.65,
    "risk_level": "high",
    "factors": {
      "level": { "score": 4, "weight": 0.30, "value": 1 },
      "count": { "score": 3, "weight": 0.20, "value": 4 },
      "cross_domain": { "score": 4, "weight": 0.25, "value": 4 },
      "duration": { "score": 3, "weight": 0.15, "value": 2.5 },
      "trend": { "score": 4, "weight": 0.10, "value": "worsening" }
    },
    "root_causes": [
      { "cause": "持续强降雨导致库水位快速上涨", "confidence": 0.85 }
    ]
  },

  "step5_trend_prediction": {
    "water_level": {
      "status": "ok",
      "current": 462.5,
      "rate_per_hour": 0.15,
      "predicted_6h": 463.4,
      "predicted_time": "2026-06-09T20:00:00+08:00"
    },
    "risk_evolution": {
      "current": "high",
      "trend": "worsening",
      "scenarios": [
        {
          "condition": "降雨持续",
          "predicted_level": "critical",
          "probability": 0.7,
          "action": "立即启动应急预案"
        }
      ]
    }
  },

  "step6_response": {
    "risk_level": "high",
    "recommendation": "立即响应，建议触发预案，通知防汛责任人到岗",
    "plan_trigger": {
      "triggered": true,
      "conditions_met": {
        "high_risk": true,
        "trend_worsening_or_stable": true,
        "cross_domain_exists": true
      },
      "params": {
        "schedulingTarget": 0,
        "tmSpan": 24,
        "adjustedWaterLevel": 463.4
      }
    }
  },

  "hitl_checkpoints": {
    "risk_confirmation": {
      "executed": true,
      "user_response": "confirmed",
      "adjusted_level": null
    },
    "plan_trigger_confirmation": {
      "executed": true,
      "user_response": "confirmed | adjusted | cancelled",
      "final_params": {}
    }
  }
}
```

---

## 异常处理

### 数据异常

| 异常场景 | 处理方式 |
|---------|---------|
| 告警值为 NULL | 标注为"数据缺失"，不参与趋势计算 |
| 水位数据缺失 | 使用告警数量变化趋势替代（见 risk-scoring-matrix.md 趋势评分 SECONDARY 指标） |
| 降雨数据缺失 | 跳过降雨关联分析，标注"降雨数据不可用" |
| 测站编码不匹配 | 标注"测站信息异常"，排除该告警的关联分析 |

### 分析异常

| 异常场景 | 处理方式 |
|---------|---------|
| 关联分析无结果 | 跨域关联评分设为 2（单域），继续流程 |
| 根因分析置信度过低（< 0.3） | 标注"根因不确定"，建议人工复核 |
| 趋势预测数据不足（< 2 个数据点） | 标注"预测数据不足"，趋势评分设为 3（持平） |
| 风险评分为边界值（3.40-3.49） | 按 risk-scoring-matrix.md 边界提升规则，上浮为高风险 |

### 超时控制

| 步骤 | 超时阈值 | 超时处理 |
|------|---------|---------|
| Step 1: 数据采集 | 30 秒 | 返回已采集数据，标注"部分数据超时" |
| Step 3: 跨域关联分析 | 60 秒 | 跳过关联分析，跨域评分设为 2 |
| Step 5: 趋势预测 | 60 秒 | 跳过预测，趋势评分设为 3（持平） |
| 整体工作流 | 5 分钟 | 输出已执行步骤的结果，标注"工作流超时" |

### 幂等性

- **重复触发**：同一用户在 5 分钟内重复触发同一工作流，返回上次结果（缓存 key = `workflow:{user_id}:{minute_bucket}`）
- **并发控制**：同一时间仅允许一个工作流实例执行，后续请求排队等待或返回"分析进行中，请稍候"
- **结果缓存**：分析结果缓存 5 分钟，期间相同触发条件返回缓存结果

---

## Agent 行为指引

执行本工作流时，Agent 应按以下步骤操作：

1. **识别触发意图**：判断用户输入是否匹配触发条件关键词
2. **执行 Step 1 数据采集**：运行 query_early_warning.py 脚本和直接 SQL 查询，收集告警、水位、降雨、气象数据。30 秒内未完成则使用已采集数据
3. **执行 Step 2 告警聚合**：按 st_code+ew_type 分组，30 分钟窗口合并，过滤已确认告警，按级别排序，截断至 100 条
4. **执行 Step 3 跨域关联分析**：调用 correlation-analysis.md 检测 dam_risk、flood_risk、data_reliability 场景。60 秒超时则跳过
5. **执行 Step 4 风险评估**：调用 root-cause-analysis.md 诊断根因，调用 risk-scoring-matrix.md 计算 5 因素加权评分
6. **HITL 检查点 1**：展示风险评估结果，等待用户确认或调整
7. **执行 Step 5 趋势预测**：调用 predictive-warning.md 进行线性外推和风险演变预测。60 秒超时则跳过
8. **执行 Step 6 响应建议**：根据风险等级生成响应建议。若满足预案触发条件（高风险 + 趋势恶化或持平 + 存在跨域关联），推断预案参数
9. **HITL 检查点 2**（仅高风险）：展示预案触发建议，等待用户确认、调整或取消。确认后调用 plan-generation Skill（save=false）

---

## 多轮对话处理

### 上下文保持规则

1. **告警上下文**：记住用户之前提到的告警ID、测站编码、告警类型
2. **分析上下文**：记住之前的分析结果（风险等级、关联分析、趋势预测）
3. **用户偏好**：记住用户的调整（如"调整为中风险"）

### 指代词解析

| 用户表达 | 解析方式 |
|---------|---------|
| "第一个告警" | 引用 step2_alert_aggregation.top_alerts[0] |
| "那个测站" | 引用上下文中最近提到的 st_code |
| "刚才的风险" | 引用 step4_risk_assessment |
| "之前的分析" | 引用最近一次完整分析结果 |

### 典型对话流程

```
用户：当前告警情况如何？
Agent：[执行完整工作流] 当前有X条告警，风险等级为[高/中/低]...

用户：第一个告警详细说说
Agent：[针对 top_alerts[0] 执行根因分析]

用户：怎么处理？
Agent：[基于根因分析给出处理建议]

用户：确认高风险
Agent：[HITL检查点1确认，继续Step 5-6]

用户：启动预案
Agent：[HITL检查点2确认，调用plan-generation]
```

### 异常对话处理

| 场景 | 处理方式 |
|------|---------|
| 用户说"没那么严重" | 调整风险等级为 medium，重新生成响应建议 |
| 用户说"先不启动预案" | 跳过预案触发，输出分析报告 |
| 用户说"换个测站" | 切换上下文到新测站，重新分析 |
| 用户问"之前分析的那个" | 引用缓存的分析结果 |
