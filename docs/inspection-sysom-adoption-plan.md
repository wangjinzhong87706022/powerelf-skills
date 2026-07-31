# powerelf-inspection 借鉴 SysOM 巡检/诊断 Skill 实施方案

> **日期**：2026-07-31（同日全仓 213 skill 深扫后修订，增补项标注 `[源: skill名]`）
> **范本**：`/opt/git/alibabacloud-aiops-skills/skills/computing/alinux/`（巡检 `alibabacloud-alinux-sysom-inspection` + 诊断 `alibabacloud-sysom-diagnosis`）+ 微信文章《凌晨告警不再慌！SysOM 巡检 Skill 一键锁定根因》
> **配套阅读**：`docs/alibabacloud-aiops-skills-treasure-map.md` Part 0 / Part 8 inspection 行
>
> **核心哲学（文章原话转述）**：巡检不止回答"有没有异常"，要回答三个进阶问题——**严重程度如何？最可能根因在哪？下一步该由谁采取什么行动？** SysOM 内部评测：异常识别准确率 80%+，**高风险项误判率 0**（"当它说高风险时，没有在喊狼来了"）。

---

## 现状基线（改造前）

`powerelf-inspection/impl/inspection_analyzer.py`（1265 行，15 维检测引擎）：

| 维度 | 现状 | SysOM 对照 |
|---|---|---|
| 输出结构 | 平铺 `[{category, findings:[{level,message,detail}], stats?, data_points}]`（`generate_report` L1127-1235） | envelope：`{ok, agent:{status, summary, findings[4字段], next_steps[]}}` |
| 异常后续 | 止步"报异常"，无根因衔接 | 命中 `memory_usage_rate` → 自动 `InvokeDiagnosis(memgraph)`，带 `trigger_report_id` 回链（`command.py:1339-1382`） |
| 无数据处理 | 中文字符串 `status: "无数据"`，无标准化 code | 8 个 `error.code → Action` 映射表；`InvalidAction.NotFound` 停止后续避免无效重试 |
| CLI 退出码 | 恒 0 | `0` 正常 / `2` 检出异常 / `3` 鉴权失败 / `4` 未就绪 / `5` API 不可用 |
| 报告模板 | Python f-string 内嵌 | `references/report-template.md` `{placeholder}` 占位符渲染 |
| 审计链 | 无 | `SKILL_SESSION_ID` 贯穿全部调用 + `source=skill_hub` 溯源标记 |
| 幂等 | 无 | `clientToken = 前缀 + sha256(排序JSON)[:48]` |

已有且无需重造：5 层异常判定（阈值→变化率→趋势→MAD→关联）、per-anomaly 置信度公式、QA 闸（`_QA_CHECKLIST` + confidence_tier）、"Agent 不可做的 5 件事"边界规则。

---

## Phase 1 · findings envelope 输出契约（数据基座，先做）

> 范本：诊断 SKILL.md L139-173 的 envelope 契约 + `report-interpretation.md` 的字段用法表。

### 1.1 目标契约

`inspection_analyzer.py --json` 的输出从裸 `analyses` 数组升级为：

```json
{
  "ok": true,
  "run_id": "insp-<uuid>",
  "command": "inspection_analyzer --days 30",
  "error": null,
  "agent": {
    "status": "critical | warning | ok | no_data | inconclusive",
    "summary": "一句话总结：N 项巡检，M 项异常，最严重的是……",
    "findings": [
      {
        "severity": "critical | warning | info",
        "title": "渗压计 P03 MAD 离群",
        "detail": "测点 P03（eq_id=1024，坝段 II）2026-07-30 14:00 起渗压 85.2kPa（窗口峰值 87.1kPa），偏离中位数 6.8×MAD；同期上游水位无显著变化",
        "category": "root_cause | anomaly | data_quality | info",
        "data_source": "monitor_data_seepage.p_value @ [-30d, now]",
        "correlated_with": []
      }
    ],
    "next_steps": [
      {"kind": "command", "label": "关联诊断", "command": "diagnose --sensor P03 --window 24h", "reason": "补齐缺失实体：外因事件（降雨/闸门操作）"},
      {"kind": "manual", "label": "现场核查", "command": null, "reason": "置信度 <60%，按边界规则需人工确认"}
    ]
  }
}
```

