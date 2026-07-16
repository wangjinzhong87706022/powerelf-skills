# 监测数据表结构参考

本文档列出监控分析引擎涉及的所有数据库表结构。数据库: `powerelf_data`。

---

## 水文气象监测

### st_rsvr_r — 水库水情

| 字段 | 类型 | 含义 | 单位 | 说明 |
|------|------|------|------|------|
| stcd | varchar(20) | 站码 | — | 主键之一 |
| tm | datetime | 采集时间 | — | 主键之一 |
| rz | decimal | 库水位 | m | 核心指标 |
| inq | decimal | 入库流量 | m³/s | |
| otq | decimal | 出库流量 | m³/s | |
| w | decimal | 蓄水量 | 万m³ | |
| blrz | decimal | 下游水位 | m | |
| eq_id | bigint | 设备ID | — | |
| st_id | bigint | 测站ID | — | |
| deleted | tinyint | 软删除 | — | 0=正常 |
| tenant_id | bigint | 租户ID | — | 查询需加 tenant_id=1 |

### st_river_r — 河道水情

| 字段 | 类型 | 含义 | 单位 |
|------|------|------|------|
| stcd | varchar(20) | 站码 | — |
| tm | datetime | 采集时间 | — |
| z | decimal | 水位 | m |
| q | decimal | 流量 | m³/s |
| xsa | decimal | 断面面积 | m² |
| xsavv | decimal | 平均流速 | m/s |
| xsmxv | decimal | 最大流速 | m/s |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

### st_pptn_r — 测站雨量

| 字段 | 类型 | 含义 | 单位 | 说明 |
|------|------|------|------|------|
| stcd | varchar(20) | 站码 | — | |
| tm | datetime | 采集时间 | — | |
| p | decimal(5,1) | 时段雨量 | mm | |
| dr | decimal(6,1) | 时段长 | **分钟(min)** | 不是小时! |
| dyp | decimal(5,1) | 日雨量 | mm | |
| cump | decimal(5,1) | 累计雨量 | mm | |
| pdr | decimal(5,5) | 降水历时 | — | |
| eq_id | bigint | 设备ID | — | |
| st_id | bigint | 测站ID | — | |
| deleted | tinyint | 软删除 | — | |
| tenant_id | bigint | 租户ID | — | |

> **重要:** dr 字段单位是**分钟**，计算降雨强度时需转换: `强度 = p / (dr/60)` mm/h

### st_pptn_region_r — 分区雨量

| 字段 | 类型 | 含义 | 单位 | 说明 |
|------|------|------|------|------|
| re_id | bigint | 区域编码 | — | |
| tm | datetime | 采集时间 | — | |
| drp | decimal(6,1) | 时段雨量 | mm | |
| intv | decimal(6,2) | 时段长 | **小时(h)** | 与 st_pptn_r 的 dr 不同! |
| pdr | decimal(6,5) | 降水历时 | h | |
| dyp | decimal(6,1) | 日累计雨量 | mm | |
| wth | char | 天气 | — | |
| deleted | tinyint | 软删除 | — | |
| tenant_id | bigint | 租户ID | — | |

---

## 设备工情监测

### rei_gate_r — 闸门工情

| 字段 | 类型 | 含义 | 单位 |
|------|------|------|------|
| stcd | varchar(20) | 站码 | — |
| slcd | char(18) | 闸码 | — |
| eq_code | varchar(20) | 设备编码 | — |
| tm | datetime | 采集时间 | — |
| gtq | decimal(10,3) | 流量 | m³/s |
| gtophgt | decimal(6,2) | 开启高度 | m |
| gtopnum | tinyint | 开启孔数 | 个 |
| status | bit | 开关状态 | 0=关/1=开 |
| msqmt | char | 流量测法 | — |
| eq_id | bigint | 设备ID | — |
| st_id | bigint | 测站ID | — |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

### rei_pump_r — 泵站工情

