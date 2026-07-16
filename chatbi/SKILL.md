---
name: powerelf-chatbi
description: "NL2SQL智能查询 — 用自然语言查数据库，生成SQL并执行。不知道查什么表时用这个。覆盖powerelf_data全库20+表。"
version: 2.0.0
author: dataagent-powerelf
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chatbi, nl2sql, sql, query, visualization, knowledge-base, water-conservancy]
    category: powerelf
---

# ChatBI NL2SQL 智能查询

自然语言转 SQL 查询引擎，覆盖 powerelf_data 全库 20+ 业务表，支持水文气象、设备工情、大坝安全、预警、巡检、数据治理等全域查询。

## When to Use

| Scenario | Use This Skill |
|----------|---------------|
| 用户用自然语言提问（"查"、"多少"、"几个"、"哪些"） | Yes |
| 需要跨表关联查询（水位+预警、设备+巡检等） | Yes |
| 不确定查哪张表，需要意图→表映射 | Yes |
| 需要 SQL 生成、执行、格式化输出 | Yes |
| 需要数据可视化（ECharts 图表） | Yes |
| 已知具体表和字段，直接写 SQL | **No，直接用 db.py** |

## Prerequisites

- **数据库:** **本地 MySQL** `127.0.0.1:3306/powerelf_data`（环境变量 POWERELF_DB_* / SRM_DB_*）
- **DB 助手:** **必须用** `skills/powerelf/lib/db.py`（不要用 water-resources 的）

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from db import query
```
- **SQL 安全:** 参考 `shared/sql_safety_rules.md`
- **Schema 参考:** `references/schema.md` — 全库表结构
- **业务规则:** `references/business_rules.md` — 表映射、SQL 模式、JOIN 规则
- **Few-Shots:** `references/few_shots.md` — 15+ 常见查询示例

## Workflow

```
用户问题
  │
  ▼
1. 意图分类 ──→ 提取关键词，匹配查询意图（水情/雨情/设备/预警/巡检/数据治理）
  │
  ▼
2. 确定时间范围 🔴 CHECKPOINT
  │               用户说了"最近一周"→ INTERVAL 7 DAY
  │               用户说了"本月"→ MONTH(tm) = MONTH(NOW())
  │               用户未指定时间 → 先查数据实际范围:
  │                 SELECT MIN(tm), MAX(tm) FROM powerelf_data.{主表} WHERE tenant_id=1
  │               用实际范围作为默认，避免查空数据
  │               SQL 必须带时间条件，禁止全表扫描
  │
  ▼
3. 表映射 ──→ 根据意图确定主表和关联表（参考 references/business_rules.md）
  │
  ▼
4. SQL 生成 ──→ 构建 SELECT 语句，确保包含 deleted=0 和 tenant_id=1
  │               参考 references/few_shots.md 中的模式
  │               治理记录表(eq_data_*/eq_equip_*)无 deleted 列，不要加 deleted=0
  │
  ▼
5. SQL 执行 ──→ 调用 db.py 执行查询
  │               import sys, os
  │               sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
  │               from db import query
  │               rows = query("SELECT ...", db='powerelf_data')
  │
  ▼
