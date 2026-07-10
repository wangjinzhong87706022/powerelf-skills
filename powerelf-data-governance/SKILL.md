---
name: powerelf-data-governance
description: "数据异常分析报告/日报/评分报告一键生成，MAD异常检测、缺失检测、智能插值、离线监测、卡滞/相关性/极端事件检测、质量评分、数据回写。水利工程数据质量治理。"
version: 2.0.0
author: Powerelf Team
license: MIT
platforms: [linux, windows, macos]
prerequisites:
  env_vars: [POWERELF_DB_HOST, POWERELF_DB_PORT, POWERELF_DB_NAME, POWERELF_DB_USER, POWERELF_DB_PASSWORD]
metadata:
  hermes:
    tags: [water-conservancy, data-governance, quality, anomaly, interpolation, scoring, offline, stagnation, correlation, writeback]
    related_skills: [powerelf-early-warning, powerelf-monitor, powerelf-chatbi, powerelf-inspection]
---

# 数据治理 Skill

水利工程数据质量治理引擎。规则内嵌，Agent 可独立执行质量判断。

**区分**：本 skill 分析"数据本身有没有异常/缺失/质量问题"，不是查询"数据内容是什么"。

## When to Use

| 场景 | 说明 |
|------|------|
| 检测监测数据是否有异常值（MAD异常检测） | 自适应窗口MAD |
| 水库水位/河道水位/渗压/雨量数据异常检测 | 分指标阈值 |
| 用MAD算法分析数据异常 | 变化率+综合判定 |
| 数据有没有问题/数据质量怎么样 | 概览型分析 |
| 判断异常值是否需要修复以及修复策略 | 置信度评估 |
| 选择插值策略填补缺失数据 | 四策略自适应 |
| 评估设备数据质量评分（四维度评分） | 35+10+40+15 |
| 判断设备是否离线及离线时长分级 | 三态+分级 |
| 分析缺失模式（周期性 vs 随机） | 模式识别 |
| 生成 YYYY-MM-DD 数据质量日报 | **直接执行**,无需额外分析:<br>`bash: cd impl && python3 generate_report.py --date YYYY-MM-DD`<br>默认输出 markdown；可选 `--format json\|html\|pdf` |
| 生成 YYYY-MM 数据异常分析报告 / 异常分析 | **直接执行**,无需额外分析:<br>`bash: cd impl && python3 generate_report.py --date YYYY-MM --type anomaly`<br>支持月度或单日,自动查询异常记录 |
| 数据纠正回写（修复异常/填补缺失） | 回写闭环 |

## When NOT to Use

| 场景 | 应使用 |
|------|--------|
| 查询水库当前水位是多少 | `powerelf-chatbi` / `water-situation` |
| 查询河道水位趋势曲线 | `water-situation` |
| 查询是否超过警戒水位 | `powerelf-early-warning` |
| 查询雨量站实时降雨量 | `powerelf-chatbi` / `water-situation` |
| 闸门/泵站运行状态查询 | `powerelf-monitor` / `gate-pump-operation` |
| 纯数据查询不涉及分析 | `powerelf-chatbi` |

## 数据库连接

> 连接层已统一至 `../_shared/lib/db.py`（单一事实源），本 skill 的 `lib/db.py` 为转发 shim。
> 支持 `POWERELF_DB_*`（标准）+ `SRM_DB_*`（旧名后备）两套环境变量。

```
环境变量:
  POWERELF_DB_HOST     数据库地址 (默认 localhost)
  POWERELF_DB_PORT     数据库端口 (默认 3306)
  POWERELF_DB_NAME     数据库名 (默认 powerelf_srm_yml)
  POWERELF_DB_USER     用户名
  POWERELF_DB_PASSWORD 密码
```

```python
# 获取连接 — 无论 CWD 在哪里都能正确找到 lib 目录
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from db import get_connection, get_sqlalchemy_url   # 转发到 _shared/lib/db.py

# pymysql 连接（用于 lib 模块）
conn = get_connection()

# SQLAlchemy URL（用于 impl 工具）
url = get_sqlalchemy_url()
```

**CLI 工具统一用 `$DB_URL`**（先 source 引导脚本，会正确尊重 `POWERELF_DB_PORT`）：
```bash
source ../_shared/bootstrap.sh   # 导出 DB_URL
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_pressure_r --field water_pressure
```