| 字段 | 类型 | 含义 | 单位 | 说明 |
|------|------|------|------|------|
| stcd | varchar(20) | 站码 | — | |
| idstcd | char(18) | 泵站编码 | — | |
| eq_code | varchar(20) | 设备编码 | — | |
| tm | datetime | 采集时间 | — | |
| uab/ubc/uca | **varchar** | 三相线电压 | V | 需 parseFloat |
| ia/ib/ic | **varchar** | 三相电流 | A | 需 parseFloat |
| p | **varchar** | 有功功率 | kW | 需 parseFloat |
| q | **varchar** | 无功功率 | kvar | 需 parseFloat |
| cos | **varchar** | 功率因数 | — | 需 parseFloat |
| freq | **varchar** | 频率 | Hz | 需 parseFloat |
| speed | **varchar** | 转速 | rpm | 需 parseFloat |
| angle | **varchar** | 叶片角度 | ° | 需 parseFloat |
| status | bit | 运行状态 | 0=停/1=运行 | |
| lx | decimal(8,1) | 冷却水流量 | L/s | |
| lu | decimal(8,1) | 冷却水压力 | MPa | |
| fan_run | bit | 风机运行 | 0=停/1=运行 | |
| fan_fault | bit | 风机故障 | 0=正常/1=故障 | |
| ot | decimal(8,1) | 进水温度 | ℃ | |
| it | decimal(8,1) | 出水温度 | ℃ | |
| ul | decimal(8,1) | 励磁电压 | V | |
| al | decimal(8,1) | 励磁电流 | A | |
| extend | json | 扩展信息 | — | |
| eq_id | bigint | 设备ID | — | |
| st_id | bigint | 测站ID | — | |
| deleted | tinyint | 软删除 | — | |
| tenant_id | bigint | 租户ID | — | |

> **重要:** 泵站电气参数字段(uab/ia/p/freq等)在数据库中为 **varchar** 类型，数值比较前必须 parseFloat。

---

## 大坝安全监测

### dsm_dfr_srvrds_srhrds — GNSS变形趋势

| 字段 | 类型 | 含义 | 单位 |
|------|------|------|------|
| point_id | varchar | 测点ID | — |
| point_address | varchar | 测点地址 | — |
| st_id | bigint | 测站ID | — |
| eq_id | bigint | 设备ID | — |
| tm | datetime | 观测时间 | — |
| wgs84_delta_h | decimal | 垂直位移变化量 | mm |
| wgs84_delta_x | decimal | 水平X位移变化量 | mm |
| wgs84_delta_y | decimal | 水平Y位移变化量 | mm |
| wgs84_total_h | decimal | H方向累计位移 | mm |
| wgs84_total_x | decimal | X方向累计位移 | mm |
| wgs84_total_y | decimal | Y方向累计位移 | mm |
| speed_gh | decimal | 高程方向速率 | mm/月 |
| speed_gx | decimal | X方向速率 | mm/月 |
| speed_gy | decimal | Y方向速率 | mm/月 |
| speed_rx | varchar | X方向速率(varchar) | — |
| speed_ry | varchar | Y方向速率(varchar) | — |
| data_b | decimal | 纬度 | ° |
| data_l | decimal | 经度 | ° |
| data_h | decimal | 大地高 | m |
| data_x/y/z | decimal | 空间直角坐标 | m |
| data_p | decimal | 平面偏移量 | mm |
| gx_data/gy_data | decimal | 高斯平面坐标 | m |
| distance | decimal | 斜距 | m |
| hangle | decimal | 水平角 | ° |
| vangle | decimal | 垂直角 | ° |
| data_count | int | 观测次数 | 次 |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

### srm_gnss_stat_day — GNSS位移统计日报表

| 字段 | 类型 | 含义 | 单位 |
|------|------|------|------|
| st_id | bigint | 测站ID | — |
| eq_id | bigint | 设备ID | — |
| tm | datetime | 统计日期 | — |
| maxh | decimal | 垂直方向最大值 | mm |
| minh | decimal | 垂直方向最小值 | mm |
| avgh | decimal | 垂直方向平均值 | mm |
| maxx | decimal | X方向最大值 | mm |
| minx | decimal | X方向最小值 | mm |
| avgx | decimal | X方向平均值 | mm |
| maxy | decimal | Y方向最大值 | mm |
| miny | decimal | Y方向最小值 | mm |
| avgy | decimal | Y方向平均值 | mm |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

### st_percolation_r — 渗流量

