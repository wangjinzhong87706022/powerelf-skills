---
name: powerelf-monitor
description: "水利工程实时监控：12类监测数据分析规则、趋势异常检测、水位变化率、位移速率计算。规则内嵌，可独立分析。"
version: 2.0.0
author: Powerelf Team
license: MIT
platforms: [linux, windows, macos]
metadata:
  hermes:
    tags: [water-conservancy, real-time-monitoring, sensor, reservoir, dam, gnss]
    related_skills: [powerelf-data-governance, powerelf-early-warning]
prerequisites:
  env_vars: [POWERELF_API_BASE, POWERELF_API_TOKEN]
---

# 实时监控 Skill v2

水利工程实时数据分析引擎。规则内嵌，Agent 可独立分析监测数据。

## 12大监测类型

### 水文气象监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| 水库水情 | st_rsvr_r | rz(库水位m), inq(入库流量m³/s), otq(出库流量m³/s), w(蓄水量), blrz(下游水位m), stcd(站码) | `rules/reservoir-analysis.md` |
| 河道水情 | st_river_r | z(水位m), q(流量m³/s), xsa(断面面积), xsavv(平均流速), xsmxv(最大流速), stcd(站码) | 基本阈值判断 |
| 闸站水情 | st_was_r | upz(上游水位m), dwz(下游水位m), tgtq(总过闸流量m³/s), stcd(站码) | 基本阈值判断 |
| 潮汐水情 | st_tide_r | tdz(潮位m), airp(气压), tdptn(潮位状态), hltdmk(高低潮标记) | 基本阈值判断 |
| 测站雨情 | st_pptn_r | p(时段雨量mm), dr(时段长min), dyp(日雨量mm), cump(累计雨量mm), stcd(站码) | `rules/rainfall-analysis.md` |
| 分区雨情 | st_pptn_region_r | drp(时段雨量mm), intv(时段长h), dyp(日累计雨量mm), wth(天气) | `rules/rainfall-analysis.md` |
| 防洪区水情 | st_flood_r | z(水位m), q(流量m³/s), fca_id(防洪区ID) | 基本阈值判断 |

### 设备工情监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| 闸门工情 | rei_gate_r | gtq(流量m³/s), gtophgt(开启高度m), gtopnum(开启孔数), status(开关状态bit), stcd(站码), slcd(闸码) | `rules/gate-pump-status.md` |
| 泵站工情 | rei_pump_r | uab/ubc/uca(三相电压varchar), ia/ib/ic(三相电流varchar), p(有功功率varchar), freq(频率varchar), speed(转速varchar), status(运行状态bit), angle(叶片角度) | `rules/gate-pump-status.md` |

### 大坝安全监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| GNSS变形 | dsm_dfr_srvrds_srhrds | wgs84_delta_h/x/y(本次变化量mm), wgs84_total_h/x/y(累计变化量mm), speed_gh/gx/gy(速率), point_id(测点ID) | `rules/gnss-deformation.md` |
| 渗流量 | st_percolation_r | percolation(渗流量L/s), stcd(站码), eq_code(设备编码) | 基本阈值判断 |
| 渗压 | st_pressure_r | ext_pressure(渗压kPa), water_pressure(水位压力kPa), ext_temperature(温度℃), section_id(断面ID), point_id(测点ID) | 基本阈值判断 |

### 其他监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| 墒情 | st_soil_moisture_r | soil_water10cm/20cm/30cm/60cm/100cm(各深度含水量%), soil_temp10cm~100cm(各深度温度℃), ec(电导率uS/cm), ph, tension(张力kPa), groundwater_depth(地下水位m), soil_moist_evaluation(评价) | 基本阈值判断 |
| 白蚁监测 | st_termite_monitor_r | termite_species(蚁种), pest_density(密度等级0-4), damage_level(危害等级), check_result(检查结果:无白蚁/发现/疑似痕迹) | 基本阈值判断 |

趋势异常检测：`rules/trend-detection.md`
水位变化率算法：`algorithms/water-level-change.md`
位移速率算法：`algorithms/displacement-rate.md`
时序预测算法（指数平滑/ARIMA/LSTM）：`algorithms/time-series-forecast.md`

## 按需加载指令

```
"水位"/"水库"/"水情"     → rules/reservoir-analysis.md + algorithms/water-level-change.md
"河道"/"河流"           → st_river_r 基本阈值判断
"闸站"/"水闸"           → st_was_r 基本阈值判断
"潮汐"/"潮位"           → st_tide_r 基本阈值判断
"雨量"/"降雨"           → rules/rainfall-analysis.md
"分区雨情"/"区域降雨"    → st_pptn_region_r 基本阈值判断
"闸门"/"泵站"           → rules/gate-pump-status.md
"GNSS"/"位移"/"变形"    → rules/gnss-deformation.md + algorithms/displacement-rate.md
"渗流"/"渗流量"         → st_percolation_r 基本阈值判断
"渗压"/"压力"           → st_pressure_r 基本阈值判断
"墒情"/"土壤"           → st_soil_moisture_r 基本阈值判断
"白蚁"/"蚁害"           → st_termite_monitor_r 基本阈值判断
"趋势"/"异常趋势"       → rules/trend-detection.md
"预测"/"预报"/"ARIMA"/"LSTM" → algorithms/time-series-forecast.md
```

## 自我进化

- 可调参数：`evolution/parameters.md`
- 反馈日志：`evolution/feedback-log.md`

---

## API 附录

| 端点 | 说明 |
|------|------|
| `GET /monitor/overview/get` | 各类型设备在线/离线/异常统计 |
| `GET /monitor/overview/list?type=riverRe` | 某类型详情列表 |
| `GET /srm/river-re/curve?stId=&eqId=&startTime=&endTime=` | 水库水位趋势 |
| `GET /srm/river-re/getBaseInfoByStIds?stIds=` | 批量查最新水库数据 |
| `GET /srm/river-re/getCurrentBlrzWarningList` | 水位变化率预警 |
| `GET /srm/river-r/curve?stId=&eqId=&startTime=&endTime=` | 河道水位趋势 |
| `GET /srm/pptn-r/curve?stId=&eqId=&startTime=&endTime=` | 雨量趋势 |
| `GET /srm/gate-real/all/now` | 所有闸门当前状态 |
| `GET /srm/pump-real/all/now` | 所有泵站当前状态 |
| `GET /srm/gnss-data-day/curve?stId=&eqId=&startTime=&endTime=` | GNSS趋势 |
| `GET /srm/percolation-r/curve?stId=&eqId=&startTime=&endTime=` | 渗流趋势 |
| `GET /srm/pressure-r/curve?stId=&eqId=&startTime=&endTime=` | 渗压趋势 |
| `POST /att/dot-user/concern` | 关注/取消关注 |

通用头与鉴权约定：见 [`../_shared/api-auth.md`](../_shared/api-auth.md)（`Authorization: Bearer ${POWERELF_API_TOKEN}` + `tenant-id: 1`）
