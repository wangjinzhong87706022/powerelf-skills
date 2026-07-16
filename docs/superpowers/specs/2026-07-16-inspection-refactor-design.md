# 设计：powerelf-inspection 重构为聚焦巡检 skill

- **日期**：2026-07-16
- **目标仓库**：`powerelf-skills` monorepo（权威源 `/home/scada/powerelf-skills`）
- **主受影响 skill**：`powerelf-inspection`
- **次受影响**：`powerelf-monitor`（对称文档 + 2 个 rule 提升）、`_shared`（接收 2 个 rule）
- **来源**：对 `powerelf-inspection/` 的代码评审 + 对照 `powerelf-data-governance`、`water-situation`（`/opt/git/water-resources-skills/skills/water-situation`）的差距分析
- **路线图位置**：接续 `2026-07-13-governance-profiling-qa-gate-design.md` §9「跨簇：profiling 若被 inspection 也需要，升 `_shared`」后续；沿用其确立的约定「方法论文档进 `_shared/`、可运行代码进 skill、判断类护栏为纯被动文档」

## 1. 背景与动机

代码评审 + 差距分析得出一致结论：`powerelf-inspection` 存在「两个世界」问题——

- **被宣传但不存在/死代码的架构**：`lib/` 内核（1164 行：`anomaly.py` 341 / `quality.py` 293 / `defect_predict.py` 209 / `route_opt.py` 271）**整体是死代码**——`impl/` 对它零 import（只 import argparse/json/sys/datetime）。SKILL.md 却把 `lib/` 当核心宣传。宣传的 Holt-Winters/ARIMA/LSTM、Mann-Kendall、规则自演化**均无代码**；置信度公式（SKILL.md:184）未实现，impl 直接硬编码 `0.95`。
- **实际运行的实现**：`impl/`（1813 行）忽略 `lib/`、弱重复实现算法（MAD ×3、变化率 ×2、趋势 ×2）、14 处裸 `except: pass` 静默 fail-open、含真实正确性 Bug。
- **大面积重复**：SKILL.md L221–320「实时监测模式」≈ 逐字复制 `powerelf-monitor`（12 类表 + 13 端点 + 按需加载指令）；本地 `references/database-schema.md` 重复 `_shared/references/schema.md`；MAD/水位变化率/位移速率/趋势/水库/雨情 在 inspection 与 `_shared`/monitor 双份。
- **零采用 `_shared` 成熟护栏**：inspection 引用了 **0 个** `_shared/references/` 文档（governance 引用了 3 个）。无 When NOT to Use 路由表、无交付前 QA 闸、无 Pitfalls、无 few_shots；规则文件满是 `WHERE st_id={st_id}` 占位符（water-situation 明令禁止的反模式）。

本 spec 把 inspection 重构为「聚焦巡检」skill：**去重对齐 `_shared`/monitor、接入 QA 护栏、修复内核 Bug、瘦身 `lib/` 并接线给 `impl/`**。

## 2. 目标与非目标

### 做
- 删除与 monitor 重复的「实时监测模式」→ 路由交接；inspection 保留**离线巡检回顾分析**。
- 解决 `lib/` vs `impl/`：瘦身 `lib/` 为薄纯函数内核并接线给 `impl/`（消除死代码 + 三份 MAD 等）。
- 修复内核 Bug：C1/C2/C3/H1/H2/H3/H4 + 文档/代码漂移 DD1/DD2。
- 接入 `_shared/references/` 护栏套件 + water-situation 成熟模式：When NOT to Use 路由表、Pitfalls、Validation Gate、depth-mode、few_shots、business_rules（带溯源）、POWERELF_SKILLS_ROOT 标准导入片段。
- 删除重复 schema 引用 → 指向 `_shared/references/schema.md`。
- 自建 `lib/report.py`（镜像 governance 模式，嵌 QA 闸 + confidence_tier + 数据质量 caveat）。
- inspection 任务质量评分**消费 data-governance 数据质量 tier**作为上下文（剔除传感器故障导致的假异常）。
- 删除 stale 的根目录 `inspection/`；monitor SKILL 对称补 inspection；`gate-pump-status.md` + `gnss-deformation.md` 升 `_shared/rules/`。
- 建真单元测试 + 重写集成冒烟测试。