| 字段 | 类型 | 含义 | 单位 |
|------|------|------|------|
| stcd | varchar(20) | 站码 | — |
| eq_code | varchar(20) | 设备编码 | — |
| tm | datetime | 采集时间 | — |
| percolation | decimal | 渗流量 | L/s |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

### st_pressure_r — 渗压

| 字段 | 类型 | 含义 | 单位 |
|------|------|------|------|
| section_id | varchar | 断面ID | — |
| point_id | varchar | 测点ID | — |
| tm | datetime | 采集时间 | — |
| ext_pressure | decimal | 渗压 | kPa |
| water_pressure | decimal | 水位压力 | kPa |
| ext_temperature | decimal | 温度 | ℃ |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

---

## 其他监测

### st_soil_moisture_r — 墒情

| 字段 | 类型 | 含义 | 单位 |
|------|------|------|------|
| stcd | varchar(20) | 站码 | — |
| tm | datetime | 采集时间 | — |
| soil_water10cm | decimal | 10cm深度含水量 | % |
| soil_water20cm | decimal | 20cm深度含水量 | % |
| soil_water30cm | decimal | 30cm深度含水量 | % |
| soil_water60cm | decimal | 60cm深度含水量 | % |
| soil_water100cm | decimal | 100cm深度含水量 | % |
| soil_temp10cm~100cm | decimal | 各深度温度 | ℃ |
| ec | decimal | 电导率 | uS/cm |
| ph | decimal | pH值 | — |
| tension | decimal | 张力 | kPa |
| groundwater_depth | decimal | 地下水位 | m |
| soil_moist_evaluation | varchar | 评价 | — |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

### st_termite_monitor_r — 白蚁监测

| 字段 | 类型 | 含义 | 说明 |
|------|------|------|------|
| stcd | varchar(20) | 站码 | — |
| tm | datetime | 监测时间 | — |
| termite_species | varchar | 蚁种 | — |
| pest_density | tinyint | 密度等级 | 0-4 |
| damage_level | varchar | 危害等级 | — |
| check_result | varchar | 检查结果 | 无白蚁/发现/疑似痕迹 |
| deleted | tinyint | 软删除 | — |
| tenant_id | bigint | 租户ID | — |

---

## 设备管理 (辅助表)

### eq_equip_base — 设备主数据

| 字段 | 类型 | 含义 | 说明 |
|------|------|------|------|
| name | varchar | 设备名称 | — |
| code | varchar | 设备编码 | — |
| type_flag | tinyint | 设备类型 | — |
| status | tinyint | 设备状态 | 0=离线/1=在线/2=异常 |
| st_base_id | bigint | 测站ID | — |
| rated_power | decimal | 额定功率 | 用于负载率计算 |

### eq_equip_offline_record — 设备离线记录

| 字段 | 类型 | 含义 | 说明 |
|------|------|------|------|
| equipment_code | varchar | 设备编码 | — |
| offline_start_time | datetime | 离线开始时间 | — |
| offline_end_time | datetime | 离线结束时间 | — |
| total_offline_duration | bigint | 总离线时长 | 分钟 |

> **注意:** `eq_equip_offline_record`, `eq_data_missing_record`, `eq_data_anomaly_record`, `eq_equip_anomaly_record` 等设备记录表**没有 `deleted` 列**，查询时不需要加 `deleted=0` 条件。

### eq_data_missing_record — 数据缺失记录

| 字段 | 类型 | 含义 |
|------|------|------|
| equipment_code | varchar | 设备编码 |
| data_missing_datetime | datetime | 缺失时间 |
| data_missing_count | int | 缺失计数 |

### eq_data_anomaly_record — 数据异常记录

| 字段 | 类型 | 含义 |
|------|------|------|
| equipment_code | varchar | 设备编码 |
| data_anomaly_datetime | datetime | 异常时间 |
| whether_fix | tinyint | 是否已修复 |

---

## SQL 通用规则

所有监测数据表查询必须包含:

```sql
AND deleted = 0
AND tenant_id = 1
```

**例外:** `eq_equip_offline_record`, `eq_data_missing_record`, `eq_data_anomaly_record`, `eq_equip_anomaly_record` 没有 `deleted` 列，只需加 `tenant_id=1`。