## 数据库查询注意事项

⚠️ **Agent 在写 SQL 查询数据库前,必须先读 `../_shared/references/schema.md`（跨 skill 单一事实源，含设备关联键映射）**。

| 常见错误假设 | 实际正确值 |
|------------|----------|
| 时间列是 `data_time` / `tm` | 实际是 **`create_time`** |
| 设备关联列是 `station_id` | 实际是 **`eq_id`**(bigint) 或 **`stcd`**(varchar) |
| 表名 `sl_rsvr_rt_r` | 实际是 **`st_rsvr_r`** |
| 环境变量前缀 `POWERELF_DB_*` | 也支持 **`SRM_DB_*`** 回退 |
| pymsql 用法 `conn.execute(sql)` | 正确: **`conn.cursor().execute(sql)`**（模板见 `references/pymysql-query-template.md`） |
| 采集率 `collection_data_number` 是总行数 | 实际是**时间槽覆盖数**,非总行数 |

## 工具命令

**第一反应：调工具，不要自己写 SQL。**

### MAD 异常检测
```bash
python3 impl/anomaly_detector.py \
  --db "$DB_URL" \
  --table st_pressure_r --field water_pressure --threshold 4.0

# 指定测站和时间
python3 impl/anomaly_detector.py --db "..." --table st_rsvr_r --field rz --threshold 3.0 --st-id 128 --days 7
```

### 缺失检测
```bash
python3 impl/missing_detector.py \
  --db "$DB_URL" \
  --table st_rsvr_r --st-id 128 --freq 60 --days 1
```

### 离线检测
```bash
python3 impl/offline_detector.py \
  --db "$DB_URL" \
  --table st_pressure_r --st-id 201 --threshold 60
```

### 质量评分
```bash
python3 impl/quality_scorer.py \
  --missing-ratio 0.05 --anomaly-ratio 0.03 \
  --offline-date-ratio 0.10 --anomaly-date-ratio 0.05 \
  --offline-count 3 --anomaly-count 2 \
  --actual-records 22 --expected-records 24
```

### 日报生成（用 terminal 执行，不要用 execute_code）
```bash
# 一键生成数据质量日报（日期替换为目标日期）
python3 impl/generate_report.py --date 2026-05-15

# 输出到文件
python3 impl/generate_report.py --date 2026-05-15 --format pdf --output /tmp/report.pdf
```

## 模块架构

```
lib/                      # Python 算法库（可编程调用）
├── db.py                 # 数据库连接（环境变量驱动）
├── mad.py                # MAD异常检测 + 变化率 + 综合判定
├── missing.py            # 缺失检测 + 模式识别
├── interpolation.py      # 智能插值（4策略自适应）
├── offline.py            # 离线检测 + 渐进告警 + MTTR
├── scoring.py            # 质量评分（4维度 + 时间衰减 + 趋势）
├── stagnation.py         # 传感器卡滞检测
├── extreme_event.py      # 极端事件区分
├── correlation.py        # 跨指标物理矛盾检测
├── device_context.py     # 设备上下文关联
├── knowledge.py          # 多后端知识检索（MySQL/RAGFlow/ES/Chroma/HTTP）
├── writeback.py          # 数据回写（异常修复/缺失填补/离线记录）
└── report.py             # 报告生成（Markdown/JSON/HTML/PDF）

impl/                     # CLI 工具（可直接终端调用）
├── anomaly_detector.py   # MAD异常检测算子
├── missing_detector.py   # 缺失检测算子
├── offline_detector.py   # 离线检测算子
└── quality_scorer.py     # 质量评分算子

rules/                    # 规则文档（按需加载）
├── anomaly-detection.md  # MAD异常检测规则
├── missing-detection.md  # 缺失检测规则
├── interpolation.md      # 智能插值规则
├── offline-detection.md  # 离线检测规则
└── quality-scoring.md    # 统计评分规则

algorithms/               # 算法详解（含ML方法）
├── mad-algorithm.md
├── interpolation-strategies.md
├── scoring-formulas.md
├── multivariate-anomaly.md     # 孤立森林/DBSCAN/自编码器
└── spatial-interpolation.md    # Kriging/高斯过程/IDW

evolution/                # 自调优系统
├── parameters.md         # 可调参数注册表（72个参数）
└── feedback-log.md       # 反馈日志
```

