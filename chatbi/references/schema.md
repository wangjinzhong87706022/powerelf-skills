# powerelf_data 全库 Schema 参考

> 覆盖 20+ 业务表，按域分组。所有表均有 `id`, `tenant_id`, `creator`, `create_time`, `updater`, `update_time`, `deleted` 基础字段（下文省略）。

---

## 水文气象监测

### st_rsvr_r — 水库水情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| rz | decimal | 库水位(m) |
| inq | decimal | 入库流量(m³/s) |
| otq | decimal | 出库流量(m³/s) |
| w | decimal | 蓄水量(万m³) |
| blrz | decimal | 下游水位(m) |

### st_river_r — 河道水情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| z | decimal | 水位(m) |
| q | decimal | 流量(m³/s) |
| xsa | decimal | 断面面积(m²) |
| xsavv | decimal | 平均流速(m/s) |
| xsmxv | decimal | 最大流速(m/s) |

### st_was_r — 闸站水情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| upz | decimal | 上游水位(m) |
| dwz | decimal | 下游水位(m) |
| tgtq | decimal | 总过闸流量(m³/s) |

### st_tide_r — 潮汐水情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| tdz | decimal | 潮位(m) |
| airp | decimal | 气压(hPa) |
| tdptn | varchar | 潮位状态 |
| hltdmk | varchar | 高低潮标记 |

### st_pptn_r — 测站雨量

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| p | decimal | 时段雨量(mm) |
| dr | int | 时段长(**分钟**) |
| dyp | decimal | 日雨量(mm) |
| cump | decimal | 累计雨量(mm) |

> 注意：`dr` 单位是**分钟**，不是小时。

### st_pptn_region_r — 分区雨量

| 字段 | 类型 | 说明 |
|------|------|------|
| region_id | bigint | 区域ID |
| tm | datetime | 采集时间 |
| drp | decimal | 时段雨量(mm) |
| intv | int | 时段长(**小时**) |
| dyp | decimal | 日累计雨量(mm) |
| wth | varchar | 天气 |

> 注意：`intv` 单位是**小时**。

### st_flood_r — 防洪区水情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| z | decimal | 水位(m) |
| q | decimal | 流量(m³/s) |
| fca_id | bigint | 防洪区ID |

### st_pump_r — 泵站水情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |

---

## 设备工情监测

### rei_gate_r — 闸门工情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| slcd | varchar | 闸码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| gtq | decimal | 流量(m³/s) |
| gtophgt | decimal | 开启高度(m) |
| gtopnum | int | 开启孔数 |
| status | int | 开关状态(bit) |

### rei_pump_r — 泵站工情

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| uab | varchar | A相电压 |
| ubc | varchar | B相电压 |
| uca | varchar | C相电压 |
| ia | varchar | A相电流 |
| ib | varchar | B相电流 |
| ic | varchar | C相电流 |
| p | varchar | 有功功率 |
| freq | varchar | 频率 |
| speed | varchar | 转速 |
| status | int | 运行状态(bit) |
| angle | decimal | 叶片角度 |

> 注意：电气参数为 varchar 类型，数值比较需 CAST。

---

## 大坝安全监测

### dsm_dfr_srvrds_srhrds — GNSS 变形监测

| 字段 | 类型 | 说明 |
|------|------|------|
| point_id | varchar | 测点ID |
| tm | datetime | 采集时间 |
| wgs84_delta_h | decimal | 本次高程变化量(mm) |
| wgs84_delta_x | decimal | 本次X方向变化量(mm) |
| wgs84_delta_y | decimal | 本次Y方向变化量(mm) |
| wgs84_total_h | decimal | 累计高程变化量(mm) |
| wgs84_total_x | decimal | 累计X方向变化量(mm) |
| wgs84_total_y | decimal | 累计Y方向变化量(mm) |
| speed_gh | decimal | 高程方向速率 |
| speed_gx | decimal | X方向速率 |
| speed_gy | decimal | Y方向速率 |

### srm_gnss_stat_day — GNSS 日统计

| 字段 | 类型 | 说明 |
|------|------|------|
| point_id | varchar | 测点ID |
| tm | datetime | 统计日期 |
| stat_data | json | 统计数据 |

### st_percolation_r — 渗流量监测

| 字段 | 类型 | 说明 |
|------|------|------|
| stcd | varchar | 站码 |
| st_id | bigint | 测站ID |
| eq_code | varchar | 设备编码 |
| tm | datetime | 采集时间 |
| percolation | decimal | 渗流量(L/s) |

### st_pressure_r — 渗压监测

| 字段 | 类型 | 说明 |
|------|------|------|
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| ext_pressure | decimal | 渗压(kPa) |
| water_pressure | decimal | 水位压力(kPa) |
| ext_temperature | decimal | 温度(℃) |
| section_id | bigint | 断面ID |
| point_id | varchar | 测点ID |

---

## 其他监测

### st_soil_moisture_r — 墒情监测