### 不做（YAGNI / 边界）
- ❌ 缺陷回写（writeback）：本轮**保持只读**，无写库路径（符合 SKILL「不可自动确认告警」安全边界）。留作 Option 3 后续。
- ❌ report chassis 升 `_shared/lib/report.py`：本轮自建、镜像模式；待两份 report.py 形状被验证后再升（推迟，同 profiling 逻辑）。
- ❌ 数据采集层（`sys_data_source_registry` 读取/匹配）升 `_shared`：本轮隔离在 inspection 内；未来候选。
- ❌ Option 3 全域三 skill 共享内核整合：超出本轮（聚焦重构，不滑向全域）。
- ❌ 实时监测/看盘/REST/预警触发能力：交 monitor。
- ❌ 自动 QA 评分器（QA 是判断题，自动打分易假精度，与 statistical-caution 既有定位冲突）。
- ❌ `inspection_tool.py` 完整 6 路拆分：仅做最小分离（采集 vs 分析）。
- ❌ 改 monitor/data-governance 的运行代码（仅 monitor 文档对称 + 2 个 doc-only rule 提升）。

## 3. 目标架构与职责边界

### 3.1 inspection「只拥有」四件事
1. **巡检业务管理**：`business_check_*` 任务/路线/巡检点/对象/结果/缺陷生命周期。
2. **巡检质量评分**（任务维度）：完成率30/及时率25/缺陷发现率25/路线覆盖率20（≠ governance 数据质量评分 35/10/40/15，**两者并存**）。
3. **缺陷预测 + 路线优化**。
4. **5 层异常融合判定 + 复合工况**：把（委托来的）传感器异常 + 巡检任务上下文做融合。

### 3.2 inspection「委托」
| 能力 | 委托给 | 处理 |
|---|---|---|
| 实时监测 12 类 + REST | `powerelf-monitor` | 删 SKILL L221–320；路由表交接 |
| MAD/异常/缺失/离线/卡滞/插值内核 | `powerelf-data-governance` / `_shared` | 5 层 L4 调 governance `mad.py`，L5 调 `correlation.py` |
| raw 数据查询 | `powerelf-chatbi` | 路由表 |
| 阈值/告警分发 | `powerelf-early-warning` | inspection 只读 `ew_info_rules.extend` 判定，分发交 early-warning |
| schema | `_shared/references/schema.md` | 删本地 `database-schema.md` |
| MAD/水位变化率/位移速率/时序预测 | `_shared/algorithms/` | 已 stub；SKILL 不再当自有宣传 |
| 趋势/水库/雨情 rules | `_shared/rules/` | 已 stub |

> **15 维度引擎保留但重架构**：每日巡检 = AI 采集昨日全类数据 + 标异常 + 复合工况（替代人工巡查的价值所在）。重构后每维度异常「检测」委托正确内核，inspection 只做「编排 + 融合判定」。

### 3.3 inspection ↔ monitor 交互模型
monitor **无 `lib/`**（纯规则内嵌 skill，规则写进 markdown、Agent 内联执行）。因此：
- **交互 ≠ 代码 import**（monitor 无可 import 的内核；旧 `inspection/SKILL.md` 写的「调 `powerelf-monitor/lib/reservoir.py`」引用了不存在的文件，是该副本该删的又一证据）。
- 交互通道只有两条：**① 共享 `_shared/` 基底；② 路由表 + related_skills 双向声明**。

划线准则 = **时间模式**：

|  | powerelf-monitor | powerelf-inspection（重构后） |
|---|---|---|
| 时间模式 | 实时/当前/在线 | 离线回顾/昨日窗口/批处理 |
| 触发 | 事件/查询驱动（REST） | 定时批处理（每日凌晨） |
| 数据访问 | REST API（轻量） | DB 直连（深度） |
| 产出 | 实时状态/趋势/预警信号 | 巡检日报 + 复合工况 + 巡检质量评分 |
| 消费者 | 值班看盘 + early-warning | 巡检员 + 管理层考核 |

两者同读 `st_*` 表，但访问/触发/产出/消费者不同。分工在**两份 SKILL.md 对称**写明（不新建独立契约文档）。

## 4. 文件变更清单