错误对象定型为 `{code, message, fix_hint}`，code 取封闭枚举（首批：`DB_CONNECT_FAILED / TABLE_MISSING / QUERY_TIMEOUT / BAD_ARGS`）——**下游按 code 分支，不解析 message**。`[源: CADT deploy envelope.py/errors.py]`

### 1.2 输出纪律（写进 SKILL.md 输出格式节）

1. **findings 核心 4 字段**（severity/title/detail/category）+ 2 个结构化附注字段：`data_source`（表.列+时间窗锚点，防结论漂移）`[源: pts-reporter]`；`correlated_with`（本 finding 消费的其他 finding id——同一份证据只归属一条主 finding，被关联者降为佐证不再独立计数）`[源: kvstore coverage 去重]`；
2. **必需实体必须写进 title/detail**：测点编码、eq_id、所属工程/坝段、异常时间窗、量级（**当前值与窗口峰值双值**，区分"持续高位"与"瞬时尖峰"）`[源: ES instance diagnose latest/window_max]`——报告读者不需要回查数据库就能行动；
3. **`category=root_cause` 即 stop-ready**：detail 已含必要实体 + 安全下一步时，不再追加分析轮次；`next_steps[]` 是**优先级计划不是 checklist**，只为补"具名缺失实体"才执行下一条；
4. **summary 计数 ≡ findings 明细**：summary 中"M 项异常"必须等于 findings 按 severity 的实际计数，禁止口径漂移 `[源: smartag-pilot Summary≡明细断言]`；
5. **0 是有效读数，不是缺失**：水位 0、流量 0、开度 0 是合法观测值，禁止把 0 归入 no_data 分支 `[源: cfw]`；
6. **推断性表述用区间不用点值**：预测/外推类 detail 写"预计 4-6 kPa"而非"4.73 kPa"，防假精度 `[源: kwp statistical-analysis]`。

### 1.3 改动清单

| 文件 | 改动 |
|---|---|
| `impl/inspection_analyzer.py` | 新增 `build_envelope(analyses, run_id)`：把 15 个 analyze_* 的 findings 归一到 4 字段 envelope；`main()` 中 `--json` 走 envelope 输出（保留 `--legacy-json` 输出旧结构过渡一个版本） |
| `impl/inspection_analyzer.py` | `main()` 退出码语义：`0` 无异常 / `2` 检出 CRITICAL / `3` DB 连接失败 / `4` inconclusive（数据不足以下结论，见 Phase 4.6 数据质量闸）/ `5` 关键表缺失（对齐 SysOM `__main__.py:78-90` + deploy_toolkit 的 inconclusive 三态思想 `[源: deploy_toolkit]`） |
| `SKILL.md` | 输出格式节写入 envelope 契约 + 五条输出纪律 + 报告"三问"结构（严重程度/最可能根因/下一步谁做什么） |
| `impl/test_inspection.py` | 新增 envelope 结构断言（字段完备性、category 枚举、退出码） |

---

## Phase 2 · 巡检→诊断自动衔接（价值最大）

> 范本：`command.py` 的单点映射扩展模式——`_has_memory_usage_issue`(L873-936) → `_invoke_memgraph_diagnosis`(L716-762，params 带 `trigger_item` + `trigger_report_id`) → `_wait_diagnosis_result`(L821-870) → 结果并入巡检结论。关闭开关 `--disable-memgraph-diagnosis`。

### 2.1 机制设计

在 `generate_report()` 收尾处加"高风险自动诊断"环节：

```
15 维分析完成
  → 筛出 severity=critical 的 findings
  → 按 (category, 触发条件) 查诊断路由表
  → 命中则自动执行对应诊断查询（限流：每次巡检最多 N=3 条诊断链，防爆炸）
  → 诊断结果写回 finding：category 升级为 root_cause，detail 追加证据链
  → envelope 的诊断段带 trigger_finding_id 回链源 finding
```

CLI 加 `--no-auto-diagnosis` 关闭开关（对齐 SysOM L1343-1345 的唯一 opt-out）。

### 2.2 首批诊断路由（对齐 SysOM"单点起步、模式可复用"策略）

SysOM 19 项巡检也只有 `memory_usage_rate` 一条自动衔接（SKILL.md L75 明示这是可扩展模式）。powerelf 首批做 3 条最高价值链：