| 字段 | 类型 | 说明 |
|------|------|------|
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| soil_water10cm | decimal | 10cm深度含水量(%) |
| soil_water20cm | decimal | 20cm深度含水量(%) |
| soil_water30cm | decimal | 30cm深度含水量(%) |
| soil_water60cm | decimal | 60cm深度含水量(%) |
| soil_water100cm | decimal | 100cm深度含水量(%) |
| soil_temp10cm | decimal | 10cm深度温度(℃) |
| soil_temp20cm | decimal | 20cm深度温度(℃) |
| soil_temp30cm | decimal | 30cm深度温度(℃) |
| soil_temp60cm | decimal | 60cm深度温度(℃) |
| soil_temp100cm | decimal | 100cm深度温度(℃) |
| ec | decimal | 电导率(uS/cm) |
| ph | decimal | pH值 |
| tension | decimal | 张力(kPa) |
| groundwater_depth | decimal | 地下水位(m) |
| soil_moist_evaluation | varchar | 墒情评价 |

### st_termite_monitor_r — 白蚁监测

| 字段 | 类型 | 说明 |
|------|------|------|
| st_id | bigint | 测站ID |
| tm | datetime | 采集时间 |
| termite_species | varchar | 蚁种 |
| pest_density | int | 密度等级(0-4) |
| damage_level | varchar | 危害等级 |
| check_result | varchar | 检查结果(无白蚁/发现/疑似痕迹) |

---

## 预警系统

### ew_info_rules — 预警规则

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 规则名称 |
| ew_type | int | 预警类型(0=水位/1=水质/2=雨量/3=开关变化/4=开关/5=大坝/6=洪水) |
| level_r | varchar | 预警等级(1=I级/2=II级/3=III级/4=IV级) |
| extend | json | 触发条件(JSON) |
| status | int | 启用状态 |
| st_id | bigint | 关联测站ID |
| eq_id | bigint | 关联设备ID |
| dot_id | bigint | 关联测点ID |

### ew_info_rules_dam — 大坝预警规则

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 规则名称 |
| ew_type | int | 预警类型 |
| level_r | varchar | 预警等级 |
| extend | json | 触发条件(JSON) |
| dam_id | bigint | 大坝ID |
| section_id | bigint | 断面ID |
| point_ids | json | 测点ID列表 |
| trigger_number | int | 触发所需测点数量 |

### ew_info_message — 预警消息

| 字段 | 类型 | 说明 |
|------|------|------|
| ew_name | varchar | 预警名称 |
| ew_type | int | 预警类型 |
| level_r | varchar | 预警等级 |
| value | varchar | 触发值 |
| gather_time | datetime | 采集时间 |
| ew_rules_id | bigint | 关联规则ID |
| message_confirm | int | 确认状态 |
| dam_id | bigint | 大坝ID |
| section_id | bigint | 断面ID |

### ew_notice_tactics — 通知策略

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 策略名称 |
| ew_level | varchar | 适用预警等级 |
| ew_rules_type | int | 适用预警类型 |
| notice_manner | varchar | 通知方式 |
| silence_time | int | 沉默期(分钟) |
| enable | int | 启用状态 |
| st_ids | varchar | 关联测站IDs |

### ew_notice_record — 通知记录

| 字段 | 类型 | 说明 |
|------|------|------|
| ew_info_id | bigint | 关联预警消息ID |
| notice_message | varchar | 通知内容 |
| notice_type | int | 通知类型(1=短信/2=邮件/3=站内/4=声光/5=微信/6=钉钉) |
| notice_status | int | 通知状态 |

### ew_camera_info — 视频AI报警

| 字段 | 类型 | 说明 |
|------|------|------|
| st_id | bigint | 关联测站ID |
| device_id | varchar | 设备ID |
| alarm_code | varchar | 报警编码(UUID) |
| alarm_stat | int | 报警状态(1=产生/2=消失) |
| alarm_grade | varchar | 报警等级 |
| type | varchar | 报警类型 |
| confirm | int | 确认状态 |
| info | varchar | 报警信息 |

---

## 设备管理

### eq_equip_base — 设备主数据

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 设备名称 |
| code | varchar | 设备编码 |
| type_flag | varchar | 设备类型(字典) |
| status | int | 状态(0=离线/1=在线/2=异常) |
| st_base_id | bigint | 关联测站ID |

### eq_data_missing_record — 数据缺失记录

| 字段 | 类型 | 说明 |
|------|------|------|
| equipment_code | varchar | 设备编码 |
| data_missing_datetime | datetime | 缺失时间 |
| data_missing_count | int | 缺失数量 |
| whether_add | int | 是否补录 |
| filled_data_content | json | 补录数据内容 |
| table_name | varchar | 数据表名 |

### eq_data_anomaly_record — 数据异常记录

| 字段 | 类型 | 说明 |
|------|------|------|
| equipment_code | varchar | 设备编码 |
| data_anomaly_datetime | datetime | 异常时间 |
| whether_fix | int | 是否修复 |
| fix_data_content | json | 修复数据内容 |
| table_name | varchar | 数据表名 |

