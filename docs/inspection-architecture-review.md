# 智能巡检方案架构评审与实测分析

> 生成时间：2026-08-13
> 评审对象：`powerelf-intelligent-inspection` v7.1.0（含 `inspection_analyzer.py` 引擎、15 维 / 5 层判定、业务内核）及其与 `powerelf-data-governance` 的协同
> 关联文档：[`inspection-run-analysis-and-optimization.md`](./inspection-run-analysis-and-optimization.md)（既有根因分析）、[`inspection-report-unification-spec.md`](./inspection-report-unification-spec.md)（落地设计，本文的姊妹篇）
> 评审方法：源码静态核查 + 真实 hermes 端到端运行轨迹抓取与报告实证

---

## 0. 执行摘要

**一句话结论**：巡检引擎本身（15 维 / 5 层判定 + 业务内核 + 自动诊断）是扎实的真实现，近 7 天实测对 5 台模拟问题设备 **5/5 命中、零误报**；但"巡检报告"不是单管道产物，而是 Agent 按 SKILL.md 边界设计**跨 skill 拼装** inspection + data-governance 输出的缝合体——这是本次报告全部 5 类问题的结构性根因。同时发现**置信度闸形同虚设**（程序层 `confidence_tier` 为硬编码字符串，"Ready to share" 是 Agent 自行断言）。

| 维度 | 评级 | 依据 |
|---|---|---|
| 检测引擎（15 维 / 5 层 / 自动诊断） | ⭐⭐⭐⭐½ | `lib/anomaly.py` 379 行真实现；实测 5/5 命中零误报；47 用例 Layer A 100% |
| 业务内核（质量/缺陷/路线） | ⭐⭐⭐⭐ | `quality.py` 311 / `defect_predict.py` 213 / `route_opt.py` 271 行，均有单测 |
| 报告生成管道 | ⭐⭐ | **无统一管道**：模板 39 行 + Agent 自由叙述；MAD/离线/置信度均非程序化 |
| 跨 skill 一致性 | ⭐⭐ | MAD 三套、离线三套；窗口/分组/计数单位分叉 |
| 置信度闸 | ⭐ | `confidence_tier="With caveats"` 硬编码；无一致性校验 |
| 自演化闭环 | ⭐⭐ | `feedback-log.md` 为规格模板，无真实条目；闭环=roadmap |
| 既有分析文档 | ⭐⭐⭐⭐⭐ | 根因扎实、实测对账；但归因有一处偏差（见 §10） |

---

## 1. 系统现状

### 1.1 工具链分层

| 层 | 工具 | 所在 skill | 作用 | 默认窗口 |
|---|---|---|---|---|
| 巡检主引擎 | `inspection_analyzer.py` | inspection | 15 维异常 + 5 层判定 + 自动诊断 + 报告渲染 | `--days`（用户指定） |
| 巡检业务 | `inspection_tool.py` | inspection | 质量评分 / 缺陷预测 / 路线优化 | 自定义起止 |
| MAD 统计（A） | `inspection_analyzer.py::analyze_mad_anomaly` | inspection | 按 `st_id` 分组、带季节护栏 | `--days` |
| MAD 统计（B） | `data-governance/impl/anomaly_detector.py` | data-governance | **全表混排**、无分组 | **30 天** |
| 离线（台账） | `classify_offline_by_duration.py` | data-governance | LEFT JOIN 离线记录分级 | **全历史（无窗口）** |
| 离线（新鲜度） | `offline_detector.py` | data-governance | `MAX(tm)` 距今超阈值推断 | 实时（阈值 bug，见 §6） |
| 离线（快照） | `inspection_analyzer.py::analyze_equipment` | inspection | `eq_equip_base.status=0` 计数 | 与窗口无关 |

### 1.2 实施深度核实（纠正"半成品"印象）

直接读内核代码，业务模块**均为真实实现，非 stub**：

| 文件 | 行数 | 实现深度 |
|---|---|---|
| `lib/anomaly.py` | 379 | 5 层判定内核 + `composite_judge` + `mad_anomaly` + `consecutive_monotonic` |
| `lib/quality.py` | 311 | 4 维评分（完成/及时/缺陷/覆盖）+ 分级 + 告警 |
| `lib/defect_predict.py` | 213 | 线性趋势 / 季节分析 / 贝叶斯热点 |
| `lib/route_opt.py` | 271 | 聚类（haversine）/ 时间均衡 / 优先级 / 诊断 |
| `impl/registry.py` | 214 | 数据源注册表 + `_ALLOWED_TABLES` SQL 注入白名单 |
| `impl/verify_output.py` | 141 | envelope 一致性 + red-flag 元检查 |
| `autoresearch/eval_cases/` | 47 用例 | Layer A 无库评测，最新 误报 0 / 漏报 0 / 根因链 1.0，47/47 通过 |