6. 输出格式化 ──→ 表格 + 可选 ECharts 图表 + 数据解读
```

### 重试机制

SQL 执行失败（BadSqlGrammarException）时：
1. 将失败 SQL + 错误码 + 原始问题重新提交生成
2. 最多重试 4 次

## Key Tables

### 水文气象监测

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| st_rsvr_r | 水库水情 | rz(库水位), inq(入库流量), otq(出库流量), w(蓄水量), blrz(下游水位) |
| st_river_r | 河道水情 | z(水位), q(流量), xsa(断面面积), xsavv(平均流速) |
| st_was_r | 闸站水情 | upz(上游水位), dwz(下游水位), tgtq(总过闸流量) |
| st_tide_r | 潮汐水情 | tdz(潮位), airp(气压), hltdmk(高低潮标记) |
| st_pptn_r | 测站雨量 | p(时段雨量mm), dr(时段长min), dyp(日雨量), cump(累计雨量) |
| st_pptn_region_r | 分区雨量 | drp(时段雨量), intv(时段长h), dyp(日累计雨量), wth(天气) |
| st_flood_r | 防洪区水情 | z(水位), q(流量), fca_id(防洪区ID) |
| st_pump_r | 泵站水情 | 泵站运行数据 |

### 设备工情

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| rei_gate_r | 闸门工情 | gtq(流量), gtophgt(开启高度), gtopnum(开启孔数), status(开关状态) |
| rei_pump_r | 泵站工情 | uab/ubc/uca(电压), ia/ib/ic(电流), p(功率), freq(频率), status(运行状态) |

### 大坝安全

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| dsm_dfr_srvrds_srhrds | GNSS变形 | wgs84_delta_h/x/y(本次变化mm), wgs84_total_h/x/y(累计变化mm), speed_gh/gx/gy(速率) |
| srm_gnss_stat_day | GNSS日统计 | GNSS 每日统计汇总 |
| st_percolation_r | 渗流量 | percolation(渗流量L/s) |
| st_pressure_r | 渗压 | ext_pressure(渗压kPa), water_pressure(水位压力), ext_temperature(温度), section_id(断面ID) |

### 其他监测

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| st_soil_moisture_r | 墒情 | soil_water10cm~100cm(各深度含水量%), ec(电导率), ph |
| st_termite_monitor_r | 白蚁监测 | termite_species(蚁种), pest_density(密度等级0-4), check_result(检查结果) |

### 预警

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| ew_info_rules | 预警规则 | name, ew_type(0~6), level_r, extend(JSON条件) |
| ew_info_rules_dam | 大坝预警规则 | name, ew_type, level_r, dam_id, section_id, trigger_number |
| ew_info_message | 预警消息 | ew_name, level_r, value, gather_time, message_confirm |
| ew_notice_tactics | 通知策略 | name, ew_level, notice_manner, silence_time |
| ew_notice_record | 通知记录 | ew_info_id, notice_type(1~6), notice_status |
| ew_camera_info | 视频AI报警 | device_id, alarm_code, alarm_stat(1=产生/2=消失), alarm_grade |

### 设备管理

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| eq_equip_base | 设备主数据 | name, code, type_flag, status(0=离线/1=在线/2=异常), st_base_id |
| eq_data_missing_record | 数据缺失记录 | equipment_code, data_missing_datetime, data_missing_count |
| eq_data_anomaly_record | 数据异常记录 | equipment_code, data_anomaly_datetime, whether_fix |
| eq_equip_offline_record | 设备离线记录 | equipment_code, offline_start_time, offline_end_time, total_offline_duration |
| eq_equip_anomaly_record | 设备异常记录 | equipment_code, anomaly_start_time, anomaly_end_time, total_anomaly_duration |

### 巡检

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| business_check_task | 巡检任务 | name, serial, task_type, plan_time, begin_time, end_time, status, bad_num |
| business_check_route | 巡检路线 | name, serial, type, status, max_time, select_id(巡检点IDs) |
| business_check_result | 巡检结果 | serial, result(0=正常/1=异常), obj_id, task_serial, problem |
| business_check_error | 巡检缺陷 | task_id, obj_id, problem, status, deal_time, deal_type |
| business_check_obj | 巡检对象 | obj_name, obj_id, obj_leibie(1=设备/2=建筑物/3=自定义) |
| business_check_point | 巡检点 | point_serial, point_name, location_way(1=GPS/2=RFID/3=二维码) |

### 数据治理

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| dg_equip_offline | 离线阈值配置 | st_type(站类型), tm(阈值min), frequency(采集频率min) |
| eq_business_equip_relation | 设备-业务映射 | business_table, eq_id, st_id, st_type, frequency |
| stats_data_collection_daily | 每日采集统计 | collection_data_number, tm(日期), table_name |
| stats_data_missing_daily | 每日缺失统计 | missing_data_number, tm(日期), table_name |
| stats_data_anomaly_daily | 每日异常统计 | anomaly_data_number, tm(日期), table_name |

### 基础信息

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| att_st_base | 测站信息 | name(站名), code(站码), type(站类型), longitude/latitude, status |
| att_dam_base | 大坝信息 | 大坝基础属性数据 |

## Business Rules

### SQL 必备条件

所有查询必须包含：
```sql
AND deleted = 0    -- 软删除过滤
AND tenant_id = 1  -- 多租户过滤
```

### 数据量限制

- 最大返回行数：2000
- 显示行数：20
- 大数据量查询加 `LIMIT` 限制

### 时间字段

- 时序数据主时间字段：`tm`（datetime 格式）
- 时间范围查询使用 `DATE_SUB(NOW(), INTERVAL n DAY/HOUR/MINUTE)`

### 特殊注意

- `st_pptn_r` 的 `dr` 单位是**分钟**，`st_pptn_region_r` 的 `intv` 单位是**小时**
- `rei_pump_r` 电气参数为 varchar 类型，数值比较需 CAST
- 预警等级 `level_r`: 1=I级(特别严重), 2=II级(严重), 3=III级(较重), 4=IV级(一般)
- 设备状态 `status`: 0=离线, 1=在线, 2=异常

## Related Skills

| Skill | 说明 |
|-------|------|
| powerelf-monitor | 实时监控分析 — 12类监测数据趋势异常检测 |
| powerelf-early-warning | 预警系统 — 阈值/开关/状态变化/大坝安全预警 |
| powerelf-inspection | 智能巡检 — 任务管理、缺陷预测、质量评估 |
| powerelf-data-governance | 数据治理 — 缺失检测、异常检测、质量评分 |
