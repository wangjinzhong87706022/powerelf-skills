---
name: powerelf-intelligent-inspection
description: 水利工程智能巡检智能体 + 实时监测
version: 7.1.0
author: PowerELF Team; Integrated AI Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [inspection, anomaly-detection, water-conservancy, dam-safety, real-time-monitoring]
    category: industrial
---

# 水利工程智能巡检智能体

融合传感器数据分析（15维度异常检测）与巡检业务管理（任务/路线/缺陷）于一体的水利工程智能巡检 AI 智能体，同时具备实时监测数据分析能力（12类监测类型、趋势预测、水位变化率、位移速率）。

## 架构概览

本系统由两大模式深度融合而成：

**模式一：深度巡检（Python + Hermes Agent + MySQL）**
- 15 维度传感器异常检测（水位、雨量、渗压、渗流、位移、闸门、泵站、水质、墒情、白蚁、巡检结果、设备状态、告警、MAD统计、多指标关联）
- 5 层异常判定体系（阈值 → 变化率 → 趋势 → MAD统计 → 相关性）
- 4 维度质量评分模型（完成率30分 + 及时率25分 + 缺陷发现率25分 + 路线覆盖率20分）
- 缺陷趋势预测 + 路线效率优化
- 规则自演化（反馈驱动的阈值适应/异常规则生成/置信度校准）
- 巡检业务管理（任务/路线/缺陷/报告）

**模式二：实时监测（REST API + 规则引擎）**
- 12 类监测类型覆盖（水文气象、设备工情、大坝安全）
- 3 类时序预测算法（Holt-Winters / ARIMA / LSTM）
- Mann-Kendall 趋势检测 + 变点检测 + 周期性检测
- 水位变化率百分比公式 + 位移速率 cm/月 分级
- 分区雨情分析 + 雨量数据校验
- 库容平衡校验
- 轻量级 API 访问（无需直连数据库）

## 目录结构

```
智能巡检/
├── SKILL.md                    # 本文件 — 整合版技能描述
├── lib/
│   ├── __init__.py
│   ├── db.py                   # 数据库连接（环境变量驱动）
│   ├── anomaly.py              # 5层异常判定内核（阈值/变化率/趋势/MAD/相关性）
│   ├── quality.py              # 4维度质量评分内核（完成/及时/缺陷/覆盖率）
│   ├── defect_predict.py       # 缺陷趋势预测内核（线性/季节/贝叶斯热点）
│   └── route_opt.py            # 路线优化内核（聚类/时间均衡/优先级）
├── impl/                       # 可执行分析工具
│   ├── inspection_analyzer.py  # 15维度异常检测引擎
│   ├── inspection_tool.py      # 质量评分/缺陷预测/路线优化
│   └── test_inspection.py      # 24个自动化测试用例
├── rules/                      # 13个规则文件（AI Agent 阅读）
│   ├── intelligent-inspection.md           # 智能巡检主规则
│   ├── anomaly-and-complex-conditions.md   # 异常与复杂场景
│   ├── quality-assessment.md               # 质量评估
│   ├── defect-classification.md            # 缺陷分类
│   ├── defect-prediction.md                # 缺陷预测
│   ├── route-optimization.md               # 路线优化
│   ├── data-collection-strategy.md         # 数据采集策略
│   ├── scheduling-rules.md                 # 调度规则
│   ├── task-lifecycle.md                   # 任务生命周期
│   ├── rule-evolution.md                   # 规则自演化
│   ├── rainfall-analysis.md                # 雨情分析（实时监测）
│   ├── reservoir-analysis.md               # 水库水情分析（实时监测）
│   └── trend-detection.md                  # 趋势异常检测（实时监测）
├── algorithms/                 # 算法文档
│   ├── anomaly-detection-hierarchy.md      # 异常判定层级
│   ├── mad-statistical-method.md           # MAD统计方法
│   ├── quality-scoring-model.md            # 质量评分模型
│   ├── multi-index-correlation.md          # 多指标关联
│   ├── trend-prediction.md                 # 趋势预测（线性回归）
│   ├── time-series-forecast.md             # 时序预测（Holt-Winters/ARIMA/LSTM）
│   ├── water-level-change.md               # 水位变化率算法
│   └── displacement-rate.md                # 位移速率算法
├── references/                 # 参考文档
│   ├── api-reference.md        # Java 后端 REST API 参考
│   └── data-model.md           # 数据库 ER 模型
├── evolution/                  # 自调优
│   ├── parameters.md
│   └── feedback-log.md
└── autoresearch/               # 自动实验基线
```

