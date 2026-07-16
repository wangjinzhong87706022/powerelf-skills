# 复用与整合路线图 (ROADMAP)

跨 spec 的**持久跟踪**：各 skill spec 的「后续 / 不做 / 推迟提升」项集中归档于此，避免散落在单个 spec 尾部而丢失。新 spec 的 §后续 追加到本文件。

约定沿用 `2026-07-13-governance-profiling-qa-gate-design.md`：「方法论文档进 `_shared/`、可运行代码进 skill、判断类护栏为纯被动文档」；提升规则「代码先进一个 skill，第 2 个 skill 需要时升 `_shared/lib/` + 各 shim」。

---

## 一、A→B→C 复用簇

来源：外部通用数据技能 → powerelf 复用路线图（governance spec §9）。

| 簇 | 内容 | 状态 | 出处 |
|---|---|---|---|
| **A** | 治理域：数据画像 + 交付前 QA 闸 | ✅ 已实施 | `2026-07-13-governance-profiling-qa-gate-design.md` + plan（git `cd1fa58`/`ac30bbe`） |
| **B** | chatbi 增强：SQL 纪律 + 图表选择（去 Vanna，agent 自主 NL2SQL 直连库） | ✅ spec + plan 已落 | `2026-07-14-chatbi-devanna-agent-sql-design.md` + plan（git `3d578ed`/`49757f3`） |
| **C** | 元工具：`data-context-extractor` → schema 文档模板 / 打包脚本 | ⏳ 未启动 | governance spec §9 |

---

## 二、推迟提升 / 整合项（各 spec §后续 汇总）

### 来自 inspection 重构（`2026-07-16-inspection-refactor-design.md`）

| 项 | 现状 | 触发条件（何时做） | 关联 |
|---|---|---|---|
| **report chassis 升 `_shared/lib/report.py` + 各 shim** | inspection 本轮自建 `lib/report.py`（镜像 governance 模式） | inspection 与 governance 两份 `report.py` 形状都被实战验证后，抽渲染/QA 底盘 | spec §10 决策；连接 data-quality tier |
| **数据采集层升 `_shared`**（`sys_data_source_registry` 读取 + 数据源匹配） | 本轮隔离在 inspection `impl/registry.py` | 第 3 个 skill 也需要同类数据源采集时 | spec §10；含 H2 SQL 参数化 |
| **profiling 升 `_shared/lib/profiling.py`** | governance `lib/profiling.py` 内 | inspection 画像需求超过 governance 现有能力时 | governance spec §9 已预见；inspection data-quality tier 连接点 |
| **writeback（Option 3，建议式缺陷回写）** | inspection 保持只读 | 安全边界明确 + 人工确认流程就绪后 | spec §10；草拟 `business_check_error` 待确认，绝不自动确认 |
| **全域三 skill 共享内核整合（Option 3）** | inspection / monitor / governance 各自独立内核 | report / 采集 / profiling / MAD 多项提升积累后 | spec §10；MAD/report/writeback/采集 统一升 `_shared` |

---

## 三、待业务/领域确认项（实现前需拍板）

| 项 | 默认处置 | 升级条件 | 出处 |
|---|---|---|---|
| `check_percent` 语义（完成率 vs 遗漏率，H1） | 以 code 现行（遗漏率）为事实源，同步修 `data-model.md` | 业务确认为完成率 → 反向修代码与 coverage 计算 | inspection spec §4 |
| 趋势阈值 doc（渗压≥12）≠ code（≥7），DD2 | 以 code 现行阈值（渗压≥7 / GNSS≥5）为事实源更新 doc | 领域审查认定 doc 阈值更安全 → 反向修代码 | inspection spec §4 |

---

> 后续 spec 的 §后续 在「二」追加；待确认项在「三」追加。
