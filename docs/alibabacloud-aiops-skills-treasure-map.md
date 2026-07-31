# Alibaba Cloud AIOps Skills · 宝藏图

> **用途**：从 `/opt/git/alibabacloud-aiops-skills/skills`（约 170 个 skill、19 个类目、2900+ md / 417 py）中提炼的可借鉴模式，供 powerelf 各 skill（inspection / monitor / early-warning / chatbi / data-governance）改造时定位范本。
>
> **日期**：2026-07-31　**方法**：SysOM 两个 skill 人工精读 + 6 个并行 agent 覆盖全仓其余类目。
> **源仓库**：`/opt/git/alibabacloud-aiops-skills`（开源，`npx skills add aliyun/alibabacloud-aiops-skills --skill <name>`）。
>
> **阅读顺序建议**：先看「Part 7 跨 skill 通用宝藏」（置信度最高，被多个不相关 skill 独立验证），再按需查「Part 1–6 分领域详录」与「Part 8 powerelf 映射表」。

---

## 目录

- [Part 0 · SysOM（alinux）—— 巡检/诊断双子 skill](#part-0--sysomalinux--巡检诊断双子-skill)
- [Part 1 · 巡检/诊断 playbooks（trouboper + devopsimpl）](#part-1--巡检诊断-playbookstrouboper--devopsimpl)
- [Part 2 · 数据库 / SQL / BI（chatbi 向）](#part-2--数据库--sql--bichatbi-向)
- [Part 3 · 告警 / 监测 / 日志 / 事件（monitor + early-warning 向）](#part-3--告警--监测--日志--事件monitor--early-warning-向)
- [Part 4 · 方法论 / 评估 / RAG / 元工具](#part-4--方法论--评估--rag--元工具)
- [Part 5 · 安全 / 治理 / Finops（data-governance 向）](#part-5--安全--治理--finopsdata-governance-向)
- [Part 6 · 存储 / 媒体 / 容器 / 部署 / 其他](#part-6--存储--媒体--容器--部署--其他)
- [Part 7 · 跨 skill 通用宝藏（综合，置信度最高）](#part-7--跨-skill-通用宝藏综合置信度最高)
- [Part 8 · powerelf skill 映射表](#part-8--powerelf-skill-映射表)
- [Part 9 · 隐藏宝石](#part-9--隐藏宝石)
- [Part 10 · 建议优先级](#part-10--建议优先级)
- [Part 11 · knowledge-work-plugins 交叉分析（chatbi 向）](#part-11--knowledge-work-plugins-交叉分析chatbi-向)
- [附录 · 关键文件路径索引](#附录--关键文件路径索引)

---

## Part 0 · SysOM（alinux）—— 巡检/诊断双子 skill

> 源：`skills/computing/alinux/`。两个 skill：`alibabacloud-alinux-sysom-inspection`（巡检）+ `alibabacloud-sysom-diagnosis`（诊断）。背景文章：《凌晨告警不再慌！SysOM 巡检 Skill 一键锁定根因》。

### 0.1 巡检 skill 核心机制

- **闭环**：巡检发现问题 → **自动衔接诊断**（命中 `sysom:metric:memory_usage_rate` 异常 → 自动 `InvokeDiagnosis` 调 memgraph → 轮询 `GetDiagnosisResult` 至 success/fail/timeout）→ 给出处置建议。高风险不"只提示"，而是自动串到根因。
- **40+ 巡检维度**：系统负载 / 内存使用率 / 磁盘读写时延 / 调度延迟 / 文件句柄 / 线程资源 / 根分区与 inode / socket leak / tcp/udp 内存 / 多类内存泄漏风险。
- **不本地判异常**：阈值/事件规则配置不在本地；异常判定来自服务端巡检报告。
- **可观测性**：统一 `SKILL_SESSION_ID` 贯穿一次 CLI 执行的所有 API 调用；UA 模板 `AlibabaCloud-Agent-Skills/{SKILL_NAME}/{session-id}`；`source=skill_hub` 标记来源。
- **自动开关**：`InitialSysom` 检查未激活时，交互式询问是否激活+安装，确认后 `InitialSysom(check_only=false)` → `InstallAgentWithType` → 复检通过才继续。
- **优雅降级**：标准巡检 API 返回 `InvalidAction.NotFound` → 标记不可用并停止后续，避免无效重试；但仍发一次 `GetInspectionReport` probe 记录可观测性。
- 文件：`skills/computing/alinux/alibabacloud-alinux-sysom-inspection/SKILL.md`、`scripts/sysom_cli/inspection/command.py`、`scripts/osops.sh`、`scripts/init.sh`、`references/{ram-policies,report-template}.md`。

### 0.2 诊断 skill 核心机制（指令工程的范本）

- **Domain Routing 表**：`症状 → 首选命令`一一对应（不清内存→`memory classify`；慢盘→`io iofsstat`→`io iodiagnose`；高负载→`load loadtask`/`load delay`；丢包→`net packetdrop`/`net netjitter`）。
- **Envelope 契约**（agent 的默认契约）：
  ```json
  {"ok":true,"command":"sysom-osops memory classify",
   "agent":{"status":"warning","summary":"...",
     "findings":[{"severity":"high","title":"...","detail":"根因/实体/证据","category":"root_cause"}],
     "next_steps":[{"kind":"command","label":"...","command":"sysom-osops memory oom","reason":"能补的缺失实体"}]}}
  ```
  `findings[]` 只含 `severity/title/detail/category`；必要实体（PID/cgroup/service/路径/OOM victim/limit-current/残留/清理目标）必须写进 `summary` 或 `detail`。
- **Follow-up Rules（停止判据）**：优先 `category=root_cause` → 最高 severity → 最贴症状的 finding；`root_cause` 在 `detail` 含必要实体+安全下一步即视为 **stop-ready**；`next_steps[]` 是优先级计划不是 checklist；只为补"具名缺失实体"才再跑一条；矛盾/出错/缺实体时才退回裸 Linux 命令。
- **不执行修复**：诊断期间不 kill 进程 / 不删文件 / 不改 sysctl / 不写 cache-drop；这些作为建议呈现，除非用户显式要求执行。
- **错误处理表**：`error.code → Action`（`TargetRequired`/`FallbackClassify`/`PermissionDenied`/`AuthenticationFailure`/`InvalidParameter`/`DiagnosisVersionNotSupported`/`DiagnosisJsonParseFailed`/`PollError`）。
- **References 表**：`| Reference | Use when |`——`classify-output-guide` / `memory-triage` / `non-memory-triage` / `deep-actions` / `parameter-guide` / `report-interpretation` / `ram-policies` / `supported-environments`。
- 文件：`skills/computing/alinux/alibabacloud-sysom-diagnosis/SKILL.md` + `references/*.md`。

### 0.3 memory-triage.md 的「实体完备性」思想

| 缺失实体 | 完备信号 |
|---|---|
| 事件/压力源 | 选定事件、受害方/影响范围、limit/current 或等效压力源 |
| 占用归属 | PID 或命令（可执行）、service/cgroup |
| 对象归属 | 文件路径 / 共享内存对象 / socket / cgroup / 内核内存类 + 量级 |
| 归属变迁 | 原主、当前持有者、残留/refcount、清理顺序 |
| 机制+动作目标 | 内存机制、currentness 限定词、清理/限流/配置目标 |

**Focused Action Map**：只根据 SysOM 输出**已点名的缺失实体**选下一个深度动作，不凭症状措辞推断路由。这是"检测→诊断"升级的关键纪律。

### 0.4 文章对照实验数据

16 类真实 OS 故障场景，Agent 接入 skill vs 纯通用能力：接入后**对话轮次 / 工具调用次数 / 整体耗时大幅下降**；内核类问题（socket 缓冲区泄漏、vmalloc 异常、memcg 误判）准确率提升尤其显著。内部评测：异常识别整体准确率 80%+，**高风险项误判率 0**。

> **核心哲学（文章原话）**：「让 AI 处理 Linux 系统问题时，不再靠模型自己『想想看』，而是直接调用一套经过验证的排查路径。」skill 含完整排查路径 + 诊断提示词 + 相关脚本，向人是开箱即用的产品，向 Agent 是可直接调用的能力。

---

## Part 1 · 巡检/诊断 playbooks（trouboper + devopsimpl）

> 覆盖 `playbooks/trouboper/*`、`others/devopsimpl/*`、`computing/ecs/*diagnose*`（alinux 已在 Part 0）。

### Top 5 宝藏

#### 1. 根因 blocking-chain 重建（多策略 fallback + 时间线渲染）
**源**：`alibabacloud-history-lock-diagnose` — `playbooks/trouboper/alibabacloud-history-lock-diagnose/scripts/smart-lock-diagnosis.py`（3782 行）

给定"被阻塞 SQL"这个**症状**，重构完整因果链回到**根锁持有者**，渲染事务时间线 `①持锁→②中间被阻塞→③诊断线程`。分层 fallback 逐步提升精度：
1. **WHERE 精确匹配**：提取异常 SQL 的表+WHERE 谓词，只查同行操作，时间窗自动扩展 `[-10min,+5min]→[-30min,+5min]→[-2h,+5min]`。
2. **全表 DML fallback**：WHERE 匹配失败（如非索引列）→ 查该表所有 DML。
3. **COMMIT 匹配**：审计日志无候选时，在锁释放时刻（`OriginTime+LockTime`）搜 COMMIT/ROLLBACK/LOGOUT 定位持有线程。
4. **活会话 probe**：最后兜底 `GetMySQLAllSessionAsync`，按 `TrxDuration`/exec-time/涉及表打分选最可能持有者。

另带 `_classify_lock_type_label()`（Record/Gap/Next-Key/MDL/Flush/INSERT-intention 决策树）与 `_render_blocking_chain()`（人读因果时间线，带北京时间标注）。

**→ powerelf-inspection**：5 层检测触发时（如渗压 MAD 离群），别只报"T 时刻异常"。实现 `diagnose_anomaly(sensor, timestamp)` 反向成链：查同站/同泵关联传感器，分层 fallback（精确窗口→全站→上游水库关联），渲染 `①上游闸门操作→②泵启停→③实测异常`。

#### 2. 决策树知识库即机读 JSON（`regex→causes[]→solutions[]`）
**源**：`alibabacloud-alb-ingress-doctor` — `others/devopsimpl/alibabacloud-alb-ingress-doctor/references/diagnostic_tree.json`（2594 行，61+ 错误模式）

每个已知失败模式是结构化节点：`category→error{id,regex,message_template,severity,causes[cause{cause_id,summary,description,diagnostic{commands[],expected_result},solution{title,steps[],yaml_example,recommended?}|solution_options[{index,title,recommended,...}]}]}`。LLM 不自由推理——正则匹配症状→按序遍历 `causes`→跑 `diagnostic.commands`→对 `expected_result`→命中则出 `solution`；多方案优先 `recommended:true`。还编码了"静默失败"（无 reconcile 错误但行为错）与版本门控方案（`v2.18+`）。

**→ powerelf-inspection**：为 15 维各建 `diagnostic_tree.json` 条目：`异常签名→causes[{诊断查询,期望状态}]→处置选项[recommended]`。如 渗压-MAD-离群→causes=[上游水位变化,降雨事件,传感器漂移,真实渗漏]，每个带一条针对 monitor 表的诊断查询+期望结果。检测发现异常→树自动定位根因。

#### 3. 根因优先级排序（P0–P3）+ 多故障必查令
**源**：`alibabacloud-network-diagnose` — `references/root-cause-priority.md` + `references/report-template.md` + SKILL.md

两套互补：(a) 严重度 rubric 把每个 finding 排 P0（停/删/黑洞路由）→P3（信息）；(b) **强制多故障规则**（SKILL.md L53）：*"找到一个问题（含 P0 根因）后，仍要继续所有适用步骤至 Step 7。不得提前跑最终分析。最终报告必须列出发现的全部问题。"* 报告模板：`结论→Check Summary 表→Root Causes（P0-P3 序，不在第一个后停）→建议动作→详细证据链`。Check Summary 表 `| Check | Result | Evidence |`（ok/warning/critical/skipped）一目了然又可下钻。

**→ powerelf-inspection**：5 层（阈值→变化率→趋势→MAD→关联）目前产出平铺异常列表。改成 (a) 每维 P0-P3 rubric（P0=安全关键传感器阈值越限；P1=趋势违反；P2=无确认因的 MAD 离群；P3=关联弱）；(b) 命中 P0 后仍跑全 5 层的强制令；(c) envelope `{conclusion, check_summary[], root_causes[], recommended_actions[], evidence_chain[]}`。

#### 4. 健康分 rubric（加权扣分 + 色阶 + 排名）
**源**：`alibabacloud-rds-postgresql-inspection` — `playbooks/trouboper/alibabacloud-rds-postgresql-inspection/scripts/inspect.py:928`（`calc_health_score`）

每实例从 100 起扣：`cpu>80%→-10`、`disk>85%→-15`、`P1告警→-10`、`慢日志>1000→-8`、`内核非最新→-3`、`月内到期→-5`、`锁→-8`。返回 `(score, deductions[])`；`score_status()` 映射色阶（🟢≥80/🟡≥60/🔴<60）。汇总报告算全局均值、分布 `{ok,warn,danger}`、**lowest-20 排名**（每行带 top-3 扣分项）。

**→ powerelf-inspection**：每个闸门/泵站 `health_score = 100 − Σ扣分`。定义每维扣分权重：安全关键传感器阈值越限 −15、持续变化率异常 −10、趋势反转 −5、MAD 离群 −5、关联断裂 −3。产出站点排名（最差在前）+ 每站 top-3 扣分项，给 SCADA 看板一个单一排序键。

#### 5. Verified / Unverified / Blocked 结论分类 + 强制执行清单
**源**：`alibabacloud-cfw-acl-diagnosis` — `references/diagnosis.md`（§8-10）

每条结论必须打标：`[Verified]`（实测查询确认）/`[Unverified]`（理论推测，需确认）/`[Blocked]`（检查跑不了，如 RAM 权限拒，附 `| Blocked Check | Required Permission | Impact |` 表）。配套**执行清单**（§8）强制步骤排序：Step 2 有 2.1/2.2/2.3 三个子查必须**全部**用真实 CLI 值完成后才能下结论——`❌ 在完成全部 Step 2 检查前跳到结论` / `❌ 在完成 Step 2 前提到 engine mode`。

**→ powerelf-inspection**：离线 MySQL 直连常遇表缺失（SL323 load-bearing 问题）或数据陈旧。给每条 finding 打 `[Verified]`（查询成功）/`[Unverified]`（部分数据推断）/`[Blocked]`（表空/列缺/站离线）。报告加 `| Blocked Check | Missing Data | Impact |` 表——直接服务"暂无数据"标注需求，同时让诊断诚实。

### 荣誉提名（各 1 行）
- **`closure_precheck.py` 比对报告风险脚本**（`cloudfw-vpc-firewall-diagnosis/scripts/`）——diff 两路由表，出 `risk_level=HIGH/LOW`+缺失路由表+编号手动动作；任何"做了 X 会坏什么"预检的干净模板。
- **`output-format.md` 填空报告骨架**（`ecs-reboot-or-crash-diagnosis/references/`）——`{placeholder}` MD 模板，AI 逐字填，按 OS 分支（Linux/Windows）；powerelf 每站报告契约。
- **28 条分级 lint 目录**（`polardb-mysql-sql-lint/references/sql-lint-rules.md`）——每条 `Severity/Category/Why/Violation/Correct/Exception`；借这个格式文档化 5 层检测规则。
- **自验证闸**（`sre-toolkit` SKILL.md Step 8）——诊断后检查"每个症状都有诊断结果？方案可执行？自动纠正最多 1 轮"。
- **SysOM 持续 enrollment + 钉钉告警**（`aes-sysom-os-diagnosis/references/manage-and-alert-workflow.md`）——巡检→告警自动链。
- **NAS 错误码→场景路由表**（`nas-mount-diagnosis` SKILL.md）——Windows 错误码（53/58/64/67/85...）直映诊断分支；故障码驱动路由。

### 共性"家风格"
- **共享章节**：`Credential Security`/`Authentication`（永不打印 AK/SK）、`RAM Policy`（`|Action|Purpose|`表）、`Observability`（每次 `aliyun` CLI 带 `--user-agent AlibabaCloud-Agent-Skills/{skill}/{session-id}`，32 位 hex）、`Prerequisites`、`Parameter Confirmation`（所有可定制参数必须先确认）、`references/{ram-policies,cli-installation-guide,acceptance-criteria,verification-method}.md`。
- **只读护栏三级升级**：① prose 禁令（`NEVER Create*/Update*/Delete*`）② 报告强制免责声明头 ③ **PreToolUse hook**（`scripts/check-write-operation.sh`，非白名单 Bash 命令返回 `permissionDecision=ask`）——最强形式，cloudfw-vpc/cfw-acl/alb-ingress/rds-pg 都带。
- **两种执行模型**：**单脚本模型**（rds-pg `inspect.py` 等，`HARD RULES`："所有巡检必须经 `python3 scripts/xxx.py`，AI 不得直接调 aliyun CLI"）vs **步进工作流模型**（network-diagnose 等，`Step 0→7` 强制序，每步即时打印，不许跳）。
- **输出格式**：批量巡检用 HTML（每实例+汇总+健康分排名）；诊断用结构化 MD（`结论→Check Summary→Root Causes→建议→证据`）；模板或 `{placeholder}` 填空（ecs-reboot）或 Python f-string（rds-pg）。
- **严重度约定**：`🔴Critical/🟡Warning` 或 `P0/P1/P2/P3`；健康分 `🟢≥80/🟡≥60/🔴<60`。

---

## Part 2 · 数据库 / SQL / BI（chatbi 向）

> 覆盖 `analyticscomputing/*`、`database/*` 的 copilot/assistant。

### Top 5 宝藏

#### 1. 分级数据集/表解析（权限→精确名→NL→表智能匹配→相关性兜底）
**源**：`analyticscomputing/quickbi/alibabacloud-quickbi-smartq/scripts/chat/cube_resolver.py`（+ `cube_name_lookup.py`，契约在 `references/chat/module-chat-dataset.md`）

powerelf"LLM 猜错表/列"的最佳解。**永远不让 LLM 冷启命名表**。`resolve_cube_id()` 跑确定性 4 步 cascade：(1) `query_accessible_cubes()` 枚举用户可见；(2) 句子含名提示时 `match_cube_by_name()` 精确（大小写/空白归一）匹配短路；(3) miss 才调真 NL→表 API（`POST /smartq/tableSearch`，自适应批量 `[30,10]` 躲"cubeIds over limit"错）；(4) 纯 Python `SequenceMatcher` 相关性打分取 top-2。`cube_name_lookup.py` 是 stdin/stdout-JSON 包装，让 agent 在 status=`similar` 时展示候选。

**→ powerelf-chatbi**：`cubeId` 换成 SL323 表名。Step1→`information_schema.tables`；Step2→对 `COLUMN_MEANINGS` 精确别名匹配（用户说"雨量"→`ST_PPTN_R`）；Step3→QBI 的 `tableSearch` 换成本地 embedding/关键词打分（你 memory 里记的那份列注释文档）；Step4 不变。这就是 memory 提倡的 `columns()` 工具模式——此处升级成分级 resolver。

#### 2. 引擎无关 text2sql 规则书（JSON 输出契约 + 反模式）
**源**：`analyticscomputing/odps/alibabacloud-odps-sql-generation/references/text2sql_principles.md`（伴 `references/sql_query_patterns.md`）

任何 NL→SELECT 引擎都适用的极简规范。三个承重点：(a) **生成顺序**——确认可用 schema→选粒度→最小查询→产出，规则"只用上下文提供的 schema；不得捏造表/列/枚举/关联键"；(b) 固定**输出契约**——纯 JSON `{sql, explanation, tables, assumptions}`，不可能的问题 sql 留空；(c) **反模式清单**（`SELECT *`、捏造枚举、JOIN 无 ON、每组 Top N 用全局 LIMIT、聚合列进 WHERE）。伴文件给可复制 DQL 模板（`ROW_NUMBER` 每组 Top N、去重取最新、累计求和、同比环比）+ NL 触发词——**正是水利形状**（Top N 雨量站、最新水位、累计雨量）。

**→ powerelf-chatbi**：几乎逐字搬进 `references/text2sql_rules.md`。JSON 契约给下一阶段（绘图）可解析产物；`assumptions` 字段把"LLM 悄悄选了某列"变成可见可捕获的声明。每条 SQL 配 lint 闸（见 #5）。

#### 3. 图表交付契约（SSE 事件 schema + "永不 Read PNG"规则）
**源**：`alibabacloud-quickbi-smartq/references/chat/module-chat-dataset.md` + `scripts/chat/chart_renderer.py`

两宝合一。(a) **SSE 事件 schema**：`relatedInfo | reasoning | text/sql | olapResult | summary | conclusion | check | error | finish`。`olapResult` 带 `values`+`chartType` 枚举（`BAR/LINE/PIE/SCATTER_NEW/INDICATOR_CARD/RANKING_LIST/DETAIL_TABLE/MAP_COLOR_NEW/PROGRESS_NEW/FUNNEL_NEW`）+`metaType`（维度 vs 度量、行 vs 列、colorLegend）。`chart_renderer.py` 的 `_CHART_TYPE_MAP` 别名字典把厂商枚举归一到标准集——真实图表类型路由器。(b) **严格交付规则**（他们点名的 #1 违规）：agent 必须**逐字**把 `![Title](path)` 贴进回复，**禁止**对 PNG 调 `Read`/`present`（给虚假交付感），必须在**一条**回复里交付 图+结论+解读，发前跑 checklist。

**→ powerelf-chatbi**：采纳 chartType 枚举与"单回复、图优先、禁 Read PNG"规则进渲染步。`_CHART_TYPE_MAP` 别名模式直接复用（把 LLM 自由文本图表选择归一到标准渲染器）。`chart_renderer.py` 的 `_CJK_FONT_CANDIDATES` 是中文标签的免费午餐。

#### 4. 计划-后执行 "attach" 会话模式 + 计划确认闸
**源**：`database/dms/alibabacloud-data-agent-skill/SKILL.md`（"Session Reuse via attach" + ANALYSIS 模式）

一石三鸟：(a) **schema 发现闸**——agent `db`（分析）前必须先 `ls`（列 Data Center 库）；skill 明示"DMS 注册的库 ≠ Data Center 的库"，强制显式 import。这是"让 LLM 查 schema 而非猜"的元模式。(b) **计划确认**——ANALYSIS/INSIGHT 模式出 `### Execution Plan` 后进 `WAIT_INPUT`，只有 `attach -q "confirm"` 解锁，让 SQL 生成在执行前可审。(c) **会话复用**——一次 `db` 建会话，后续全走 `attach --session-id`，保留"前次 SQL、表画像、用户意图"——省去重复画像、保持多轮 ChatBI 一致。

**→ powerelf-chatbi**：引入会话 handle，让追问（"7 月也来一份"）复用已解析的表/列而非重新发现。非平凡查询引入计划步：展示已解析表+所选列+生成的 SQL，用户确认后再执行——在"LLM 选错列"触库前截住。

#### 5. 静态 SQL lint 闸（28+ 规则，不查 DB 元数据）
**源**：`playbooks/trouboper/alibabacloud-polardb-mysql-sql-lint/SKILL.md` + `scripts/sql_lint.py`

执行前校验闸，正好抓 powerelf 的失败模式。双模：纯静态（即时不连库）与完整（静态+DAS 诊断）。安全规则很有教益："**永不**为元数据连库"、"**永不**对未知表 `COUNT(*)`"、"**永不**取表结构"——因为其后端**做不到**。powerelf **能**查元数据，所以教训是反过来的：提供 `columns()` 一等工具让 lint 闸有真值。静态规则书（全表扫、缺索引、`UPDATE/DELETE` 无 WHERE、危险 DDL）可复用，多语句路径（按 `;` 拆、逐条跑规则、跨批检测可合并 `ALTER`）是批量 ChatBI 校验的模型。

**→ powerelf-chatbi**：在生成与执行间插 `lint_sql(sql, resolved_tables)`。喂给它的列来自 resolver（#1）返回值，使 lint 最强规则变成"每个引用列都存在于 `resolved_tables`"——针对本地 LLM 屡屡捏造列名的结构性护栏。拒掉→把缺列原因回灌 LLM 重试。

### Schema 查找深潜（powerelf 最大痛点）
四种策略，按相关度排：

- **A. 分级确定 resolver（最佳——QuickBI `cube_resolver.py`）**：枚举权限→精确名→API 智能匹配→SequenceMatcher 兜底。关键是 LLM **绝不**在 text2sql 中产表名；Python 模块返回 `cubeId`，只有 SQL 生成步看到已解析 schema。`cube_name_lookup.py` 包成打印纯 JSON 到 stdout（日志到 stderr）的 CLI——正是 agent 可调的工具形态。路径：`skills/analyticscomputing/quickbi/alibabacloud-quickbi-smartq/scripts/chat/cube_resolver.py`。
- **B. 目录 API 上的元数据 CLI（DataWorks `alibabacloud-dataworks-metadata`）**：数据模型 `Catalog→Database→Table→Column/Partition`，经 `list-tables --parent-meta-entity-id`、`list-columns --table-id`、`get-table --include-business-metadata true`、`list-lineages` 暴露。实体 ID 结构化（`maxcompute-table:::project:schema:table`）。`columns(table)` 工具返回真元数据（非猜出来的字符串）的架构模板。skill 强制每次调 `--read-timeout 60 --connect-timeout 10`、写前幂等检查。路径：`skills/analyticscomputing/dide/alibabacloud-dataworks-metadata/SKILL.md`。
- **C. prompt 里放引擎无关规则，不放 schema（MaxCompute `text2sql_principles.md`）**：刻意分层——规则书 = 引擎无关生成规则；方言参考另文；模板另文。schema **不**在 prompt——只有规则"只用上下文提供的 schema；缺则返空 SQL+声明缺口"。这正是 powerelf SKILL.md 需要的纪律——不该含 `schema.md` 列表（你 memory 已警告这会变成打地鼠），只放规则。路径：`.../odps-sql-generation/references/text2sql_principles.md`。
- **D. 反例——查不了元数据的 lint skill（polardb-mysql-sql-lint）**：其安全规则（"永不连库取元数据；DAS API 无此接口"）展示没有 schema 查找会怎样——被迫退回纯静态启发式。反证 powerelf 必须建 A/B：有真 `columns()` 工具，lint 闸从**语法级**升级为**结构级**（列存在性校验）。

**综合**：建 `resolve_table(question, name_hint?)` Python 工具仿 `cube_resolver.resolve_cube_id()`（A），背后用 `columns(table)` 仿 DataWorks `list-columns`（B），SL323 schema 移出 SKILL.md 只放生成规则（C，`text2sql_principles.md`），每条生成的 SQL 过列存在性 lint（D 的反转）。

### 荣誉提名
- **QuickBI 意图路由表**（`quickbi-smartq/SKILL.md` "Routing Decision Table" + 优先级规则）——关键词优先派发（"报告"压一切；"解读/洞察"次之；具体查询最后）；ChatBI 问题→模块路由的意图分类器。
- **选项卡交互**（`analyticdb-mysql-copilot/SKILL.md`）——消歧时给 ≤10 张选项卡而非让用户打字；映射"你指哪个站？"。
- **region 路由覆盖表**（`analyticdb-mysql-copilot` §1.2）——`--region`/`--endpoint` 强制映射的 P0 规则；powerelf 多租户 DB 路由模型。
- **PolarDB-X 分区键多维分析**（`drds/alibabacloud-polardbx-sql/SKILL.md`）——5 维打分（等值查询比、基数、热点风险、PK 状态、语义）；"选最佳索引/分片键"的可迁移模板。
- **session-id 可观测**（`rds-copilot`、`polardb-ai-assistant`）——32-hex session-id + per-command `--user-agent` + OTEL baggage；端到端追踪 ChatBI 查询的免费观测层。
- **Data-Agent `attach --checkpoint N` / `--from-start`**——长流式分析的精确恢复。
- **DMS 写保护阶梯**（`dms-skill execute_query.sh`）——`--dry-run`→`--force`，DDL 硬阻；写路径的安全执行契约。
- **AnalyticDB `describe-chat-message` 双模**——同端点既服务"产品知识 Q&A"（无集群）又服务"实例诊断"（集群在 query）；把 docs-RAG 与活数据折到一个 API 后面。
- **Data-Agent CLAW 模式**（v1.8.2+）——per-message `SessionConfig.Mode` 覆盖；在 ChatBI 里切"快问答"与"深分析"无需新会话。

---

## Part 3 · 告警 / 监测 / 日志 / 事件（monitor + early-warning 向）

> 覆盖 `middleware/cms/*`、`security/sas/*`、`storage/sls/*`、`netcdn/*`、`mediaservices/live/*`、`middleware/{apigateway,pts}/*`。

### Top 5 宝藏

#### 1. 类型化规则 schema（判别联合三联）`datasourceConfig ↔ queryConfig ↔ conditionConfig`
**源**：`middleware/cms/alibabacloud-cms-manage/references/alerting.md`（L72-82, L108-310）；强化于 `alibabacloud-cms-alert-rule-create/references/cms2-step3-detection-config.md`

CMS 2.0 规则**不是**自由 JSON。三子对象成严格类型系统：`datasourceConfig.type`（PROMETHEUS/APM/UMODEL）决定 `queryConfig.type` 决定 `conditionConfig.type`（PROMETHEUS_SIMPLE_CONDITION / APM_SIMPLE_CONDITION / APM_COMPOSITE_CONDITION / UMODEL_METRICSET_CONDITION），错配即拒。每种 condition 有自己的阈值语法——`APM_SIMPLE_CONDITION` 带 `thresholdList`（一规则多级别，见宝 #3），`APM_COMPOSITE_CONDITION` 带 AND/OR `relation` 的 `compareList`。

**→ powerelf-early-warning**：MySQL `ew_info_rules.extend` JSON 现在是 schema 查找瓶颈（你已 memo `powerelf-schema-lookup-architecture`）。把 ad-hoc `extend` blob 换成判别联合文档：规则上加 `kind:"threshold|trend|missing_data|composite"`；每 kind 一份 `extend` JSON schema（threshold 得 `{operator,value,unit,duration}`，composite 得 `{relation:AND|OR, of:[...]}`）；DB 级 CHECK / app 级 validator 拒错配 kind——在**写时**而非**查时**杀死"LLM 猜列名"。

#### 2. 动态度量发现 + 意图→度量关键词兜底表
**源**：`middleware/cms/alibabacloud-cms-alert-rule-create/references/step2-query-generation.md`；`references/step0-intent-routing.md`（L25-48）

两层模式解"agent 要选对度量"。**主**：始终调 `describe-metric-meta-list` 枚举锁定 namespace 的度量——agent 永不硬编码。**兜底（仅 API 失败）**：静态 关键词→度量类 表（`CPU`→cpu 度量、`Memory`→memory、`Disk`、`Net`、`Connection`、`IOPS`、`Latency`、`Error|Fail|Drop`、`Load|Queue`）。关键词表是**意图分类**而非度量目录——把 agent 带到正确街区，API 再选精确度量。

**→ powerelf**：你已有痛点（`powerelf-schema-lookup-architecture`："本地 LLM 不读文档 / COLUMN_MEANINGS 是唯一源"）的教科书解。保留 `COLUMN_MEANINGS`（它是兜底表），但暴露一个 `db.metrics(namespace)` 式查询函数让 agent 先调——正是你已草拟的"查询函数替代 SKILL.md 打地鼠"。

#### 3. 分级 `thresholdList` + 自动生成中文消息模板
**源**：`middleware/cms/alibabacloud-cms-manage/references/alerting.md`（L120-135, L179-189, L209-213）；`cms-alert-rule-create/references/cms2-step3-detection-config.md`（L11-19, L55-69）

两得。(a) **一规则多级别**：`APM_SIMPLE_CONDITION.thresholdList` 是 `[{severity:"WARN",threshold:80},{severity:"CRITICAL",threshold:95}]`——一条规则在正确级别触发，而非 N 条重复配置。CMS 1.0 用 `--escalations-critical-*/--escalations-warn-*/--escalations-info-*` 并行参数组镜像。(b) **预算消息**：CREATE 时从规则自身字段算 `message` 与 `annotations._cms_rule_display_statement`：`"<监控对象> {{$labels.instance}} <指标中文> 最近 <durationSecs/60> 分钟持续<operator中文> <threshold> <unit>触发<severity中文>告警，当前值 {{printf "%.2f" $value}}"`。severity 有 zh-CN 映射（CRITICAL→严重、ERROR→错误、WARN→警告、INFO→普通）。

**→ powerelf-early-warning**：现在大概率一规则一阈值。改 `thresholdList` 后"水位告警 80%=警告/90%=严重/95%=紧急"一行表达；预算消息模板意味着 dispatch 时无需 LLM——规则已自带中文句子。monitor 的 12 类趋势自然映射到 `aggregate`（`AVG|SUM|COUNT|MAX|MIN|P50|P75|P90|P99|CONTINUES`）。

#### 4. 告警动作分类法 + 每告警可用动作 probe（playbook 模式）
**源**：`security/sas/alibabacloud-sas-alert-handler/references/operation-codes.md`；`references/workflow-details.md`（L22-52, L66-128）

三可借。(a) **动作 4 类分类法**：威胁处置（`block_ip`、`kill_and_quara`、`virus_quara`、`kill_process`、`cleanup`…）、白名单（`advance_mark_mis_info`、`mark_mis_info`…）、忽略、人工——每 op 带必填参（`block_ip`→`expireTime`、`kill_and_quara`→`subOperation`）。(b) **每告警类型默认建议表**（异常登录→封 IP、恶意软件→杀+隔离、容器安全→ case/忽略…）——agent 询问前读的**静态 playbook**。(c) **硬约束**：每告警的**可用**动作必须经 `DescribeSecurityEventOperations` 单独查——不能假设 op X 适用于告警 Y。须查 `UserCanOperate=true`。另有"高级白名单是全量替换，必须合并现有 MarkField 规则"的微妙点。

**→ powerelf-early-warning dispatch**：把硬编码的 `if alert_type==...` 链改成数据化的 `(alert_type→default_action→required_params)` 表，加"可用动作 probe"步（执行前查某联系/webhook 是否还在）。"白名单更新要合并现有规则"直接映射告警静默/抑制列表更新。

#### 5. 写操作的强制配置汇总确认闸
**源**：`middleware/cms/alibabacloud-cms-alert-rule-create/references/step5-preview-execute.md`（L14-50）；SKILL.md critical rule #12（L98-107）

任何写前展示短而格式固定的 preview 块，执行等用户显式确认——**即便在自动化/模拟环境**。模板具体：产品 / Namespace / 指标(中文) / 统计方式 / 阈值(操作符+值+单位) / 评估周期(连续N周期×周期秒数) / 严重级别 / 资源范围 / 联系人组 / 规则名。critical rule #12 明禁以"自动化"为由跳过，强制输出"等待用户确认"。

**→ powerelf**：early-warning 写 `ew_info_rules` 前必须渲染这种汇总卡。`step3-detection-config.md` 的单位换算子规则（`"超过1G"→1073741824 if unit=Byte`、`"超过80%"→80 if Percentage`）也值得逐字抄——单位是水利传感器的 perennial bug 源（水位 m/cm、流量 m³/s vs L/s、墒情 %）。

### 告警规则编写深潜——7 阶段向导（硬闸）
powerelf 规则存 MySQL `ew_info_rules` 的 JSON `extend`。Alibaba `cms-alert-rule-create`+`cms-manage/alerting.md` 是最近类比，揭示**带硬闸的 7 阶段向导**：

| 阶段 | 干什么 | 硬闸 |
|---|---|---|
| 0 意图路由 | 关键词表选引擎（CMS 1.0 vs Prometheus/APM/UModel）；未知→`describe-project-meta` 搜；歧义→必问 | 永不混引擎 |
| 1 上下文锁定 | 绑 workspace+scope | workspace/cluster_id/serviceId **必须**来自 AskUser，永不捏造/自动选 |
| 2 查询/度量生成 | 主：`describe-metric-meta-list`；兜底：关键词表；用户确认匹配度量 | 永不纯靠硬编码度量列表；字段名来自 schema 非模型记忆 |
| 3 检测配置 | severity/operator/threshold(s)/duration/schedule；APM 用 `thresholdList` | 单位自动换算 |
| 4 通知对象 probe | CMS1.0 `DescribeContactGroupList`；CMS2.0 `ListAlertWebhooks` | **强制预查**——channels[].identifiers 指真实 ID，非占位 |
| 5 预览+执行 | 渲染汇总卡，等显式 yes | 即便自动化也必须出汇总+"等待确认"（critical rule #12）|
| 6 验证 | 重取规则，展示完整 JSON 给用户 | 强制 |
| 7 PATCH 补充 | APM 规则需二阶段 patch level/alertMetricInput/notifyTime/控制台显示单位 | `patch --use-patch-api`（增量）优于 `update`（全替换，覆盖风险）|

**给 powerelf MySQL JSON 设计的要点**：
1. **规则体拆成类型化子对象**（datasource/query/condition/notify）。现 flat `extend` 逼 LLM 猜形状；判别 schema 让校验 trivial。
2. **度量名解析当运行时查询，不当读文档任务**（你 memo 已结论）。
3. **写时预算人读消息，非触发时**——存 `message_template` 列，dispatch 时填当前值，省热路径一次 LLM 调用。
4. **持久化规则前 probe 通知对象**——悬空联系人 ID 是告警系统 #1 静默失败；对 `extend.notify` 中每个 ID 加外键式检查。
5. **"核心规则写"与"元数据 patch"分离**——CREATE→PATCH 分离存在因控制台需要 validator 在 CREATE 拒绝的显示字段。
6. **单位归一放进编写层**——`step3-detection-config.md` 单位自适应表是 10 行 helper 防一整类坏规则；水利单位比云度量更乱，直接抄。

### 荣誉提名
- **Event Hub→SLS LogStore 管线**（`cms-manage/references/event-hub.md`）：每次告警触发写成 `cms-event-store-{workspace}` 的 CloudEvents 行，经 SLS GetLogs 回查（`severity:CRITICAL AND status:OCCURRED`）——powerelf 告警历史+去重存储模板。
- **意图路由作 Step 0**（`cms-alert-rule-create/references/step0-intent-routing.md`）：关键词→引擎表带"未知产品→API 搜"+"歧义→必问"——powerelf 多规则引擎时的 router 骨架。
- **NL→查询分层纪律**（`sls-query/references/query-analysis.md`）："每个能在 index search 表达的 filter 放第一个 `|` 前；SQL/SPL 只在其后"——让 agent 停在廉价查询路径。
- **两阶段 CREATE→PATCH**（`cms-manage/references/alerting.md` L316-396）：validator 友好的最小 create + 显示元数据 patch。
- **多步工作流契约**（`sas-incident-manage/SKILL.md` Workflow A/B）：显式"MUST 执行两命令，不跳 Step 2"+ bash 块。
- **session UA 可观测**（`sas-incident-manage` Observability）：一个 32-hex session-id 全程复用。
- **Patch-vs-update 决策矩阵**（`cms-manage/references/alerting.md` L60-69）。
- **模板 apply + 占位符替换**（同上 L482-566）：`alert template apply --var k=v` 支持 `${k}`/`{{k}}`/`{{.k}}`，自动把 alertmanager 方言体翻成 CMS 三段 schema——powerelf 规则模板（每类水站一个）模型。
- **ContextStore agent 记忆**（`middleware/cms/alibabacloud-agentloop-contextstore/SKILL.md`）：`memory`（偏好/事实）+`experience`（从 agent trace 总结的排障剧集）两存储——early-warning agent 记每站历史事件 playbook。
- **DataAgent 内建 skill 路由**（`storage/sls/alibabacloud-sls-data-agent/SKILL.md`）：`--skill builtin.sls.sls-sql-generation|spl-generation|...`——宽 skill 内暴露窄专家子 skill 的模式。
- **filter 客户端 fail-fast**（`cms-manage/references/alerting.md` L28-52）：拒空 `--alert-rule-id` 防静默 list-all 信息泄露。

---

## Part 4 · 方法论 / 评估 / RAG / 元工具

> 覆盖 `aiml/{agentloop,sfm,learn,agentbay,avatar,docmind,opensearch}/*`、`developertools/{solutions,skillsexplorer,openapiexplorer}/*`。

### Top 5 宝藏

#### 1. 「先背后写」读校验闸（recite-before-write）
**源**：`developertools/solutions/alibabacloud-terraform-code-generation/SKILL.md` Steps 4.2–4.3（`references/alicloud-providers.md` 是查找索引）

agent 写一行 HCL 前，必须 (a) grep 本地目录找资源行+弃用标记，(b) WebFetch 权威 provider 文档，(c) 产每资源**"recitation"**——逐字必填参列表、2–5 个关键可选参、文档示例的最小 snippet。"若缺必填/可选参，返 4.2。跳过或用部分 recitation 是 hard failure。"代码只能**从 recitations 写**，绝不凭记忆："若需一个 recitation 里没有的参，回 4.2 重取；不许猜。"

**为何顶级**：参数幻觉（NL→code/config 的最大失败模式）的廉价、模型无关结构性解。还产可审计的中间产物（recitations），评审/评估者可独立于生成代码打分。

**→ powerelf**：任何从 NL 产 SQL/Python/配置的 skill（巡检查询生成、`db.py columns()` 链、报告模板生成）都应要求 agent 先逐字 recite 已校验列名/schema/模板字段，只从 recitation 产。直接硬化 MEMORY 记的"本地LLM不读文档/猜列名"问题。

#### 2. 三查询评估分析模式（带分数带）
**源**：`aiml/agentloop/alibabacloud-agentloop-evaluation/scripts/analyze_evaluation_results.py`（~519 行）+ `references/result-analysis.md`

分析器对固定 `evaluation_detail` 存储发恰好三条有界 SQL 查询，粒度递增：
1. **总览**——`total_count/scored_count/avg(normalized_score)/low_score_count(score<threshold)/low_score_rate`。
2. **按 evaluator**——同指标 group by `evaluator_display_name`，按 `low_score_count DESC`。
3. **低分案例**——真实证据行（score/explanation/latency/data_link），按 `score ASC`，封顶 `--max-cases`（硬限 200）。

归一化分入固定带（Very poor `<0.3`…Excellent `≥0.9`），默认低分阈 `0.5`。解读纪律：先读最低分案例、聚类重复失败（缺事实/指令违反/工具错/输出畸形/evaluator 歧义）、每案引 task/run/evaluator/eval-id/score/timestamp，"把观察证据与假设分开——只在重复模式可见后才建议改动"。

**→ powerelf**：在巡检输出上建同款三层分析器——(1) 整体巡检通过率 (2) 按 skill/模板 (3) 最差 N 个巡检+trace 链接。能量化"巡检 skill 到底有没有找到真缺陷"而非靠感觉。

#### 3. 「诚实状态契约」+ grep 后生成闸
**源**：`alibabacloud-terraform-code-generation/SKILL.md` Steps 5.4, 5.6, 7

三强化。(a) **硬规则 §2 诚实报告**：除非命令真跑过返该状态，永不报 `fmt:ok`/`validate:ok`；跳过的步骤说 `SKIPPED(reason)`，失败的说 `FAILED(reason)`。(b) **后生成 grep 闸**：写完 HCL 跑 bash grep 必须打印 `OK_VERSION`/`OK_CFG_SOURCE`/`OK_REGION_VAR`——任何 `BAD_*` 阻断。(c) **按行 kind 的弃用字段审计**（`references/deprecated-fields.md`）：每个已知坏字段标 `rename/split/soft-split/deprecated-no-replacement`，SKILL.md 嵌 awk 循环遍历参考表只查实际生成的资源。(d) **validate 循环**最多 3 次重试，扫 `terraform validate -json` 诊断找 error 与 `[DEPRECATED]` 标注。

**→ powerelf**：任何产配置/SQL/报告的 skill 都可采纳 OK_/BAD_ grep 闸 + "四个精确状态串"输出契约。行 kind 分类法（rename vs split vs no-replacement）是编码"validator 抓不到但仍错"的干净方式。

#### 4. 先忆后行 / experience-first 循环
**源**：`aiml/agentloop/alibabacloud-agentloop-experience/SKILL.md` + `scripts/search_context.js`

核心指令是工作流排序规则："**先 recall 历史经验**——分析或实现前，把回忆历史 AgentLoop 经验作为最初动作之一。"按具体错误/标识符查询 recall，`--threshold 0.6`、`--limit 5` 门控，关键是把 recalled 内容当**上下文非权威**："若 recalled 内容与当前仓库/日志/用户请求冲突，信当前证据。"遇"非平凡障碍或改方法"时重 recall，空结果优雅降级（继续任务）。

**→ powerelf**：工业巡检事件重复度极高。生成新巡检计划前，对历史巡检发现/缺陷案例/SL323 异常的 curated 存储跑 recall——浮出"这个闸门失败模式我们见过，后来查明是 X"而不覆盖实时证据。

#### 5. 可搜意图单元分解 + 面向能力改写
**源**：`developertools/solutions/alibabacloud-find-skills/SKILL.md` §"Intent Analysis for Search" + "Search Text Selection"

复合用户请求沿五轴（Action/Object/Context-source/Expected-output/Support-needs）分解成**可搜意图单元**，各自独立搜。关键改写规则："若搜词多为领域专属标签、文档标题、组织内术语、策略名、私有术语，搜前向底层能力改写。"迭代梯子：全意图→产品/任务关键词→中英变体→同义词→更宽词→类目语义搜；"对某意图单元至少试过一条能力导向搜词前，不得断言'无专用 Skill'"。

**→ powerelf**：路由器（Hermes）现靠短 description 前缀。采纳意图单元分解+能力改写能改进复合工业请求路由（"查一下3号闸门的渗压并生成巡检报告"→拆"监测查询"+"报告生成"两意图）而非逼一个 skill 兼顾。

### 评估方法论深潜——agentloop-evaluation 如何测 agent 质量
skill 是 AgentLoop API（`2026-05-20`）+ SLS logstore 上的编排层；方法论在 `references/{spec-format,api-map,result-analysis}.md` 与两个 Python 包装器。

**三个 evaluator 原型**（保用户要求类型，永不静默替换）：
- `AGENT`——judge agent；config=`{prompt, variables}`。
- `LLM`——prompt-based LLM judge（比全 agent 轻）。
- `CODE`——确定性打分（基于规则的度量）。

**Golden 集/数据源**——三任务模式：
- One-shot（`taskMode=oneshot`）：`dataFilter.provided` 下一个样本；返 `eval-temp-*` 任务 ID 速试 evaluator。
- Batch trace（`data_type=trace`）：评估观测生产 trace；服务自动填 `storeName=logstore-tracing`；需有界 `maxRecords`+带时区 ISO-8601 `[start,end)` 回填窗（naive 被拒）。
- Batch dataset（`data_type=dataset`）：评估已有 AgentLoop 数据集；evaluator 变量**直接映数据集列名**（`input/output/expected_output`），`dataFilter.query` 是无 WHERE 的 SQL 片段。

**`variable_mapping` 设计 judge**——evaluator 声明变量；任务映到评估数据字段/路径。内建正确性是 `Builtin.agent_correctness`（非 `Builtin.correctness`）需恰好 `input/output/expected_output`。内建名假定不稳——先跑 `discover` 用返回的确切 `Builtin.*` 名。

**每评估记录捕获**（固定 `evaluation_detail` SLS Logstore）：`score_value`、`normalized_score_value`（排名/分带用 [0,1]）、`score_range`、`status`(success/unknown/failed)、`explanation`、`evaluation_process`(原始，默认省)、`eval_latency`、`eval_metrics`、`custom_outputs`、`data_link`(回指 trace/数据集行)、`task_id/run_id/evaluator_name`。

**分数带**（匹配 Evaluation Explorer UI）：Very poor `<0.3`、Poor `0.3–<0.5`、Medium `0.5–<0.7`、Good `0.7–<0.9`、Excellent `≥0.9`。默认低分阈 `0.5`；分析默认 over `status=success`。

**安全/成本纪律**——mutation 确认协议是方法论的结构部分：每个 mutation（建/改 evaluator、建任务、`--execute`、continuous 启用、unbounded 批、删）走 preview→confirm→execute；`--allow-continuous`/`--allow-unbounded` 是 agent 不得自授权的门控 flag。只读分析永不需确认。

**净模型**：evaluator-as-judge（AGENT/LLM/CODE）over golden/观测数据集 → 归一化分入固定 logstore → 三层下钻（总览→按 evaluator→最差案例）→ 聚类失败模式 → 只在重复模式上提议改动。

### 荣誉提名
- **沙箱契约即数据**（`mcp-core-script-generate/references/runscript-contract.md` + `scripts/check_sandbox.py`）：白名单模块、禁 API、`BLK-4001` 规则（参值不含小写 `aliyun` 子串）——生成代码的紧致可机检安全策略。
- **目录自动从上游建**（`terraform-code-generation/scripts/build_alicloud_providers.py`）：clone provider 仓、walk `website/docs/{r,d}/*.html.markdown`、4 步正则 cascade 提子类+弃用状态——免人工维护静态参考表的模型。
- **混合检索参**（`bailian-rag-knowledgebase/scripts/retrieve.py`）：`dense_similarity_top_k=100`、`sparse_similarity_top_k=100`、`enable_reranking=true`、`qwen3-rerank-hybrid`——值得逐字抄的已知良好 RAG 配置。
- **API-key 自动发现链**（`bailian-rag-knowledgebase/scripts/api_key.py`）：配置文件→env→自动建并持久化，完成前强制 `grep -rn "sk-"` 自检——永不向模型暴露凭证。
- **只读/写 skill 分离**（`pai-dlc-job` 写 vs `pai-dlc-job-diagnostics` 只读）：两 skill 共享显式字段契约（`--job-id`/`--pod-id` 透传）但干净分爆炸半径——直接适用 powerelf 把巡检（读）与处置（写）拆开。
- **"listing ≠ diagnosing"+"总以分析收尾"**（`pai-eas-service-diagnose` frontmatter）：两反模式护栏——防浅诊断输出。
- **mutation 确认协议 + cost-aware flag**（`agentloop-evaluation`）：三步 preview/confirm/execute 分 continuous-cost 与 unbounded 的 opt-in flag——任何碰有状态资源的 skill 可用。

---

## Part 5 · 安全 / 治理 / Finops（data-governance 向）

> 覆盖 `security/{solutions,asc,riskmanagement,sddp,csas,kms,lvwang}/*`、`migrationom/{governance,ram,bpstudio}/*`、`others/accs/*`、`playbooks/wadaps/*`。

### Top 5 宝藏

#### 1. YAML 驱动检查目录 + 4 原语规则引擎（`full|partial|fail|error` 判定）
**源**：`security/solutions/alibabacloud-security-health-check`
- 目录：`references/checks/{waf,sas,cfw,ddos}.yaml`（每检查 `id/name/category/weight(1-15)/severity/rule/remediation`）
- 引擎：`scripts/engine/scorer.py`（`evaluate_rule` L88-127；`score_product` L132-163）

每检查是数据不是代码。加新治理维度只需 YAML 段，零改 Python。规则 DSL 极小——4 原语覆盖几乎所有数据质量检查：
- `ratio`——分子/分母→阈值（如完整性=非空行/总行）
- `range`——数值在带（如陈旧小时数、插值%）
- `exists`——相等（如"列在不在"、"最新值是否在 T 内"）
- `enum`——值在 {expect, partial_values, fail_values}（如传感器状态=online|offline|degraded）

每规则返判定与 `score_pct={full:1.0,partial:0.5,fail:0.0,error:0.0}`。`error` 不同于 `fail`——评估异常（缺 JSONPath、除零）打 0 但单独标，报告可说"无法评估"而非假"失败"。

**→ powerelf-data-governance**：每水利传感器表一份 `<table>.yaml`（或每维一份：完整性/一致性/及时性/陈旧度/插值）。`ratio` 管 null 密度；`range` 管 `latest_timestamp_age_hours`；`enum` 管 `sensor_status`。MySQL 直连层填引擎已消费的同 JSON 形状。

#### 2. 加权归一 + 字母等级带 + 每维雷达
**源**：`security/solutions/alibabacloud-security-health-check`
- 评分：`scripts/engine/scorer.py` L162——`normalized = total_score / weight_sum * 100`
- 分级：`scripts/engine/report_html.py` L28-33, L40-44——`GRADE_BANDS = [(90,'A','Excellent'),(75,'B','Good'),(60,'C','Passing'),(0,'D','Needs Improvement')]`
- 每产品雷达：`build_context` L61-73（5 轴雷达的 labels/scores 数组）

**关键设计决策**：**severity 不影响分——只 `weight` 影响。** `waf.yaml` L4："severity 只用于报告排序，不影响评分。"分离两个数据治理 skill 常混的关切：(a) 数值健康分（纯权重驱动、可审计、稳定）与 (b)"先修什么"排序（severity×effort）。按 `weight_sum` 归一使分可比——3 表评估与 30 表评估都落同 0–100 尺。

**→ powerelf**：定义 5 维分（你已命名的）= 成员检查的加权均，表级分=维度加权均，fleet 级分=表加权均。A/B/C/D 带 90/75/60 直套。

#### 3. 渐进披露报告漏斗（overview→pillar→detail→resources）
**源**：`migrationom/governance/alibabacloud-governance-evaluation-report`
- 设计：SKILL.md L12-22（"progressive disclosure funnel"，4 层）
- 报告格式：`references/report-format-{overview,pillar,detail}.md`
- 数量规则：`report-format-overview.md` "数量控制规则"——`Error≤5:全列; 6-10:全列但简; >10:Top10按RecommendationLevel`
- 严重度分类：SKILL.md "Field Reference"——Risk `Error>Warning>Suggestion>None` × RecommendationLevel `Critical>High>Medium>Suggestion`

解"扫出 200 条然后呢"。每层有明确职责：overview=速诊+指方向；pillar=按域聚焦下钻；detail=单检查+处置；resources=违规行/设备。每层以**锚定实际数据的模板化下一步**收尾（"想查看 {pick a high-risk DisplayName} 怎么修复"）而非泛泛"看文档"。**数量控制规则表是真宝石**——告诉 agent 截断成摘要行前到底显几行。

**→ powerelf**：overview=fleet 分+每表热图+top 陈旧传感器；pillar=单表跨 5 维下钻；detail=一维（如及时性）+失败传感器；resources=真实 `(sensor_id, latest_timestamp, age_hours)` 行。数量配额逐字抄。

#### 4. 三件套交付（HTML 执行层 + Excel 运维 + Markdown 内部）
**源**：`security/solutions/alibabacloud-security-health-check`
- 计划：SKILL.md "Output Artifacts"（L102-109）+ "Key Design Principles"（L232-238）
- 模板：`assets/templates/{report.html.j2, exec_summary.md.j2}`
- 渲染器：`scripts/engine/report_{html,excel,markdown}.py`，全由一个 `scores.json` 中间态驱动（`scorer.py` L206-213）
- Excel 规格：`exec_summary.md.j2` L72——"10 列结构"带"Implementation Status"列供运维跟处置

一个评分中间态（`scores.json`），三受众，三可并行渲染器。exec_summary 模板结构范本：(1) 总结论+等级 (2) 按逻辑域非按产品分组的风险分解 (3) P0/P1/P2 带 effort 标的建议动作 (4) 下一步。开头强制 dynamic-range 规则——"本评估覆盖 N 产品：[list]"——报告永不撒范围谎。

**→ powerelf**：产一个 `governance_scores.json`，再 `report_html.py`（操作员看板）、`report_excel.py`（SCADA 团队处置工单队列）、`report_markdown.py`（塞进巡检/elf chat）。带手动"实施状态"列的 10 列 Excel 是水利运维交接的正确形状。

#### 5. 建议生成引擎（P0/P1/P2 × effort × 复合排名）
**源**：`others/accs/alibabacloud-finops-inspect` + `security/solutions/alibabacloud-security-health-check`
- P 分桶规则：`finops-inspect/SKILL.md` L292-297 + per-resource 判断（L248-253, 269, 273, 286-288）
- 复合 Top-10 排名：`report_html.py` L105-118——`rank_key = -(sev*2 + verd*3 + eff + weight*0.3)`
- 处置 YAML：`references/checks/*.yaml` `remediation:{effort,steps,doc}`

finops 给脆的 pass/fail 阈值逻辑（"CPU<5% AND mem<10% AND net<50Kbps→Critical Idle"；"未挂载盘创建>30d→升 P0"），security-health-check 给排名数学——单一复合键平衡 severity、判定量级、易修性、权重。Top-10 排序公式小到可直接落。`effort:low|medium|high` 嵌在处置 YAML，报告可说"先修这个，便宜"。

**→ powerelf**：每数据质量维定义显式 P 阈值：
- P0 = 陈旧>24h 在 load-bearing SL323 表，或必填列 null 密度>50%
- P1 = 插值比>20%，或配对雨/闸传感器一致性失配
- P2 = 仅观测（如表新建<7 天——借下面的"观测窗"规则）

### 评分 rubric 深潜——三种评分哲学
**A. 加权求和+字母等级（security-health-check）——最成熟**
per-check：`score_pct={full:1,partial:0.5,fail:0,error:0}[verdict]`、`score=weight×score_pct`。per-product：`normalized=total/weight_sum×100`（承重 trick）。multi-product：MVP 简均，phase2 按 purchase 加权（同 powerelf 想"按表重要性加权"）。Grade 硬切 A≥90/B≥75/C≥60/D<60。关键不变量：severity 只管排序；weight 是唯一分驱动；单产品分归一到 0-100 可比；partial-credit(0.5) 是唯一灰区。Top-10 复合排名 `-(sev*2+verd*3+eff+weight*0.3)`（verd fail=2/partial=1，权重 3× severity——硬失败压过高严重度 partial）。
**路径**：`scripts/engine/scorer.py`、`scripts/engine/report_html.py`。

**B. 平台算分+下钻呈现（governance-evaluation-report）**
`TotalScore` 0-1 来自云治理中心 API `list-evaluation-results`。skill **自己不算分**——是呈现/下钻层。矩阵 Risk×RecommendationLevel 两轴分类可两种过滤。数量配额是"显多少"的 rubric 非"评什么"：Error≤5 全列/6-10 简列/>10 Top10；Warning/Suggestion 概览从不列只计数。**教训**：若你坐在已有评分源（如未来 SCADA 质量服务）上，这是模板——你的 skill 拥漏斗与配额，不拥有数学。

**C. 阈值分桶严重度，无复合分（finops-inspect）**
无 0-100。每资源经显式布尔阈值落入一桶：Critical Idle(P0) `CPU<5% AND mem<10% AND net<50Kbps`；Low Util(P1) `CPU<10% OR mem<20%`；Observe(P2) `CPU 5-10%` 或 7 天观测窗；Normal。**带例外的门**：`PayType=Serverless` 缩容到 0 正常——显式**排除**而非惩罚；资源<7 天进"观测窗"排除浪费判断避假阳。**教训**：有些维度脆阈值桶比 0-100 更诚实。powerelf"陈旧度"是候选——"传感器静默>24h=P0"、">6h=P1"、"插值>窗口20%=P2"比模糊 73/100 自然。

**powerelf 推荐（混合）**：headline 完整性/一致性/及时性复合分用 A（加权），处置清单用 C（阈值分桶+显式布尔+每 SL323 表型例外白名单），报告层用 B 的显示配额。

### 荣誉提名
- **观测窗规则**（`finops-inspect/SKILL.md` L80）：资源<7 天排除闲置判断——直接适用"别把新装传感器标陈旧"。
- **已知例外白名单**（`finops-inspect/SKILL.md` L262）：Serverless 缩容到 0 是正常非浪费——按表型建模豁免（如雨量计旱季合理报零）。
- **数值校验清单**（`security-health-check/SKILL.md` L214-231）：发回复前对每个引用数字对 `scores.json` 强制字符级比较——防幻觉。
- **pinned 依赖自动装策略**（L179-206）：脚本 ImportError 精确名 `pyyaml jsonpath-ng jinja2 openpyxl`→自动 `pip install` 免确认。
- **HITL 参数确认闸**（`finops-inspect/SKILL.md` L190-217）：展示已解析参→问→等→执行；确认必须是与执行**分离的 agent turn**。
- **API 节流策略**（L351-357）：CMS 间隔 50-100ms、指数退避 1→2→4s max3、10 分钟总超时、超时返部分结果——MySQL 直连扫遇限流可直接落。
- **分类审计基线**（`openclaw-skill-security-scan/references/baseline.md`）：6 固定类目×{Pass/Warning/Fail}+"1+🔴=Critical"闸——非数值配置检查模型。
- **severity-icon 报告模板**（`openclaw-skill-security-scan/references/report_template.md`）：单 skill 判定模板（Safe/Sensitive/Risky/Malicious/...）。
- **解耦元数据缓存**（`governance-evaluation-report/SKILL.md` L292-305）：检查定义缓存 24h，结果始终实时，`--refresh` 强刷——分稳定 schema 元数据与易变传感器读数。
- **`--risky`/`--issues-only` 过滤**（governance pillar 模式）：隐藏合规项降噪。
- **三桶×两轴过滤**（pillar `-l Critical,High -r Error,Warning`）：独立优先级×风险过滤组合。
- **Extract→JSON→render 分离**（`wadaps/migration-mas-cloud-migration-survey` `scripts/extract.py`→JSON→`generate_report.py`）：同 `scores.json` 中间态解耦，推广到 docx 输出。
- **安全红线**（`wadaps/.../SKILL.md` "Safety Red Lines"）：显式"永不输出真实 IP/密码/定价"——水利 governance 样本可能含站坐标/操作员名时的 PII 模板。
- **维度化巡检报告**（`polardb-mysql-inspection/references/report-format.md`）：5 固定维度各带表块——比加权分简单的每表卡片布局。
- **session-id 可观测**（三个优先 skill 皆有）：`AlibabaCloud-Agent-Skills/<skill>/<uuid>` UA + OTel `baggage`——追哪次 agent run 产了哪份治理报告。

---

## Part 6 · 存储 / 媒体 / 容器 / 部署 / 其他

> 覆盖 `storage/{oss,ots,pds,disk,hbr}/*`、`container/csk/*`、`mediaservices/*`、`doweb/*`、`entcmc/*`、`computing/{computenest,ehpc,ecs}/*`、`playbooks/{optdes,wadaps}/*`、`others/solutions/*`、`solutions/*`。

### Top 5 宝藏

#### 1. 证据接地诊断 worker + 绝对范围边界
**源**：`playbooks/optdes/alibabacloud-pts-reporter/SKILL.md`（+ `references/tuning-knowledge-base.md`）

cluster 中 craft 最密。只读分析器带硬不变量：
- **输出契约是类型化 schema**：`findings[]{area,severity,evidence,suggestion}`——每个 `evidence` **必须**引真实 API 响应值。
- **NO-DATA-NO-ANALYSIS 规则**：核心 API 重试后仍空/错则跳过分析直接退出——永不无数据造 finding。
- **绝对范围边界**：显式列出范围外（实例级 CPU/Mem/Disk/Net），带字面移交模板（"这需实例级度量，请用云监控/诊断 skill"）。
- **FAST-FAIL 参数解析**：有界重试——`list-pts-scene` 至多 1 次、`get-pts-scene` 至多 1 次，然后停问用户。硬规则"永不循环/重试/猜参数"。
- **知识库分离**：`tuning-knowledge-base.md` 是策展的 症状→发现 映射，每条尾带"Data source (PTS report fields)"锚点防漂移。

**→ powerelf**：monitoring-analyzer 或 early-warning-diagnostic skill 采纳同脚手架——每条告警解释必须引 `(表,时间戳,列,值)` 四元组；范围外请求（"泵为何机械故障？"）给模板化移交；症状→发现映射放参考文件带显式数据源锚点。直击本地 LLM 幻觉。

#### 2. 二维度量聚合语法（时间 × 跨实体）
**源**：`storage/disk/alibabacloud-ebs-disk-metric-analyzer/SKILL.md`

任何时序平台的可推广 API 设计。三正交参组一次调用：
- `--aggre-ops AVG_OVER_TIME|SUM_OVER_TIME|MAX_OVER_TIME|...`（序列内归约）
- `--aggre-over-line-ops SUM|AVG|COUNT|MAX|MIN`（跨实体归约）
- `--group-by-labels DiskId|DeviceType|DeviceCategory|EcsInstanceId|Azone`（分区）

外加：period 感知时间范围限（5s 周期→最多 12h；3600s→更长）；JSON `dimensions` 批量过滤（`{"DiskId":["d-bp111","d-bp222"],"EcsInstanceId":["i-bp123"]}`）替 N+1 调用；JMESPath/jq 管线下游重塑示例。

**→ powerelf**：水位/流量/墒情/泵状态度量清晰映射——`--group-by-labels StationId|River|Region|SensorType`、跨站聚合成流域视图、短窗异常检测 vs 长窗趋势分析的周期选择。一个 API 形态替掉 monitor 里大量临时 SQL。

#### 3. 异步任务 envelope + 统一任务控制动词
**源**：`container/csk/alibabacloud-ack-cli/SKILL.md` + `references/async-tasks.md` + `scripts/wait-for-task.sh`

三件组成长任务模式：
- **Envelope**：每次写立即返 `{task_id,request_id,resource_id}`。三者都留（request_id 工单、resource_id 任务完成前也能跟进）。
- **阶段感知轮询**：`describe-task-info` 返 `state` 与 `current_stage`——helper 脚本只记阶段**变迁**防刷屏：`if [ "$STAGE" != "$LAST_STAGE" ]; then echo "[${ELAPSED}s] state=${STATE} stage=${STAGE}"`。
- **统一控制动词**：`pause-task`/`resume-task`/`cancel-task` 跨**所有**任务类型（集群建/升/扩、addon 装）—— standout idea：一个控制面管所有长操作。
- **每操作时长表**：参考文档列预期时长（建集群 8-20 分、addon 30 秒-5 分等）让 agent 设 sane 轮询超时。

**→ powerelf**：长跑数据治理 pass（大表 schema diff、回填巡检照片、重建 chatbi embedding）现无统一 job 模型。采纳 `task_id`+`state`+`current_stage`+统一 pause/resume/cancel 三件套给每个异步操作一致 UX。阶段变迁日志胜 `sleep` 循环。

#### 4. 同步/异步自动检测 + 验证诚实规则
**源**：`storage/oss/alibabacloud-oss-media-process/SKILL.md`

两新 craft：
- **自动检测执行路径**：脚本查操作名内部分流到同步（`x-oss-process`）或异步（`x-oss-async-process`）——"无需 `--async`/`--wait` flag"。调用方传一条操作链，脚本处理轮询至完成。
- **验证诚实 prose**：长且异常严的块，禁 LLM 声称做过而没做的验证。"若未跑只读验证步，不得把机读输出属性描述为独立确认"；"不得假定本地装了 PIL/ffprobe"；"不得用 `head_object` 替代媒体属性验证"。区分 metadata-验证 vs visual-验证（水印正确需视觉非仅文件存在）。
- **歧义输出默认上云**：用户说"保存"不带"下载到本地"→存 OSS 不下载；仅显式请求才本地下载。

**→ powerelf**：chatbi 图表导出、巡检照片处理、监测片段导出。验证诚实规则普适——任何产关于自身输出（大小/行数/格式）声明的 skill 都该逐字抄。"歧义保存措辞"规则适用任何说"存一下"未必指本地盘的工业用户。

#### 5. 父子路由 skill + 显式输入/输出契约
**源**：`playbooks/optdes/alibabacloud-pts-pilot/SKILL.md`

纯路由 skill（零 CLI 执行，只经 `Skill` 工具委派）结构异常严谨：
- **子 skill 注册表**：每子 skill 列 Status/Intent Signature/Positive Triggers/**Negative Triggers**/Handoff fields。**Negative triggers 一等公民**——每子声明什么**不该**路由给它。
- **每子 I/O 契约**：显式字段表（Required/Conditional/Optional）。路由器只传用户显式给的——"不需收全字段或构复杂对象，让子 skill 处理缺的"。
- **不问红线**：除缺 `SceneId` 这一种，路由器**永不**问用户其他缺参——静默委派。
- **Announce→Handoff 原子序**：恰好一行公告，立刻调 Skill 工具，中间无读文件/搜。
- **主动跟进路由**：reporter 找到瓶颈后，路由器主动提议找产品级诊断 skill 并路由——内建"下一步"移交环。
- **ZIP 布局 trick**：父 `SKILL.md` 在 ZIP 根 + 子 skill 文件夹平级。

**→ powerelf**：一个 `powerelf-router` 坐在 inspection/monitoring/early-warning/chatbi/data-governance 之上作 worker skill，各有注册行+显式契约。**Negative Triggers 列**是关键洞察——逼路由器作者前置想边界 case 而非让路由漂移。

### 荣誉提名
- **video-editor**（`mediaservices/ice/alibabacloud-video-editor/SKILL.md`）：关注分离——`references/` 是 LLM 知识库（时间线模板），`scripts/` 是纯执行器只提交/轮询；LLM 从 references 组 JSON，永不写 SDK 调用。适用 chatbi 图表规格组装。
- **opc-advisor**（`computing/ecs/alibabacloud-opc-advisor/SKILL.md`）：状态机顾问（非单发）带 PII 绝对闸（user-data=Yes 则 Starter tier 不可达）、模糊量词或拒绝硬停、输出前自检任一失败 HARD-BLOCK 重写。**隐藏宝石**。
- **video-translation**（`mediaservices/ice/alibabacloud-video-translation/SKILL.md`）：阶段闸清单显式标 HARD-GATE/BLOCKING/Non-blocking/Conditional-Blocking；参数决策表分类每参 MUST-ask/Fixed/Can-default/Scenario——杀 LLM 参数即兴。
- **ecs-code-deploy**（`computing/computenest/alibabacloud-ecs-code-deploy/SKILL.md`）：SCRIPT-FIRST 规则（手动 CLI 前先 toolkit 脚本）；重复部署快捷检测（config.yaml 带 instanceId→跳 init 直 deploy）；跨平台 `$SKILL_DIR` 解析 A/B 带反模式。
- **tablestore-openclaw-memory**（`storage/ots/...`）：jq 结构化配置变更 + 严格 per-input 正则校验表；npm registry racing（同时测 npmjs 与 npmmirror 取快）应对中国网络抖动。
- **ehpc-instant-job-skill**（`computing/ehpc/...`）：预配置文件加载（先查 `./jobconfig/pre-config.json`，存在/缺/坏三分支）——尊重持久化用户配置的 skill 模型。

### 隐藏宝石（专述）
**`alibabacloud-opc-advisor`** ——表面"个人创业者"低门槛建站推荐 skill，craft 密度极高：状态机交互流（非单轮生成）、2-question rule（只问 2 个 high-stakes 字段，其余 5 个推断）、vague/refusal 必中断、输出前 7 项硬自检任一失败即 discard 重写。"iron-rule"编号系统 + "Hard Block" 语义 + "inferred from stated signal"（非凭空推断）的字段处理，比很多技术型 skill 更严谨。对 powerelf 任何"收集需求→产出方案"的 skill（chatbi 选表/选维度、governance 选治理策略）都是现成工艺模板。

---

## Part 7 · 跨 skill 通用宝藏（综合，置信度最高）

> 这些模式被**多个互不相关 skill 独立实现**——是经过验证的通用解法，非偶然技巧。按出现广度与对 powerelf 价值排序。

### 7.1 「先查后写」——绝不让 LLM 猜列名/表名/参数（4 处，最强信号）
精确命中 MEMORY 痛（[[powerelf-schema-lookup-architecture]]）。
- QuickBI：4 级 cascade resolver，LLM 永不直接产表名。
- CMS 告警：主路径 `describe-metric-meta-list` 动态枚举，失败才退关键词表。
- MaxCompute：规则进 prompt，schema 不进；缺则返空+声明缺口。
- Terraform：写代码前必"recitation"逐字背参数。
**共性结论**：把 schema/列名从 SKILL.md 抽出，变运行时查询函数（`columns(table)`/`resolve_table()`）。

### 7.2 结构化输出 envelope（findings/severity/category/next_steps）
- SysOM：`{summary, findings[{severity,detail,category}], next_steps[]}`
- network-diagnose：`结论→Check Summary→Root Causes(排序)→Actions→Evidence`
- pts-reporter：`findings[]{area,severity,evidence,suggestion}`，evidence 必引真实值
- ChatBI：`{sql,explanation,tables,assumptions}` JSON 契约
**共性**：固定"输出形状"让下一步机读决策。

### 7.3 「Verified / Unverified / Blocked」三元结论 + 不短路
- cfw-acl：每结论标三态，Blocked 附缺失表。
- network-diagnose：找到 P0 后仍跑完所有步骤，报告列全部问题。
- pai-eas：listing≠diagnosing，不许只甩原始命令收尾。
**直击 powerelf**：SL323 表缺失/数据暂无常见。Blocked 把"暂无数据"变显式可审计状态。

### 7.4 评分系统（权重求和+等级，severity 与 score 解耦）
- security-health-check：`Σ(weight×verdict_pct)` 归一到 0-100；severity 只排序不进分；A/B/C/D。
- rds-pg：100 起扣分，色阶+worst-20 排名。
- finops：阈值分桶 P0/P1/P2 + 已知例外白名单。
**结论**：headline 用权重评分+等级，治理清单用阈值分桶+白名单。

### 7.5 知识即数据（YAML/JSON 目录，非代码）
- security-health-check：`checks/*.yaml`+4 原语引擎，加维度零改 Python。
- alb-ingress-doctor：`diagnostic_tree.json`（regex→causes→solutions），LLM 按正则匹配走树。
- pts-reporter：`tuning-knowledge-base.md` 症状→发现带数据源锚点。
**直击 inspection**：15 维检测知识做成 `diagnostic_tree.json`，命中后自动沿树定位根因（对齐 Part 0 巡检→诊断链）。

### 7.6 写操作三道护栏 + 强制预览确认
- 三级升级：prose 禁令→报告免责头→PreToolUse hook（`check-write-operation.sh`）。
- cms-alert-rule-create：写前必渲染汇总卡，critical rule #12 禁以"自动化"为由跳过。
- agentloop-evaluation：mutation 三步 preview→confirm→execute，cost flag 不得自授权。

### 7.7 评估闭环（golden 集 + 三层下钻分析器）
- agentloop-evaluation：3 evaluator 原型（AGENT/LLM/CODE）→归一化分入 logstore→三查询分析器（总览→按 evaluator→最差 N）→聚类失败模式。
- 分数带：<0.3/0.3-0.5/0.5-0.7/0.7-0.9/≥0.9。
- **powerelf 已有 `eval_criteria.md`（10 条二元 EVAL）**——golden 雏形，可升格为测量仪。

### 7.8 报告分层 + 显示配额 + 多格式三件套
- governance-evaluation-report：4 层漏斗+数量控制规则（≤5 全列/6-10 简/>10 Top10）。
- security-health-check：一个 `scores.json`→HTML/Excel/MD 三渲染器。
- 渐进披露每层以锚定数据的模板化下一步收尾。

### 7.9 可观测性（session-id + UA + OTel baggage）
- 几乎所有 skill 的"家风格"：32-hex session-id 全程复用 + `--user-agent AlibabaCloud-Agent-Skills/<skill>/<id>` + OTel `baggage` 传播。
- 廉价的"哪次 agent run 产了哪份报告"审计链。

### 7.10 读/写 skill 分离
- `pai-dlc-job`（写）vs `pai-dlc-job-diagnostics`（读）共享字段契约但分爆炸半径。
- SysOM 诊断："诊断期间不执行修复"。
**直击 powerelf**：把巡检（读）与处置（写）拆成独立 skill。

---

## Part 8 · powerelf skill 映射表

| powerelf skill | 最值得借的宝藏 | 源文件 |
|---|---|---|
| **inspection** | ① 根因 blocking-chain 重建（分层 fallback 找根因）② `diagnostic_tree.json` 知识树自动定位 ③ health-score 100 扣分制 ④ Verified/Blocked 标签 | `playbooks/trouboper/alibabacloud-history-lock-diagnose/scripts/smart-lock-diagnosis.py`；`others/devopsimpl/alibabacloud-alb-ingress-doctor/references/diagnostic_tree.json`；`.../rds-postgresql-inspection/scripts/inspect.py` |
| **chatbi** | ① QuickBI 4 级表名 resolver ② MaxCompute text2sql 规则书+反模式 ③ 图表交付契约（chartType 枚举 + 禁 Read PNG）④ 静态 SQL lint 闸+列存在性校验 | `quickbi-smartq/scripts/chat/cube_resolver.py`；`odps/.../references/text2sql_principles.md`；`polardb-mysql-sql-lint/scripts/sql_lint.py` |
| **early-warning** | ① 规则体拆判别联合类型（datasource/query/condition/notify）② `thresholdList` 一规则多级别+写时预生成中文消息 ③ 通知对象写前 probe ④ 单位自动换算表 | `middleware/cms/alibabacloud-cms-alert-rule-create/references/{step3-detection-config,step5-preview-execute}.md`；`.../cms-manage/references/alerting.md` |
| **monitor** | ① 二维度量聚合语法（时间×跨实体）② Event Hub→LogStore 告警历史管线 | `storage/disk/alibabacloud-ebs-disk-metric-analyzer/SKILL.md`；`cms-manage/references/event-hub.md` |
| **data-governance** | ① YAML 检查目录+4 原语引擎 ② 权重评分+等级（severity 解耦）③ 渐进报告漏斗+数量配额 ④ 三格式交付（HTML/Excel/MD）⑤ 阈值分桶+例外白名单 | `security/solutions/alibabacloud-security-health-check/scripts/engine/{scorer,report_html}.py`+`references/checks/*.yaml`；`migrationom/governance/.../references/report-format-overview.md` |

---

## Part 9 · 隐藏宝石

- **`opc-advisor`**（`computing/ecs/alibabacloud-opc-advisor/SKILL.md`）：状态机交互范本——2-question rule、vague/refusal 必中断、输出前 7 项硬自检任一失败 discard 重写。任何"需求→方案"skill 必看。
- **`ebs-disk-metric-analyzer`**：二维度量聚合语法，替掉 monitor 大量临时 SQL。
- **`pts-reporter`**：NO-DATA-NO-ANALYSIS + 绝对范围边界 + 移交话术——直击本地 LLM 幻觉。
- **`opc-advisor`/`video-translation` 的 HARD-GATE/BLOCKING 标签法**：每参标 MUST-ask/Fixed/Can-default/Scenario，杀死参数即兴。

---

## Part 10 · 建议优先级

只做 3 件事，按序：

1. **「先查后写」落到 `db.columns()` + 表名 resolver**（§7.1）。命中已记录最大痛，4 个现成范本。chatbi/early-warning/governance 共同地基。
2. **inspection 的 `diagnostic_tree.json` + 根因 escalation 链**（Part 8 inspection ①②）。15 维检测从"报异常"升级到"自动定位根因"。
3. **data-governance 的 YAML 检查目录 + 4 原语引擎 + 权重评分**（§7.4+§7.5+Part 8 governance ①②）。一份 `scores.json`→HTML/Excel/MD 三件套，补 governance 最缺的报告层。

通用 §7.2（envelope）、§7.3（Verified/Blocked）、§7.6（写护栏）属"全项目统一升级"，建议作**项目级约定**逐 skill 推广，而非单点改造。

---

## Part 11 · knowledge-work-plugins 交叉分析（chatbi 向）

> **源仓库**：`/home/scada/knowledge-work-plugins/`（Anthropic 风格的"知识工作"skill 合集，含 bio-research/finance/marketing/operations 等多领域）。本节聚焦其 `data/skills/` 下的 10 个**分析师工作流** skill，与 Part 0–10 的阿里云运维 skill 形成**互补的两种 craft**。
>
> **阅读建议**：先看 §11.0 两库定位对比；chatbi 改造直接看 §11.1；其他 skill 看 §11.2。

### 11.0 仓库定位：两种互补的 craft

| 仓库 | 性质 | 擅长的 craft | 对 chatbi 的角色 |
|---|---|---|---|
| **alibabacloud-aiops-skills**（Part 0–10） | 云运维 / 诊断 skill | envelope / 写护栏 / 可观测性 / schema 查询 / SQL lint / 专家诊断路径 | 管"SQL 怎么**写对**" |
| **knowledge-work-plugins/data**（本节） | **分析师工作流** skill（问题→SQL→验证→可视化→看板） | 交付前 QA / 分析陷阱目录 / 可视化设计 / 领域知识库 / 置信度评估 | 管"分析怎么**做得靠谱**" |

**关键判断**：chatbi 产的是"数据分析"而非"运维操作"——所以本节的模式**更贴合 chatbi 的本质**。两者不冲突：alibabacloud 解决 schema-lookup / lint / envelope，本节解决验证 / 陷阱 / 知识库 / 置信度。**叠加才是完整解法。**

`data/skills/` 的 10 个 skill：`data-context-extractor`（元 skill：抽取领域知识生成定制数据 skill）、`write-query` / `sql-queries`（NL→SQL + 方言库）、`explore-data`（数据画像）、`validate-data`（交付前 QA）、`analyze`（问答编排）、`create-viz` / `data-visualization`（可视化）、`build-dashboard`（HTML 看板）、`statistical-analysis`（统计方法）。

---

### 11.1 chatbi 专项借鉴

> **chatbi 已有的强项**（避免重复造）：关联键铁律（stcd/eq_id）、`deleted=0`/`tenant_id` 标准过滤、dr 单位陷阱、varchar CAST 陷阱、`references/few_shots.md`（15+ 实例）、`rules/chart-selection.md` 12 类图表选择树 + ECharts 模板、`rules/intent-classification.md` 3 意图分类。**下面只列真缺的。**

#### 🔴 Tier 1（填真缺口，价值最高）

**1. data-context-extractor → 建一份水利领域知识库**
- **chatbi 现状**：只有 `schema.md`（DDL/字段）+ `few_shots.md`（范例）+ 表映射。MEMORY 记的 [[powerelf-schema-lookup-architecture]] 说"COLUMN_MEANINGS 是含义唯一源"——但列注释**缺业务语义层**。
- **本节给的结构**（`data-context-extractor/SKILL.md` + `references/{domain-template,skill-template,example-output}.md`）：① **实体消歧**（"水位"是水库 `rz`? 河道 `z`? 闸站上游 `upz`? ——水利数据真歧义）② **术语表**（汛限水位 / 警戒水位 / 保证水位 / 蓄水量 / 入库出库流量 的精确定义 + 公式）③ **标准过滤** ④ **每域 gotchas** ⑤ **指标定义**（source / formula / caveats）。其 Bootstrap 模式还示范了"问分析师哪 3–5 张表最重要、术语怎么消歧、该滤掉什么"的抽取流程。
- **借鉴动作**：建 `chatbi/references/domain-knowledge.md`（或 `references/domain/` 分域），沉淀实体消歧表 + 水利术语表 + 指标公式。这是比 COLUMN_MEANINGS 丰富的"部族知识"载体，与运行时 `columns()` 互补。

**2. validate-data → 给 pipeline 加"交付前验证闸"+ 置信度**
- **chatbi 现状**：`intent-classification.md` 的流水线是 `生成SQL→执行→选图→解读`，**执行与解读之间无显式验证闸**（仅 INTERPRETATION 步引用 `_shared/analysis-qa-checklist.md`）；输出**无置信度评级**。
- **本节给的**（`validate-data/SKILL.md`，383 行）：① **Pre-Delivery QA 清单**四组（数据质量 / 计算 / 合理性 / 呈现）② **分析陷阱目录**（join 爆炸、**平均值之平均**、不完整周期对比、分母漂移、时区错配、幸存者偏差、Simpson 悖论、look-ahead、cherry-pick——**每一个都是水利趋势分析的真坑**）③ **结果健全性检查**（量级 / 交叉验证 / 红旗）④ **3 级置信度**（Ready to share / Share with caveats / Needs revision）。
- **借鉴动作**：在流水线插 `VALIDATE` 步，把陷阱目录本地化为水利版（dr 单位、varchar CAST、eq_id vs stcd、deleted=0、汛期 vs 非汛期可比性、闸门调度导致的水位正常波动），输出带 `confidence_tier`。直击审计 A4/A5 缺口。

**3. SQL 输出契约升级为结构化 envelope**
- **chatbi 现状**：`sql-generation.md` 输出格式是极简的 `## sql语句 / ## 数据`。
- **本节给的**（`write-query/SKILL.md` Step 5：查询 + 每段解释 + 性能注 + 修改建议；与 Part 2 `odps/text2sql_principles.md` 的 `{sql,explanation,tables,assumptions}` 契约一致）。
- **借鉴动作**：输出改 `{sql, tables_used, assumptions, note}`——`assumptions` 把"agent 悄悄把'水位'当成 rz"变成**可见可捕获**的声明。直击 B1 缺口。

#### 🟡 Tier 2（打磨）

**4. chart-selection 补"何时不该用"+ 设计原则 + 数字格式 + 无障碍**
- **chatbi 现状**：`chart-selection.md` 只有选择树 + ECharts JSON，**无反例、无设计纪律、无数字格式化**。
- **本节给的**（`data-visualization/SKILL.md` + `create-viz/SKILL.md`）："饼图 <6 类才用"、"3D 永不"、"双轴谨慎"、标题写洞察非指标、柱状从零起、按值排序、色盲友好色板、数字格式化 helper（K/M/B、%、货币）、无障碍 checklist。
- **借鉴动作**：**逻辑抄，代码不抄**（chatbi 用 ECharts 不是 matplotlib）。水利数字常超大（蓄水量 m³、累计雨量 mm），数字格式化尤其值。

**5. explore-data 的列分类法 → 让选图更聪明**
- **本节**：列分 7 类（Identifier / Dimension / Metric / Temporal / Text / Boolean / Structural），驱动"建议维度 / 指标"。
- **借鉴动作**：给 SL323 列打分类标签，chart-selection 不再只靠"字段数 / 行数"，而靠"Metric×Temporal→line、Dimension×Metric→bar"等语义组合。

**6. MySQL 方言模式库**
- **chatbi 现状**：依赖 `_shared/sql-discipline.md`，缺系统性 **MySQL 模式库**。
- **本节给的**（`sql-queries/SKILL.md`）：MySQL 安全除法 `a/NULLIF(b,0)`、`DATE_FORMAT(tm,'%Y-%m')` 截断、`JSON_EXTRACT(extend,'$.content[0]')`（**直击 ew_info_rules.extend**）、窗口函数、CTE、`ROW_NUMBER` 去重取最新、cohort 保留、funnel。
- **借鉴动作**：建 `chatbi/references/mysql-patterns.md`，尤其 `JSON_EXTRACT` 解 extend——early-warning 也用得上。

#### 🟢 Tier 3（更广）

- **analyze 的复杂度路由**（快答 / 全分析 / 正式报告三档 → 变输出深度）：chatbi `intent-classification.md` 有未实现的 `ANALYSIS` 意图，可据此落地。
- **statistical-analysis 的谨慎规则**（移动平均、周期对比、季节性、相关≠因果、假精度）：对 chatbi 的 INTERPRETATION 步有用。

---

### 11.2 附带对其他 powerelf skill 的借鉴

- **data-governance** ← `validate-data` 的 QA 清单 + 陷阱目录 + 完整性 Green/Yellow/Orange/Red（governance 有评分，这丰富报告层）；`explore-data` 的 profiling 与 governance 的 detector 互补（一个看分布、一个看异常）。
- **inspection / monitor** ← `statistical-analysis`（移动平均、周期对比、季节性检测、z-score/IQR/百分位离群、趋势预测、相关≠因果）——补强 trend-detection。
- **全项目** ← `data-context-extractor/scripts/package_data_skill.py` 的 `validate_skill()`（frontmatter 守卫：检 SKILL.md 存在 / 有 name+description / 无 `[PLACEHOLDER]` 残留）——skill 作者的小工具。

---

### 11.3 chatbi 建议优先级

按"填缺口 × 改动小"排：

1. **Tier 1.2 验证闸 + 置信度**——pipeline 加一步 VALIDATE，本地化水利陷阱。改动在 `rules/intent-classification.md` + 新建 `references/validation-checklist.md`。
2. **Tier 1.1 领域知识库**——建 `references/domain-knowledge.md`（实体消歧 + 术语表），最补 schema 痛。
3. **Tier 1.3 SQL 输出 envelope**——`rules/sql-generation.md` 输出格式升级，带 `assumptions`。

这三件把审计里 chatbi 的 A4/A5/B1 三个 🟡/❌ 一次性补成 ✅，范本都在本节现成。

---

### 11.4 knowledge-work-plugins 关键文件路径

> 所有路径相对 `/home/scada/knowledge-work-plugins/`。

- `data/skills/data-context-extractor/SKILL.md`（+ `references/{sql-dialects,domain-template,skill-template,example-output}.md`、`scripts/package_data_skill.py`）
- `data/skills/validate-data/SKILL.md`（Pre-Delivery QA + 陷阱目录 + 3 级置信度）
- `data/skills/write-query/SKILL.md`（NL→SQL 6 步工作流）
- `data/skills/sql-queries/SKILL.md`（多方言库 + MySQL 段 + 窗口/CTE/cohort/funnel/dedup 模式）
- `data/skills/explore-data/SKILL.md`（列分类法 + 数据画像 + 质量评估框架）
- `data/skills/data-visualization/SKILL.md`、`data/skills/create-viz/SKILL.md`（选图 + 设计 + 数字格式 + 无障碍）
- `data/skills/build-dashboard/SKILL.md`（自包含 HTML 看板 + 大数据集预聚合）
- `data/skills/statistical-analysis/SKILL.md`（描述统计 / 趋势 / 离群 / 假设检验 / 谨慎规则）
- `data/skills/analyze/SKILL.md`（问答编排 + 复杂度路由）

---

## 附录 · 关键文件路径索引

> 所有路径相对 `/opt/git/alibabacloud-aiops-skills/`。

### SysOM（Part 0）
- `skills/computing/alinux/alibabacloud-alinux-sysom-inspection/SKILL.md`
- `skills/computing/alinux/alibabacloud-alinux-sysom-inspection/scripts/sysom_cli/inspection/command.py`
- `skills/computing/alinux/alibabacloud-sysom-diagnosis/SKILL.md`
- `skills/computing/alinux/alibabacloud-sysom-diagnosis/references/{memory-triage,non-memory-triage,deep-actions,parameter-guide,report-interpretation,classify-output-guide,ram-policies,supported-environments}.md`

### 巡检/诊断（Part 1）
- `skills/playbooks/trouboper/alibabacloud-history-lock-diagnose/scripts/smart-lock-diagnosis.py`
- `skills/others/devopsimpl/alibabacloud-alb-ingress-doctor/references/diagnostic_tree.json`
- `skills/playbooks/trouboper/alibabacloud-network-diagnose/references/{root-cause-priority,report-template}.md`
- `skills/playbooks/trouboper/alibabacloud-rds-postgresql-inspection/scripts/inspect.py`
- `skills/playbooks/trouboper/alibabacloud-cfw-acl-diagnosis/references/diagnosis.md`
- `skills/playbooks/trouboper/alibabacloud-polardb-mysql-sql-lint/{SKILL.md,scripts/sql_lint.py,references/sql-lint-rules.md}`

### 数据库/SQL/BI（Part 2）
- `skills/analyticscomputing/quickbi/alibabacloud-quickbi-smartq/scripts/chat/{cube_resolver,cube_name_lookup,chart_renderer}.py`
- `skills/analyticscomputing/quickbi/alibabacloud-quickbi-smartq/references/chat/module-chat-dataset.md`
- `skills/analyticscomputing/odps/alibabacloud-odps-sql-generation/references/{text2sql_principles,sql_query_patterns}.md`
- `skills/analyticscomputing/dide/alibabacloud-dataworks-metadata/SKILL.md`
- `skills/database/dms/alibabacloud-data-agent-skill/SKILL.md`
- `skills/database/adb/alibabacloud-analyticdb-mysql-copilot/SKILL.md`

### 告警/监测/日志（Part 3）
- `skills/middleware/cms/alibabacloud-cms-alert-rule-create/{SKILL.md,references/{step0-intent-routing,step2-query-generation,step3-detection-config,step5-preview-execute,cms2-step3-detection-config}.md}`
- `skills/middleware/cms/alibabacloud-cms-manage/references/{alerting,event-hub}.md`
- `skills/security/sas/alibabacloud-sas-alert-handler/references/{operation-codes,workflow-details}.md`
- `skills/storage/sls/alibabacloud-sls-query/references/query-analysis.md`

### 方法论/评估/RAG（Part 4）
- `skills/developertools/solutions/alibabacloud-terraform-code-generation/{SKILL.md,references/alicloud-providers.md,scripts/build_alicloud_providers.py}`
- `skills/aiml/agentloop/alibabacloud-agentloop-evaluation/{scripts/analyze_evaluation_results.py,references/{result-analysis,spec-format,api-map}.md}`
- `skills/aiml/agentloop/alibabacloud-agentloop-experience/{SKILL.md,scripts/search_context.js}`
- `skills/developertools/solutions/alibabacloud-find-skills/SKILL.md`
- `skills/aiml/sfm/alibabacloud-bailian-rag-knowledgebase/scripts/{retrieve,api_key}.py`

### 安全/治理/Finops（Part 5）
- `skills/security/solutions/alibabacloud-security-health-check/{SKILL.md,scripts/engine/{scorer,report_html,report_excel,report_markdown}.py,references/checks/*.yaml,assets/templates/*}`
- `skills/migrationom/governance/alibabacloud-governance-evaluation-report/{SKILL.md,references/report-format-{overview,pillar,detail}.md}`
- `skills/others/accs/alibabacloud-finops-inspect/SKILL.md`

### 存储/媒体/容器/部署（Part 6）
- `skills/playbooks/optdes/alibabacloud-pts-reporter/{SKILL.md,references/tuning-knowledge-base.md}`
- `skills/storage/disk/alibabacloud-ebs-disk-metric-analyzer/SKILL.md`
- `skills/container/csk/alibabacloud-ack-cli/{SKILL.md,references/async-tasks.md,scripts/wait-for-task.sh}`
- `skills/storage/oss/alibabacloud-oss-media-process/SKILL.md`
- `skills/playbooks/optdes/alibabacloud-pts-pilot/{SKILL.md,references/routing-rules.md}`
- `skills/computing/ecs/alibabacloud-opc-advisor/SKILL.md`

---

*本文档为 powerelf 改造的外部范本索引。每个宝藏均带源文件路径，便于实施时直接定位。*