## 前置条件

### 环境变量（深度巡检 — 数据库直连）

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `POWERELF_DB_HOST` | 数据库主机 | `localhost` |
| `POWERELF_DB_PORT` | 数据库端口 | `3306` |
| `POWERELF_DB_NAME` | 数据库名 | `powerelf_srm_yml` |
| `POWERELF_DB_USER` | 数据库用户 | `root` |
| `POWERELF_DB_PASSWORD` | 数据库密码 | （必填） |

> 连接层已统一至 `../_shared/lib/db.py`（本 skill 的 `lib/db.py` 为转发 shim），
> 同样支持旧名 `SRM_DB_*` 后备。CLI 工具的 `--db "$DB_URL"` 需先 source 引导脚本：
> `source ../_shared/bootstrap.sh`（会正确尊重 `POWERELF_DB_PORT`）。

### 环境变量（实时监测 — REST API）

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `POWERELF_API_BASE` | API 基础地址 | 必填，如 `https://srm.example.com` |
| `POWERELF_API_TOKEN` | Bearer Token | 必填 |

### Python 依赖

```bash
pip install pandas numpy sqlalchemy pymysql scikit-learn
```

## 深度巡检模式

### 工具命令

#### 1. 传感器巡检分析（15维度）

```bash
python3 impl/inspection_analyzer.py --db "$DB_URL"
python3 impl/inspection_analyzer.py --db "$DB_URL" --days 30 --output report.md
python3 impl/inspection_analyzer.py --db "$DB_URL" --days 7 --json
```

分析维度：水库水情、雨量、渗压、渗流、GNSS位移、闸门、泵站、水质、墒情、白蚁、巡检结果、设备状态、告警、MAD统计异常、多指标关联异常

#### 2. 质量评分 / 缺陷预测 / 路线分析

```bash
python3 impl/inspection_tool.py --mode full --db "$DB_URL" --start 2026-01-01 --end 2026-12-31
python3 impl/inspection_tool.py --mode quality --db "$DB_URL"
python3 impl/inspection_tool.py --mode defects --db "$DB_URL" --months 6
python3 impl/inspection_tool.py --mode routes --db "$DB_URL"
python3 impl/inspection_tool.py --mode registry --db "$DB_URL"
```

#### 3. 自动化测试

```bash
python3 impl/test_inspection.py --db "$DB_URL" --days 7
```

### 15 分析维度一览

| # | 维度 | 数据表 | 检测方法 |
|---|------|--------|----------|
| 1 | 水库水情 | `st_rsvr_r` | 水位趋势/突变/出入库平衡 |
| 2 | 雨量 | `st_pptn_r` | 24h累计/暴雨分级(红橙黄蓝) |
| 3 | 渗压 | `st_pressure_r` | 连续上升/突变/MAD统计 |
| 4 | 渗流 | `st_percolation_r` | 突变/统计异常 |
| 5 | GNSS位移 | `dsm_dfr_srvrds_srhrds` | 速率/累计/加速异常 |
| 6 | 闸门 | `rei_gate_r` | 开度突变/频繁波动/流量异常 |
| 7 | 泵站 | `rei_pump_r` | 三相不平衡/频率异常 |
| 8 | 水质 | `wq_pcp_d` | pH/DO/NH3N/TN/TP 阈值 |
| 9 | 墒情 | `st_soil_moisture_r` | 干旱评估/深层湿度 |
| 10 | 白蚁 | `st_termite_monitor_r` | 蚁情检测/危害等级 |
| 11 | 巡检结果 | `business_check_task` | 完成率/遗漏率/缺陷率 |
| 12 | 设备状态 | `eq_equip_base` | 在线率/离线/异常设备 |
| 13 | 告警分析 | `ew_info_message` | 告警等级/未确认识别 |
| 14 | MAD统计异常 | 多传感器 | Modified Z-Score 跨传感器 |
| 15 | 多指标关联 | 多传感器 | 水位-渗压/水位-流量/降雨-水位 |

### 5 层异常判定体系