> 结论：引擎与业务内核是工程级实现，带正负样本与回归覆盖。**本评审的所有问题均不在引擎层，而在报告组装层与置信度闸。**

---

## 2. 核心架构问题：报告非单管道产物

### 2.1 事实

- `inspection_analyzer.py:1676 generate_report` 内部是**自洽的**：15 个 `analyze_*` 共享同一 `days` 窗口与统一 findings schema；`analyze_mad_anomaly`（`:1262`）已正确**按 `st_id` 分组**（`:1279`）并带季节护栏（`:1300`）；`analyze_equipment`（`:889`）是 `status` 快照计数。**它自己生成的报告不会出现本次的 5 类问题。**
- 但交付报告里出现了"524 条记录""全表混排 507 次变化率""MAD 只 4 维被当成 15 维""42.2%(54/128)"——这些**只能来自额外混入的 data-governance 输出**。
- 已确认：报告模板 `references/report-template.md`（39 行）**零引用** governance；全仓库**无 orchestrator** 脚本同时运行两 skill。故混装只可能发生在 **Agent 交付层**。

### 2.2 根因（实测确认，见 §3-4）

不是 Agent"擅自"混装——而是 **inspection SKILL.md 的"When NOT to Use"表主动把 MAD/离线 转交给 data-governance**（`SKILL.md:128-131`）。Agent 面对含"MAD统计""设备状态"的提示词，按边界指引**合规地**调用了 governance 工具。**只要边界表这么写，跨 skill 组装就结构性必然。**

### 2.3 三套重复逻辑（技术债）

- **MAD 三份**：inspection `analyze_mad_anomaly`（按 st_id，正确）/ governance `anomaly_detector.py`（全表混排）/ `_shared/lib` outliers。
- **离线三份**：inspection `analyze_equipment`（快照）/ `classify_offline_by_duration`（记录无窗）/ `offline_detector`（新鲜度，阈值 bug）。

---

## 3. 实测：真实 hermes 运行轨迹

### 3.1 会话信息

| 指标 | 实测值 |
|---|---|
| 会话 ID | `20260813_140543_8f197a`（可 `hermes sessions export` 复查） |
| 模型 | 本地 `Qwen3.6-27B-Q4_K_S.gguf`（量化 27B） |
| 工具调用 | 16 次 / 8 轮 API / cache_read 283,939 tokens / 估算成本 $0 |
| 提示词 | "对全部设备执行一次完整智能巡检：覆盖近 7 天所有监测维度…三问结构报告" |

### 3.2 调用顺序

```
skill_view ×3  → powerelf-intelligent-inspection ✅
                → powerelf-data-governance       ✅
                → powerelf-monitor               ❌ "Ambiguous: 2 skills match, Refusing to guess"
todo (计划)
terminal ×1    → inspection_analyzer.py --days 7          （正确，envelope ok）
terminal ×1    → classify_offline_by_duration.py          （governance 离线）
terminal ×4    → anomaly_detector.py  ×4 表               （governance MAD，冗余）
terminal ×4    → profiler.py          ×4 表               （governance 行数，冗余）
todo (更新)
assistant      → 合成 "# 水利工程智能巡检报告…"（混装产物）
```

### 3.3 轨迹级发现

1. **跨 skill 加载是设计使然**：inspection + governance 同时被 `skill_view` 载入；Agent 按提示词中的"MAD统计/设备状态"主动调用 governance 9 次。
2. **`powerelf-monitor` 路由失败**：版本目录重复导致 2 个同名 skill，加载被拒。
3. **8 次 governance 调用纯冗余**：`anomaly_detector`×4 重复 inspection 已自带的 4 表 MAD；`profiler`×4 重复行数统计。

---

## 4. 实测：返回报告实证（5 问题全部复现）