### 新建
| 路径 | 内容 |
|---|---|
| `powerelf-inspection/lib/report.py` | 镜像 governance `report.py`：分节 → MD/JSON/HTML + 嵌 QA 闸 + 挂 confidence_tier + 附 data-quality tier caveat |
| `powerelf-inspection/lib/test_anomaly.py` / `test_quality.py` / `test_defect_predict.py` / `test_route_opt.py` | 纯函数单测（合成 fixture，脱离 DB）；含各 Bug 回归用例 |
| `powerelf-inspection/impl/registry.py`（或 `lib/datasource.py`） | 从 `inspection_tool.py` 抽出的数据采集层（`sys_data_source_registry` 读取 + 数据源匹配）；H2 SQL 参数化在此隔离 |
| `powerelf-inspection/references/few_shots.md` | JOIN-by-name 真 SQL（禁 `{占位符}`），覆盖 `ew_info_rules` / `st_river_r` / `business_check_task` |
| `powerelf-inspection/references/business_rules.md` | 带溯源领域字典：任务状态 1/2/3、`ew_type` 0–4、`type_flag`、`route.type` 10/20/30/40、`wptn`、`eq_equip_base.status` 0/1/2 |
| `powerelf-inspection/references/pitfalls.md` | inspection 专属 7 类陷阱（见 §5.4） |
| `_shared/rules/gate-pump-status.md` + `_shared/rules/gnss-deformation.md` | 从 `powerelf-monitor/rules/` 提升（第 2 个 skill 需要） |

### 修改
| 路径 | 改动 |
|---|---|
| `powerelf-inspection/SKILL.md` | 删实时监测模式（L221–320）→ 路由条目 + 「与 monitor 的分工」；加 When NOT to Use 路由表 / Pitfalls / Validation Gate / depth-mode；引用 `_shared/references/` 全套；Related Skills 加 monitor；修漂移（置信度公式对齐、Holt-Winters 等标 roadmap、趋势阈值 doc↔code 对齐、"24 测试/92 题"更正）；POWERELF_SKILLS_ROOT 标准导入片段 |
| `powerelf-inspection/lib/anomaly.py` | 瘦身为 5 层融合判定 + **真正实现置信度公式**（替硬编码 0.95，DD1）；L4 委托 governance MAD（修 M2）；L5 委托 correlation + 守非空（修 C3）；L2 修触发报告（M1）；L3 阈值对齐 docs（DD2） |
| `powerelf-inspection/lib/quality.py` | 修 C1（自定义权重分支）/ C2（缺陷率分母→`bad_num/real_objitem`，SELECT 补取该列）/ H1（敲定 `check_percent` 语义并落 schema+business_rules）；**接 governance 数据质量 tier**：缺陷率分子剔除传感器故障/卡滞/离线导致的假异常 |
| `powerelf-inspection/lib/defect_predict.py` | M3 标定阈值或标注为启发式 |
| `powerelf-inspection/lib/route_opt.py` | M4 改用 haversine（已有未用 helper） |
| `powerelf-inspection/lib/db.py` | 补导出 `get_readonly_sqlalchemy_url` |
| `powerelf-inspection/impl/inspection_analyzer.py`（1234→瘦） | 15 个 `analyze_*` 改为「读数→调 lib 内核+委托内核→追加发现」；H3（14 处 except:pass→记日志）；H2（SQL 参数化、白名单标识符）；H4（2-sigma→稳健 MAD 委托）；去重复 report（D5） |
| `powerelf-inspection/impl/inspection_tool.py` | C2/H2 同上；最小分离采集层到 `registry.py`（S4）；统一调 `lib/report.py` |
| `powerelf-inspection/impl/test_inspection.py` | 加 skip-if-unavailable 守卫（T4）；改调 analyzer 不重算（T1）；"无数据"改 skip（T2）；更正用例数 |
| `powerelf-inspection/references/{data-model,api-reference}.md` | 补溯源（来源） |
| `powerelf-monitor/SKILL.md` | `related_skills` 加 inspection；镜像「与 inspection 的分工」+ 路由条目 |