### eq_equip_offline_record — 设备离线记录

| 字段 | 类型 | 说明 |
|------|------|------|
| equipment_code | varchar | 设备编码 |
| offline_start_time | datetime | 离线开始时间 |
| offline_end_time | datetime | 离线结束时间 |
| total_offline_duration | bigint | 累计离线时长(秒) |

### eq_equip_anomaly_record — 设备异常记录

| 字段 | 类型 | 说明 |
|------|------|------|
| equipment_code | varchar | 设备编码 |
| anomaly_start_time | datetime | 异常开始时间 |
| anomaly_end_time | datetime | 异常结束时间 |
| total_anomaly_duration | bigint | 累计异常时长(秒) |

---

## 巡检管理

### business_check_task — 巡检任务

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 任务名称 |
| serial | varchar | 任务编号 |
| task_type | varchar | 任务类型 |
| route_id | bigint | 关联路线ID |
| plan_time | datetime | 计划时间 |
| begin_time | datetime | 实际开始时间 |
| end_time | datetime | 实际结束时间 |
| status | varchar | 任务状态 |
| plan_checknum | int | 计划检查数 |
| real_checknum | int | 实际检查数 |
| bad_num | int | 缺陷数 |
| exceed_time | int | 超时时间 |

### business_check_route — 巡检路线

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 路线名称 |
| serial | varchar | 路线编号 |
| type | varchar | 路线类型 |
| status | varchar | 路线状态 |
| max_time | int | 最大巡检时间(分钟) |
| standard | varchar | 巡检标准 |
| select_id | varchar | 巡检点IDs |
| in_order | int | 是否按顺序 |

### business_check_result — 巡检结果

| 字段 | 类型 | 说明 |
|------|------|------|
| serial | varchar | 结果编号 |
| result | int | 结果(0=正常/1=异常) |
| obj_id | bigint | 巡检对象ID |
| task_serial | varchar | 任务编号 |
| problem | varchar | 问题描述 |
| lon_lat | varchar | 经纬度 |

### business_check_error — 巡检缺陷

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | bigint | 关联任务ID |
| obj_id | bigint | 关联对象ID |
| result_id | bigint | 关联结果ID |
| problem | varchar | 问题描述 |
| status | varchar | 处理状态 |
| deal_time | datetime | 处理时间 |
| deal_type | varchar | 处理方式 |

### business_check_obj — 巡检对象

| 字段 | 类型 | 说明 |
|------|------|------|
| obj_name | varchar | 对象名称 |
| obj_id | bigint | 对象ID |
| obj_leibie | int | 对象类别(1=设备/2=建筑物/3=自定义) |
| type_id | bigint | 类型ID |
| point_id | bigint | 关联巡检点ID |

### business_check_point — 巡检点

| 字段 | 类型 | 说明 |
|------|------|------|
| point_serial | varchar | 巡检点编号 |
| point_name | varchar | 巡检点名称 |
| location_way | int | 定位方式(1=GPS/2=RFID/3=二维码) |
| lon_lat | varchar | 经纬度 |
| rfid_id | varchar | RFID编码 |
| qr_code | varchar | 二维码 |

---

## 数据治理

### dg_equip_offline — 离线阈值配置

| 字段 | 类型 | 说明 |
|------|------|------|
| st_type | varchar | 站类型 |
| tm | int | 离线阈值(分钟) |
| frequency | int | 采集频率(分钟) |

### eq_business_equip_relation — 设备-业务映射

| 字段 | 类型 | 说明 |
|------|------|------|
| business_table | varchar | 业务表名 |
| eq_id | bigint | 设备ID |
| st_id | bigint | 测站ID |
| st_type | varchar | 站类型 |
| frequency | int | 采集频率 |
| offline_threshold | int | 离线阈值 |

### stats_data_collection_daily — 每日采集统计

| 字段 | 类型 | 说明 |
|------|------|------|
| collection_data_number | int | 采集数据条数 |
| tm | datetime | 统计日期 |
| table_name | varchar | 数据表名 |

### stats_data_missing_daily — 每日缺失统计

| 字段 | 类型 | 说明 |
|------|------|------|
| missing_data_number | int | 缺失数据条数 |
| tm | datetime | 统计日期 |
| table_name | varchar | 数据表名 |

### stats_data_anomaly_daily — 每日异常统计

| 字段 | 类型 | 说明 |
|------|------|------|
| anomaly_data_number | int | 异常数据条数 |
| tm | datetime | 统计日期 |
| table_name | varchar | 数据表名 |

---

## 基础信息

### att_st_base — 测站信息

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 站名 |
| code | varchar | 站码 |
| type | varchar | 站类型 |
| longitude | decimal | 经度 |
| latitude | decimal | 纬度 |
| status | int | 状态(0=离线/1=在线/2=异常) |

### att_dam_base — 大坝信息

| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar | 大坝名称 |
| ... | ... | 大坝基础属性 |