| # | 文档问题 | 报告原文 | 库内实测（2026-08-13） | 判定 |
|---|---|---|---|---|
| ① | 离线数偏多 | "总离线设备 524 台记录… 42.2% (54/128)" | `status=0` 实为 **54/149 = 36.2%** | ❌ 记录/设备混用 + 分母过期 |
| ② | MAD 只 4 维 | "数据质量评分"表仅 水位/雨量/渗压/渗流 | 来自 4× anomaly_detector | ❌ 跨工具拼接 |
| ③ | 渗压 507 却正常 | "渗压 0.0% \| 507 次 \| 数据分布正常" | 全表混排基线误报 | ❌ 自相矛盾 |
| ④ | MAD 率虚高 | "水位 21.6% / 雨量 19.0%" | 报告自注"~786m MOCK 高值" | ❌ 7–30 天 MOCK 残留 |
| ⑤ | 前后不一致 | "15 维度全部成功" vs "水质/墒情/白蚁无数据" | 4 维无数据 | ❌ 自相矛盾 |

### 4.1 引擎正面实证（最重要的肯定）

5 台模拟问题设备**全部命中、零误报**，与 `simulate_7d_data.py` 设计一一对应：

| Finding | 设备 | 现象 | 设计预期 |
|---|---|---|---|
| F005 🔴 | GNSS 测站97 | 速率 1.2mm/d（>1.0 II 级）+ Δh 12mm | CRITICAL ✅ |
| F003/F004 🟡 | 渗压计93 | 突变 +17.08kPa + MAD z=57.6 | WARNING ✅ |
| F007 🟡 | 闸门90 | 开度 1.18→2.50m（+1.32m） | WARNING ✅ |
| F008 🟡 | 泵站89 | 三相 50/62/38A，不平衡 24% | WARNING ✅ |
| F001/F002 🔵 | 雨量85 | 单时段 35mm，蓝色预警 | INFO ✅ |

三问结构（严重程度 / 根因 / 下一步行动）、P0–P2 行动表、根因链（"水位-渗压因果链已验证"、"-2h 水位变幅"）均正确落地。**自动诊断路由 Phase 2 工作正常。**

> **结论：引擎不需要改动。问题 100% 在报告组装层与置信度闸。**

---

## 5. 新发现（既有分析文档未覆盖）

| # | 发现 | 证据 |
|---|---|---|
| **N1** | **置信度闸形同虚设** | `inspection_analyzer.py:1772` 硬编码 `confidence_tier="With caveats"`；程序层无任何一致性计算。报告里"Ready to share"是 Agent 自行断言。带 5 处内部矛盾的报告被评为可分享。 |
| **N2** | **根因比文档深一层** | 不是 Agent 擅自混装，是 SKILL.md 边界表主动转交 governance（`SKILL.md:128-131`）。结构性必然跨 skill。 |
| **N3** | **离线分母过期** | 42.2%(54/128)；库内 `eq_equip_base` 现为 149 台，应为 36.2%(54/149)。 |
| **N4** | **monitor 路由歧义** | `skill_view` 返回 "Ambiguous: 2 skills match"；版本目录重复。 |
| **N5** | **governance 调用冗余** | `anomaly_detector`×4 + `profiler`×4 重复 inspection 已算的 MAD/行数。 |

> **N1 是本次实测最重要的发现**：号称"Ready to share"的报告带着 5 处矛盾出厂。现有 QA 闸（`_QA_CHECKLIST`）只渲染静态文本，**不校验跨章节数值一致性**。这是性价比最高的修复点。

---

## 6. 两个确认的真实 bug

### 6.1 `offline_detector.py:91` 阈值键不匹配（P0）

```python
DEFAULT_THRESHOLDS = {"SP": 360, "GN": 60, "PP": 60, ...}   # 键 = 站类型码
threshold = DEFAULT_THRESHOLDS.get(table, 60)                # table = 表名(st_rsvr_r)
```
键是站类型码（SP/GN/…），传入却是表名 → **永不命中 → 全量 fallback 60 分钟**。`dg_equip_offline` 里 SP=360/PP=120/YZ=0 配置从未生效，解释了"渗压计批量判离线 76 天"。既有文档 P0#3 完全正确。

### 6.2 测试库 MOCK 污染（P0）

`simulate_7d_data.py:97 _delete_window` 只清 `days` 窗口。上一代 MOCK（rz≈786m / p=60mm）残留在 7–30 天带，污染 `anomaly_detector` 30 天 MAD → 水位 21.6% / 雨量 19% 虚高。既有文档 P0#1 正确。

---

## 7. 目标架构方案

**核心原则：一份报告 = 一个管道 = 一份契约。**

### 7.1 确立 `inspection_analyzer.py` 为唯一报告生产者

它已具备 15 个同窗同 schema 维度 + 自带按 st_id 的 MAD + 设备快照。离"唯一生产者"差两步：
1. 把离线三口径补进 `analyze_equipment`；
2. **从 SKILL.md 删除"MAD/离线 → 转 governance"的边界指引**，从源头切断 Agent 的跨 skill 调用（否则 Agent 下次仍会按指引调 governance）。