| 触发（巡检异常） | 自动诊断链（分层 fallback，参考 history-lock-diagnose 的时间窗扩展） | 产出 |
|---|---|---|
| 渗压 MAD 离群（CRITICAL） | ① 同站上游水位同期变化 → ② 同期降雨事件（`st_pptn_r`）→ ③ 同期闸门操作（`rei_gate_r`）→ ④ 均无 → 标"疑似传感器漂移或真实渗漏，需人工" | `①上游水位抬升 → ②渗压响应` 因果链或排除结论 |
| 水位变化率超限（CRITICAL） | ① 同期闸门开度变化 → ② 泵站启停记录 → ③ 上游降雨 | 区分"调度行为"与"异常水情" |
| 闸门关闭但有流量（CRITICAL） | ① 复核闸门状态时序（是否状态码跳变）→ ② 同断面流量计交叉验证 | 区分"传感器故障"与"真实漏水" |

**路由内检查序按根因先验概率排列**：每条路由表条目标注各候选根因的经验概率（如 渗压离群 → 上游水位变化 ~50% / 降雨 ~25% / 闸门操作 ~15% / 传感器漂移 ~10%），先查高概率分支，命中即停 `[源: remote-connection-diagnose 先验概率表]`。首版概率拍经验值，后续按 `evolution/feedback-log.md` 实测修正。

时间窗分层扩展：`[-2h,+30min] → [-12h,+30min] → [-3d,+30min]`（对齐 smart-lock-diagnosis 的 `-10min→-30min→-2h` 三级窗）。**纵向扩窗之外加一层横向 fallback**：本维度全部时间窗查空后，允许切换到关联维度再试一次（如渗压查不到外因 → 查同坝段其他渗压计是否同步离群，区分"单点故障"与"面上异常"）`[源: 分区1 横向兜底]`。

**诊断链执行纪律** `[源: ecs-diagnose / liverecord / ddos-native-intercept]`：
- **准入条件**：跨表大窗口查询（如近 3 年同期分布）只在前置轻量检查已命中且实体缺口明确时才执行，不作为例行动作（昂贵诊断准入）；
- **证据充分即停**：任一层已产出 root_cause 级证据链就终止后续 fallback，不为"完整性"跑满全部层级；
- **尝试轨迹入报告**：每条诊断链在 finding.detail 记录"已查窗口与结果"（如 `已查 [-2h/-12h/-3d] 降雨记录均为空`）——让"已检为空"与"忘了检"可区分；
- **瞬时错误重试至多一次**：查询超时/连接闪断只重试 1 次，再失败即标准化为 code 并入结果。

### 2.3 改动清单

| 文件 | 改动 |
|---|---|
| `impl/inspection_analyzer.py` | 新增 `run_auto_diagnosis(engine, critical_findings, thresholds)`：路由表匹配 + 分层 fallback 查询 + 结果回填 finding |
| `references/diagnosis-routing.md`（新建） | 诊断路由表文档：`触发条件 → 诊断查询序列 → 期望结果 → 结论模板`，每条带数据源锚点（表名+列名），对齐 pts-reporter 的"症状→发现映射带数据源锚点"防漂移 |
| `SKILL.md` | 工作流程节加"高风险自动诊断"步 + `--no-auto-diagnosis` 说明 + 扩展指引（"新增巡检维度的专项诊断复用本路由表模式"，对齐 SysOM SKILL.md L76） |
| `impl/test_inspection.py` | 路由匹配、fallback 降级、限流 N=3、opt-out 测试 |

### 2.4 硬护栏（对齐 SysOM 诊断 skill 只读纪律）

- 诊断链**只读**：只发 SELECT，不写任何表；
- 诊断失败不毁报告：各阶段失败标准化为 code（`DIAG_QUERY_FAILED / DIAG_NO_EVIDENCE / DIAG_TIMEOUT`），并入 finding.detail 而非中断（对齐 `command.py:836-870` 的失败标准化）；
- 最终报告**禁止内联可执行的处置 SQL/命令**（UPDATE/DELETE/重启设备指令），用"建议在维护窗口内核查 X"式措辞（对齐诊断 SKILL.md L100-107）。

---

## Phase 3 · 实体缺口 → 聚焦动作路由表

> 范本：`memory-triage.md` L56-78 的"缺失实体 → 唯一命令"映射 + "Focused Action Map 只根据已点名缺失实体选下一步，不凭症状措辞推断"纪律。