## 能力概览

| 子模块 | 文件 | 功能 |
|--------|------|------|
| 缺失检测 | `lib/missing.py` + `rules/missing-detection.md` | 期望周期数比较，连续缺失递增告警，模式识别 |
| 异常检测 | `lib/mad.py` + `rules/anomaly-detection.md` | 自适应窗口MAD，分指标阈值，变化率检测，综合判定 |
| 智能插值 | `lib/interpolation.py` + `rules/interpolation.md` | 四策略自适应选择（线性/二次/样条/滑动平均），置信度评估 |
| 离线监测 | `lib/offline.py` + `rules/offline-detection.md` | 三态判定，渐进式告警，离线时长分级，MTTR |
| 统计评分 | `lib/scoring.py` + `rules/quality-scoring.md` | 四维度评分（35+10+40+15），时间衰减，趋势分析 |
| 卡滞检测 | `lib/stagnation.py` | 传感器连续输出相同值检测，近似卡滞检测 |
| 极端事件区分 | `lib/extreme_event.py` | 区分汛期高水位等合法极端事件与数据异常 |
| 相关性异常 | `lib/correlation.py` | 跨指标物理矛盾检测（渗压-渗流/水位-渗流等5规则） |
| 设备上下文 | `lib/device_context.py` | 设备信息+缺陷+维保+知识库关联，智能运维建议 |
| 知识检索 | `lib/knowledge.py` | 多后端统一检索（MySQL/RAGFlow/ES/Chroma/HTTP） |
| 数据回写 | `lib/writeback.py` | 异常修复/缺失填补/设备状态/离线记录 CRUD |
| 报告生成 | `lib/report.py` | 日报/异常报告/评分报告，MD/JSON/HTML/PDF输出 |

## 核心分析能力

### 1. MAD 异常检测

自适应窗口 MAD + 变化率检测 + 综合判定。分指标阈值见下，算法详见 `rules/anomaly-detection.md`、`algorithms/mad-algorithm.md`

| 指标 | 阈值 | 理由 |
|------|------|------|
| 水位(rz/z) | 3.0 | 日变化平缓，异常容易识别 |
| 雨量(p) | 5.0 | 波动大，需要更高容忍度 |
| 渗压(water_pressure/ext_pressure) | 4.0 | 中等波动 |
| 渗流(percolation)/流量(inq/otq) | 4.0 | 中等波动 |
| GNSS位移(wgs84_delta_h) | 3.5 | 缓慢变化，突变即异常 |
| 通用默认 | 4.0 | 兜底值 |

### 2. 智能插值

四策略自适应选择 + 置信度评估。详见 `rules/interpolation.md`、`algorithms/interpolation-strategies.md`

### 3. 质量评分

四维度加权评分（35%+10%+40%+15%），含时间衰减与趋势分析。详见 `rules/quality-scoring.md`、`algorithms/scoring-formulas.md`

### 4. 缺失检测 / 5. 离线检测

详见 `rules/missing-detection.md`、`rules/offline-detection.md`

### 6. 卡滞检测 / 7. 极端事件区分 / 8. 相关性异常

详见 `lib/stagnation.py`、`lib/extreme_event.py`、`lib/correlation.py`

### 9. 设备上下文关联

异常 + 知识库 + 运维建议。详见 `lib/device_context.py`

### 10. 数据回写（数据闭环）

| 操作 | 函数 |
|------|------|
| 修复异常 | `writeback.fix_anomaly(conn, id, fix_data)` |
| 填补缺失 | `writeback.fill_missing(conn, id, filled_data)` |
| 更新设备状态 | `writeback.update_device_status(conn, device_id, status)` |
| 创建/更新离线/异常记录 | `writeback.create/update_offline/anomaly_record(...)` |
| 批量操作 | `writeback.batch_fix/fill_...(...)` |

### 11. 报告生成

| 报告类型 | 调用方式 | 输出格式 |
|---------|---------|---------|
| 数据质量日报 | `report.generate_daily_report_from_db(date)` | Markdown / JSON / HTML / PDF |
| 异常分析报告 / 评分报告 | `report.generate_anomaly/score_report()` | Markdown / JSON / HTML / PDF |

