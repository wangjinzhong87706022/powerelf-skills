---
name: powerelf-intelligent-inspection
description: 水利工程智能巡检智能体 + 实时监测
version: 7.1.0
author: PowerELF Team; Integrated AI Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [inspection, anomaly-detection, water-conservancy, dam-safety]
    category: industrial
    related_skills: [powerelf-data-governance, powerelf-early-warning, powerelf-monitor]
---

# 水利工程智能巡检智能体

融合传感器数据分析（15维度异常检测）与巡检业务管理（任务/路线/缺陷）于一体的水利工程智能巡检 AI 智能体。

## 架构概览

本系统由一大模式构成：

**深度巡检（Python + Hermes Agent + MySQL）**
- 15 维度传感器异常检测（水位、雨量、渗压、渗流、位移、闸门、泵站、水质、墒情、白蚁、巡检结果、设备状态、告警、MAD统计、多指标关联）
- 5 层异常判定体系（阈值 → 变化率 → 趋势 → MAD统计 → 相关性）
- 4 维度质量评分模型（完成率30分 + 及时率25分 + 缺陷发现率25分 + 路线覆盖率20分）
- 缺陷趋势预测 + 路线效率优化
- 规则自演化（反馈驱动的阈值适应/异常规则生成/置信度校准）
- 巡检业务管理（任务/路线/缺陷/报告）

> **实时监测**（当前值、12 类监测趋势、REST 看盘、预警触发）由 **`powerelf-monitor`** 负责。

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
│   └── test_inspection.py      # 20个pytest集成测试（带skip守卫）
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
│   ├── time-series-forecast.md             # 时序预测（Holt-Winters/ARIMA/LSTM，📌 roadmap）
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
>
> **部署环境**：设置 `POWERELF_SKILLS_ROOT` 环境变量指向 powerelf-skills 根目录，
> 各 skill 的 shim 会自动通过该变量定位 `_shared/lib/db.py`，无需固定目录深度。

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

### 适用场景

本 skill 适用于：
- 昨日/本周/本月**离线巡检回顾分析**（批处理、DB 直连）
- 巡检质量评分（完成率/及时率/缺陷率/覆盖率）
- 缺陷趋势预测 + 路线效率优化
- 规则自演化（阈值适应/异常规则生成）
- 巡检业务管理（任务/路线/缺陷/报告）

### When NOT to Use

| 你想要的 | 应使用 |
|---|---|
| 某站当前水位/流量实时值、趋势看盘 | `powerelf-chatbi` / `powerelf-monitor` |
| 数据质量（异常/缺失/离线/卡滞/插值） | `powerelf-data-governance` |
| 阈值/告警判定与分发 | `powerelf-early-warning` |
| 实时 12 类监测、REST、预警触发 | `powerelf-monitor` |

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
第3层: 趋势检测 (单向持续，min_consecutive 编码于 impl)
  └─ 同向持续达阈值 → 第4层
     ├─ 水位: 6 点窗口 / 5 次连续上升/下降
     ├─ 渗压: 7 点窗口 / 6 次连续上升
     └─ GNSS: 5 点窗口 / 4 次连续加速
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

## 实时监测（→ powerelf-monitor）

实时/当前值、12 类监测趋势、REST 看盘、预警触发由 **`powerelf-monitor`** 负责（详见其 SKILL.md）。本 skill 仅做**离线巡检回顾分析**（定时批处理、DB 直连、昨日窗口、日报 + 复合工况 + 巡检考核）。两者经 `_shared/`（算法/规则/schema）共享基底、经路由表交互，无代码 import。

| 你想要的 | 用哪个 skill |
|---|---|
| 某站**当前**水位/最新值、实时趋势看盘、预警 | powerelf-monitor |
| **昨日/本周/本月**巡检回顾、日报、复合工况、巡检质量考核 | powerelf-inspection（本 skill） |

相关算法（MAD/水位变化率/位移速率/时序预测/趋势检测/水库·雨情分析）见 `../_shared/algorithms/` 与 `../_shared/rules/`，两 skill 同源引用。

## 自演化机制

通过 `rules/rule-evolution.md` + `evolution/` 实现反馈驱动的闭环自优化：

