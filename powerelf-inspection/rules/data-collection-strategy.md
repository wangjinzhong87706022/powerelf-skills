# 数据采集策略

## 核心问题

Agent 怎么知道某个巡检点该采什么数据？

## 答案：数据源注册表 + 关键词匹配

数据源的映射关系存储在 `sys_data_source_registry` 表中（详见 `docs/18-数据源动态注册机制.md`）。Agent 运行时查询注册表，按检查项的 `required` 文本匹配关键词，动态确定要查询的传感器表。

**扩展方式**：新增数据源 = INSERT 一条注册表记录，不改代码、不改规则文件。

## 注册表结构

```sql
SELECT name, source_table, keywords, station_type, max_distance,
       query_fields, default_hours, judge_rules, sort_order
FROM sys_data_source_registry
WHERE status = 1 AND deleted = 0
ORDER BY sort_order;
```

| 字段 | 说明 |
|------|------|
| name | 数据源名称，如"水位监测" |
| source_table | 传感器数据表名，如 `st_river_r` |
| keywords | 匹配关键词，逗号分隔，如"水位,库水位,上游水位" |
| station_type | 关联测站类型（`dsm_cz_info.type`），NULL=不需要测站 |
| max_distance | Haversine 距离阈值（米） |
| query_fields | 查询字段，如"z,q,tm" |
| default_hours | 默认查询时间范围（小时） |
| judge_rules | 判定规则JSON（阈值/变化率/MAD） |
| sort_order | 匹配优先级（越小越优先） |

## 匹配算法

```python
def match_data_sources(required_text, registry):
    """根据检查项文本匹配数据源（按 sort_order 优先级）"""
    matched = []
    for source in registry:  # 已按 sort_order 排序
        keywords = [kw.strip() for kw in source['keywords'].split(',')]
        if any(kw in required_text for kw in keywords):
            matched.append(source)
    return matched

def match_with_fallback(required_text, registry):
    """带降级策略的匹配：匹配失败时标记为需人工检查"""
    matched = match_data_sources(required_text, registry)
    if not matched:
        return [{"name": "人工检查", "source_table": None,
                 "reason": f"无匹配数据源，检查项: {required_text[:50]}",
                 "action": "需巡检员现场检查并手动记录"}]
    return matched
```

**匹配示例**：

```
检查项: "检查上游水位是否超过汛限水位"
  → 匹配 keywords "水位" → st_river_r (sort_order=10)

检查项: "观察坝体有无渗漏现象"
  → 匹配 keywords "渗漏" → st_percolation_r (sort_order=21)

检查项: "检查闸门开度及运行状态"
  → 匹配 keywords "闸门" → rei_gate_r (sort_order=50)
  → 匹配 keywords "运行" → eq_equip_base (sort_order=60)
  → 两个数据源都查
```

## 测站关联

确定了数据源后，如果 `station_type` 不为空，需要通过巡检点坐标关联最近的测站。

### 测站信息表：dsm_cz_info

| 字段 | 类型 | 说明 |
|------|------|------|
| id | varchar(64) | 主键 |
| code | varchar(18) | 测站编码（如 `1#swz`, `2#swz`） |
| name | varchar(255) | 测站名称 |
| x | decimal(11,4) | 经度(X坐标) |
| y | decimal(11,4) | 纬度(Y坐标) |
| type | char(2) | 类型（1=水位站, 2=GNSS站） |

### Haversine 距离匹配

```python
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    """计算两点间的球面距离（米）"""
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

def find_nearest_station(point_lat, point_lon, station_type, max_dist_m):
    """查找最近的测站"""
    stations = db.query(
        "SELECT id, code, name, x, y FROM dsm_cz_info WHERE type=%s AND deleted=0",
        station_type
    )
    nearest, min_dist = None, max_dist_m
    for s in stations:
        dist = haversine(point_lat, point_lon, float(s['y']), float(s['x']))
        if dist < min_dist:
            min_dist, nearest = dist, s
    return nearest
```

**距离阈值**（从注册表 `max_distance` 字段读取）：

| 数据源 | station_type | max_distance |
|--------|-------------|--------------|
| 水位监测 | '1' | 500m |
| GNSS位移 | '2' | 100m |
| 雨量监测 | — | 5000m |
| 渗压监测 | — | 50m |
| 渗流监测 | — | 50m |

## Agent 采集流程