### 3.1 水利版实体缺口表（新建 `references/entity-gap-actions.md`）

| 缺失实体 | 完备信号 | 聚焦动作（查询） |
|---|---|---|
| 异常归属传感器 | eq_id + 测点编码 + 所属工程/坝段 | `eq_business_equip_relation` + `att_st_base` 关联链 |
| 外因事件 | 同期降雨/闸门操作/泵启停记录（有或明确排除） | `st_pptn_r` / `rei_gate_r` / 泵站工况表 时间窗查询 |
| 量级基线 | 当前值 + 历史同期中位数/MAD + 偏离倍数 | 历史同期分布查询（近 3 年同月） |
| 阈值依据 | 命中的规则 ID + `ew_info_rules.extend` 中的阈值原文 | `ew_info_rules` + `JSON_EXTRACT(extend, ...)` |
| 数据质量佐证 | 该测点近期缺失率/插值率（排除"坏数据当异常"） | 引 powerelf-data-governance 的质量评分 |

### 3.2 使用纪律（写进 SKILL.md）

- 仅当 envelope/finding **点名了具体缺失实体**时才执行对应聚焦动作，一次一条;
- 已闭合的实体**不重复核查**（对齐 memory-triage L26-54："不给已闭合实体加裸命令验证"）；
- 5 类实体全齐 → finding 升格 `root_cause`，stop-ready；
- **禁止实体替换**：聚焦动作查空时，禁止拿"相邻测点/相似时段/同类工程"的数据顶替缺失实体下结论——只能呈现候选选项让用户选择，或按固定终止模板收束（`该实体经 X/Y/Z 三途径查询均无数据，无法闭合，本 finding 维持 [Unverified]`）`[源: ecs-diagnose 空结果协议三条 FORBIDDEN]`；
- **禁止跨字段拼凑**：不得把 A 测点的量级 + B 测点的时间窗拼成一条"完备"证据 `[源: ai-innovation-lab 置0协议]`。

Phase 3 与 Phase 2 的关系：Phase 2 是**自动**衔接（预置路由），Phase 3 是 agent 交互式追问时的**手动**路由——同一张实体表，两个消费入口。

---

## Phase 4 · 工程加固（低成本顺手项）