**一键生成（推荐）**:
```python
from lib.report import generate_daily_report_from_db
md = generate_daily_report_from_db('2026-05-15')  # ← 替换为目标日期
print(md)
```

**CLI 工具**:
```bash
python3 impl/generate_report.py --date 2026-05-15
```

## 按需加载指令

```
"数据质量"/"质量总览"     → rules/quality-scoring.md
"异常"/"异常检测"/"MAD"   → rules/anomaly-detection.md + algorithms/mad-algorithm.md
"缺失"/"数据缺失"        → rules/missing-detection.md
"插值"/"填补"/"修复"     → rules/interpolation.md + algorithms/interpolation-strategies.md
"离线"/"设备状态"        → rules/offline-detection.md
"评分"/"厂商排名"        → rules/quality-scoring.md + algorithms/scoring-formulas.md
"卡滞"/"传感器卡住"      → API: stagnation.detect_stagnation()
"极端事件"/"汛期异常"    → API: extreme_event.classify_extreme_event()
"相关性矛盾"             → API: correlation.detect_correlation_anomaly()
"设备上下文"/"运维建议"   → API: device_context.analyze_with_context()
"知识库"/"知识检索"      → API: knowledge.search_knowledge()
"报告"/"日报"/"PDF"      → API: report.generate_daily_report_from_db(date)  # 一键生成
"孤立森林"/"DBSCAN"/"多变量" → algorithms/multivariate-anomaly.md
"空间插值"/"Kriging"     → algorithms/spatial-interpolation.md
```

## 边界规则

以下情况**必须人工确认**，Agent 只能建议不能决策：

| 场景 | 原因 |
|------|------|
| 数据插值超过连续3天 | 插值结果不可靠，需现场复测 |
| 设备离线超过7天 | 可能是设备故障而非通信问题 |
| 多台设备同时异常 | 可能是系统性问题而非个别设备 |
| 异常值在设计允许范围内 | 可能是正常工况，需专家判断 |
| 厂商排名用于采购决策 | 需结合价格、售后等多维度评估 |

**反例（不要做的事）**：
- 不要自动插值后直接覆盖原始数据
- 不要在没有确认的情况下将"异常"改为"正常"
- 不要跳过缺失检测直接做质量评分
- 不要对单条数据做全局性结论

## 巡检前检查清单

执行数据治理分析前，确认以下事项：

- [ ] 明确分析的时间范围和目标
- [ ] 确认要分析的传感器表和字段
- [ ] 确认离线阈值配置是否合理（dg_equip_offline）
- [ ] 确认设备-业务映射是否完整（eq_business_equip_relation）

## 输出模板

```
## 数据质量报告

### 总体评分: {score}/100 ({grade})

| 维度 | 得分 | 说明 |
|------|------|------|
| 完整性 | {completeness}/30 | 缺失率 |
| 准确性 | {accuracy}/30 | 异常率 |
| 及时性 | {timeliness}/20 | 离线时长 |
| 一致性 | {consistency}/20 | 采集频率 |

### 关键发现
- {finding_1}

### 待确认事项
- {pending_1}

### 行动建议
| 优先级 | 动作 | 负责人 | 截止时间 |
|--------|------|--------|----------|
| {priority} | {action} | {owner} | {deadline} |
```

## Workflow

```
确定时间窗口 -> 获取原始数据 -> 选择分析方法 -> 执行算法 -> 生成判定结果 -> 记录到治理表
```

**第一步必须确定分析时间窗口，所有后续查询和分析限定在该窗口内。**

1. **确定分析时间窗口**
   - 用户指定 → 使用用户给定的起止时间
   - 用户未指定 → 按分析类型选择默认窗口:
     - 缺失检测/异常检测/数据统计 → 前一天
       ```sql
       START = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
       END = CURDATE()
       ```
     - 离线检测 → 滚动检测，无固定窗口
     - 质量评分 → 当前月
       ```sql
       START = DATE_FORMAT(CURDATE(), '%Y-%m-01')
       END = CURDATE()
       ```
   - 所有后续 SQL 必须带 `WHERE tm BETWEEN '{START}' AND '{END}'`