```
第1层: 阈值判定 (绝对越限)
  └─ 超标 → 第2层
第2层: 变化率检测 (突变)
  └─ 突变且无外部因素 → 第3层
第3层: 趋势检测 (单向持续)
  └─ 同向持续达阈值 → 第4层
第4层: MAD统计异常 (离群点)
  └─ 统计异常 → 第5层
第5层: 多指标关联 (矛盾分析)
  └─ 关联异常 → CRITICAL
```

置信度公式: `0.3×阈值分 + 0.2×数据质量 + 0.2×趋势分 + 0.2×历史分 + 0.1×上下文分`
- >85%: 直接推送
- 60-85%: 推送+建议确认
- <60%: 必须人工确认

### 巡检业务数据模型

详见 `references/data-model.md`。关键实体：

| 实体 | 表名 | 用途 |
|------|------|------|
| 巡检任务 | `business_check_task` | 谁在何时巡检什么，状态/结果 |
| 巡检路线 | `business_check_route` | 路线定义（包含巡检点列表） |
| 巡检点 | `business_check_point` | 物理巡检位置（GPS/RFID/QR） |
| 巡检对象 | `business_check_obj` | 被巡检的设备/建筑/自定义 |
| 巡检项 | `business_check_obj_type_item` | 具体的检查要求 |
| 巡检结果 | `business_check_result` | 正常/异常 + 处理意见 |
| 缺陷记录 | `business_check_error` | 异常项生成的缺陷工单 |

状态流转：`1(待巡检) → 2(巡检中) → 3(已完成)`

### 边界规则

#### Agent 必须请求人工确认的场景
1. CRITICAL 级别异常（如渗压骤升、大坝位移加速）
2. 设备缺陷处理方案（维修/更换决策）
3. 巡检路线调整（增减巡检点）
4. 汛期应急响应触发
5. 违法行为上报

#### Agent 不可做的 5 件事
1. 不可自动触发应急预案
2. 不可自动修改预警阈值
3. 不可自动确认告警
4. 数据不足时不可下结论（<10个数据点）
5. 不可跳过现场确认环节

## 实时监测模式

12 类监测数据实时分析引擎，通过 REST API 访问数据，规则内嵌，Agent 可独立分析。

### 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `POWERELF_API_BASE` | API 基础地址 | `https://srm.example.com` |
| `POWERELF_API_TOKEN` | API 鉴权 Token | （必填） |

通用请求头：
```
Authorization: Bearer ${POWERELF_API_TOKEN}
tenant-id: 1
```

### 12 大监测类型

#### 水文气象监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| 水库水情 | st_rsvr_r | rz(库水位m), inq(入库流量m³/s), otq(出库流量m³/s), w(蓄水量), blrz(下游水位m), stcd(站码) | `rules/reservoir-analysis.md` |
| 河道水情 | st_river_r | z(水位m), q(流量m³/s), xsa(断面面积), xsavv(平均流速), xsmxv(最大流速), stcd(站码) | 基本阈值判断 |
| 闸站水情 | st_was_r | upz(上游水位m), dwz(下游水位m), tgtq(总过闸流量m³/s), stcd(站码) | 基本阈值判断 |
| 潮汐水情 | st_tide_r | tdz(潮位m), airp(气压), tdptn(潮位状态), hltdmk(高低潮标记) | 基本阈值判断 |
| 测站雨情 | st_pptn_r | p(时段雨量mm), dr(时段长min), dyp(日雨量mm), cump(累计雨量mm), stcd(站码) | `rules/rainfall-analysis.md` |
| 分区雨情 | st_pptn_region_r | drp(时段雨量mm), intv(时段长h), dyp(日累计雨量mm), wth(天气) | `rules/rainfall-analysis.md` |
| 防洪区水情 | st_flood_r | z(水位m), q(流量m³/s), fca_id(防洪区ID) | 基本阈值判断 |

#### 设备工情监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| 闸门工情 | rei_gate_r | gtq(流量m³/s), gtophgt(开启高度m), gtopnum(开启孔数), status(开关状态bit), stcd(站码), slcd(闸码) | `rules/anomaly-and-complex-conditions.md` |
| 泵站工情 | rei_pump_r | uab/ubc/uca(三相电压varchar), ia/ib/ic(三相电流varchar), p(有功功率varchar), freq(频率varchar), speed(转速varchar), status(运行状态bit), angle(叶片角度) | `rules/anomaly-and-complex-conditions.md` |