| # | 项 | 范本 | 落点 |
|---|---|---|---|
| 4.1 | 无数据标准化 code（**四分法**） | `status:"无数据"` 字符串 → 四类互斥 code：`NOT_APPLICABLE`（该工程无此类设备，不算异常）/ `NO_DATA`（表存在但窗口内无记录，已查证为空）/ `QUERY_FAILED`（查询报错，**严禁写 0 或空充数**）/ `DATA_LOSS_GUARD`（DB 有值但报告拿不到 = Skill 自身故障，最高优先级修复）。关键表缺失时停止该维度且不重试（对齐 `InvalidAction.NotFound`）`[源: waf-security-monitor Error vs Empty + ecs-health-inspection 数据丢失守卫]`。**前提数据**：新建 `references/data-freshness.md` 登记各监测表期望上报周期与典型滞后（雨量 5min/水位 1h/渗压 …），`MAX(tm)` 滞后超 N 个周期 → 判"采集中断"（NO_DATA 的子类，措辞不同：设备可能离线而非无此类数据）`[源: kwp data-context-extractor Data Freshness 表]` | `inspection_analyzer.py` 各 analyze_* 的空数据分支 + 新建 `references/data-freshness.md` |
| 4.2 | run_id 审计链 + state 台账 | `SKILL_SESSION_ID`：env 优先 + 格式校验 + fallback 自动生成 `insp-<uuid>`，回写 env 保证同进程一致（`openapi.py:50-59`）；每次运行追加一行 state 记录（run_id/参数/退出码/异常计数/耗时）到本地 `state/inspection_runs.jsonl`，供趋势回看与评测取数 `[源: opc-deploy iron-rules state 台账]` | `inspection_analyzer.py` 入口生成，envelope/报告文件名/state 行共享同一 run_id |
| 4.3 | `{placeholder}` 报告模板外置 | `report-template.md` + `_render_report_markdown` 字符串替换（`command.py:939-943`），模板读取失败回退内置默认（L66-98） | 新建 `references/report-template.md`（6 段式：巡检概览/异常明细/诊断信息/关键发现/TOP 排行/最终结论+三问，收尾加 **Data Notes 表**——列出本次所有 NOT_APPLICABLE/NO_DATA/QUERY_FAILED 项 `[源: waf-security-monitor]`），`generate_report` 改为渲染模板 |
| 4.4 | 幂等键 | `sha256(排序JSON)[:48]` clientToken（`command.py:162-165`）；重试必须复用同一 token `[源: agentloop-dataset]` | 若巡检结果回写数据库（对接 `lib/report.py` 落库路径时），写入带幂等键防重复 |
| 4.5 | 报告写盘失败不毁输出 | 写盘失败仅记录 `report_file_write_error`，正文兜底走 stdout（`command.py:1172-1182` + csas 写盘兜底） | `main()` 的 `--output` 分支包 try/except |
| 4.6 | **第 0 层数据质量闸**（新增，检测前置） | 15 维分析前先跑数据可信度检查：采样密度（分级用完整性色阶：>99% 绿 / 95-99 黄 / 80-95 橙 / <80 红 `[源: kwp explore-data]`）、值域合法性（物理量纲边界 + 占位值探测 0/-1/999999、round-number bias）、聚合一致性（min≤avg≤max）、**跨列一致性**（如闸门状态=关但流量>0 属矛盾数据，标 data_quality 而非直接判异常）；不达标的维度整体标 `inconclusive` 而非硬跑出假异常 `[源: ebs-disk 数据质量9步 + kwp explore-data 准确性红旗]` | `inspection_analyzer.py` 新增 `check_data_quality(df, dim_config)`，接退出码 4 |
| 4.7 | MySQL 双超时 | 所有连接强制 `connect_timeout` + `read_timeout` 双参数，防单查询挂死整轮巡检 `[源: 分区3 通例]` | `_shared/db.py` 连接参数 |
| 4.8 | THRESHOLDS 集中字典 | 15 维阈值散在各 analyze_* 内的部分收拢为模块级 `THRESHOLDS` 字典，**每项附一行 Why 注释**（阈值依据：规范条文/历史分位数/专家经验）`[源: ES instance diagnose]`。注意：与 `ew_info_rules` 动态阈值不冲突——字典只收静态兜底值，动态规则仍是单一来源 | `inspection_analyzer.py` 头部 |
| 4.9 | 时序判定三分通道 + 季节性/空闲护栏 | 变化率/趋势类判定拆成互斥 elif 三分支：**瞬时尖峰**（单点，window_max 高但 latest 已回落）/ **台阶变点**（水平位移持续，最像传感器重标定或工况切换）/ **缓变趋势**——三者根因先验不同，诊断路由分流 `[源: ES instance diagnose 互斥分支 + kwp statistical-analysis 点异常vs变点]`；**季节性护栏**：趋势层与 MAD 层基线优先用**历年同期**（近 3 年同月）而非仅"近 30 天"，防 7 月初汛被判异常 `[源: kwp statistical-analysis Seasonality]`；关联分析（第 5 层）加空闲护栏——基础量近乎无变化时跳过相关性判定，避免对平线算出伪相关 `[源: CV 空闲护栏]` | 各 analyze_* 的变化率/趋势/MAD/关联分支 |

---

## Phase 5 · A/B 对照评测协议（验证手段）

> 范本：文章的对照实验——16 类真实 OS 故障场景，接入 skill vs 纯通用能力，测**对话轮次 / 工具调用次数 / 整体耗时 / 定位准确率**。

### 5.1 静态评测先行（A/B 之前，成本更低）`[源: flink agent-operating-protocol + convert_evals.py]`

- 建 `autoresearch/eval_cases/`：每个检测维度至少一对 **✅ 应报 / ❌ 不应报** 成对用例（构造 SQL fixture 或历史数据快照），❌ 用例写明边界理由（如"变化率 4.9%/h，阈值 5%，差 0.1 不应触发"）；
- 补一组**空数据用例**：分别覆盖 NOT_APPLICABLE / NO_DATA / QUERY_FAILED 三态，断言 envelope code 正确且**没有伪造数值**；
- 评测用占位实体（`st-xxx` 式虚构测点）先验证流程正确性，再上真实案例；
- 输出校验脚本化：`verify_output.py` 断言 summary 计数≡findings 明细、退出码与 status 一致、CRITICAL finding 必带 5 类实体 `[源: waf-security-monitor verify_output.py + ddos EXECUTED 计数硬校验]`；再加 5 条**输出 red-flag 元检查**（任一命中即评测 fail 待人工复核）：跨期变化>50% 无解释、可疑精确整数、恰好 0%/100% 的比率、跨期/跨段完全相同值（查询丢维度嫌疑）、结果与预期完美一致 `[源: kwp validate-data Red Flags]`。