2. 从原始监测表获取数据（限定在时间窗口内）
3. 根据任务类型选择对应分析方法（异常/缺失/离线/评分/卡滞/相关性/极端事件）
4. 执行内嵌算法（MAD/插值/评分/缺失检测/离线判定/卡滞/相关性/极端事件判定）
5. 生成结构化判定结果（含置信度/严重级别/建议）
6. **数据回写** — 调用 `lib/writeback.py` 将修复结果写回数据库
7. **生成报告** — 调用 `lib/report.py` 输出结构化报告（Markdown/JSON/HTML/PDF）

## 核心数据表

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| eq_data_missing_record | 数据缺失记录 | equipment_code, data_missing_datetime, data_missing_count, whether_add, filled_data_content(JSON), table_name |
| eq_data_anomaly_record | 数据异常记录 | equipment_code, data_anomaly_datetime, whether_fix, fix_data_content(JSON), table_name |
| eq_equip_offline_record | 设备离线记录 | equipment_code, offline_start_time, offline_end_time, total_offline_duration(秒) |
| eq_equip_anomaly_record | 设备异常记录 | equipment_code, anomaly_start_time, anomaly_end_time, total_anomaly_duration(秒) |
| stats_data_collection_daily | 每日采集统计 | collection_data_number, tm(日期), table_name |
| stats_data_missing_daily | 每日缺失统计 | missing_data_number, tm(日期), table_name |
| stats_data_anomaly_daily | 每日异常统计 | anomaly_data_number, tm(日期), table_name |
| dg_equip_offline | 离线阈值配置 | st_type(站类型), tm(阈值min), frequency(采集频率min) |
| eq_business_equip_relation | 设备-业务映射 | business_table, eq_id, st_id, st_type, frequency, offline_threshold |
| eq_equip_base | 设备主数据 | name, code, type_flag, status(0=离线/1=在线/2=异常), st_base_id |

## 数据输入

原始监测表：

| 表名 | 说明 | 检测字段 |
|------|------|----------|
| st_rsvr_r | 水库水情 | rz(水位), inq(入库流量), otq(出库流量) |
| st_river_r | 河道水位 | z(水位) |
| st_pptn_r | 雨量 | p(雨量) |
| st_pressure_r | 渗压 | ext_pressure, water_pressure |
| st_percolation_r | 渗流 | percolation |
| dsm_dfr_srvrds_srhrds | GNSS位移 | wgs84_delta_h/x/y |

## 自我进化

- 可调参数：`evolution/parameters.md` (72个参数，含MAD/插值/评分/离线/缺失各维度的合理范围)
- 反馈日志：`evolution/feedback-log.md`（记录误报/漏报，指导参数调整）
- 自动实验基线：`autoresearch-data-governance/`

## 机器学习算法（参考）

| 算法 | 文件 | 适用场景 |
|------|------|----------|
| 孤立森林 | `algorithms/multivariate-anomaly.md` | 多维联合异常检测 |
| DBSCAN | `algorithms/multivariate-anomaly.md` | 密度聚类异常发现 |
| 自编码器 | `algorithms/multivariate-anomaly.md` | 复杂非线性模式 |
| Kriging | `algorithms/spatial-interpolation.md` | 空间最优估计 |
| 高斯过程 | `algorithms/spatial-interpolation.md` | 空间不确定性量化 |
| 反距离加权 | `algorithms/spatial-interpolation.md` | 快速空间估算 |

## API 附录

| 端点 | 说明 |
|------|------|
| `GET /stats/data-stats/get-data-quality-overview` | 数据质量总览 |
| `GET /stats/equip-stats/get-equip-overall-stats` | 设备评分总览 |
| `GET /stats/equip-stats/get-manufacturer-rank` | 厂商质量排名 |
| `GET /eq/data-missing-record/page?eqCode=` | 缺失记录 |
| `POST /stats/data-stats/start-data-missing-check` | 手动触发检测 |

通用头与鉴权约定：见 [`../_shared/api-auth.md`](../_shared/api-auth.md)（`Authorization: Bearer ${POWERELF_API_TOKEN}` + `tenant-id: 1`）

## Related Skills

- `powerelf-early-warning` — 预警规则与通知联动
- `powerelf-monitor` — 监测数据采集与实时监控