#### 大坝安全监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| GNSS变形 | dsm_dfr_srvrds_srhrds | wgs84_delta_h/x/y(本次变化量mm), wgs84_total_h/x/y(累计变化量mm), speed_gh/gx/gy(速率), point_id(测点ID) | `rules/anomaly-and-complex-conditions.md` |
| 渗流量 | st_percolation_r | percolation(渗流量L/s), stcd(站码), eq_code(设备编码) | 基本阈值判断 |
| 渗压 | st_pressure_r | ext_pressure(渗压kPa), water_pressure(水位压力kPa), ext_temperature(温度℃), section_id(断面ID), point_id(测点ID) | 基本阈值判断 |

#### 其他监测

| 类型 | 数据表 | 核心字段 | 分析规则 |
|------|--------|----------|----------|
| 墒情 | st_soil_moisture_r | soil_water10cm/20cm/30cm/60cm/100cm(各深度含水量%), soil_temp10cm~100cm(各深度温度℃), ec(电导率uS/cm), ph, tension(张力kPa), groundwater_depth(地下水位m), soil_moist_evaluation(评价) | 基本阈值判断 |
| 白蚁监测 | st_termite_monitor_r | termite_species(蚁种), pest_density(密度等级0-4), damage_level(危害等级), check_result(检查结果:无白蚁/发现/疑似痕迹) | 基本阈值判断 |

### 实时监测算法

| 算法 | 文件 | 说明 |
|------|------|------|
| 时序预测 | `algorithms/time-series-forecast.md` | Holt-Winters/ARIMA/LSTM 三种算法 + 水利场景参数建议 |
| 水位变化率 | `algorithms/water-level-change.md` | 百分比公式(1%/3%/5%三级) + 10min流量汇总 + 库容平衡 |
| 位移速率 | `algorithms/displacement-rate.md` | 最大最小差值/月份数(cm/月) + 四级分级(稳定/缓慢/中速/快速) |
| 趋势检测 | `rules/trend-detection.md` | Mann-Kendall S统计量 + 变点检测 + 自相关周期检测 |
| 雨情分析 | `rules/rainfall-analysis.md` | 6级雨量划分 + 分区雨情 + 累计趋势 + 数据校验 |
| 水库水情 | `rules/reservoir-analysis.md` | 水位变化率 + 库容平衡 + 10分钟流量 + 异常识别 |

### API 附录

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

### 实时监测按需加载指令

```
"水位"/"水库"/"水情"     → rules/reservoir-analysis.md + algorithms/water-level-change.md
"河道"/"河流"           → st_river_r 基本阈值判断
"闸站"/"水闸"           → st_was_r 基本阈值判断
"潮汐"/"潮位"           → st_tide_r 基本阈值判断
"雨量"/"降雨"           → rules/rainfall-analysis.md
"分区雨情"/"区域降雨"    → st_pptn_region_r 基本阈值判断
"闸门"/"泵站"           → rules/anomaly-and-complex-conditions.md
"GNSS"/"位移"/"变形"    → rules/anomaly-and-complex-conditions.md + algorithms/displacement-rate.md
"渗流"/"渗流量"         → st_percolation_r 基本阈值判断
"渗压"/"压力"           → st_pressure_r 基本阈值判断
"墒情"/"土壤"           → st_soil_moisture_r 基本阈值判断
"白蚁"/"蚁害"           → st_termite_monitor_r 基本阈值判断
"趋势"/"异常趋势"       → rules/trend-detection.md
"预测"/"预报"/"ARIMA"/"LSTM" → algorithms/time-series-forecast.md
```

## 自演化机制

通过 `rules/rule-evolution.md` + `evolution/` 实现反馈驱动的闭环自优化：

1. **阈值适应**：精度<0.70 收紧，召回<0.70 放宽，单次调整≤15%，间隔≥7天
2. **排除规则生成**：≥3个同一原因的误报 → 自动生成抑制条件
3. **新检测规则生成**：≥3个同一模式的漏报 → 自动生成新规则
4. **置信度校准**：每50条反馈重新校准置信度分桶
5. **演化目标**：精度>0.85，召回>0.90，人工干预率<20%