### 删除
| 对象 | 理由 |
|---|---|
| 根目录 `inspection/`（整个） | 未跟踪 stale 副本；lib 代码重复；SKILL.md 指向不存在的 `powerelf/lib/db.py` |
| `powerelf-inspection/references/database-schema.md` | 与 `_shared/references/schema.md` 重复 → 改指针 |
| `powerelf-inspection/SKILL.md` L221–320 实时监测模式 | 与 monitor 逐字重复 |
| `lib/` 内 3 份 MAD、2 份变化率、2 份趋势（lib 瘦身时） | 统一委托，去重 |
| `powerelf-monitor/rules/{gate-pump-status,gnss-deformation}.md` 提升后 | 改为指向 `_shared` 的指针（或删，由提升后同源引用取代） |

### Bug 修复映射
| Bug | 位置 | 落点 |
|---|---|---|
| C1 自定义权重分支数学不成立 | `lib/quality.py:188-195` | lib/quality.py |
| C2 缺陷发现率分母错（spec 要 `bad_num/real_objitem`，代码用 `plan_checkobj`） | `impl/inspection_tool.py:213-216` | lib/quality.py + inspection_tool.py |
| C3 相关性 `all([])==True` 空真 | `impl/inspection_analyzer.py:1038` | lib/anomaly.py + inspection_analyzer.py |
| H1 `check_percent` 完成率 vs 遗漏率自相矛盾 | data-model.md:121 ↔ quality-assessment.md:64-66 ↔ 代码 | lib/quality.py + schema/business_rules；**默认以 code 现行语义（遗漏率）为事实源**、同步修 data-model.md；若业务确认为完成率则反向修代码与 coverage 计算（待业务确认，见 ROADMAP §三） |
| H2 f-string 拼表/列名（注入面） | `impl/inspection_tool.py:158-172`、`inspection_analyzer.py:119` | impl/registry.py（隔离）+ 参数化 |
| H3 14 处裸 `except: pass` | `impl/inspection_analyzer.py`（61/77/122/159/189…） | 改记日志 + 非空错误 |
| H4 2-sigma 参数法用于偏态水位 | `impl/inspection_analyzer.py:250` | 改稳健 MAD 委托 |
| DD1 置信度公式未实现 | SKILL.md:184 ↔ anomaly-detection-hierarchy.md:64-72 | lib/anomaly.py 实现 + SKILL 对齐 |
| DD2 趋势阈值 doc（渗压≥12）≠ code（≥7） | anomaly-detection-hierarchy.md:38-43 ↔ inspection_analyzer.py:369/505/232 | **默认以 code 现行阈值（渗压≥7 / GNSS≥5）为事实源更新 doc**；若领域审查认定 doc 阈值更安全则反向修代码（待领域确认，见 ROADMAP §三） |
| D1/D3/S1/S2 死代码/重复/巨型文件 | lib/* ↔ impl/inspection_analyzer.py:1234 | lib 瘦身 + 接线 |
| T1/T2/T3/T4 测试不测真东西/假通过/需联库 | impl/test_inspection.py | 新单测 + 重写集成测试 |

## 5. 组件设计

### 5.1 `lib/anomaly.py`（瘦身后）
纯函数、吃序列、返回判定 dict，无 DB 耦合（DB 访问只在 impl）。
```python
def composite_anomaly_judge(layers, context) -> dict:
    """5 层融合 → {triggered_layers, confidence, severity, suggestion}.
    confidence 按 SKILL 文档公式：0.3×阈值 + 0.2×数据质量 + 0.2×趋势 + 0.2×历史 + 0.1×上下文（DD1 真正实现）."""
def layer5_correlation(series_a, series_b, rule) -> dict | None:
    """委托 governance/lib/correlation.py；守非空——空序列返回 None 而非 all([])==True（C3）."""
# L4 MAD：删除本地实现，调用 governance/lib/mad.py::detect_anomalies（M2）
```

### 5.2 `lib/quality.py`（修复后）
```python
def compute_quality_score(metrics, weights=_DEFAULT_WEIGHTS) -> dict:
    """4 维任务质量评分（30/25/25/20）。修 C1：自定义权重分支按 weights 归一化正确计分。
    C2：defect_rate = sum(bad_num) / sum(real_objitem)（非 plan_checkobj）。
    H1：check_percent 语义单一化为 [完成率]，文档/代码/schema 对齐。
    连接点：consume data_quality_tier(governance) 剔除传感器故障导致的假缺陷。"""
```

### 5.3 数据质量 tier → inspection 评分（连接点，read-only）
inspection 缺陷发现率计算前，调 governance `stagnation` / `extreme_event` / `offline` 结论标记「该异常为传感器问题」，从缺陷分子剔除；报告附设备 data-quality tier 作 caveat。inspection **只读** governance 产出，不写库。

### 5.4 `references/pitfalls.md`（inspection 专属 7 类）
1. `{st_id}`/`{equipment_code}` 占位符污染（规则文件现满是此反模式）→ 改 JOIN-by-name。
2. 关联键混乱 `eq_id`(bigint) / `stcd`(varchar) / `st_id`（`_shared/references/schema.md` 铁律）。
3. GNSS 表名不一致：规则里 `srm_gnss_data_day` vs schema/SKILL 的 `dsm_dfr_srvrds_srhrds`。
4. `ew_info_rules.extend` JSON 脆弱（`{"content":["248",null],"condition":">"}`）→ 用前验存在性 + well-formed（对齐 water-situation 阈值存在性校验）。
5. 泵站电参 `uab/ia/freq` 是 varchar，三相不平衡算术静默失败/强转。
6. 传感器故障 vs 真极端混淆（MAD 突跳被当真异常）→ 接 governance `stagnation`/`extreme_event` 区分。
7. 双数据库：本地 `powerelf_srm_yml` vs 远程 `sl323` 数据密度差异极大。

### 5.5 SKILL.md Validation Gate（采用 `_shared/references/analysis-qa-checklist.md` + inspection 专属）
交付前必过：关联键已核验 / `ew_info_rules` 数据存在性已确认 / 传感器故障已排除 / business_check 状态码正确 / 缺陷率已用 data-quality tier 校正；附三级置信度（Ready / With caveats / Needs revision）。

## 6. 数据流（重构后每日巡检）

```
[定时触发 每日凌晨]
   │
   ▼
读 _shared/lib/db.py 直连 → 取昨日窗口 12+ 类 st_* 数据（impl/registry.py 统一采集，SQL 参数化）
   │
   ▼
逐维度编排：per-dimension 检测委托（governance MAD / _shared 水位变化率·位移速率 / monitor 范畴规则）
   │
   ▼
5 层融合判定（lib/anomaly.py：阈值→变化率→趋势→MAD→相关性）+ 复合工况识别
   │   ├─ 缺陷率分子用 governance data-quality tier 剔除传感器故障（连接点）
   │   └─ 置信度按文档公式计算（DD1）
   │
   ▼
巡检业务分析（lib/quality.py 任务质量评分 / defect_predict.py / route_opt.py）
   │
   ▼
lib/report.py 组装日报（嵌 QA 闸 + confidence_tier + data-quality caveat）
   │
   ▼
依次过两道护栏：① analysis-qa-checklist.md（数字/逻辑）② statistical-caution.md（措辞）
   │
   ▼
交付（read-only，不写库；异常分发交 early-warning）
```

## 7. 错误处理

- **H3**：所有采集/解析异常改记日志 + 上抛/非空错误提示，不再 `except: pass` 静默吞；DB 不可达 → 非零退出 + 清晰提示（沿用 `_shared/lib/db.py`）。
- **H2**：表名/列名走白名单校验（`sys_data_source_registry` 的值与已知集合比对），参数用占位符绑定，禁 f-string 拼。
- **C3**：相关性判定守非空序列，空序列返回 None。
- **只读安全**：本轮无写库路径，重构不可能损坏数据。
- **QA 闸**：被动清单 + 三级评级，不自动打分（与 statistical-cautious 一致）；缺数据项标「无法核验」而非误报通过。

## 8. 测试与验证

1. **纯函数单测（CI 阻断、脱离 DB）** — `lib/test_*.py`，对齐 governance `test_outliers.py` 风格；覆盖 5 层判定/置信度公式/质量评分；**每 Bug 配回归用例**（C1 自定义权重、C2 缺陷率分母、C3 空序列、H1 check_percent、H4 偏态序列 vs 稳健 MAD、DD1 公式数值断言）→ 修 T1/T3。
2. **集成冒烟（联库、非 CI 阻断、skip-if-unavailable）** — 重写 `impl/test_inspection.py`：加守卫（T4）、改调 analyzer 不重算（T1）、"无数据"改 skip（T2）、更正用例数；runbook：`source ../_shared/bootstrap.sh && python3 impl/test_inspection.py --db "$DB_URL"`。
3. **文档/链接 grep 校验（CI）** — 确认 `_shared/references/` 引用齐全、规则无 `{占位符}`、schema 全指向 `_shared`、置信度公式 doc↔code 一致、few_shots SQL 无 `{`/`}`。
4. **手动冒烟（不入 CI）** — 联库跑 analyzer/tool 真日期窗口，人工核对报告渲染（MD/JSON/HTML）+ QA 闸节 + confidence_tier + data-quality caveat。

## 9. 分期

每期独立可合并，skill 期际保持可用；P0+P1 为安全最小集。

- **P0 清理**（无逻辑改动）：删 stale `inspection/`、删 dup schema 引用、删实时监测段→路由、monitor 对称编辑、2 rule 升 `_shared`。
- **P1 修 Bug**（correctness）：C1/C2/C3/H1/H2/H3/H4 + DD1/DD2。
- **P2 lib 瘦身 + 接线**（结构，最大）：抽内核、15 analyze_* 改调 lib+委托、删 3×MAD、实现置信度公式、inspection_tool 最小分离（采集→registry.py）、自建 `lib/report.py`。
- **P3 SKILL 重结构 + _shared 采用**（docs/护栏）：路由表/Pitfalls/QA 闸/depth-mode/few_shots/business_rules/修"24-92"/POWERELF_SKILLS_ROOT 片段/related_skills/连接 data-quality tier。
- **P4 测试**：Layer 1–4。

## 10. 关键决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 目标姿态 | Option 2：重构为聚焦巡检 skill | 平衡价值/风险，对齐 A→B→C 路线图 |
| 实时监测模式 | 整段删除交 monitor；inspection 保留离线回顾 | 与 monitor 逐字重复；划线=时间模式（实时 vs 离线回顾） |
| 15 维度引擎 | 保留但重架构（编排+融合，检测委托） | 每日巡检替代人工巡查的核心价值；检测委托消重 |
| lib/ vs impl/ | 瘦身 lib/ + 接线给 impl/ | 消死代码+三份 MAD；纯函数内核可脱离 DB 单测（顺带修 T1/T3） |
| 两套质量评分 | 并存不合并 | 量不同对象（数据可信度 vs 任务绩效）/不同源表/不同消费者；同名维度是假朋友；接口处用 data-quality tier 连接 |
| monitor 交互 | `_shared` 基底 + 路由双向，无代码 import | monitor 无 lib；monorepo 约定 |
| gate-pump/gnss-deformation rule | 升 `_shared/rules/` | 第 2 个 skill 需要（doc-only，低风险） |
| writeback | 本轮不做，保持只读 | 安全边界（不可自动确认告警）；留 Option 3 |
| report.py | 本轮自建镜像，不升 _shared | blast radius（不动 governance 工作代码）；待两份形状验证后再升 |
| inspection_tool 拆分 | 仅最小分离（采集 vs 分析） | lib 瘦身已做重活；6 路全拆 YAGNI；隔离采集=把 H2 关进笼子 |
| QA 闸 | 被动清单 + 三级评级，不自动打分 | QA 是判断题，自动评分假精度 |

## 11. 后续（不在本 spec 内）

已归档至持久路线图 [`docs/superpowers/ROADMAP.md`](../ROADMAP.md)（跨 spec 单一事实源，含触发条件与关联）。本 spec 推迟项：

- **report chassis 升 `_shared/lib/report.py`** —— 待两份 `report.py` 形状验证后抽底盘。
- **数据采集层升 `_shared`** —— `sys_data_source_registry` 读取 + 数据源匹配；第 3 个 skill 需要时。
- **profiling 升 `_shared/lib/profiling.py`** —— governance spec §9 已预见。
- **writeback（Option 3）** —— 建议式缺陷回写，安全边界就绪后。
- **全域三 skill 共享内核整合（Option 3）** —— 多项提升积累后。

> 待业务/领域确认项（H1 `check_percent` 语义、DD2 趋势阈值）亦见 ROADMAP §三。