1. **阈值适应**：精度<0.70 收紧，召回<0.70 放宽，单次调整≤15%，间隔≥7天
2. **排除规则生成**：≥3个同一原因的误报 → 自动生成抑制条件
3. **新检测规则生成**：≥3个同一模式的漏报 → 自动生成新规则
4. **置信度校准**：每50条反馈重新校准置信度分桶
5. **演化目标**：精度>0.85，召回>0.90，人工干预率<20%

## Pitfalls（高频错误）

开发/维护中常见的 7 类陷阱（含 ❌错误示例与 ✅正确做法），详见 `references/pitfalls.md`：

1. **占位符污染** — SQL 中 `{st_id}` 占位符导致注入
2. **关联键混淆** — `eq_id`(bigint)/`stcd`(varchar)/`st_id`(int) 易混
3. **GNSS 表名** — `dsm_dfr_srvrds_srhrds` 易写错
4. **extend JSON** — `ew_info_rules.extend` 格式坏导致解析异常
5. **泵站 varchar** — 电压/电流为 varchar，不能直接数值比较
6. **传感器故障 vs 真极端** — 需区分传感器故障和真实异常
7. **双数据库 session** — 同时连接 inspection/governance 库时 session 混乱

## Few-Shots（SQL 最佳实践）

常用 SQL 模式（参数化查询、JOIN-by-Name、标识符白名单、CAST 类型转换、聚合统计、分页、事务控制），详见 `references/few_shots.md`。

## Validation Gate（交付前 QA 闸）

报告交付前需过 QA 闸（详见 `../_shared/references/analysis-qa-checklist.md`），逐条自检后填入 `confidence_tier`。

### Inspection 专属 5 项

1. [ ] 关联键（`eq_id`/`stcd`/`st_id`）已核验，未混用
2. [ ] `ew_info_rules` 阈值数据存在性已确认（`extend` JSON 解析健壮性）
3. [ ] 传感器故障 vs 真异常已区分（消费 `data-quality tier`）
4. [ ] `business_check_task` 状态码（1/2/3）正确过滤
5. [ ] 缺陷率已用 `real_objitem` 分母，并做 data-quality 校正

### 置信度评级

| 等级 | 含义 | 适用场景 |
|------|------|----------|
| **Ready to share** | 数据完整、计算正确、数字自洽 | 核心指标无缺失、QA 清单全绿 |
| **Share with caveats** | 有已知局限但不影响结论主体 | 部分数据缺失（已标注） |
| **Needs revision** | 存在影响结论的缺陷 | 关键指标缺失/错误 |

## 输出深度模式（depth-mode）

| 模式 | 输出内容 | 适用场景 |
|------|----------|----------|
| **精简（terse）** | 仅异常数值列表，无描述 | 批量告警聚合 |
| **标准（standard）** | 异常 + 1–2 个关联指标 | 日报/周报例行分析 |
| **详细（detailed）** | 多维度 + 趋势图 + 异常检测详情 | 专项报告/人工复核 |

## 共享引用（_shared）

本 skill 与 `powerelf-monitor` / `powerelf-data-governance` 同源引用以下 `_shared/` 文档：

| 文档 | 用途 |
|------|------|
| `_shared/references/schema.md` | DDL、关联键、类型定义（单一事实源） |
| `_shared/references/sql-discipline.md` | SQL 写作 6 维解析 + 7 条纪律 |
| `_shared/references/analysis-qa-checklist.md` | 交付前 QA 闸（四类清单 + 8 陷阱） |
| `_shared/references/statistical-caution.md` | 统计措辞护栏（避免过度推断） |
| `_shared/references/data-profiling.md` | 数据画像方法论（完整性/一致性） |
| `_shared/algorithms/` | MAD、水位变化率、位移速率、时序预测 |
| `_shared/rules/` | 闸门/泵站工情、GNSS 变形（已提升） |

### 文档漂移说明

- **Holt-Winters / ARIMA / LSTM / Mann-Kendall**：标记为 📌 roadmap（见 `ROADMAP.md`），当前未在 `lib/` 中实现。
- **趋势阈值**：已在代码中编码（水位≥6 点窗口/5 次连续、渗压≥7 点窗口/6 次连续、GNSS≥5 点窗口/4 次连续），见 `impl/inspection_analyzer.py` 中 `consecutive_monotonic` 调用。
- **自演化**：规则自演化（阈值适应/排除规则生成）当前为 AI Agent 辅助流程，全自动闭环标记为 📌 roadmap。
