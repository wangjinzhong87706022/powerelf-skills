# 水利知识图谱语义层建设方案（知识图谱四要素 + 子图召回落地）

> **维护者**：powerelf 团队 · **最后更新**：2026-08-10
> **关联文档**：`docs/aiops-articles-synthesis-and-roadmap.md`（演进路线图）·
> `docs/water-conservancy-knowledge-graph-and-root-cause-ranking.md`（物理拓扑建图 + 根因排序既有方案）
> **知识来源**：`/home/scada/SmartTwinRes-skills/pdfs/`（桃曲坡水库核心文档）· 现有项目代码资产

---

## 〇、背景与目标

### 0.1 现状：物理拓扑层已建成，语义知识层缺失

early-warning-v3 已落地**物理拓扑图谱**（`topology-schema.sql` + `build_topology.py`）：

- `topo_node`：6 类物理节点（project / station / device / dam / section / point），从 11 张业务表抽取 364 节点
- `topo_edge`：4 种物理边（belongs_to / upstream_of / causes / near），832 边
- `causal-rules.json`：25 条水利因果规则（CR-001~025，含因果延迟 lag_min/lag_max），驱动 causes 边与根因排序时序校验
- `topo_alarm_event`：告警收敛 → 故障事件落盘 + 五维根因打分

但对照文章二（阿里根因 Agent）的**知识图谱四要素**：

```
原始工单 ──引用──> 根因空间 ──引用──> Skills ──引用──> Tools
```

powerelf 的对应物**散落各处、未建引用网络**：

| 四要素 | powerelf 现状 | 缺什么 |
|--------|--------------|--------|
| 工单/案例 | `powerelf-inspection/state/inspection_runs.jsonl`（真实运行记录）、PDF 历年洪水资料（2008/2013/2019/2020/2021 洪水调度汇报） | 未结构化、未入库 |
| 根因空间 | 15 维度是**检测维度**（检什么异常），根因层（为什么异常）缺失；`causal-rules.json` 只有物理因果链 | 缺标准根因节点 + 症状→根因映射 |
| Skills | inspection `rules/*.md`（13 个）、`_shared/rules/*.md`（5 个）、`early-warning-v3` 规则文档 | Markdown 平铺，无法 lint/回放，未建引用 |
| Tools | `impl/` 可执行函数（inspection_analyzer.py / inspection_tool.py / eval_runner.py）、`lib/`（anomaly.py / db.py / topology.py） | 未注册为工具节点，未接引用 |

### 0.2 本方案目标

1. 在物理拓扑之上**叠加语义知识层**：把 PDF 文档、规则、案例、根因、工具注册为图谱节点，建引用网络；
2. 复用现有 `topo_node/topo_edge` 存储模式（轻量 MySQL 边表，**不引入 Neo4j**），新增语义表，物理层与语义层桥接；
3. 实现**运行时子图召回 + 四段注入**（CASE / CAUSE / SKILL / TOOL），对齐文章二最优雅设计；
4. 与路线图衔接：Phase 1 在 inspection 单模块闭环验证，Phase 2 抽共享层。

---

## 一、双层图谱总体架构