### 7.2 契约五要素（跨 skill 若需共存则必须对齐）

| 要素 | 规则 |
|---|---|
| 观测窗口 | `--days` 是唯一驱动计数的窗口 |
| 基线窗口 | 30 天 MAD / 全历史离线严重度只作"判定依据"，单独成列，不混入汇总 |
| 计数单位 | 每个数字标单位（设备数 vs 记录数）；汇总用 `DISTINCT eq_id` |
| 分组 | 所有传感器统计按 `st_id` 分组（禁全表混排） |
| 共享 envelope | findings/stats 加 `window`、`count_unit` 字段 |

### 7.3 离线三口径（采纳既有文档 §6.4）

| 口径 | 回答 | 计算 | 语义 |
|---|---|---|---|
| A 当前快照 | 现在多少离线 | `eq_equip_base.status=0` | 实时 |
| B 窗口内新增 | 本周期新发生几次 | `offline_start_time ∈ 窗口` | 跟随 `--days` |
| C 窗口内活跃度 | 本周期谁没产数据 | 窗口内 `COUNT(DISTINCT eq_id)` | 跟随 `--days` |

汇总只统计 B+C，A 单列。**前提：先修阈值 bug，否则 C 无意义。**

---

## 8. 实施方案（实测重排后的优先级）

> 既有文档把 5 个症状拆成 P0–P2 共 10 项分别修；实测表明应先立"一致性闸 + 切断跨 skill 调用"，可塌缩多项。详见 [`inspection-report-unification-spec.md`](./inspection-report-unification-spec.md)。

| 优先 | 动作 | 针对 | 工作量 |
|---|---|---|---|
| **1** | 报告一致性断言闸（`generate_report` 末尾，~40 行） | N1 + 全部 5 问题 | 小 |
| **2** | 删 SKILL.md 的 MAD/离线 转交指引 + 报告路径停用 governance MAD/offline | N2 + N5 | 小 |
| **3** | 修 `offline_detector.py:91` 阈值键（按 st_type 读 `dg_equip_offline`） | 离线误判 | 小 |
| 4 | 离线分母实时化（`analyze_equipment` 实算 total） | N3 | 极小 |
| 5 | MOCK 清理扩 30 天 / 全清 `eq_code='MOCK'` | 问题④ | 小 |
| 6 | 清理 monitor 版本目录重复 | N4 | 小 |
| 7 | MAD/离线 DRY 下沉 `_shared/lib` | 三套重复 | 中 |
| 8 | 报告增强（图表/窗口声明/三口径） | 体验 | 中 |

**"只做 3 件事"即可消除本次全部可见问题**：① 一致性闸 ② 删边界指引 ③ 修阈值键。

---

## 9. 风险与建议

- **最大风险**：停用 governance MAD/offline 进报告，可能被当成"能力倒退"。需讲清：那不是丢能力，而是**消除一个制造假阳性的重复实现**，inspection 已有等价且更准的能力。
- **顺序铁律**：阈值修复（优先 3）必须在三口径（C）之前，否则 C 建立在错误阈值上。
- **回归保护**：任何改动后必须重跑 `simulate_7d_data.py` + `inspection_analyzer --days 7`，确认 **5/5 命中零误报不退化**（这是引擎红线，见 [`inspection-analyzer-end-to-end-smoke`](../) memory）。

---

## 10. 对既有分析文档的 meta 评审

**优点**：根因到 SQL/字段级、有实测对账（§9）、窗口语义论证严谨、三口径离线思路优秀、5.2"B 为主 + A 一致性约束"与本文契约方案完全一致——认可采纳。

**三处需修正**：

1. **问题②③归因偏差**：文档说"MAD 来自 data-governance 的 `anomaly_detector`，inspection 是另一套工具"。但 `inspection_analyzer.py:1262` 本就有正确的按 st_id MAD。真正问题是**两套都跑且混装**。故 P0#2"让 anomaly_detector 按 st_id 分组"是次优解——更干净的是报告路径停用全表那份。
2. **未点出"无报告管道 + 边界转交"这一总根因**：把 5 症状拆成 10 项。先立唯一生产者 + 删边界指引，可塌缩多项。
3. **缺"可复现性 + 置信度闸"维度**：报告数字不可复现（4.5 #3），且置信度闸是硬编码（N1）。应：每份报告 embed 自身运行参数；置信度由程序化一致性闸驱动而非 Agent 断言。