> 实际实现见 `impl/inspection_analyzer.py`，以下为流程概要。

```python
def generate_report(engine, days=30, limit=5000):
    """巡检报告生成流程（实际实现）"""

    # 1. 加载阈值配置（从 ew_info_rules + sys_data_source_registry 动态读取）
    thresholds = load_thresholds(engine)

    # 2. 按维度逐项分析（每项独立查询数据库）
    analyses = []
    analyses.append(analyze_water_level(engine, days, thresholds))     # st_rsvr_r
    analyses.append(analyze_rainfall(engine, min(days, 7), thresholds)) # st_pptn_r
    analyses.append(analyze_pressure(engine, days, thresholds))         # st_pressure_r
    analyses.append(analyze_percolation(engine, days))                  # st_percolation_r
    analyses.append(analyze_displacement(engine, days, thresholds))     # dsm_dfr_srvrds_srhrds
    analyses.append(analyze_gate(engine, days))                         # rei_gate_r
    analyses.append(analyze_pump(engine, days, thresholds))             # rei_pump_r
    analyses.append(analyze_water_quality(engine, days))                # wq_pcp_d
    analyses.append(analyze_soil_moisture(engine, days))                # st_soil_moisture_r
    analyses.append(analyze_termite(engine, days))                      # st_termite_monitor_r
    analyses.append(analyze_inspection_results(engine, days))           # business_check_task
    analyses.append(analyze_equipment(engine))                          # eq_equip_base
    analyses.append(analyze_alerts(engine, days))                       # ew_info_message
    analyses.append(analyze_mad_anomaly(engine, days, thresholds))      # 第4层：MAD统计异常
    analyses.append(analyze_correlation(engine, min(days, 7), thresholds)) # 第5层：多指标关联

    # 3. 汇总发现，生成报告
    return generate_markdown_report(analyses)
```
```

## 采集频率策略

```
基准频率(business_check_task.task_type):
  日常巡检(task_type=10): 每日1次 (06:00自动采集)
  经常巡检(task_type=20): 每周1次
  定期巡检(task_type=30): 每月1次
  专项巡检: 按需触发

动态调整(基于 ew_info_rules 表):
  if ew_info_rules.extend.condition 触发:
    → 对应传感器采集频率提升至每5分钟

  if 汛期 (6-9月):
    日常巡检 → 每日2次 (06:00 + 18:00)

  if st_river_r.z > ew_info_rules[level_r=3].extend.content[0] (水位超阈值):
    → 水位数据 → 每5分钟采集
    → 渗流数据 → 每15分钟采集
    → GNSS数据 → 每30分钟采集

  if srm_gnss_data_day.speed_gh > 0.5 (位移速率异常):
    → GNSS数据 → 每15分钟采集

  if eq_equip_base.status = 0 (设备离线):
    → 设备状态 → 每5分钟检查
    → 恢复后 → 回到基准频率
```

## 扩展数据源

**新增数据源只需 INSERT 注册表**，无需修改任何规则文件或代码：

```sql
-- 示例：新增水质监测
INSERT INTO sys_data_source_registry
  (name, source_table, keywords, station_type, max_distance,
   query_fields, default_hours, judge_rules, sort_order) VALUES
('水质监测', 'st_wq_r',
 '水质,pH,溶解氧,浊度,氨氮',
 NULL, 1000, 'ph,do,ntu,nh3n,tm', 24,
 '{"thresholds":{"ph_low":6,"ph_high":9,"do_low":5}}',
 35);
```

Agent 下次巡检时自动识别"水质"关键词，查 `st_wq_r` 表。

## SmartTwinRes 扩展数据源

以下数据源来自 SmartTwinRes 水库项目，已注册到 `sys_data_source_registry`：

| 数据源 | 表名 | 匹配关键词 | 说明 |
|--------|------|-----------|------|
| 设备缺陷 | `eq_equip_defect` | 缺陷,设备缺陷,故障,事故缺陷 | 设备缺陷全生命周期 |
| 违法行为 | `srm_illegal_acts` | 违法,违规,非法,钓鱼,采砂 | 巡查中发现的违规行为 |
| 测量机器人 | `srm_robot_data_day` | 机器人,全站仪,精密测量 | 大坝精密变形监测(与GNSS互补) |

> DDL 和预置数据：`docs/sql/smarttwinres-inspection-tables.sql`