### 5.2 A/B 对照

- 从 `autoresearch/eval_criteria.md`（现有 10 条二元 EVAL）扩展：选 10-16 个真实历史异常案例（可从 `ew_info_message` 和 `evolution/feedback-log.md` 挑），每案例记录 ground truth 根因；
- 双臂运行：A 臂加载改造后 skill，B 臂仅通用能力 + 裸 schema；
- 记录四指标进 `autoresearch/results.tsv`；
- **验收线**（对齐 SysOM 标准）：CRITICAL 判定误报率 = 0（宁可降级为 WARNING 也不误报高风险——"不喊狼来了"）；**配套对冲指标：CRITICAL 漏报率 ≤ 20%**（防止靠"全降级"刷零误报）`[源: 分区2 对冲指标建议]`；根因链正确率 ≥ 60%（首期）。

### 5.3 评测后闭环

- 误报/漏报案例按七字段格式（现象/根因/触发条件/修复/验证/影响面/复发计数）写入 `evolution/feedback-log.md`，**同类问题出现 ≥2 次才升格为规则/路由表修改**，避免单例过拟合 `[源: lessons-learned]`。

---

## 实施顺序与依赖

```
Phase 1 (envelope)          ←── 数据基座，1-2 天
   ↓
Phase 2 (自动诊断衔接)       ←── 核心价值，2-3 天，依赖 Phase 1 的 finding 结构
   ↓
Phase 3 (实体缺口路由)       ←── 1 天，复用 Phase 2 的路由表格式
   ‖（可并行）
Phase 4 (工程加固)          ←── 各项独立，可穿插
   ↓
Phase 5 (A/B 评测)          ←── 全部完成后跑一轮，验证收益
```

## 明确不做（Out of Scope）

- 不引入 SysOM 的云端服务判定模式（"不用本地阈值"）——powerelf 是本地库直连架构，阈值单一来源已由 `ew_info_rules` + `load_thresholds()` 保证；
- 不做诊断期间的任何写操作/处置执行——维持"巡检（读）与处置（写）分离"（宝藏图 §7.10）；
- 不一次性铺满 15 维全部诊断路由——对齐 SysOM"19 项巡检只做 1 条衔接、模式可复用"的克制策略，首批 3 条，按 `evolution/feedback-log.md` 反馈逐步扩展。

---

## 附 · 全仓深扫修订记录（2026-07-31，213 skill / 4 分区）

**本次修订合入**：Phase 1（error 封闭码+fix_hint、data_source/correlated_with 附注字段、双值证据、summary≡明细、0≠缺失、退出码加 4=inconclusive）；Phase 2（先验概率排序、横向 fallback、昂贵诊断准入、证据充分即停、尝试轨迹、重试一次）；Phase 3（禁实体替换+固定终止模板、禁跨字段拼凑）；Phase 4（无数据四分法+数据丢失守卫、state 台账、Data Notes 表、第 0 层数据质量闸、MySQL 双超时、THRESHOLDS 字典、持续/尖峰双通道+空闲护栏）；Phase 5（静态评测先行+成对用例+verify_output、漏报率对冲、lessons-learned ≥2 次闭环）。

**评估后未采纳**：
- PRECHECK/POSTVERIFY 双闸门（CADT quality-gates）——面向写操作部署流程，本 skill 只读，不适用；
- STRICT MODE recite 管道验证（ddos）——针对多轮对话中 agent 伪造数据，本方案证据已由 data_source 锚点+verify_output 脚本覆盖，暂不加对话级仪式；
- 服务端权威幂等 `INSERT ON DUPLICATE KEY`（ehpc）——落库路径尚未启用，保留在 4.4 备注即可；
- 健康分 rubric（rds-pg，宝藏图 Part 1 #4）——有价值但属新特性非本轮借鉴改造，另立议题。
