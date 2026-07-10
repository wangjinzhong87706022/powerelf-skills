# SQL 生成规则

> 📖 **典型查询示例库**：见 `references/few_shots.md`（15+ 个水情/雨情/设备/预警/巡检/数据治理/大坝安全领域的 NL→SQL 实例，均含 `deleted=0` 与 `tenant_id=1`）。生成 SQL 前优先检索相似示例。

## NL2SQL 流程

```
用户问题 → Vanna API → SQL → 执行 → 数据

重试机制:
  if SQL执行失败 (BadSqlGrammarException):
    将失败SQL + 错误码 + 原始问题 → 重新提问
    最多重试 4 次
```

## 水利领域表映射

### 水文气象监测表

| 数据类型 | 主表 | 核心字段 | 说明 |
|----------|------|----------|------|
| 水库水情 | st_rsvr_r | rz(库水位m), inq(入库流量m³/s), otq(出库流量m³/s), w(蓄水量), blrz(下游水位m) | 水库实时监测 |
| 河道水情 | st_river_r | z(水位m), q(流量m³/s), xsa(断面面积), xsavv(平均流速) | 河道实时监测 |
| 闸站水情 | st_was_r | upz(上游水位m), dwz(下游水位m), tgtq(总过闸流量m³/s) | 闸站实时监测 |
| 潮汐水情 | st_tide_r | tdz(潮位m), airp(气压), hltdmk(高低潮标记) | 潮汐监测 |
| 防洪区水情 | st_flood_r | z(水位m), q(流量m³/s), fca_id(防洪区ID) | 防洪区监测 |
| 测站雨量 | st_pptn_r | p(时段雨量mm), dr(时段长**min**), dyp(日雨量mm), cump(累计雨量mm) | ⚠️ dr单位是分钟 |
| 分区雨量 | st_pptn_region_r | drp(时段雨量mm), intv(时段长h), dyp(日累计雨量mm), wth(天气) | 区域雨情 |

### 设备工情监测表

| 数据类型 | 主表 | 核心字段 | 说明 |
|----------|------|----------|------|
| 闸门工情 | rei_gate_r | gtq(流量m³/s), gtophgt(开启高度m), gtopnum(开启孔数), status(开关状态bit) | 闸门实时状态 |
| 泵站工情 | rei_pump_r | uab/ubc/uca(电压varchar), ia/ib/ic(电流varchar), p(功率varchar), freq(频率varchar), status(运行状态bit) | ⚠️ 电气参数为varchar |

### 大坝安全监测表

| 数据类型 | 主表 | 核心字段 | 说明 |
|----------|------|----------|------|
| GNSS变形 | dsm_dfr_srvrds_srhrds | wgs84_delta_h/x/y(本次变化mm), wgs84_total_h/x/y(累计变化mm), speed_gh/gx/gy(速率) | GNSS变形监测 |
| 渗流量 | st_percolation_r | percolation(渗流量L/s) | 渗流监测 |
| 渗压 | st_pressure_r | ext_pressure(渗压kPa), water_pressure(水位压力kPa), ext_temperature(温度℃), section_id(断面ID) | 渗压监测 |

### 其他监测表

| 数据类型 | 主表 | 核心字段 | 说明 |
|----------|------|----------|------|
| 墒情 | st_soil_moisture_r | soil_water10cm~100cm(各深度含水量%), soil_temp10cm~100cm(温度℃), ec(电导率), ph, soil_moist_evaluation(评价) | 土壤墒情 |
| 白蚁监测 | st_termite_monitor_r | termite_species(蚁种), pest_density(密度等级0-4), check_result(检查结果) | 白蚁监测 |

### 基础信息表

| 数据类型 | 主表 | 核心字段 | 说明 |
|----------|------|----------|------|
| 设备信息 | eq_equip_base | name(名称), code(编码), type_flag(类型字典), status(0=离线/1=在线/2=异常), st_base_id(关联测站) | 设备主数据 |
| 测站信息 | att_st_base | name(站名), code(站码), type(站类型), longitude/latitude(经纬度), status(0=离线/1=在线/2=异常) | 测站主数据 |
| 预警规则 | ew_info_rules | name(规则名), ew_type(0=水位/1=水质/2=雨量/3=开关变化/4=开关), level_r(等级I-IV), extend(JSON条件) | 预警配置 |
| 预警消息 | ew_info_message | ew_name(预警名), level_r(等级), value(触发值), gather_time(采集时间), message_confirm(确认状态) | 预警记录 |
| 巡检任务 | business_check_task | name(任务名), status(状态), plan_time(计划时间), begin_time/endTime(实际时间), bad_num(缺陷数) | 巡检管理 |
| 巡检缺陷 | business_check_error | problem(问题描述), status(处理状态), deal_time(处理时间) | 缺陷管理 |

## 常见问题模式

```
# 水库查询
"最近一周XX的水位" → SELECT tm, rz, inq, otq FROM st_rsvr_r WHERE st_id = ? AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY) ORDER BY tm
"XX水库的最新数据" → SELECT * FROM st_rsvr_r WHERE st_id = ? ORDER BY tm DESC LIMIT 1

# 河道查询
"XX河道的水位" → SELECT tm, z, q FROM st_river_r WHERE st_id = ? AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY)

# 雨量查询
"今天下了多少雨" → SELECT st_id, SUM(p) as total FROM st_pptn_r WHERE DATE(tm) = CURDATE() GROUP BY st_id
"XX站的日雨量" → SELECT dt, dp FROM st_pptn_dp_s WHERE st_id = ? AND dt > DATE_SUB(NOW(), INTERVAL 30 DAY)

# 设备查询
"哪些设备离线" → SELECT name, code FROM eq_equip_base WHERE status = 0 AND deleted = 0
"XX设备的异常记录" → SELECT * FROM eq_data_anomaly_record WHERE equipment_code = ?

# 预警查询
"最近的预警" → SELECT ew_name, level_r, value, gather_time FROM ew_info_message WHERE deleted = 0 ORDER BY gather_time DESC LIMIT 20
"II级以上的预警" → SELECT * FROM ew_info_message WHERE level_r IN ('1','2') AND gather_time > DATE_SUB(NOW(), INTERVAL 7 DAY)

# 巡检查询
"未完成的巡检任务" → SELECT name, plan_time, status FROM business_check_task WHERE status != 'completed' AND deleted = 0
"本月发现的缺陷" → SELECT problem, create_time FROM business_check_error WHERE MONTH(create_time) = MONTH(NOW())

# 聚合查询
"XX的平均值" → SELECT AVG(field) FROM table WHERE ... AND deleted = 0
"按月统计" → SELECT DATE_FORMAT(tm, '%Y-%m') as month, AVG(rz) FROM st_rsvr_r GROUP BY month
```

## SQL 输出格式

```
## **sql语句**
SELECT * FROM st_rsvr_r WHERE ...

## **数据**
| 水位 | 入库流量 | 出库流量 |
| 150.5 | 120.3 | 80.1 |
```

## 注意事项

- 所有查询需带 `AND deleted = 0` 软删除过滤
- 多租户环境需带 `AND tenant_id = ?` 过滤
- 时间字段格式: tm (datetime)
- 大数据量查询限制: max-num = 2000
- 显示行数: display-num = 20
- 泵站电气参数为 varchar 类型，数值比较前需 CAST 或应用层转换
- dr（时段长）在 st_pptn_r 中单位是**分钟**，在 st_pptn_region_r 中 intv 单位是**小时**