```
┌────────────────────────── Layer 2 语义知识层（本方案新增）──────────────────────────┐
│  doc(文档) ──derived_from──> regulation(规程条款) ──constrains──> action(处置措施)    │
│  doc ──records──> case(历史案例) ──has_symptom──> root_cause(标准根因)                │
│  case ──references──> skill(规则) ──references──> tool(可执行工具)                    │
│  root_cause ──mitigated_by──> action            skill ──implements──> tool           │
└──────────────┬──────────────────────────────────────────────┬───────────────────────┘
               │ relates_to（桥接：语义节点挂到物理节点）       │ belongs_to（物理层级）
┌──────────────┴──────────────────────────────────────────────┴───────────────────────┐
│                    Layer 1 物理拓扑层（early-warning-v3 已有）                        │
│  project ──belongs_to──> station ──belongs_to──> device/point/section/dam           │
│  upstream_of（水力上下游）/ causes（CR-001~025 物理因果链）/ near（空间邻近）         │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**设计要点**：

- **物理层与语义层分表存储**（`topo_node/topo_edge` 已存 364 节点，不混入语义节点，避免污染根因排序与爆炸半径 BFS）；
- 语义层节点通过 `relates_to` 边挂到物理节点（如「汛限水位超限」根因 → station:XXX），召回时可从语义节点跳到物理子图；
- 语义层**不需要**告警聚合/爆炸半径能力，它的职责是「知识检索 + 注入」，查询是只读的。

---

## 二、语义节点类型设计

### 2.1 新增 8 类语义节点（node_type 前缀 `sem_` 区分物理层）

| node_type | 含义 | 知识来源 | 关键属性 | 示例 |
|-----------|------|----------|----------|------|
| `sem_doc` | 文档 | PDF 四案/鉴定/水情通报；项目 rules/*.md | title / source / category / page | 桃曲坡水库调度规程 |
| `sem_regulation` | 规程条款（可执行的规则条款） | 调度规程、汛期调度运用计划 | clause_no / trigger_condition / rule_text / source_doc | 「库水位达汛限 786.80m 停马栏河引水，开低洞/溢洪道闸门」 |
| `sem_parameter` | 水库特征参数 | 调度规程「水库运用参数」、基础数据曲线 | param_name / value / unit / source_doc / applies_to(节点) | 总库容 5720万m³、坝高 61m、汛限 786.80m（主汛期）/ 788.00m（次汛期） |
| `sem_case` | 历史案例（工单/洪水事件） | inspection_runs.jsonl、PDF 历年洪水汇报、feedback-log.md | occurred_at / symptom_summary / diagnosis_path / resolution / outcome | 2021-10 洪水调度案例、2020-8-16 洪水案例 |
| `sem_root_cause` | 标准根因 | 由案例聚类归并（人工确认）；causal-rules 根因层 | definition / typical_symptoms / counter_examples / dimension | 「闸门开度异常导致出库流量超限」 |
| `sem_skill` | 规则（Skill 化载体，目标 YAML） | inspection rules/*.md、_shared rules/*.md、causal-rules.json | trigger / steps / output_format / related_root_cause / version | rainfall-analysis.md、trend-detection.md |
| `sem_tool` | 可执行工具 | impl/*.py、lib/*.py | signature / params /适用条件 / owner_skill | inspection_analyzer.generate_report()、lib/topology.py:rank_root_causes() |
| `sem_action` | 处置措施（预案动作） | 防洪抢险应急预案、大坝安全管理应急预案、调度规程 | action_steps / prerequisite / authority / risk_level / hitl_required | 「开溢洪道 2#闸门 0.5m 泄流」「启动Ⅲ级应急响应」 |

### 2.2 物理节点扩展

物理层已有 6 类；若 PDF 中存在未覆盖对象（如抢险物资、视频监控点位），可在 Layer 1 追加 `inspection_obj`（schema 中已预留该类型），本方案暂不扩展。

---

## 三、语义边类型设计

| edge_type | 方向 | 含义 | 示例 |
|-----------|------|------|------|
| `derived_from` | 语义→语义 | 条款/参数/预案出自文档 | sem_regulation →derived_from→ sem_doc |
| `records` | 文档→案例 | 文档记载历史事件 | sem_doc →records→ sem_case |
| `has_symptom` | 案例→根因 | 案例呈现的症状指向标准根因 | sem_case →has_symptom→ sem_root_cause |
| `references` | 案例/根因→技能 | 处置该问题用到哪条规则 | sem_case →references→ sem_skill |
| `implements` | 技能→工具 | 规则执行依赖的工具 | sem_skill →implements→ sem_tool |
| `mitigated_by` | 根因→处置 | 该根因的处置措施 | sem_root_cause →mitigated_by→ sem_action |
| `constrains` | 条款→处置 | 规程限制的处置动作 | sem_regulation →constrains→ sem_action |
| `relates_to` | 语义→物理 | 语义节点挂到物理对象 | sem_parameter →relates_to→ station:XXX（汛限水位→水库站） |
| `similar_to` | 语义→语义 | 案例相似（聚类归并产物） | sem_case →similar_to→ sem_case |

边字段复用 `topo_edge` 模式：`weight`、`evidence`（人类可读依据，如「pdf 调度规程 §3.2」）、`rule_id`。

---

## 四、存储 schema（轻量 MySQL 边表，延续既有方案）

物理层复用现有 `topo_node/topo_edge/topo_alarm_event`（不修改）。语义层新增 2 张表：

```sql
-- ============================================================
-- 表 1: sem_node — 语义知识节点表
-- ============================================================
CREATE TABLE sem_node (
  node_id       VARCHAR(80)  NOT NULL               COMMENT '节点ID, 格式 sem_xxx:{id}, 如 sem_case:20211006-001',
  node_type     VARCHAR(20)  NOT NULL               COMMENT 'sem_doc/sem_regulation/sem_parameter/sem_case/sem_root_cause/sem_skill/sem_tool/sem_action',
  ref_id        VARCHAR(64)  NOT NULL               COMMENT '来源标识（PDF 文件名+页码 / 规则文件名 / 函数名等）',
  name          VARCHAR(255) NOT NULL               COMMENT '节点显示名',
  content       TEXT                    DEFAULT NULL COMMENT '正文（规则全文/案例摘要/条款原文），子图召回时序列化注入',
  properties    JSON                  DEFAULT NULL COMMENT '扩展属性: 来源/分类/版本/标签/向量化的文本字段',
  embedding     BLOB                    DEFAULT NULL COMMENT 'content 的向量（维度对齐所选 embedding 模型）, 用于语义召回',
  tenant_id     BIGINT       NOT NULL DEFAULT 1,
  deleted       BIT(1)       NOT NULL DEFAULT b'0',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (node_id),
  UNIQUE KEY uk_type_ref (node_type, ref_id),
  KEY idx_type (node_type),
  KEY idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='语义知识节点表 — 文档/条款/参数/案例/根因/技能/工具/处置';

-- ============================================================
-- 表 2: sem_edge — 语义引用边表
-- ============================================================
CREATE TABLE sem_edge (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  from_node     VARCHAR(80)  NOT NULL               COMMENT '起始节点 node_id',
  to_node       VARCHAR(80)  NOT NULL               COMMENT '目标节点 node_id（可为物理节点 station:123, 即 relates_to 桥接）',
  edge_type     VARCHAR(20)  NOT NULL               COMMENT 'derived_from/records/has_symptom/references/implements/mitigated_by/constrains/relates_to/similar_to',
  weight        DECIMAL(5,2) NOT NULL DEFAULT 1.00,
  evidence      VARCHAR(500)          DEFAULT NULL  COMMENT '建图依据（PDF §页码 / 文件行号 / 人工录入）',
  tenant_id     BIGINT       NOT NULL DEFAULT 1,
  deleted       BIT(1)       NOT NULL DEFAULT b'0',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_edge (from_node, to_node, edge_type),
  KEY idx_from (from_node, edge_type),
  KEY idx_to (to_node, edge_type),
  KEY idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='语义引用边表 — 知识图谱语义层关系存储';
```

**为何不用现有 `topo_node` 直接扩类型**：物理层 BFS（爆炸半径/故障团）与语义层检索（子图召回）的
访问模式、数据规模、更新频率都不同；合并会拖慢告警侧查询并让建图脚本互相耦合。分表 + `relates_to`
桥接是成本最低的隔离方案。

---

## 五、建图流程（四源抽取 + 人工兜底）

### 5.1 源 A：PDF 核心文档 → 条款/参数/处置节点（新脚本 `scripts/build_sem_from_pdfs.py`）

对 `pdfs/01-核心文档-四案/`（调度规程 / 汛期调度运用计划 / 防洪抢险应急预案 / 大坝安全管理应急预案）
做**人工辅助半自动抽取**（PDF 文本可用 `pdftotext` 提取，条款结构化需人工确认后入库）：

| 抽取对象 | 目标节点 | 示例（调度规程实况） |
|----------|----------|----------------------|
| 水库概况/参数表 | sem_parameter | 总库容 5720万m³；坝高 61m；坝长 259m；溢洪道 7 孔 10.5×5.5m 闸门；泄流净宽 73.5m；低放水洞洞径 3m、最大流量 97m³/s |
| 汛限水位 | sem_parameter + constrains → sem_action | 主汛期(7/8/9月) 786.80m；次汛期(6/10月) 788.00m；汛期严禁长时间超汛限运行 |
| 防洪调度三阶段 | sem_regulation | 「库水位达汛限→停马栏河引水、开低洞/溢洪道闸门（控制泄流段）→ 无法维持时全开（自由泄流段）→ 回落后闸控维持汛限」 |
| 供水约束 | sem_regulation | 高干各站引用流量 ≥0.3m³/s、调整步长 ≥0.2m³/s；低洞出库 ≥10.0m³/s、调整 ≥1.0m³/s |
| 应急响应分级与动作 | sem_action | 应急响应启动条件、开闸泄流步骤、抢险物资调用（PDF 07 抢险物资信息） |
| 历史洪水事件 | sem_case | 2021-09/10、2020-8-16、2019-9-14、2013-7-22、2008-8-22 洪水调度汇报（PDF 06） |

### 5.2 源 B：现有规则文档 → skill/tool 节点（脚本 `scripts/build_sem_from_rules.py`）

- 遍历 `powerelf-inspection/rules/*.md`（13 个）、`_shared/rules/*.md`（5 个）→ 每条规则一个 `sem_skill` 节点，
  `content` 存规则正文；首行 metadata（触发条件/步骤）写入 `properties`；
- 扫描 `impl/*.py`、`lib/*.py` 的函数签名（`list_symbols` 可得）→ 每个可执行函数一个 `sem_tool` 节点；
- `sem_skill →implements→ sem_tool`：规则正文里提到的函数名建边（grep 式关联，人工复核）；
- `causal-rules.json` 25 条：每条生成 `sem_skill` 节点（触发=from_type+from_subtype 异常，步骤=沿 causes 链
  排查），同时已生成物理 causes 边，语义层仅登记「这条规则用在哪」。

### 5.3 源 C：真实运行记录 → case 节点（脚本 `scripts/build_sem_from_runs.py`）

- `powerelf-inspection/state/inspection_runs.jsonl`：每次巡检的运行记录 → `sem_case`（symptom_summary 取
  异常 finding、resolution 取处置结论、outcome 取验证结果）；
- `evolution/feedback-log.md`：人工记录的误报/漏报案例 → `sem_case`（outcome=误报/漏报，这是 Skill 自进化
  与覆盖率统计的关键输入）；
- 相邻两阶段产出 `sem_root_cause`：把症状文本聚类（向量 + 关键词），人工确认为标准根因后建
  `sem_case →has_symptom→ sem_root_cause`。

### 5.4 源 D：人工维护的引用表（兜底 + 起步）

Phase 1 阶段（1~2 周）可先手工维护一份 JSON 引用表（对齐路线图「先建引用关系表，哪怕 JSON 手工维护」）：

```json
{
  "skills": [
    { "name": "rainfall-analysis", "path": "powerelf-inspection/rules/rainfall-analysis.md",
      "trigger": "降雨量骤增", "tools": ["inspection_analyzer.generate_report"], "root_causes": ["暴雨入库"] }
  ],
  "cases": [
    { "id": "20211006-001", "source": "pdfs/06-历年洪水资料", "symptom": "连续暴雨→库水位快速上涨→超汛限",
      "root_cause": "强降雨入库", "actions": ["停马栏河引水", "开溢洪道闸门泄流"], "outcome": "成功" }
  ]
}
```

### 5.5 建图顺序与验收

| 步骤 | 内容 | 验收标准 |
|------|------|----------|
| 1 | 建 `sem_node/sem_edge` 表 | DDL 执行成功，索引齐全 |
| 2 | 源 A：人工抽取调度规程 + 应急预案（最高价值，先做） | ≥10 条参数/条款/处置节点，constrains 边成链 |
| 3 | 源 B：规则文档扫描入库 | 13+5 规则全入库，skill→tool 边 ≥50% 覆盖率 |
| 4 | 源 C：运行记录入库 | inspection_runs.jsonl 全量入库，误报/漏报案例带标签 |
| 5 | 根因聚类 | 首轮人工确认 ≥20 个标准根因 |
| 6 | 混合检索验证 | 用 cases.json 评测集跑「召回率@5 ≥ 60%」 |

---

## 六、运行时子图召回 + 四段注入（对齐文章二）

### 6.1 召回流程

```
新告警/新症状 → 提取症状特征文本
             → 混合检索（BM25 关键词 + sem_node.embedding 向量，合并去重打分）
             → 命中候选：sem_case（相似历史案例）/ sem_root_cause（候选根因）
             → 沿引用网络 BFS 拉小子图（references / implements / mitigated_by / constrains / relates_to）
             → 按相关性截断（每类 TOP3）
             → 序列化为四段注入诊断 Agent：
                 CASE  : 相似历史案例（症状 / 排查路径 / 处置结论 / outcome）
                 CAUSE : 候选根因（定义 / 典型症状 / 反例边界）
                 SKILL : 关联规则（触发条件 / 步骤模板 / 输出格式）
                 TOOL  : 工具清单（签名 / 参数 / 适用条件）
```

### 6.2 实现要点

- **检索层**：BM25 可用 SQL `LIKE` + 词频打分起步（MySQL 无内置 BM25），向量可用现有 LLM embedding；
  量小（<1k 节点）时 BM25 + 关键词已够，向量作为 Phase 2 增强；
- **子图 BFS**：复用 `lib/topology.py` 的 BFS 思路，但查询对象是 `sem_edge`——写一个
  `retrieve_subgraph(symptom_text, max_nodes=12)`，先检索命中的 sem_case/sem_root_cause，
  再沿引用网络取一跳关联（skill → tool → action）；
- **四段注入**：把子图节点 `content` 截断（每段 ≤800 字）后拼进诊断 Prompt 的 system 上下文，
  与 inspection 现有诊断路由（`references/diagnosis-routing.md` 的 DIAG_ROUTES）衔接——先路由后注入，
  注入的 CASE/CAUSE/SKILL 用于辅助判断，不覆盖既有规则判定；
- **效果对照**：用 `powerelf-inspection/autoresearch/eval_cases/cases.json` 评测集跑
  「注入前 vs 注入后」的误报率/漏报率/根因链率（既有 runner `impl/eval_runner.py` 已支持），
  此即路线图 Phase 1 的实验报告交付物。

### 6.3 与物理拓扑的协同

| 场景 | 物理层（已有） | 语义层（新增） |
|------|--------------|---------------|
| 告警来了一条渗压超限 | 沿 belongs_to 找到所属测站/大坝，causes 链找上游降雨/水位 | 检索相似渗压案例、相关规则（渗压诊断）、处置动作 |
| 汛期水位逼近汛限 | 爆炸半径评估影响面 | 召回调度规程条款（sem_regulation）+ 处置动作（开闸泄流） |
| 根因排序 TOP1 确认 | 五维打分 + 置信度闸 | 回灌：把本次根因记入 sem_case，误报/漏报进 feedback-log |

---

## 七、与路线图衔接

| 路线图条目 | 本方案的落地动作 |
|-----------|-----------------|
| P0-1 拆两问 | ①物理拓扑复用评估（topo_node 三表已 DB 化，迁 `_shared/knowledge-graph/` 可行性高）；②语义引用网络=本方案全篇，从零建 |
| P0-2 inspection 子图召回 MVP | 本方案 §6 在 inspection 单模块闭环：手工 JSON 引用表（§5.4）+ `retrieve_subgraph()` + 四段注入 + cases.json 对照 |
| P1-1 规则 YAML 化 + lint | 语义层 skill 节点的规范化载体；lint 校验规则触发条件/输出格式的 schema |
| P1-2 覆盖率指标 | sem_root_cause ↔ cases.json 维度对照：量化「知识盲区」（哪些根因无案例覆盖、哪些规则无工具支撑） |
| P1-3 战术速赢 | 五段式报告模板承接 CASE/CAUSE/SKILL/TOOL 注入结果；告警时间窗聚类复用物理层 topo_alarm_event |
| Phase 2 共享层 | `_shared/knowledge-graph/` 放 sem_node/sem_edge 建图脚本 + retrieve_subgraph + 检索工具，三模块共用 |
| Phase 3 编排/分流 | 四段注入作为多步诊断 Agent 的上下文输入；大小模型分流：清晰症状走规则直判（BM25 命中高置信案例即直判） |

---

## 八、落地清单（建议执行顺序）

1. **本周**：建 `sem_node/sem_edge` 表（DDL 见 §4）；手工 JSON 引用表（§5.4）覆盖 inspection 13 规则 + 5 案例起步；
2. **本周**：写 `retrieve_subgraph()`（先用 BM25，不引向量）并接进 inspection 诊断 Prompt；
3. **第 2 周**：跑 cases.json 注入前/后对照，出 Phase 1 实验报告；PDF 源 A 人工抽取调度规程参数/条款入库；
4. **第 3~4 周**：源 B/C 脚本化入库（rules→skill、impl→tool、inspection_runs→case），根因聚类人工确认 ≥20 个；
5. **Phase 2**：抽 `_shared/knowledge-graph/` 共享层，YAML 化 + lint + 覆盖率指标，三模块接入。

**风险与对策**：
- PDF 条款结构化依赖人工确认 → 先只抽「参数表 + 明确条款」，其余留 `properties` 原文待后续；
- 向量召回依赖 embedding 服务 → Phase 1 用 BM25，不阻塞 MVP；
- 物理层 364 节点与语义层节点 id 前缀不同 → `node_id` 统一 `{type}:{ref_id}` 格式，前缀天然隔离，查询按前缀过滤。


